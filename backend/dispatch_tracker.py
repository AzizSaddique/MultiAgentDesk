"""
Duplicate-Send Protection Registry for AgentDesk Outreach.
Prevents repeated transmission of identical outreach messages or duplicate sends
against the same draft_id. Thread-safe and in-memory.
"""
import hashlib
import threading
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class DispatchedRecord:
    draft_id: str
    recipient_email: str
    subject: str
    dispatched_at: str
    status: str
    provider: str
    content_hash: str

class DispatchTracker:
    """
    Thread-safe registry of dispatched outreach emails to enforce idempotency
    and block duplicate transmissions.
    """
    def __init__(self, max_records: int = 1000):
        self._lock = threading.Lock()
        self._by_draft_id: Dict[str, DispatchedRecord] = {}
        self._by_content_hash: Dict[str, str] = {}  # content_hash -> draft_id
        self._max_records = max_records

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
        Registers a successful or simulated dispatch in the registry.
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

            # Evict oldest entry if capacity reached
            if len(self._by_draft_id) >= self._max_records:
                oldest_id = next(iter(self._by_draft_id))
                old_rec = self._by_draft_id.pop(oldest_id, None)
                if old_rec and old_rec.content_hash in self._by_content_hash:
                    self._by_content_hash.pop(old_rec.content_hash, None)

            self._by_draft_id[draft_id] = record
            self._by_content_hash[chash] = draft_id
            return record

    def is_dispatched(self, draft_id: str) -> bool:
        with self._lock:
            return draft_id in self._by_draft_id

    def clear(self):
        """Reset registry (primarily used for test isolation)."""
        with self._lock:
            self._by_draft_id.clear()
            self._by_content_hash.clear()

# Global singleton tracker
global_dispatch_tracker = DispatchTracker()
