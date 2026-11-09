# Phase A.2.6 — Database Integrity Report

**Target Database:** `storage/dispatches.db`  
**Audit Phase:** A.2.6 — Windows Host-Level Egress Enforcement  
**Audit Date:** 2026-11-09  
**Auditor:** Independent Adversarial Security Agent  

---

## 1. Executive Summary

In adherence to the strict audit boundaries for Phase A.2.6, all testing, verification, and empirical probing were performed without altering the production SQLite database `storage/dispatches.db`. 

All database operations during the audit accessed the database file strictly using SQLite's read-only URI mode (`file:storage/dispatches.db?mode=ro`).

**Integrity Verification:**
- Zero database writes, schema migrations, or data alterations were executed.
- Row counts in all tables match the established Phase A.1 baseline exactly.
- `PRAGMA integrity_check` returned `ok`.
- The two baseline foreign key violations (leads 124 and 125 referencing non-existent discovery jobs) remain unaltered.
- Working tree is clean on Git `main`.

---

## 2. Read-Only Query Verification Script

The following Python script was executed to query the database state in read-only mode:

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

| Table Name | Phase A.1 Baseline | Phase A.2.5 Baseline | Phase A.2.6 Audit Count | Delta | Status |
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
**Assessment:** The SQLite database file structure, indexes, and B-trees are healthy with zero corruption.

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
**Assessment:** The two historical orphaned rows (records 124 and 125 referencing non-existent discovery jobs) remain intact. In accordance with safety rules, no automated database fixes or schema migrations were attempted.

---

## 5. Git Working Tree Integrity

`git status` was executed to verify that no tracked production files were modified or staged:

```powershell
git status
```
**Output:**
```
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

---

## 6. Conclusion

The production SQLite database and Git repository remain 100% intact, pristine, and unmodified.

