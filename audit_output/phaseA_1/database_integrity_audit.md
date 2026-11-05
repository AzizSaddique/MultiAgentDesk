# AgentDesk — Phase A.1: Database Safety & Integrity Audit

**Audit Date:** November 5, 2026  
**Auditor:** Antigravity AI Systems Architecture Team  
**Database File:** `storage/dispatches.db`  
**Connection Mode:** STRICT READ-ONLY (`file:storage/dispatches.db?mode=ro`, URI mode enabled)  
**Safety Protocol:** Zero writes executed. Zero records modified. Historical foreign-key violations preserved and unrepaired.

---

## 1. Executive Database Summary

An independent, read-only diagnostic of `storage/dispatches.db` was conducted using Python SQLite URI read-only inspection. 

### Key Empirical Findings:
1. **Physical Integrity:** `PRAGMA integrity_check` returned `ok`. There is zero physical page corruption or B-tree damage.
2. **Current Record Invariant:**
   - **`discovered_leads`:** Exactly **149 rows**.
   - **`discovery_jobs`:** Exactly **6 rows**.
   - **`draft_records`:** Exactly **146 rows**.
   - **`outreach_drafts`:** Exactly **2 rows**.
   - **`outreach_history`:** Exactly **3 rows**.
   - **`dispatched_records`:** Exactly **0 rows**.
3. **Foreign-Key Violations:** `PRAGMA foreign_key_check` reported exactly **2 violations**, corresponding to rows 124 and 125 of `discovered_leads` referencing an orphaned job `job-phase3-live-expansion`.
4. **Phase 6.3 Import Status:** The Phase 6.3 projected import of 21 solar EPC candidates **has NOT been executed**. The database remains in its pre-import baseline state (149 leads, 6 jobs).

---

## 2. Table Schemas and Physical Row Counts

| Table Name | Physical Row Count | Primary Key | Foreign Keys | Schema Definition |
| :--- | :---: | :---: | :--- | :--- |
| `discovered_leads` | **149** | `id TEXT` | `job_id REFERENCES discovery_jobs(id)` | Stores enriched lead metadata, contact info, relevance scores, and evidence lists. |
| `discovery_jobs` | **6** | `id TEXT` | None | Tracks natural language discovery jobs, telemetry metrics, and pipeline stages. |
| `draft_records` | **146** | `id TEXT` | None | Legacy compatibility store holding raw JSON draft payloads. |
| `outreach_drafts` | **2** | `id TEXT` | None (Explicit `lead_id TEXT`) | Durably tracks outreach draft status (`drafted`, `approved`, `rejected`, `sent`). |
| `outreach_history` | **3** | `id TEXT` | None (Explicit `draft_id TEXT`) | Audit log recording all draft dispatches, provider modes, and delivery statuses. |
| `dispatched_records`| **0** | `draft_id TEXT`| None | Idempotency registry preventing duplicate sends via SHA-256 message hashing. |

### Complete DDL Definitions

```sql
-- 1. discovered_leads
CREATE TABLE discovered_leads (
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
);

-- 2. discovery_jobs
CREATE TABLE discovery_jobs (
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
);

-- 3. outreach_drafts
CREATE TABLE outreach_drafts (
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
);

-- 4. outreach_history
CREATE TABLE outreach_history (
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
);

-- 5. dispatched_records
CREATE TABLE dispatched_records (
    draft_id TEXT PRIMARY KEY,
    recipient_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    dispatched_at TEXT NOT NULL,
    status TEXT NOT NULL,
    provider TEXT NOT NULL,
    content_hash TEXT NOT NULL
);

-- 6. draft_records
CREATE TABLE draft_records (
    id TEXT PRIMARY KEY,
    raw_json TEXT NOT NULL
);
```

---

## 3. Database Indexes

| Table | Index Name | Indexed Columns | Index Type |
| :--- | :--- | :--- | :--- |
| `discovered_leads` | `idx_disc_leads_email_stat` | `email_verification_status` | Standard B-Tree |
| `discovered_leads` | `idx_disc_leads_job` | `job_id` | Standard B-Tree |
| `discovery_jobs` | `idx_disc_jobs_created` | `created_at DESC` | Descending B-Tree |
| `discovery_jobs` | `idx_disc_jobs_status` | `status` | Standard B-Tree |
| `dispatched_records` | `idx_content_hash` | `content_hash` | Standard B-Tree |
| `outreach_drafts` | `idx_drafts_created` | `created_at DESC` | Descending B-Tree |
| `outreach_drafts` | `idx_drafts_lead_id` | `lead_id` | Standard B-Tree |
| `outreach_drafts` | `idx_drafts_status` | `status` | Standard B-Tree |
| `outreach_history` | `idx_history_dispatched_at` | `dispatched_at DESC` | Descending B-Tree |
| `outreach_history` | `idx_history_draft_id` | `draft_id` | Standard B-Tree |
| `outreach_history` | `idx_history_status` | `status` | Standard B-Tree |

---

## 4. Foreign-Key Relationships & Historical Violations

### 4.1 PRAGMA foreign_key_check Results
Executing `PRAGMA foreign_key_check;` yields exactly two violating rows:

```
Violation 1: ('discovered_leads', 124, 'discovery_jobs', 0)
Violation 2: ('discovered_leads', 125, 'discovery_jobs', 0)
```

### 4.2 Details of the Violating Rows
Querying rowids 124 and 125 in `discovered_leads`:
- **Row 124:**
  - `id`: `'lead-p3-multiline-001'`
  - `company_name`: `'Multiline Engineering Co.'`
  - `website`: `'https://multiline.com.pk'`
  - `job_id`: `'job-phase3-live-expansion'`
- **Row 125:**
  - `id`: `'lead-p3-wattey-001'`
  - `company_name`: `'Wattey Energy'`
  - `website`: `'https://watteyenergy.pk'`
  - `job_id`: `'job-phase3-live-expansion'`

### 4.3 Root Cause Analysis
- `discovered_leads` references `discovery_jobs(id)` via foreign key constraint: `FOREIGN KEY (job_id) REFERENCES discovery_jobs(id)`.
- Querying `SELECT id FROM discovery_jobs WHERE id = 'job-phase3-live-expansion'` returns **0 rows**.
- These two records were inserted during historical Phase 3 testing before the parent job record was inserted or without enforcing foreign-key constraints (`PRAGMA foreign_keys = ON` is disabled by default in SQLite connections unless explicitly turned on).
- **Safety Invariant:** In compliance with strict safety directives, **these historical violations were not modified or repaired**. They remain preserved as documented historical artifacts.

---

## 5. Phase 6.3 Audit Artifacts Reconciliation

The workspace includes audit artifacts from Phase 6.3:
- `audit_output/phase6_3_import_safety_gate.md`
- `audit_output/phase6_3_deduplication_report.md`
- `audit_output/phase6_3_import_preview.csv`
- `audit_output/phase6_3_rollback_plan.md`

### Reconciliation Findings:
1. In `phase6_3_import_safety_gate.md`:
   - Scope: Staged 21 candidate solar EPC leads (`cand-p6-002` through `cand-p6-024` and `cand-p6-029`).
   - Planned parent job ID: `job-phase6-live-expansion`.
   - Verdict: Stated `READY FOR EXPLICIT PRODUCTION IMPORT APPROVAL`.
2. Actual Production Inspection:
   - `SELECT COUNT(*) FROM discovered_leads WHERE job_id = 'job-phase6-live-expansion'` -> **0 rows**.
   - `SELECT COUNT(*) FROM discovery_jobs WHERE id = 'job-phase6-live-expansion'` -> **0 rows**.
   - Total leads count remains exactly **149**; total jobs count remains exactly **6**.
3. **Conclusion:** The Phase 6.3 projected import was **NOT executed** in production. The database remains in its pre-import state.

---

## 6. Existing Discovery Jobs Summary

| Job ID | Prompt | Discovered Count | Verified Emails | Created At | Provider Used |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `job-phase4-live-expansion` | Phase 4 Live Discovery: Lahore Commercial & Industrial Solar EPC Leads | 24 | 24 | 2026-11-01T15:00:00Z | Live Web Crawl & Registry |
| `job-893d08794b` | Discover European B2B SaaS companies specializing in logistics... | 7 | 7 | 2026-10-28T15:49:18Z | directory |
| `job-a7389689e2` | Find 20 IoT companies in Germany that may need embedded software... | 13 | 13 | 2026-10-28T15:35:07Z | directory |
| `job-live-expansion-lahore` | Expanded targeted discovery of commercial and industrial solar EPC... | 14 | 14 | 2026-10-28T07:54:29Z | Live Web Discovery |
| `job-31700f20dc` | Find commercial solar EPC companies and industrial rooftop solar... | 25 | 25 | 2026-10-28T07:08:01Z | directory |
| `job-lahore-solar-c-and-i` | Targeted search for commercial and industrial solar EPC companies... | 66 | 66 | 2026-10-27T18:14:48Z | Public Business Directory |

**Total Leads Attributed across 6 Registered Jobs:** 147 leads.  
**Orphaned Leads Attributed to Missing Job `job-phase3-live-expansion`:** 2 leads (rows 124 and 125).  
**Grand Total:** **149 leads**.

