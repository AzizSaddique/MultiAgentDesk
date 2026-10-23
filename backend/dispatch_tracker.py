"""
Duplicate-Send Protection Registry and Outreach History for AgentDesk.
Prevents repeated transmission of identical outreach messages or duplicate sends
against the same draft_id.
Enforces thread-safe in-flight locks to stop concurrent double-sends, and persists
dispatched records and comprehensive outreach history to SQLite in storage/
to survive service restarts.
"""
import os
import uuid
import sqlite3
import hashlib
import threading
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set, Any

try:
    from .providers.email_dispatcher import sanitize_log_message
except (ImportError, ValueError):
    try:
        from providers.email_dispatcher import sanitize_log_message
    except ImportError:
        def sanitize_log_message(text: str, custom_secrets=None) -> str:
            return text or ""

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
    Thread-safe registry of dispatched outreach emails and history audit log.
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
        """Initializes SQLite schema, creates history tables, and backfills legacy records."""
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                # 1. Idempotency table
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

                # 2. Outreach History table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS outreach_history (
                        id TEXT PRIMARY KEY,
                        draft_id TEXT NOT NULL,
                        recipient_email TEXT NOT NULL,
                        recipient_name TEXT,
                        company_name TEXT,
                        subject TEXT NOT NULL,
                        body_preview TEXT,
                        source_url TEXT,
                        status TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        is_simulated INTEGER NOT NULL DEFAULT 0,
                        dispatched_at TEXT NOT NULL,
                        error_message TEXT
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_history_dispatched_at ON outreach_history(dispatched_at DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_history_status ON outreach_history(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_history_draft_id ON outreach_history(draft_id)")

                # 3. Backfill any legacy dispatched_records into outreach_history
                conn.execute("""
                    INSERT OR IGNORE INTO outreach_history
                    (id, draft_id, recipient_email, recipient_name, company_name, subject, body_preview, source_url, status, provider, is_simulated, dispatched_at, error_message)
                    SELECT
                        'hist_' || dr.draft_id,
                        dr.draft_id,
                        dr.recipient_email,
                        '',
                        '',
                        dr.subject,
                        '',
                        '',
                        dr.status,
                        dr.provider,
                        CASE WHEN dr.status = 'simulated' THEN 1 ELSE 0 END,
                        dr.dispatched_at,
                        NULL
                    FROM dispatched_records dr
                    WHERE NOT EXISTS (
                        SELECT 1 FROM outreach_history oh WHERE oh.draft_id = dr.draft_id AND oh.status = dr.status
                    )
                """)
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
            # Fall back gracefully if SQLite is unavailable
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
        Registers a successful or simulated dispatch in the idempotency registry,
        releases in-flight lock, and persists to SQLite.
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

    def record_history_entry(
        self,
        draft_id: str,
        recipient_email: str,
        subject: str,
        status: str,
        provider: str,
        is_simulated: bool = False,
        recipient_name: str = "",
        company_name: str = "",
        body_preview: str = "",
        source_url: str = "",
        error_message: Optional[str] = None,
        dispatched_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Persists an outreach history event (drafted, simulated, sent, failed) to SQLite.
        Sanitizes error messages to ensure zero credential or secret leakage.
        """
        clean_error = sanitize_log_message(error_message) if error_message else None
        now_iso = dispatched_at or datetime.now(timezone.utc).isoformat()
        entry_id = f"hist_{uuid.uuid4().hex[:12]}"
        preview = " ".join(body_preview.strip().split())[:300] if body_preview else ""

        entry = {
            "id": entry_id,
            "draft_id": draft_id,
            "recipient_email": recipient_email.strip(),
            "recipient_name": recipient_name.strip() if recipient_name else "",
            "company_name": company_name.strip() if company_name else "",
            "subject": subject.strip(),
            "body_preview": preview,
            "source_url": source_url.strip() if source_url else "",
            "status": status.strip().lower(),
            "provider": provider.strip(),
            "is_simulated": bool(is_simulated),
            "dispatched_at": now_iso,
            "error_message": clean_error,
        }

        with self._lock:
            if self._db_path:
                try:
                    with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                        conn.execute("""
                            INSERT INTO outreach_history
                            (id, draft_id, recipient_email, recipient_name, company_name, subject, body_preview, source_url, status, provider, is_simulated, dispatched_at, error_message)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            entry["id"], entry["draft_id"], entry["recipient_email"],
                            entry["recipient_name"], entry["company_name"], entry["subject"],
                            entry["body_preview"], entry["source_url"], entry["status"],
                            entry["provider"], 1 if entry["is_simulated"] else 0,
                            entry["dispatched_at"], entry["error_message"]
                        ))
                        conn.commit()
                except Exception:
                    pass

        return entry

    def query_history(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dict[str, Any]], int, int, Dict[str, int]]:
        """
        Queries outreach history with optional filters, search, and pagination.
        Returns: (items, total_count, total_pages, counts_by_status)
        """
        with self._lock:
            default_counts = {"all": 0, "sent": 0, "simulated": 0, "failed": 0, "drafted": 0}
            if not self._db_path or not os.path.isfile(self._db_path):
                return [], 0, 0, default_counts

            try:
                with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                    # 1. Status counts across all records (for summary pills)
                    cur = conn.execute("SELECT status, COUNT(*) FROM outreach_history GROUP BY status")
                    counts_by_status = {"all": 0, "sent": 0, "simulated": 0, "failed": 0, "drafted": 0}
                    for row in cur.fetchall():
                        counts_by_status[row[0]] = row[1]
                    counts_by_status["all"] = sum(v for k, v in counts_by_status.items() if k != "all")

                    # 2. Build filtered WHERE clause
                    where_clauses = []
                    params = []

                    if status and status.strip().lower() not in ("all", ""):
                        where_clauses.append("status = ?")
                        params.append(status.strip().lower())

                    if search and search.strip():
                        s_term = f"%{search.strip().lower()}%"
                        where_clauses.append(
                            "(LOWER(recipient_email) LIKE ? OR LOWER(company_name) LIKE ? OR LOWER(subject) LIKE ? OR LOWER(provider) LIKE ?)"
                        )
                        params.extend([s_term, s_term, s_term, s_term])

                    if start_date and start_date.strip():
                        s_date = start_date.strip()
                        if "T" not in s_date:
                            s_date = f"{s_date}T00:00:00"
                        where_clauses.append("dispatched_at >= ?")
                        params.append(s_date)

                    if end_date and end_date.strip():
                        e_date = end_date.strip()
                        if "T" not in e_date:
                            e_date = f"{e_date}T23:59:59.999999"
                        where_clauses.append("dispatched_at <= ?")
                        params.append(e_date)

                    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

                    # 3. Total matching records
                    cur = conn.execute(f"SELECT COUNT(*) FROM outreach_history{where_sql}", params)
                    total_count = cur.fetchone()[0]

                    # 4. Pagination
                    page_num = max(1, page)
                    limit = max(1, min(100, page_size))
                    offset = (page_num - 1) * limit
                    total_pages = max(1, (total_count + limit - 1) // limit) if total_count > 0 else 0

                    query_sql = f"""
                        SELECT id, draft_id, recipient_email, recipient_name, company_name,
                               subject, body_preview, source_url, status, provider,
                               is_simulated, dispatched_at, error_message
                        FROM outreach_history
                        {where_sql}
                        ORDER BY dispatched_at DESC
                        LIMIT ? OFFSET ?
                    """
                    cur = conn.execute(query_sql, params + [limit, offset])
                    items = []
                    for row in cur.fetchall():
                        items.append({
                            "id": row[0],
                            "draft_id": row[1],
                            "recipient_email": row[2],
                            "recipient_name": row[3] or "",
                            "company_name": row[4] or "",
                            "subject": row[5],
                            "body_preview": row[6] or "",
                            "source_url": row[7] or "",
                            "status": row[8],
                            "provider": row[9],
                            "is_simulated": bool(row[10]),
                            "dispatched_at": row[11],
                            "error_message": row[12],
                        })

                    return items, total_count, total_pages, counts_by_status
            except Exception:
                return [], 0, 0, default_counts

    def export_history_csv(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """
        Generates RFC 4180 compliant CSV of filtered outreach history.
        Ensures all secrets/tokens are sanitized.
        """
        items, _, _, _ = self.query_history(
            status=status,
            search=search,
            start_date=start_date,
            end_date=end_date,
            page=1,
            page_size=10000,
        )

        headers = [
            "Event ID",
            "Dispatched At (UTC)",
            "Status",
            "Provider",
            "Is Simulated",
            "Recipient Email",
            "Recipient Name",
            "Company Name",
            "Subject",
            "Source URL",
            "Error Diagnostics",
        ]

        def escape_csv(val: Any) -> str:
            clean_str = str(val if val is not None else "").replace('"', '""')
            return f'"{clean_str}"'

        rows = [",".join(headers)]
        for item in items:
            row_data = [
                escape_csv(item["id"]),
                escape_csv(item["dispatched_at"]),
                escape_csv(item["status"]),
                escape_csv(item["provider"]),
                escape_csv("True" if item["is_simulated"] else "False"),
                escape_csv(item["recipient_email"]),
                escape_csv(item["recipient_name"]),
                escape_csv(item["company_name"]),
                escape_csv(item["subject"]),
                escape_csv(item["source_url"]),
                escape_csv(item["error_message"] or ""),
            ]
            rows.append(",".join(row_data))

        return "\r\n".join(rows)

    def is_dispatched(self, draft_id: str) -> bool:
        with self._lock:
            return draft_id in self._by_draft_id

    def is_in_flight(self, draft_id: str) -> bool:
        with self._lock:
            return draft_id in self._in_flight_drafts

    def clear(self):
        """Reset registry and clear tables (primarily used for test isolation)."""
        with self._lock:
            self._by_draft_id.clear()
            self._by_content_hash.clear()
            self._in_flight_drafts.clear()
            self._in_flight_hashes.clear()
            if self._db_path:
                try:
                    with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                        conn.execute("DELETE FROM dispatched_records")
                        conn.execute("DELETE FROM outreach_history")
                        conn.commit()
                except Exception:
                    pass

# Global singleton tracker
global_dispatch_tracker = DispatchTracker()
