"""
Duplicate-Send Protection Registry for AgentDesk Outreach.
Prevents repeated transmission of identical outreach messages or duplicate sends
against the same draft_id.
Enforces thread-safe in-flight locks to stop concurrent double-sends, and persists
dispatched records to SQLite in storage/ to survive service restarts.
"""
import os
import sqlite3
import hashlib
import threading
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Set

@dataclass
class DispatchedRecord:
    draft_id: str
    recipient_email: str
    subject: str
    dispatched_at: str
    status: str
    provider: str
    content_hash: str

def _get_default_db_path() -> Optional[str]:
    """Locates or prepares storage/dispatches.db in the repository root."""
    try:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.normpath(os.path.join(backend_dir, ".."))
        storage_dir = os.path.join(root_dir, "storage")
        if not os.path.isdir(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)
        return os.path.join(storage_dir, "dispatches.db")
    except Exception:
        return None

class DispatchTracker:
    """
    Thread-safe registry of dispatched outreach emails.
    Enforces idempotency, blocks concurrent duplicate in-flight requests,
    and persists records across backend restarts.
    """
    def __init__(self, max_records: int = 1000, db_path: Optional[str] = None):
        self._lock = threading.Lock()
        self._by_draft_id: Dict[str, DispatchedRecord] = {}
        self._by_content_hash: Dict[str, str] = {}  # content_hash -> draft_id
        self._in_flight_drafts: Set[str] = set()
        self._in_flight_hashes: Set[str] = set()
        self._max_records = max_records
        self._db_path = db_path if db_path is not None else _get_default_db_path()
        self._init_sqlite()

    def _init_sqlite(self):
        """Initializes SQLite schema and loads previously dispatched records."""
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS dispatched_records (
                        draft_id TEXT PRIMARY KEY,
                        recipient_email TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        dispatched_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        content_hash TEXT NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON dispatched_records(content_hash)")
                conn.commit()

                # Load existing records into in-memory lookup
                cur = conn.execute("SELECT draft_id, recipient_email, subject, dispatched_at, status, provider, content_hash FROM dispatched_records")
                for row in cur.fetchall():
                    rec = DispatchedRecord(
                        draft_id=row[0],
                        recipient_email=row[1],
                        subject=row[2],
                        dispatched_at=row[3],
                        status=row[4],
                        provider=row[5],
                        content_hash=row[6],
                    )
                    self._by_draft_id[rec.draft_id] = rec
                    self._by_content_hash[rec.content_hash] = rec.draft_id
        except Exception:
            # Fall back to in-memory only if SQLite is unavailable
            pass

    @staticmethod
    def compute_content_hash(recipient_email: str, subject: str, body: str) -> str:
        clean_recipient = recipient_email.strip().lower()
        clean_subject = " ".join(subject.strip().split())
        clean_body = " ".join(body.strip().split())
        combined = f"{clean_recipient}::{clean_subject}::{clean_body}".encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def check_duplicate(
        self,
        draft_id: str,
        recipient_email: str,
        subject: str,
        body: str
    ) -> Optional[DispatchedRecord]:
        """
        Checks whether this draft_id has already been sent, or whether an identical email
        (same recipient, subject, and body) has already been dispatched.
        """
        with self._lock:
            # 1. Check exact draft_id match
            if draft_id in self._by_draft_id:
                return self._by_draft_id[draft_id]

            # 2. Check identical content hash (prevents repeated send with new draft_id)
            chash = self.compute_content_hash(recipient_email, subject, body)
            if chash in self._by_content_hash:
                prev_draft_id = self._by_content_hash[chash]
                if prev_draft_id in self._by_draft_id:
                    return self._by_draft_id[prev_draft_id]

            return None

    def claim_dispatch(
        self,
        draft_id: str,
        recipient_email: str,
        subject: str,
        body: str
    ) -> Tuple[bool, Optional[str], Optional[DispatchedRecord]]:
        """
        Atomically checks if the draft or identical email was already dispatched OR
        is currently in-flight. If available, reserves the in-flight lock.
        Returns:
            (allowed: bool, reason: Optional[str], record: Optional[DispatchedRecord])
            reason is 'already_dispatched' | 'in_flight' | None
        """
        with self._lock:
            # 1. Check if already dispatched
            if draft_id in self._by_draft_id:
                return False, "already_dispatched", self._by_draft_id[draft_id]

            chash = self.compute_content_hash(recipient_email, subject, body)
            if chash in self._by_content_hash:
                prev_draft_id = self._by_content_hash[chash]
                if prev_draft_id in self._by_draft_id:
                    return False, "already_dispatched", self._by_draft_id[prev_draft_id]

            # 2. Check if currently in-flight (concurrent duplicate protection)
            if draft_id in self._in_flight_drafts or chash in self._in_flight_hashes:
                return False, "in_flight", None

            # 3. Reserve in-flight lock
            self._in_flight_drafts.add(draft_id)
            self._in_flight_hashes.add(chash)
            return True, None, None

    def release_claim(
        self,
        draft_id: str,
        recipient_email: str,
        subject: str,
        body: str
    ) -> None:
        """
        Releases an in-flight reservation if dispatch was aborted or encountered an error.
        """
        with self._lock:
            self._in_flight_drafts.discard(draft_id)
            chash = self.compute_content_hash(recipient_email, subject, body)
            self._in_flight_hashes.discard(chash)

    def record_dispatch(
        self,
        draft_id: str,
        recipient_email: str,
        subject: str,
        body: str,
        status: str,
        provider: str
    ) -> DispatchedRecord:
        """
        Registers a successful or simulated dispatch in the registry, releases in-flight lock,
        and persists to SQLite.
        """
        with self._lock:
            chash = self.compute_content_hash(recipient_email, subject, body)
            now_iso = datetime.now(timezone.utc).isoformat()
            record = DispatchedRecord(
                draft_id=draft_id,
                recipient_email=recipient_email.strip(),
                subject=subject.strip(),
                dispatched_at=now_iso,
                status=status,
                provider=provider,
                content_hash=chash,
            )

            # Evict oldest entry from memory if capacity reached
            if len(self._by_draft_id) >= self._max_records:
                oldest_id = next(iter(self._by_draft_id))
                old_rec = self._by_draft_id.pop(oldest_id, None)
                if old_rec and old_rec.content_hash in self._by_content_hash:
                    self._by_content_hash.pop(old_rec.content_hash, None)

            self._by_draft_id[draft_id] = record
            self._by_content_hash[chash] = draft_id

            # Clear in-flight flags
            self._in_flight_drafts.discard(draft_id)
            self._in_flight_hashes.discard(chash)

            # Persist to SQLite
            if self._db_path:
                try:
                    with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO dispatched_records
                            (draft_id, recipient_email, subject, dispatched_at, status, provider, content_hash)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (record.draft_id, record.recipient_email, record.subject,
                              record.dispatched_at, record.status, record.provider, record.content_hash))
                        conn.commit()
                except Exception:
                    pass

            return record

    def is_dispatched(self, draft_id: str) -> bool:
        with self._lock:
            return draft_id in self._by_draft_id

    def is_in_flight(self, draft_id: str) -> bool:
        with self._lock:
            return draft_id in self._in_flight_drafts

    def clear(self):
        """Reset registry (primarily used for test isolation)."""
        with self._lock:
            self._by_draft_id.clear()
            self._by_content_hash.clear()
            self._in_flight_drafts.clear()
            self._in_flight_hashes.clear()
            if self._db_path:
                try:
                    with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                        conn.execute("DELETE FROM dispatched_records")
                        conn.commit()
                except Exception:
                    pass

# Global singleton tracker
global_dispatch_tracker = DispatchTracker()
