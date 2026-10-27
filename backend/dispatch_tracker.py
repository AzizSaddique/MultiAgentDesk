"""
Duplicate-Send Protection Registry and Outreach History for AgentDesk.
Prevents repeated transmission of identical outreach messages or duplicate sends
against the same draft_id.
Enforces thread-safe in-flight locks to stop concurrent double-sends, and persists
dispatched records and comprehensive outreach history to SQLite in storage/
to survive service restarts.
"""
import os
import json
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

def _get_outreach_draft_cls():
    """Robust resolver for OutreachDraft model across multiple package environments."""
    try:
        from backend.models import OutreachDraft
        return OutreachDraft
    except ImportError:
        pass
    try:
        from .models import OutreachDraft
        return OutreachDraft
    except (ImportError, ValueError):
        pass
    try:
        from models import OutreachDraft
        return OutreachDraft
    except ImportError:
        return None

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

                # 3. Discovery Jobs table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS discovery_jobs (
                        id TEXT PRIMARY KEY,
                        prompt TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        started_at TEXT,
                        completed_at TEXT,
                        provider_used TEXT NOT NULL,
                        total_target INTEGER NOT NULL,
                        discovered_count INTEGER NOT NULL DEFAULT 0,
                        verified_email_count INTEGER NOT NULL DEFAULT 0,
                        duplicate_count INTEGER NOT NULL DEFAULT 0,
                        skipped_count INTEGER NOT NULL DEFAULT 0,
                        failed_count INTEGER NOT NULL DEFAULT 0,
                        progress_percent INTEGER NOT NULL DEFAULT 0,
                        current_stage TEXT,
                        plan_json TEXT,
                        error_message TEXT
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_disc_jobs_created ON discovery_jobs(created_at DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_disc_jobs_status ON discovery_jobs(status)")

                # 4. Discovered Leads table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS discovered_leads (
                        id TEXT PRIMARY KEY,
                        job_id TEXT NOT NULL,
                        company_name TEXT NOT NULL,
                        website TEXT NOT NULL,
                        industry TEXT,
                        city TEXT,
                        country TEXT,
                        services_description TEXT,
                        email TEXT,
                        email_verification_status TEXT NOT NULL,
                        phone TEXT,
                        phone_verification_status TEXT NOT NULL,
                        source_urls TEXT NOT NULL,
                        discovery_source TEXT NOT NULL,
                        discovery_query TEXT NOT NULL,
                        discovered_at TEXT NOT NULL,
                        relevance_score REAL NOT NULL,
                        relevance_explanation TEXT NOT NULL,
                        research_status TEXT NOT NULL,
                        failure_reason TEXT,
                        verified_fields TEXT NOT NULL,
                        is_live INTEGER NOT NULL DEFAULT 1,
                        FOREIGN KEY (job_id) REFERENCES discovery_jobs(id)
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_disc_leads_job ON discovered_leads(job_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_disc_leads_email_stat ON discovered_leads(email_verification_status)")

                # 5. Outreach Drafts table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS outreach_drafts (
                        id TEXT PRIMARY KEY,
                        lead_id TEXT NOT NULL,
                        company_name TEXT NOT NULL,
                        recipient_name TEXT,
                        recipient_role TEXT,
                        recipient_email TEXT NOT NULL,
                        has_verified_email INTEGER NOT NULL DEFAULT 0,
                        subject TEXT NOT NULL,
                        body TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'drafted',
                        created_at TEXT NOT NULL,
                        updated_at TEXT,
                        source_url TEXT,
                        grounding_notes TEXT,
                        verified_facts_used TEXT,
                        discovery_source TEXT,
                        discovery_query TEXT,
                        relevance_explanation TEXT,
                        flagged_for_manual_review INTEGER NOT NULL DEFAULT 0,
                        manual_review_reason TEXT,
                        raw_json TEXT NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_drafts_lead_id ON outreach_drafts(lead_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_drafts_status ON outreach_drafts(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_drafts_created ON outreach_drafts(created_at DESC)")

                # 6. Legacy draft_records table compatibility
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS draft_records (
                        id TEXT PRIMARY KEY,
                        raw_json TEXT NOT NULL
                    )
                """)

                # 7. Backfill any legacy dispatched_records into outreach_history

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

    # -------------------------------------------------------------------------
    # Automated Lead Discovery Jobs & Leads Persistence
    # -------------------------------------------------------------------------
    def save_discovery_job(self, job: Any) -> None:
        if not self._db_path:
            return
        job_data = job.model_dump() if hasattr(job, "model_dump") else dict(job)
        with self._lock:
            try:
                with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO discovery_jobs
                        (id, prompt, status, created_at, started_at, completed_at, provider_used,
                         total_target, discovered_count, verified_email_count, duplicate_count,
                         skipped_count, failed_count, progress_percent, current_stage, plan_json, error_message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        job_data["id"], job_data["prompt"], job_data["status"], job_data["created_at"],
                        job_data.get("started_at"), job_data.get("completed_at"), job_data.get("provider_used", "auto"),
                        job_data.get("total_target", 25), job_data.get("discovered_count", 0),
                        job_data.get("verified_email_count", 0), job_data.get("duplicate_count", 0),
                        job_data.get("skipped_count", 0), job_data.get("failed_count", 0),
                        job_data.get("progress_percent", 0), job_data.get("current_stage", "Queued"),
                        job_data.get("plan_json", ""), job_data.get("error_message")
                    ))
                    conn.commit()
            except Exception:
                pass

    def update_discovery_job(self, job_id: str, updates: Optional[Dict[str, Any]] = None, **kwargs) -> None:
        if not self._db_path:
            return
        all_updates = dict(updates or {})
        all_updates.update(kwargs)
        if not all_updates:
            return
        with self._lock:
            try:
                set_clauses = [f"{k} = ?" for k in all_updates.keys()]
                values = list(all_updates.values()) + [job_id]
                sql = f"UPDATE discovery_jobs SET {', '.join(set_clauses)} WHERE id = ?"
                with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                    conn.execute(sql, values)
                    conn.commit()
            except Exception:
                pass

    def get_discovery_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        if not self._db_path:
            return None
        with self._lock:
            try:
                with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                    cur = conn.execute("""
                        SELECT id, prompt, status, created_at, started_at, completed_at, provider_used,
                               total_target, discovered_count, verified_email_count, duplicate_count,
                               skipped_count, failed_count, progress_percent, current_stage, plan_json, error_message
                        FROM discovery_jobs WHERE id = ?
                    """, (job_id,))
                    row = cur.fetchone()
                    if not row:
                        return None
                    return {
                        "id": row[0],
                        "prompt": row[1],
                        "status": row[2],
                        "created_at": row[3],
                        "started_at": row[4],
                        "completed_at": row[5],
                        "provider_used": row[6],
                        "total_target": row[7],
                        "discovered_count": row[8],
                        "verified_email_count": row[9],
                        "duplicate_count": row[10],
                        "skipped_count": row[11],
                        "failed_count": row[12],
                        "progress_percent": row[13],
                        "current_stage": row[14],
                        "plan_json": row[15],
                        "error_message": row[16],
                    }
            except Exception:
                return None

    def list_discovery_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self._db_path:
            return []
        with self._lock:
            try:
                with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                    cur = conn.execute("""
                        SELECT id, prompt, status, created_at, started_at, completed_at, provider_used,
                               total_target, discovered_count, verified_email_count, duplicate_count,
                               skipped_count, failed_count, progress_percent, current_stage, plan_json, error_message
                        FROM discovery_jobs
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))
                    jobs = []
                    for row in cur.fetchall():
                        jobs.append({
                            "id": row[0],
                            "prompt": row[1],
                            "status": row[2],
                            "created_at": row[3],
                            "started_at": row[4],
                            "completed_at": row[5],
                            "provider_used": row[6],
                            "total_target": row[7],
                            "discovered_count": row[8],
                            "verified_email_count": row[9],
                            "duplicate_count": row[10],
                            "skipped_count": row[11],
                            "failed_count": row[12],
                            "progress_percent": row[13],
                            "current_stage": row[14],
                            "plan_json": row[15],
                            "error_message": row[16],
                        })
                    return jobs
            except Exception:
                return []

    def save_discovered_lead(self, lead: Any) -> None:
        if not self._db_path:
            return
        lead_data = lead.model_dump() if hasattr(lead, "model_dump") else dict(lead)
        with self._lock:
            try:
                import json
                source_urls_json = json.dumps(lead_data.get("source_urls", []))
                verified_fields_json = json.dumps(lead_data.get("verified_fields", []))

                with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO discovered_leads
                        (id, job_id, company_name, website, industry, city, country,
                         services_description, email, email_verification_status, phone,
                         phone_verification_status, source_urls, discovery_source, discovery_query,
                         discovered_at, relevance_score, relevance_explanation, research_status,
                         failure_reason, verified_fields, is_live)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        lead_data["id"], lead_data["job_id"], lead_data["company_name"], lead_data["website"],
                        lead_data.get("industry", ""), lead_data.get("city", ""), lead_data.get("country", ""),
                        lead_data.get("services_description", ""), lead_data.get("email", ""),
                        lead_data.get("email_verification_status", "not_found"), lead_data.get("phone", ""),
                        lead_data.get("phone_verification_status", "not_found"), source_urls_json,
                        lead_data.get("discovery_source", "search"), lead_data.get("discovery_query", ""),
                        lead_data["discovered_at"], lead_data.get("relevance_score", 0.8),
                        lead_data.get("relevance_explanation", ""), lead_data.get("research_status", "completed"),
                        lead_data.get("failure_reason"), verified_fields_json,
                        1 if lead_data.get("is_live", True) else 0
                    ))
                    conn.commit()
            except Exception:
                pass

    def query_discovered_leads(
        self,
        job_id: str,
        search: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
        category: Optional[str] = None,
        email_status: Optional[str] = None,
        research_status: Optional[str] = None,
        sort_by: Optional[str] = "discovered_at",
        sort_order: Optional[str] = "desc",
        page: int = 1,
        page_size: int = 25,
        **kwargs,
    ) -> Tuple[List[Dict[str, Any]], int, int, Dict[str, int]]:
        default_counts = {
            "all": 0,
            "verified_public": 0,
            "publicly_listed": 0,
            "verified_by_provider": 0,
            "domain_valid": 0,
            "syntax_valid": 0,
            "mailbox_unverified": 0,
            "needs_review": 0,
            "found_unverified": 0,
            "not_found": 0,
            "invalid": 0,
        }
        if not self._db_path:
            return [], 0, 0, default_counts

        with self._lock:
            try:
                import json
                with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                    # 1. Verification counts for this job
                    cur = conn.execute(
                        "SELECT email_verification_status, COUNT(*) FROM discovered_leads WHERE job_id = ? GROUP BY email_verification_status",
                        (job_id,)
                    )
                    counts = dict(default_counts)
                    raw_rows = cur.fetchall()
                    total_leads = 0
                    for status_val, status_count in raw_rows:
                        counts[status_val] = status_count
                        total_leads += status_count
                    counts["all"] = total_leads

                    # Legacy compatibility: 'verified_public' in counts represents all valid/public emails if not explicitly set
                    if counts["verified_public"] == 0:
                        counts["verified_public"] = (
                            counts.get("publicly_listed", 0)
                            + counts.get("verified_by_provider", 0)
                            + counts.get("domain_valid", 0)
                            + counts.get("syntax_valid", 0)
                            + counts.get("mailbox_unverified", 0)
                        )

                    # 2. Filter clauses
                    where_clauses = ["job_id = ?"]
                    params = [job_id]

                    if email_status and email_status.strip().lower() not in ("all", ""):
                        req_status = email_status.strip().lower()
                        if req_status == "verified_public":
                            where_clauses.append(
                                "email_verification_status IN ('verified_public', 'publicly_listed', 'verified_by_provider', 'domain_valid', 'syntax_valid', 'mailbox_unverified')"
                            )
                        else:
                            where_clauses.append("email_verification_status = ?")
                            params.append(req_status)

                    if research_status and research_status.strip().lower() not in ("all", ""):
                        where_clauses.append("research_status = ?")
                        params.append(research_status.strip().lower())

                    if country and country.strip():
                        where_clauses.append("LOWER(country) = ?")
                        params.append(country.strip().lower())

                    if city and city.strip():
                        where_clauses.append("LOWER(city) = ?")
                        params.append(city.strip().lower())

                    if category and category.strip():
                        where_clauses.append("LOWER(industry) LIKE ?")
                        params.append(f"%{category.strip().lower()}%")

                    if search and search.strip():
                        st = f"%{search.strip().lower()}%"
                        where_clauses.append("(LOWER(company_name) LIKE ? OR LOWER(website) LIKE ? OR LOWER(services_description) LIKE ? OR LOWER(email) LIKE ? OR LOWER(city) LIKE ?)")
                        params.extend([st, st, st, st, st])

                    where_sql = " WHERE " + " AND ".join(where_clauses)

                    # Total matching
                    cur = conn.execute(f"SELECT COUNT(*) FROM discovered_leads{where_sql}", params)
                    total_count = cur.fetchone()[0]

                    # Pagination
                    page_num = max(1, page)
                    limit = max(1, min(100, page_size))
                    offset = (page_num - 1) * limit
                    total_pages = max(1, (total_count + limit - 1) // limit) if total_count > 0 else 0

                    cur = conn.execute(f"""
                        SELECT id, job_id, company_name, website, industry, city, country,
                               services_description, email, email_verification_status, phone,
                               phone_verification_status, source_urls, discovery_source, discovery_query,
                               discovered_at, relevance_score, relevance_explanation, research_status,
                               failure_reason, verified_fields, is_live
                        FROM discovered_leads
                        {where_sql}
                        ORDER BY relevance_score DESC, discovered_at DESC
                        LIMIT ? OFFSET ?
                    """, params + [limit, offset])

                    leads = []
                    for row in cur.fetchall():
                        try:
                            s_urls = json.loads(row[12]) if row[12] else []
                        except Exception:
                            s_urls = []
                        try:
                            v_fields = json.loads(row[20]) if row[20] else []
                        except Exception:
                            v_fields = []

                        leads.append({
                            "id": row[0],
                            "job_id": row[1],
                            "company_name": row[2],
                            "website": row[3],
                            "industry": row[4] or "",
                            "city": row[5] or "",
                            "country": row[6] or "",
                            "services_description": row[7] or "",
                            "email": row[8] or "",
                            "email_verification_status": row[9],
                            "phone": row[10] or "",
                            "phone_verification_status": row[11],
                            "source_urls": s_urls,
                            "discovery_source": row[13],
                            "discovery_query": row[14],
                            "discovered_at": row[15],
                            "relevance_score": float(row[16]),
                            "relevance_explanation": row[17] or "",
                            "research_status": row[18],
                            "failure_reason": row[19],
                            "verified_fields": v_fields,
                            "is_live": bool(row[21]),
                        })

                    return leads, total_count, total_pages, counts
            except Exception:
                return [], 0, 0, default_counts

    def get_discovered_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        if not self._db_path:
            return None
        with self._lock:
            try:
                import json
                with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                    cur = conn.execute("""
                        SELECT id, job_id, company_name, website, industry, city, country,
                               services_description, email, email_verification_status, phone,
                               phone_verification_status, source_urls, discovery_source, discovery_query,
                               discovered_at, relevance_score, relevance_explanation, research_status,
                               failure_reason, verified_fields, is_live
                        FROM discovered_leads WHERE id = ?
                    """, (lead_id,))
                    row = cur.fetchone()
                    if not row:
                        return None
                    try:
                        s_urls = json.loads(row[12]) if row[12] else []
                    except Exception:
                        s_urls = []
                    try:
                        v_fields = json.loads(row[20]) if row[20] else []
                    except Exception:
                        v_fields = []
                    return {
                        "id": row[0],
                        "job_id": row[1],
                        "company_name": row[2],
                        "website": row[3],
                        "industry": row[4] or "",
                        "city": row[5] or "",
                        "country": row[6] or "",
                        "services_description": row[7] or "",
                        "email": row[8] or "",
                        "email_verification_status": row[9],
                        "phone": row[10] or "",
                        "phone_verification_status": row[11],
                        "source_urls": s_urls,
                        "discovery_source": row[13],
                        "discovery_query": row[14],
                        "discovered_at": row[15],
                        "relevance_score": float(row[16]),
                        "relevance_explanation": row[17] or "",
                        "research_status": row[18],
                        "failure_reason": row[19],
                        "verified_fields": v_fields,
                        "is_live": bool(row[21]),
                    }
            except Exception:
                return None

    def export_discovered_leads_csv(
        self,
        job_id: str,
        search: Optional[str] = None,
        email_status: Optional[str] = None,
    ) -> str:
        leads, _, _, _ = self.query_discovered_leads(
            job_id=job_id,
            search=search,
            email_status=email_status,
            page=1,
            page_size=10000,
        )

        headers = [
            "Lead ID",
            "Company Name",
            "Website",
            "Industry",
            "City",
            "Country",
            "Business Description",
            "Public Email",
            "Email Verification Status",
            "Phone",
            "Phone Verification Status",
            "Relevance Score",
            "Relevance Explanation",
            "Discovery Source",
            "Discovered At (UTC)",
            "Source URLs",
        ]

        def escape_csv(val: str) -> str:
            clean = (val or "").replace('"', '""')
            return f'"{clean}"'

        def format_phone_csv(val: Optional[str]) -> str:
            """
            Formats phone numbers for spreadsheet exports (CSV).
            Encapsulates string with formula syntax '="<phone>"' to prevent spreadsheet software
            (Excel, Google Sheets, Calc) from stripping leading zeros ('03111111926' -> '3111111926')
            or converting international numbers to scientific notation ('+924235789000' -> '9.23E+11').
            Preserves corrupted numbers as literal text without inventing digits.
            """
            if not val:
                return '""'
            clean = str(val).strip().replace('"', '""')
            if not clean:
                return '""'
            return f'"=""{clean}"""'

        rows = [",".join(headers)]
        for item in leads:
            urls_str = "; ".join(item.get("source_urls", []))
            row_data = [
                escape_csv(item["id"]),
                escape_csv(item["company_name"]),
                escape_csv(item["website"]),
                escape_csv(item["industry"]),
                escape_csv(item["city"]),
                escape_csv(item["country"]),
                escape_csv(item["services_description"]),
                escape_csv(item["email"]),
                escape_csv(item["email_verification_status"]),
                format_phone_csv(item["phone"]),
                escape_csv(item["phone_verification_status"]),
                escape_csv(f"{item['relevance_score']:.2f}"),
                escape_csv(item["relevance_explanation"]),
                escape_csv(item["discovery_source"]),
                escape_csv(item["discovered_at"]),
                escape_csv(urls_str),
            ]
            rows.append(",".join(row_data))

        return "\r\n".join(rows)

    def is_dispatched(self, draft_id: str) -> bool:
        with self._lock:
            return draft_id in self._by_draft_id

    def is_in_flight(self, draft_id: str) -> bool:
        with self._lock:
            return draft_id in self._in_flight_drafts

    def save_draft(self, draft: Any) -> None:
        """Persists an OutreachDraft object to SQLite and keeps draft_records in sync."""
        if not self._db_path:
            return
        try:
            raw_json = draft.model_dump_json() if hasattr(draft, "model_dump_json") else json.dumps(draft)
            verified_facts_json = json.dumps(getattr(draft, "verified_facts_used", []))
            has_verified = 1 if getattr(draft, "has_verified_email", False) else 0
            flagged = 1 if getattr(draft, "flagged_for_manual_review", False) else 0

            with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO outreach_drafts (
                        id, lead_id, company_name, recipient_name, recipient_role, recipient_email,
                        has_verified_email, subject, body, status, created_at, updated_at,
                        source_url, grounding_notes, verified_facts_used, discovery_source,
                        discovery_query, relevance_explanation, flagged_for_manual_review,
                        manual_review_reason, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    draft.id,
                    draft.lead_id,
                    draft.company_name,
                    getattr(draft, "recipient_name", ""),
                    getattr(draft, "recipient_role", ""),
                    draft.recipient_email,
                    has_verified,
                    draft.subject,
                    draft.body,
                    getattr(draft, "status", "drafted"),
                    draft.created_at,
                    getattr(draft, "updated_at", None),
                    getattr(draft, "source_url", ""),
                    getattr(draft, "grounding_notes", ""),
                    verified_facts_json,
                    getattr(draft, "discovery_source", ""),
                    getattr(draft, "discovery_query", ""),
                    getattr(draft, "relevance_explanation", ""),
                    flagged,
                    getattr(draft, "manual_review_reason", None),
                    raw_json,
                ))
                conn.execute("INSERT OR REPLACE INTO draft_records (id, raw_json) VALUES (?, ?)", (draft.id, raw_json))
                conn.commit()
        except Exception:
            pass

    def get_draft(self, draft_id: str) -> Optional[Any]:
        """Retrieves an OutreachDraft by ID."""
        if not self._db_path or not draft_id:
            return None
        try:
            with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                cur = conn.execute("SELECT raw_json FROM outreach_drafts WHERE id = ?", (draft_id,))
                row = cur.fetchone()
                if not row:
                    cur = conn.execute("SELECT raw_json FROM draft_records WHERE id = ?", (draft_id,))
                    row = cur.fetchone()
                if row:
                    data = json.loads(row[0])
                    draft_cls = _get_outreach_draft_cls()
                    if draft_cls:
                        return draft_cls.model_validate(data)
                    return data
        except Exception:
            pass
        return None

    def get_draft_by_lead_id(self, lead_id: str) -> Optional[Any]:
        """Retrieves existing active draft for a lead to prevent duplicates."""
        if not self._db_path or not lead_id:
            return None
        try:
            clean_id = lead_id.strip()
            variants = [clean_id]
            if clean_id.startswith("disc-"):
                variants.append(clean_id[5:])
            else:
                variants.append(f"disc-{clean_id}")

            with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                placeholders = ",".join("?" for _ in variants)
                query = f"""
                    SELECT raw_json FROM outreach_drafts
                    WHERE lead_id IN ({placeholders}) AND status != 'rejected'
                    ORDER BY created_at DESC LIMIT 1
                """
                cur = conn.execute(query, tuple(variants))
                row = cur.fetchone()
                if row:
                    data = json.loads(row[0])
                    draft_cls = _get_outreach_draft_cls()
                    if draft_cls:
                        return draft_cls.model_validate(data)
                    return data
        except Exception:
            pass
        return None

    def query_drafts(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Any], int, int, Dict[str, int]]:
        """Queries drafts with pagination, text search, and status counts."""
        default_counts = {"all": 0, "drafted": 0, "approved": 0, "rejected": 0, "sent": 0, "flagged": 0}
        if not self._db_path:
            return [], 0, 0, default_counts

        try:
            with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                counts = dict(default_counts)
                cur = conn.execute("SELECT status, COUNT(*) FROM outreach_drafts GROUP BY status")
                for row in cur.fetchall():
                    s = (row[0] or "").lower()
                    if s in counts:
                        counts[s] = row[1]
                cur_all = conn.execute("SELECT COUNT(*) FROM outreach_drafts")
                counts["all"] = cur_all.fetchone()[0]
                cur_flag = conn.execute("SELECT COUNT(*) FROM outreach_drafts WHERE flagged_for_manual_review = 1")
                counts["flagged"] = cur_flag.fetchone()[0]

                clauses = []
                params: List[Any] = []

                if status and status.lower() != "all":
                    if status.lower() == "flagged":
                        clauses.append("flagged_for_manual_review = 1")
                    else:
                        clauses.append("status = ?")
                        params.append(status.lower())

                if search and search.strip():
                    term = f"%{search.strip().lower()}%"
                    clauses.append("(LOWER(company_name) LIKE ? OR LOWER(recipient_email) LIKE ? OR LOWER(subject) LIKE ? OR LOWER(recipient_name) LIKE ?)")
                    params.extend([term, term, term, term])

                where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

                count_sql = f"SELECT COUNT(*) FROM outreach_drafts {where_sql}"
                total = conn.execute(count_sql, tuple(params)).fetchone()[0]

                total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1
                offset = (max(1, page) - 1) * page_size

                data_sql = f"""
                    SELECT raw_json FROM outreach_drafts
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                cur_params = list(params)
                cur_params.extend([page_size, offset])
                cur = conn.execute(data_sql, tuple(cur_params))

                draft_cls = _get_outreach_draft_cls()

                drafts = []
                for row in cur.fetchall():
                    try:
                        data = json.loads(row[0])
                        if draft_cls:
                            d = draft_cls.model_validate(data)
                        else:
                            d = data
                        drafts.append(d)
                    except Exception:
                        pass

                return drafts, total, total_pages, counts
        except Exception:
            return [], 0, 0, default_counts

    def update_draft(self, draft_id: str, updates: Dict[str, Any]) -> Optional[Any]:
        """Updates fields of an existing draft and persists."""
        draft = self.get_draft(draft_id)
        if not draft:
            return None

        if "subject" in updates and updates["subject"] is not None:
            draft.subject = updates["subject"].strip()
        if "body" in updates and updates["body"] is not None:
            draft.body = updates["body"].strip()
        if "recipient_name" in updates and updates["recipient_name"] is not None:
            draft.recipient_name = updates["recipient_name"].strip()
        if "status" in updates and updates["status"] is not None:
            draft.status = updates["status"]

        draft.updated_at = datetime.now(timezone.utc).isoformat()
        self.save_draft(draft)
        return draft

    def approve_draft(self, draft_id: str) -> Optional[Any]:
        """Explicitly approves a draft. Safety check: requires verified public email."""
        draft = self.get_draft(draft_id)
        if not draft:
            return None
        if not draft.has_verified_email:
            raise ValueError("Safety Gate: Cannot approve outreach draft without a verified public business email address.")
        if draft.status == "sent":
            raise ValueError("Draft has already been sent.")

        draft.status = "approved"
        draft.updated_at = datetime.now(timezone.utc).isoformat()
        self.save_draft(draft)

        self.record_history_entry(
            draft_id=draft.id,
            recipient_email=draft.recipient_email,
            subject=draft.subject,
            status="approved",
            provider="human-approval",
            is_simulated=False,
            recipient_name=draft.recipient_name,
            company_name=draft.company_name,
            body_preview=draft.body,
            source_url=draft.source_url,
            dispatched_at=draft.updated_at,
        )
        return draft

    def discard_draft(self, draft_id: str, reason: Optional[str] = None) -> Optional[Any]:
        """Discards / rejects an outreach draft."""
        draft = self.get_draft(draft_id)
        if not draft:
            return None
        if draft.status == "sent":
            raise ValueError("Cannot discard a draft that has already been dispatched.")

        draft.status = "rejected"
        draft.updated_at = datetime.now(timezone.utc).isoformat()
        self.save_draft(draft)

        self.record_history_entry(
            draft_id=draft.id,
            recipient_email=draft.recipient_email,
            subject=draft.subject,
            status="rejected",
            provider="human-review",
            is_simulated=False,
            recipient_name=draft.recipient_name,
            company_name=draft.company_name,
            body_preview=draft.body,
            source_url=draft.source_url,
            error_message=reason or "Discarded by operator",
            dispatched_at=draft.updated_at,
        )
        return draft

    def delete_draft(self, draft_id: str) -> bool:
        """Permanently deletes a draft record."""
        if not self._db_path or not draft_id:
            return False
        try:
            with sqlite3.connect(self._db_path, timeout=5.0) as conn:
                conn.execute("DELETE FROM outreach_drafts WHERE id = ?", (draft_id,))
                conn.execute("DELETE FROM draft_records WHERE id = ?", (draft_id,))
                conn.commit()
            return True
        except Exception:
            return False

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
                        conn.execute("DELETE FROM discovery_jobs")
                        conn.execute("DELETE FROM discovered_leads")
                        conn.execute("DELETE FROM outreach_drafts")
                        conn.execute("DELETE FROM draft_records")
                        conn.commit()
                except Exception:
                    pass


# Global singleton tracker
global_dispatch_tracker = DispatchTracker()
