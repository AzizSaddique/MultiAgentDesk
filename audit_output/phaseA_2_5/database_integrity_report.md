# Phase A.2.5 — Database Integrity Report

**Target Database:** `storage/dispatches.db`  
**Audit Phase:** A.2.5 — Independent Adversarial Security Verification  
**Audit Date:** 2026-11-06  
**Auditor:** Independent Adversarial Security Agent  

---

## 1. Executive Summary

In compliance with the mandatory audit safety rules, all security testing in Phase A.2.5 was conducted without modifying the production SQLite database. The production database was queried strictly using SQLite's read-only URI mode (`?mode=ro`).

**Integrity Verification:**
- Zero records were created, updated, or deleted.
- Total table row counts match the exact Phase A.1 and Phase A.2.4 baselines.
- `PRAGMA integrity_check` returned `ok`.
- `PRAGMA foreign_key_check` confirmed the two pre-existing baseline orphaned rows (`discovered_leads` rowids 124 and 125) remain unaltered.

---

## 2. Read-Only Query Script & Verification Commands

The following Python script was executed against the production database:

```python
import sqlite3
import pathlib

db_uri = pathlib.Path('storage/dispatches.db').resolve().as_uri() + '?mode=ro'
conn = sqlite3.connect(db_uri, uri=True)
cur = conn.cursor()

print('discovered_leads:', cur.execute('SELECT COUNT(*) FROM discovered_leads').fetchone()[0])
print('discovery_jobs:', cur.execute('SELECT COUNT(*) FROM discovery_jobs').fetchone()[0])
print('dispatched_records:', cur.execute('SELECT COUNT(*) FROM dispatched_records').fetchone()[0])
print('draft_records:', cur.execute('SELECT COUNT(*) FROM draft_records').fetchone()[0])
print('outreach_drafts:', cur.execute('SELECT COUNT(*) FROM outreach_drafts').fetchone()[0])
print('integrity:', cur.execute('PRAGMA integrity_check').fetchall())
print('fk:', cur.execute('PRAGMA foreign_key_check').fetchall())

conn.close()
```

---

## 3. Table Row Counts Baseline Comparison

| Table Name | Phase A.1 Baseline | Phase A.2.4 Baseline | Phase A.2.5 Audit Count | Delta | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `discovered_leads` | 149 | 149 | **149** | 0 | **UNMODIFIED** |
| `discovery_jobs` | 6 | 6 | **6** | 0 | **UNMODIFIED** |
| `dispatched_records` | 0 | 0 | **0** | 0 | **UNMODIFIED** |
| `draft_records` | 342 | 342 | **342** | 0 | **UNMODIFIED** |
| `outreach_drafts` | 2 | 2 | **2** | 0 | **UNMODIFIED** |

---

## 4. SQLite Pragmas Verification

### 4.1 PRAGMA integrity_check
```sql
PRAGMA integrity_check;
```
**Output:** `[('ok',)]`  
**Assessment:** The SQLite b-tree structure, freelists, index pages, and data pointers are completely healthy with zero corruption.

### 4.2 PRAGMA foreign_key_check
```sql
PRAGMA foreign_key_check;
```
**Output:**
```python
[
    ('discovered_leads', 124, 'discovery_jobs', 0),
    ('discovered_leads', 125, 'discovery_jobs', 0)
]
```
**Assessment:** The two orphaned records identified during Phase A.1 (leads 124 and 125 referencing non-existent discovery jobs) remain in place. No migrations or cleanup operations were performed during Phase A.2.5, strictly respecting the read-only audit boundary.

---

## 5. Conclusion

The production database is completely intact and matches the initial state prior to the commencement of Phase A.2.5.

