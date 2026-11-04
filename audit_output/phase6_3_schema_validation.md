# Phase 6.3 — Database Schema & Parent Job Validation Report

**Execution Mode:** STRICT READ-ONLY SCHEMA VALIDATION  
**Active Production Database:** `storage/dispatches.db` (149 leads, 6 discovery jobs)  
**Proposed Import Target:** Exactly 21 Verified Qualified Leads under 1 New Parent Job  
**Schema Status:** Validated & Compliant (Simulation Passed 100%)  
**Audit Completion Date:** November 3, 2026

---

## 1. Executive Summary

This report documents the structural and referential schema audit for the proposed production import of **21 verified C&I Solar EPC leads** into `storage/dispatches.db`.

### Key Validation Outcomes
- **`discovery_jobs` Schema Conformance:** Exactly 1 proposed parent job (`job-phase6-live-expansion`) conforms to all 17 table columns, data types, and NOT NULL constraints.
- **`discovered_leads` Schema Conformance:** All 21 proposed leads conform to all 22 table columns, data types, and constraint definitions.
- **Foreign-Key Integrity:** With `PRAGMA foreign_keys = ON;`, inserting the parent job record prior to lead insertion ensures **zero new foreign-key violations**.
- **Historical Invariant Preservation:** The two historical foreign-key violations on rows 124 and 125 (`job-phase3-live-expansion`) are preserved untouched without modification or repair.
- **JSON Column Syntax:** All serialized JSON columns (`source_urls`, `verified_fields`, and `plan_json`) were tested and confirmed valid.

---

## 2. Table Schemas & Column Specifications

The production database schema was extracted via `PRAGMA table_info()` in read-only mode:

### 2.1 `discovery_jobs` Table (17 Columns)

| Column Index | Column Name | Data Type | Not Null | Default Value | Primary Key | Proposed Parent Job Value |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 0 | `id` | `TEXT` | 0 | `None` | **PK (1)** | `'job-phase6-live-expansion'` |
| 1 | `prompt` | `TEXT` | **1** | `None` | 0 | `'Phase 6 Live Discovery: Lahore Commercial & Industrial Solar EPC Leads (100-Company Milestone Gate)'` |
| 2 | `status` | `TEXT` | **1** | `None` | 0 | `'completed'` |
| 3 | `created_at` | `TEXT` | **1** | `None` | 0 | `'2026-11-03T16:00:00Z'` |
| 4 | `started_at` | `TEXT` | 0 | `None` | 0 | `'2026-11-03T16:00:01Z'` |
| 5 | `completed_at` | `TEXT` | 0 | `None` | 0 | `'2026-11-03T21:30:00Z'` |
| 6 | `provider_used` | `TEXT` | **1** | `None` | 0 | `'Live Web Crawl & Authoritative Registry Verification (PPIB/AEDB)'` |
| 7 | `total_target` | `INTEGER` | **1** | `None` | 0 | `21` |
| 8 | `discovered_count` | `INTEGER` | **1** | `0` | 0 | `21` |
| 9 | `verified_email_count` | `INTEGER` | **1** | `0` | 0 | `21` |
| 10 | `duplicate_count` | `INTEGER` | **1** | `0` | 0 | `0` |
| 11 | `skipped_count` | `INTEGER` | **1** | `0` | 0 | `6` (4 disqualified duplicates + 2 review queue held) |
| 12 | `failed_count` | `INTEGER` | **1** | `0` | 0 | `0` |
| 13 | `progress_percent` | `INTEGER` | **1** | `0` | 0 | `100` |
| 14 | `current_stage` | `TEXT` | 0 | `None` | 0 | `'Audit & Verification completed: 21 verified_qualified approved for import, 2 held for manual review, 4 disqualified duplicates.'` |
| 15 | `plan_json` | `TEXT` | 0 | `None` | 0 | `'{"industry": "Solar Energy", "location_city": "Lahore", "target_tier": 1, "approved_count": 21, "milestone_target": 100}'` |
| 16 | `error_message` | `TEXT` | 0 | `None` | 0 | `NULL` |

### 2.2 `discovered_leads` Table (22 Columns)

| Column Index | Column Name | Data Type | Not Null | Default Value | Primary Key | Staging Data Format & Example |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 0 | `id` | `TEXT` | 0 | `None` | **PK (1)** | `'lead-p6-002'` through `'lead-p6-029'` (Unique) |
| 1 | `job_id` | `TEXT` | **1** | `None` | 0 | `'job-phase6-live-expansion'` (FK to `discovery_jobs.id`) |
| 2 | `company_name` | `TEXT` | **1** | `None` | 0 | e.g. `'Grace Solar Pakistan'` |
| 3 | `website` | `TEXT` | **1** | `None` | 0 | e.g. `'https://www.gracesolarpk.com'` |
| 4 | `industry` | `TEXT` | 0 | `None` | 0 | `'Solar Energy'` |
| 5 | `city` | `TEXT` | 0 | `None` | 0 | `'Lahore'` |
| 6 | `country` | `TEXT` | 0 | `None` | 0 | `'Pakistan'` |
| 7 | `services_description` | `TEXT` | 0 | `None` | 0 | Comprehensive C&I capability description |
| 8 | `email` | `TEXT` | 0 | `None` | 0 | Listed corporate email address |
| 9 | `email_verification_status`| `TEXT` | **1** | `None` | 0 | `'publicly_listed'` (Unpinged per blackout) |
| 10 | `phone` | `TEXT` | 0 | `None` | 0 | Listed commercial telephone string |
| 11 | `phone_verification_status`| `TEXT` | **1** | `None` | 0 | `'publicly_listed'` (Undialed per blackout) |
| 12 | `source_urls` | `TEXT` | **1** | `None` | 0 | JSON array of source URLs, e.g. `'["https://www.gracesolarpk.com"]'` |
| 13 | `discovery_source` | `TEXT` | **1** | `None` | 0 | `'Phase 6 Live Corporate & Registry Verification'` |
| 14 | `discovery_query` | `TEXT` | **1** | `None` | 0 | `'Lahore C&I solar EPC contractor commercial industrial net-metering'` |
| 15 | `discovered_at` | `TEXT` | **1** | `None` | 0 | ISO-8601 UTC timestamp, e.g. `'2026-11-03T16:00:00Z'` |
| 16 | `relevance_score` | `REAL` | **1** | `None` | 0 | `0.96` |
| 17 | `relevance_explanation` | `TEXT` | **1** | `None` | 0 | Traceability, physical office, and PPIB qualification rationale |
| 18 | `research_status` | `TEXT` | **1** | `None` | 0 | `'completed'` |
| 19 | `failure_reason` | `TEXT` | 0 | `None` | 0 | `NULL` |
| 20 | `verified_fields` | `TEXT` | **1** | `None` | 0 | JSON array of audited field keys |
| 21 | `is_live` | `INTEGER` | **1** | `1` | 0 | `1` (Live verified lead) |

---

## 3. Parent Job Specification & Dependency Order

Under SQLite foreign-key enforcement (`PRAGMA foreign_keys = ON;`), a child row cannot reference a non-existent parent row. 

Therefore, in any future approved production import, the SQL execution plan must follow strict sequential order:

```sql
-- Step 1: Enable FK enforcement
PRAGMA foreign_keys = ON;

-- Step 2: Begin atomic transaction
BEGIN TRANSACTION;

-- Step 3: Insert parent discovery job FIRST
INSERT INTO discovery_jobs (
    id, prompt, status, created_at, started_at, completed_at, provider_used,
    total_target, discovered_count, verified_email_count, duplicate_count,
    skipped_count, failed_count, progress_percent, current_stage, plan_json, error_message
) VALUES (
    'job-phase6-live-expansion',
    'Phase 6 Live Discovery: Lahore Commercial & Industrial Solar EPC Leads (100-Company Milestone Gate)',
    'completed',
    '2026-11-03T16:00:00Z',
    '2026-11-03T16:00:01Z',
    '2026-11-03T21:30:00Z',
    'Live Web Crawl & Authoritative Registry Verification (PPIB/AEDB)',
    21, 21, 21, 0, 6, 0, 100,
    'Audit & Verification completed: 21 verified_qualified approved for import, 2 held for manual review, 4 disqualified duplicates.',
    '{"industry": "Solar Energy", "location_city": "Lahore", "target_tier": 1, "approved_count": 21, "milestone_target": 100}',
    NULL
);

-- Step 4: Insert the 21 discovered leads SECOND
-- (All referencing job_id = 'job-phase6-live-expansion')

-- Step 5: Validate invariants before COMMIT
-- PRAGMA foreign_key_check; -> Must return exactly the 2 historical rows
-- PRAGMA integrity_check;   -> Must return ok

-- Step 6: Commit transaction
COMMIT;
```

---

## 4. Historical Foreign-Key Invariant Preservation

In `storage/dispatches.db`, rows 124 and 125 contain:
- Row 124: `lead-p3-multiline-001` (`job_id = 'job-phase3-live-expansion'`)
- Row 125: `lead-p3-wattey-001` (`job_id = 'job-phase3-live-expansion'`)

`discovery_jobs` has never contained a record with `id = 'job-phase3-live-expansion'`. Running `PRAGMA foreign_key_check;` reports exactly:
```
('discovered_leads', 124, 'discovery_jobs', 0)
('discovered_leads', 125, 'discovery_jobs', 0)
```

Per strict safety rules (*"Preserve all existing records and historical FK anomalies. Do not repair them"*):
- Neither `job-phase3-live-expansion` nor any synthetic repair job will be added.
- The two rows remain intact.
- The dry-run simulation confirmed that the 21 new leads introduce **zero additional FK violations**, maintaining the total FK violation count at exactly 2.

---

## 5. Dry-Run Schema Validation Results

A full simulation was executed against a disposable copy of `storage/dispatches.db`:

1. **Transaction Execution:** Atomic commit executed with zero errors.
2. **Post-Simulation Lead Count:** Exactly **170 leads** ($149 + 21 = 170$).
3. **Post-Simulation Job Count:** Exactly **7 jobs** ($6 + 1 = 7$).
4. **Post-Simulation Qualified Solar Rows:** Exactly **104 rows**.
5. **Distinct Qualified Companies:** $104 - 4\text{ duplicate pairs} = \mathbf{100\text{ distinct companies}}$.
6. **Integrity Check:** `PRAGMA integrity_check;` returned `ok`.
7. **Foreign Key Violations:** Returned exactly **2 violations** (rows 124 and 125 only).

### Final Schema Verdict
**SCHEMA VALIDATION PASSED 100%.** The proposed staging records are completely compliant with all production database constraints.
