# Phase 5 Final Integrity Review & Pre-Import Evidence Verification
## Comprehensive Audit of Lahore C&I Solar EPC Candidates, Registries, and Database Baseline

**Report Date:** November 2, 2026  
**Workspace:** `C:\Users\azize\source\AgentDesk`  
**Active Production Database:** `storage/dispatches.db`  
**Database Access Mode:** Strictly Read-Only (`file:storage/dispatches.db?mode=ro`)  
**Point-in-Time Cryptographic Backup:** `storage/dispatches.db.backup_phase3_preexec_20261028_152157` (405,504 bytes, SHA-256 `caafb07cc8f7481156b71c677589aa0c0165e9aa74dce05d7fa5a45ac82500bd`)  
**Deliverable Files:**
- [phase5_final_integrity_review.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase5_final_integrity_review.md)
- [phase5_final_integrity_review.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase5_final_integrity_review.csv)
**Cross-Referenced Source Artifacts:**
- [phase5_preimport_dry_run_report.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase5_preimport_dry_run_report.md)
- [phase4_approved_import_preview.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase4_approved_import_preview.csv)
- [phase4_candidate_evidence_audit.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase4_candidate_evidence_audit.csv)
- [phase4_candidate_evidence_audit.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase4_candidate_evidence_audit.md)
- [phase3_final_reconciliation.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase3_final_reconciliation.md)
- [phase3_execution_results.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase3_execution_results.md)

---

## 1. Executive Summary & Safety Invariants

In strict adherence to project safety protocols:
- **Zero Database Mutations:** The production SQLite database `storage/dispatches.db` was accessed exclusively in URI read-only mode (`?mode=ro`). Zero rows have been inserted, updated, or deleted.
- **Zero Backups Restored:** The active database has not been replaced or overwritten.
- **Zero Outreach Dispatched:** No cold outreach drafts were generated; zero emails or messages were transmitted.
- **Integrity First:** No evidence was invented, assumed, or upgraded. Every claim was cross-examined against live server HTTP responses, authoritative government PDF registries, and active database constraints.
- **Critical Finding Disclosed:** An audit of the previous turn's dry-run report ([phase5_preimport_dry_run_report.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase5_preimport_dry_run_report.md)) revealed that **Section 5 of that markdown document contained an illustrative / hallucinated table** featuring synthetic company names (e.g. *Pantera Energy, SkyElectric, Reon Energy, Inverex*) with fabricated registration numbers (*CR/24/001/C-1, CR/24/002/C-1*, etc.). In contrast, the actual import preview file ([phase4_approved_import_preview.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase4_approved_import_preview.csv)) and audit ledger ([phase4_candidate_evidence_audit.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase4_candidate_evidence_audit.csv)) contain the genuine candidate entities discovered in Phase 4 (e.g. *RS Energy, Purewave Energy, Energy Alternatives, Orient Energy Systems, Greaves Pakistan, Albario Engineering*, etc.). This report audits the true 34 candidates from the actual CSV preview.

```
====================== FINAL INTEGRITY REVIEW SUMMARY ======================
Active Production Database:        storage/dispatches.db (READ-ONLY)
Active Database Rows (Intact):     125 rows (105 solar + 20 preserved non-solar)
Active DB Qualified Solar Co.:     55 distinct companies (Reconciling 4 duplicates)
Phase 3 Reported Baseline:         45 companies (Reconciled: omitted job-live-expansion)
Total Candidates Audited:          45 candidates
  ↳ Tier 1: Approved Qualified:    24 candidates (100% verified, clean websites & offices)
  ↳ Tier 2: Hold for Review:       10 candidates (Miscited codes, 404 subpaths, WAF, non-solar core)
  ↳ Tier 3: Excluded / Deferred:   11 candidates (8 DNS/offline failures + 3 active DB collisions)
Authoritative PPIB PDFs Audited:   List of Certified Installer C-1 & C-3 (25-10-2024)
  ↳ Accreditations Confirmed:      15 candidates in preview + 7 in held candidates
  ↳ Miscited Codes Identified:     2 candidates (Renergent Energy, Enabling Solutions)
Current Execution State:           STOPPED — Awaiting Explicit Operator Instructions
============================================================================
```

---

## 2. Forensic Reconciliation: Markdown Table vs. CSV Import Preview

A primary task of this review was resolving the discrepancy identified in the Phase 5 dry-run report.

### 2.1 The Hallucinated Section 5 Table in `phase5_preimport_dry_run_report.md`
In the previous report's Section 5, a markdown table presented candidate companies such as:
- `lead-p4-001` labeled as *Pantera Energy (Pvt) Ltd* claiming `CR/24/001/C-1`
- `lead-p4-002` labeled as *SkyElectric (Pvt) Ltd* claiming `CR/24/002/C-1`
- `lead-p4-003` labeled as *Reon Energy Limited* claiming `CR/24/003/C-1`
- Sequential template certification numbers: `CR/24/001/C-1` through `CR/24/045/C-1`

### 2.2 The Ground-Truth CSV Data in `phase4_approved_import_preview.csv`
Inspection of the actual underlying data file ([phase4_approved_import_preview.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase4_approved_import_preview.csv)) and candidate audit ledger ([phase4_candidate_evidence_audit.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase4_candidate_evidence_audit.csv)) proves that the actual data records are genuine Pakistani commercial solar businesses:
- `lead-p4-001`: **RS Energy** (`rsenergy.com.pk`), New Garden Town, Lahore
- `lead-p4-002`: **Purewave Energy** (`purewave.pk`), Johar Town, Lahore
- `lead-p4-003`: **Energy Alternatives** (`energyalternatives.com.pk`), Main Multan Road, Lahore
- `lead-p4-010`: **Orient Energy Systems** (`orient-power.com`), Defence Road / Raiwind Road, Lahore
- `lead-p4-011`: **Greaves Pakistan** (`greavesenergy.com`), Sunder Das Road, Lahore

> [!WARNING]
> **Audit Finding:** The markdown table in Section 5 of [phase5_preimport_dry_run_report.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase5_preimport_dry_run_report.md) was an AI-hallucinated presentation block that failed to reflect the actual CSV rows. **The production database was never touched, and the CSV file remains the authoritative candidate payload.**

---

## 3. Authoritative PPIB / AEDB Registry Verification

To satisfy Task 4, the official government registries were directly retrieved from the Private Power & Infrastructure Board (PPIB) web portal:
1. `https://www.ppib.gov.pk/installers/List%20of%20Certified%20Installer%20C-1%20(25-10-2024).pdf` (51,169 characters)
2. `https://www.ppib.gov.pk/installers/List%20of%20Certified%20Installer%20C-3%20(25-10-2024).pdf` (61,115 characters)

Every single candidate claim was audited directly against the official PDF text.

### 3.1 Authenticated PPIB Certifications (Authoritative Corroboration)

| Candidate ID | Company Name | Registry Status | Official Registration Code | Official Registered Address in PPIB Register |
|:---|:---|:---:|:---:|:---|
| `cand-p4-008` | Direct Energy (Private) Limited | Category C-1 | `CR/24/020/C-1 (Rev-3)` | 25B, D1, Ghalib Road, Gulberg III, Lahore |
| `cand-p4-010` | Orient Energy Systems (Private) Limited | Category C-1 | `CR/24/039/C-1 (Rev-1)` | 1 Km Defence Road, Off Raiwind Road, Ali Akbar Road, Lahore |
| `cand-p4-011` | Greaves Pakistan (Private) Limited | Category C-1 | `CR/22/105/C-1` | 3, Sunder Das Road, Lahore |
| `cand-p4-012` | Albario Engineering (Private) Limited | Category C-1 | `CR/21/024/C-1` | 91-C, Model Town / Defence Road, Lahore |
| `cand-p4-013` | Elite Engineering (Private) Limited | Category C-1 | `CR/22/031/C-1 (Rev-1)` | 113-L1 Valencia Town / 23 KM Raiwind Road, Lahore |
| `cand-p4-014` | Siddiq Renewable Energy (Private) Limited | Category C-1 | `CR/22/122/C-1` | 47, Grand Trunk Road, Hide Market, Lahore |
| `cand-p4-015` | Resolv (Private) Limited | Category C-1 | `CR/22/045/C-1 (Rev-1)` | 248-C, 4th Floor, Commercial Broadway, Phase-8, DHA, Lahore |
| `cand-p4-016` | HiSEL Power Pakistan (Private) Limited | Category C-1 | `CR/21/004/C-1` | 94 Tipu Block / 128-C Garden Block, New Garden Town, Lahore |
| `cand-p4-019` | I4 Junction (Private) Limited | Category C-1 | `CR/24/058/C-1 (Rev-3)` | 52-D, Commercial Area, Near Zaitoon Office, New Lahore City, Lahore |
| `cand-p4-030` | Aerospace Baykee Pakistan (Private) Limited | Category C-1 | `CR/23/014/C-1 (Rev-2)` | 10-R, Al-Haseeb Industrial Estate, Defence Road, Kacha, Lahore |
| `cand-p4-032` | Buraq Energy Solutions | Category C-3 | `CR/22/014/C-3 (Rev-2)` | House No. 39, GS-II Ext, Larech Colony, Garhi Shahu, Lahore |
| `cand-p4-038` | The Imperial Electric Company (Private) Limited | Category C-1 | `CR/24/173/C-1` | National Tower, 28 Egerton Road, Lahore |
| `cand-p4-042` | Enabling Solutions (SMC-Private) Limited | Category C-1 | `CR/24/078/C-1 (Rev-2)` | Office No. 4, 2nd Floor, Pakland City Center, I-8 Markaz, Islamabad |
| `cand-p4-043` | Zeus Energy (Private) Limited | Category C-1 | `CR/22/041/C-1` | Regional Office Lahore / Head Office Islamabad |
| `cand-p4-044` | Allied Engineering & Services (Private) Limited | Category C-1 | `CR/23/037/C-1 (Rev-1)` | 16 KM, Multan Road, Lahore (Head Office: Karachi) |
| `cand-p4-045` | Supernet Limited | Category C-1 | `CR/22/038/C-1 (Rev-1)` | 2nd Floor, Garden Heights, New Garden Town, Lahore (Head Office: Islamabad) |

*(Note on Held Candidates: PPIB official registrations were also independently verified for held candidates `Dynamic Green` [CR/24/060/C-1], `Mehver Tech` [CR/22/061/C-1], `Saver-Solar` [CR/24/233/C-3], `Haruto Eng` [CR/24/234/C-3], `Green Craft` [CR/24/186/C-3], `Noorsons` [CR/24/187/C-3], `MA Solar` [CR/24/229/C-3], and `Alpha Renewables` [CR/24/043/C-1]).*

### 3.2 Miscited PPIB Registration Codes Discovered
1. **`cand-p4-031` (Renergent Energy (Pvt) Ltd):**
   - *Preview Claim:* `CR/24/007/C-3`
   - *Official PPIB C-3 Record:* **`CR/23/051/C-3 (Rev-1)`** (Entry #47, valid until 30-06-2024/extended, registered at 22-C, GECHS Phase-III, Peco Road, Lahore). The claim code was miscited in the discovery phase.
2. **`cand-p4-042` (Enabling Solutions (SMC-Pvt) Ltd):**
   - *Preview Claim:* `CR/22/032/C-1`
   - *Official PPIB C-1 Record:* **`CR/24/078/C-1 (Rev-2)`** (Entry #78, valid until 08-06-2025). The claim code was miscited.

---

## 4. Independent Live Website & Evidence URL Validation

Every URL in `source_urls` and `website` across all 34 preview candidates was tested via live HTTP/HTTPS requests.

### 4.1 Unreachable Domains & WAF Challenges
- **`lead-p4-006` (Zynergy Solutions):** `https://zynergysolutions.com` returns HTTP 301 redirecting to `https://www.zynergysolutions.com/` (HTTP 200 OK). The bare domain caused connection drops on naive scrapers, but the canonical site is operational with active C&I solar portfolio.
- **`lead-p4-015` (RESOLV (Pvt) Ltd):** `https://resolvltd.com` returns HTTP 406 / HTTP 503 (`Not Acceptable!`), caused by Cloudflare / ModSecurity bot-protection blocking automated requests lacking interactive browser tokens.
- **`lead-p4-021` (INXOL Energy):** `https://inxolenergy.com` requires TLS modern cipher negotiation; successfully returns HTTP 200 OK with curl.
- **`lead-p4-044` (Allied Engineering & Services):** `https://aesl.com.pk` actively blocks Python urllib with immediate TCP reset; verified HTTP 200 OK with curl and browser headers.

### 4.2 Subpath 404 Deep Links (URL Inaccuracies)
- **`lead-p4-001` (RS Energy):** `https://rsenergy.com.pk/projects/` returns HTTP 404. Live homepage inspection reveals the actual page is **`https://rsenergy.com.pk/projects.php`** (HTTP 200 OK).
- **`lead-p4-004` (MB Solar Energy):** `https://mbsolar.pk/commercial-solar/` returns HTTP 404. The root domain is active and advertises industrial net-metering on the homepage slider.
- **`lead-p4-039` (Industrial Engineering & Chemicals):** `https://iecpakistan.com/solar-solutions/` returns HTTP 404. Live inspection reveals the actual page is **`https://iecpakistan.com/solar-energy/`** (HTTP 200 OK).

### 4.3 Primary Core Business Ambiguities
- **`lead-p4-027` (Isra Innovative Technologies):** Live website title is *`Israintech – CCTV Surveillance, Eye AI`*. The company is predominantly an IT/CCTV security camera vendor that lists solar as an auxiliary product.
- **`lead-p4-028` (Power Zone Engineering & Services):** Live website title is *`Diesel Generators in Pakistan - Affordable Power Solutions`*. The company is predominantly a diesel generator supplier with a secondary solar division.

### 4.4 Non-Lahore Corporate Headquarters
- **`lead-p4-042` (Enabling Solutions) & `lead-p4-043` (Zeus Energy):** Both companies are headquartered in **Islamabad** (I-8 Markaz and Blue Area). Their website titles and PPIB registrations list Islamabad. While they serve Punjab, their Lahore operational premises are listed generically as "Regional Operations Office, Lahore" without verifiable physical street addresses.
- **`lead-p4-045` (Supernet Limited):** Headquartered in Islamabad (Fazal-e-Haq Road); operates a verified regional branch at Garden Heights, New Garden Town, Lahore.

---

## 5. Recalculation & Reconciliation of Qualified Company Counts

### 5.1 Active Database Baseline Breakdown (125 Total Rows)
Querying `storage/dispatches.db` directly in read-only mode confirms:
- `job-lahore-solar-c-and-i`: 70 rows (`is_live = 0`, seed solar leads)
  - `confirmed`: 27 rows
  - `needs_review`: 22 rows
  - `partially_confirmed`: 20 rows
  - `unsupported`: 1 row
- `job-31700f20dc`: 19 rows (`is_live = 1`, live solar leads)
  - `completed`: 16 rows
  - `needs_review`: 1 row
  - `unsupported`: 2 rows
- `job-live-expansion-lahore`: 14 rows (`is_live = 1`, live solar leads)
  - `completed`: 14 rows
- `job-phase3-live-expansion`: 2 rows (`is_live = 1`, Multiline & Wattey)
  - `completed`: 2 rows
- `job-a7389689e2`: 13 rows (`is_live = 0`, German IoT leads — preserved)
- `job-893d08794b`: 7 rows (`is_live = 0`, European B2B SaaS leads — preserved)

Total DB Rows: $70 + 19 + 14 + 2 + 13 + 7 = \mathbf{125\text{ rows}}$.  
Total Solar Leads: $70 + 19 + 14 + 2 = \mathbf{105\text{ solar leads}}$.  
Total Preserved Non-Solar Leads: $13 + 7 = \mathbf{20\text{ non-solar leads}}$.

### 5.2 Ground-Truth Distinct Qualified Solar Companies (Active DB)
A solar company is qualified in the database if its `research_status` is either `'confirmed'` (seed leads) or `'completed'` (live leads):
- Seed `confirmed`: **27 rows**
- Live `completed`: **32 rows** ($16 + 14 + 2$)
- Total qualified solar rows: $27 + 32 = \mathbf{59\text{ rows}}$

#### Cross-Job Deduplication Among the 59 Qualified Rows:
Exhaustive pairwise matching across normalized names, canonical domains, phone numbers, and emails identifies exactly **4 duplicate pairs** between seed and live records:
1. `Premier Energy (Pvt) Ltd`: `lead-solar-001` (seed `confirmed`) $\leftrightarrow$ `lead-83c89a62d3` (live `completed`)
2. `BrightArc Solutions`: `lead-solar-006` (seed `confirmed`) $\leftrightarrow$ `lead-448eb552b5` (live `completed`)
3. `ELCO (Electrical Complex & Solar EPC)`: `lead-solar-008` (seed `confirmed`) $\leftrightarrow$ `lead-bbb10addef` (live `completed`)
4. `EBR Energy Pakistan (Pvt) Ltd`: `lead-solar-036` (seed `confirmed`) $\leftrightarrow$ `lead-994a46d0e7` (live `completed`)

Every other record among the 59 qualified rows is a unique company. Therefore:
$$\mathbf{59 \text{ qualified rows}} - \mathbf{4 \text{ duplicate rows}} = \mathbf{55 \text{ distinct qualified companies currently in active DB}}$$

### 5.3 Reconciliation with Phase 3 Baseline (45 Companies)
In [phase3_final_reconciliation.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase3_final_reconciliation.md), Phase 3 reported a post-execution total of **45 qualified companies**.  
**Why the discrepancy exists:**
1. Phase 3 began from an initial baseline of 39 qualified companies ($23\text{ seed} + 16\text{ live in job-31700f20dc}$).
2. Phase 3 executed 4 seed upgrades ($23 \to 27$) and inserted 2 new live leads (Multiline & Wattey, $16 \to 18$). $27 + 18 = 45$.
3. Phase 3 **completely omitted** the 14 completed leads residing in `job-live-expansion-lahore` (`lead-live-6genergy` through `lead-live-zorays`) from their baseline calculation!
4. When those 14 non-duplicate completed leads are accounted for alongside the 4 cross-job duplicates:
   $$45 \text{ (Phase 3 Reported Total)} + 14 \text{ (job-live-expansion-lahore)} - 4 \text{ (cross-job duplicates)} = \mathbf{55 \text{ true distinct qualified companies}}.$$

---

## 6. Three-Tier Candidate Classification & Final Recommendations

All 45 candidates audited across Phase 4 and Phase 5 have been classified in [phase5_final_integrity_review.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase5_final_integrity_review.csv):

### Tier 1: Approved Qualified Candidates (24 Records)
*100% verified physical Lahore premises, active operational websites, verified commercial solar capabilities, 0 active database collisions, 0 registry code discrepancies.*

1. `cand-p4-002` / `lead-p4-002`: **Purewave Energy** (`purewave.pk`) — Johar Town, Lahore
2. `cand-p4-003` / `lead-p4-003`: **Energy Alternatives** (`energyalternatives.com.pk`) — Main Multan Road, Lahore
3. `cand-p4-008` / `lead-p4-008`: **Direct Energy (Pvt) Ltd** (`directenergyltd.com`) — Gulberg III, Lahore; PPIB C-1 (`CR/24/020/C-1`)
4. `cand-p4-010` / `lead-p4-010`: **Orient Energy Systems (Pvt) Ltd** (`orient-power.com`) — Defence Road, Lahore; PPIB C-1 (`CR/24/039/C-1`)
5. `cand-p4-011` / `lead-p4-011`: **Greaves Pakistan (Pvt) Ltd** (`greavesenergy.com`) — Sunder Das Road, Lahore; PPIB C-1 (`CR/22/105/C-1`)
6. `cand-p4-012` / `lead-p4-012`: **Albario Engineering (Pvt) Ltd** (`aepl.com.pk`) — Model Town / Defence Road, Lahore; PPIB C-1 (`CR/21/024/C-1`)
7. `cand-p4-013` / `lead-p4-013`: **Elite Engineering (Pvt) Ltd** (`eliteengineering.com.pk`) — Valencia Town / Raiwind Road, Lahore; PPIB C-1 (`CR/22/031/C-1`)
8. `cand-p4-014` / `lead-p4-014`: **Siddiq Renewable Energy (Pvt) Ltd** (`sre.com.pk`) — DHA Phase 8 / GT Road, Lahore; PPIB C-1 (`CR/22/122/C-1`)
9. `cand-p4-016` / `lead-p4-016`: **HiSEL Power Pakistan (Pvt) Ltd** (`hiselpower.pk`) — New Garden Town, Lahore; PPIB C-1 (`CR/21/004/C-1`)
10. `cand-p4-019` / `lead-p4-019`: **I4 Junction (Pvt) Ltd** (`i4junction.com`) — New Lahore City, Lahore; PPIB C-1 (`CR/24/058/C-1`)
11. `cand-p4-020` / `lead-p4-020`: **TransfoLine (Pvt) Ltd** (`transfoline.com.pk`) — Raiwind Road, Lahore
12. `cand-p4-022` / `lead-p4-022`: **GetSolar** (`getsolar.com.pk`) — College Road, Lahore
13. `cand-p4-023` / `lead-p4-023`: **Emergent Engineering Services** (`emergentengg.com`) — Wapda Town, Lahore
14. `cand-p4-024` / `lead-p4-024`: **Fazal Engineering (Sky Solar)** (`fazalengineering.com`) — Faisal Town / Bedian Road, Lahore
15. `cand-p4-025` / `lead-p4-025`: **Skynergy Solutions** (`skynergy.pk`) — Johar Town, Lahore
16. `cand-p4-026` / `lead-p4-026`: **C-Solar** (`c-solar.pk`) — Kot Lakhpat, Lahore
17. `cand-p4-029` / `lead-p4-029`: **Aexon Energy (Pvt) Ltd** (`aexonenergy.com`) — Bund Road, Lahore
18. `cand-p4-030` / `lead-p4-030`: **Aerospace Baykee Pakistan (Pvt) Ltd** (`baykee.pk`) — Defence Road, Kacha, Lahore; PPIB C-1 (`CR/23/014/C-1`)
19. `cand-p4-032` / `lead-p4-032`: **Buraq Energy Solutions** (`buraqsolar.com`) — Garhi Shahu, Lahore; PPIB C-3 (`CR/22/014/C-3`)
20. `cand-p4-038` / `lead-p4-038`: **The Imperial Electric Co. (Pvt) Ltd** (`iec.com.pk`) — Egerton Road, Lahore; PPIB C-1 (`CR/24/173/C-1`)
21. `cand-p4-041` / `lead-p4-041`: **SunGrid Power Solutions** (`sungridpower.pk`) — Gulberg II, Lahore
22. `cand-p4-044` / `lead-p4-044`: **Allied Engineering & Services (Pvt) Ltd** (`aesl.com.pk`) — Multan Road, Lahore; PPIB C-1 (`CR/23/037/C-1`)
23. `cand-p4-006` / `lead-p4-006`: **Zynergy Solutions** (`zynergysolutions.com`) — Airline Boulevard, Lahore (Canonical `www` domain confirmed)
24. `cand-p4-021` / `lead-p4-021`: **INXOL Energy** (`inxolenergy.com`) — Valencia Town, Lahore (Verified live via curl)

---

### Tier 2: Hold for Operator Review / Data Rectification (10 Records)
*Evidentiary discrepancies identified; should be held until data fields are updated or operator grants explicit override.*

1. `cand-p4-001` / `lead-p4-001` (**RS Energy**): Subpath `/projects/` is 404; must update to `https://rsenergy.com.pk/projects.php`.
2. `cand-p4-004` / `lead-p4-004` (**MB Solar Energy**): Subpath `/commercial-solar/` is 404; project portfolio on homepage.
3. `cand-p4-015` / `lead-p4-015` (**RESOLV (Pvt) Ltd**): Website protected by WAF bot-challenge screen (HTTP 406/503), preventing direct automated scraping.
4. `cand-p4-027` / `lead-p4-027` (**Isra Innovative Technologies**): Core business is CCTV & AI surveillance hardware.
5. `cand-p4-028` / `lead-p4-028` (**Power Zone Engineering & Services**): Core business is diesel generators trading and rentals.
6. `cand-p4-031` / `lead-p4-031` (**Renergent Energy (Pvt) Ltd**): Registration code miscited as `CR/24/007/C-3`; must be rectified to official `CR/23/051/C-3 (Rev-1)`.
7. `cand-p4-039` / `lead-p4-039` (**Industrial Engineering & Chemicals**): Subpath `/solar-solutions/` is 404; must update to `https://iecpakistan.com/solar-energy/`.
8. `cand-p4-042` / `lead-p4-042` (**Enabling Solutions**): Headquartered in Islamabad (I-8 Markaz) without verified street address in Lahore; code miscited as `CR/22/032/C-1` (official: `CR/24/078/C-1`).
9. `cand-p4-043` / `lead-p4-043` (**Zeus Energy (Pvt) Ltd**): Headquartered in Islamabad; advertises as "Solar EPC Company in Islamabad" without verified physical Lahore premises.
10. `cand-p4-045` / `lead-p4-045` (**Supernet Limited**): Publicly listed IT/Telecom conglomerate; solar is an auxiliary corporate division.

---

### Tier 3: Excluded / Deferred Candidates (11 Records)
*Previously identified and held during Phase 4 audit.*

1. `cand-p4-005` (**AE Power**): Active DB corporate duplicate of `lead-solar-035`.
2. `cand-p4-007` (**Sultan Energy**): Domain `sultanenergy.com.pk` offline / DNS failed.
3. `cand-p4-009` (**Professional Energy Solutions**): Domain `pespak.com` unresolvable.
4. `cand-p4-017` (**Dynamic Green**): Phone collision with active DB `lead-solar-015`.
5. `cand-p4-018` (**Mehver Technologies**): Domain `mehvertech.com` offline.
6. `cand-p4-033` (**Saver-Solar**): Domain `saversolar.com.pk` offline.
7. `cand-p4-034` (**Haruto Engineering**): Domain `harutosolar.com` offline.
8. `cand-p4-035` (**Green Craft**): Domain `greencraft.pk` offline.
9. `cand-p4-036` (**Noorsons Trading**): Domain `noorsonstrading.com` unconfigured directory index.
10. `cand-p4-037` (**MA Solar Solutions**): Domain `masolarsolutions.pk` offline.
11. `cand-p4-040` (**Alpha Renewables**): Active DB corporate duplicate of `lead-solar-070` (shared PPIB license `CR/24/043/C-1`).

---

## 7. Projected Database Impact Under Verified Scenarios

Depending on operator instructions, the projected metrics will be:

| Metric | Current Active DB Baseline | Scenario A: Import Only Tier 1 (24 Flawless Leads) | Scenario B: Import All 34 Preview Leads (With Field Rectifications) |
|:---|:---:|:---:|:---:|
| **Total Rows in `discovered_leads`** | **125** | **149 (+24)** | **159 (+34)** |
| ↳ *Predefined Seed Solar Leads (`is_live=0`)* | 70 | 70 (Intact) | 70 (Intact) |
| ↳ *Live Solar Leads (`is_live=1`)* | 35 | 59 (+24) | 69 (+34) |
| ↳ *Preserved Non-Solar Leads (`is_live=0`)* | 20 | 20 (Intact) | 20 (Intact) |
| **Total Lahore Solar Scope Rows** | **105** | **129 (+24)** | **139 (+34)** |
| **Distinct Qualified Solar Companies** | **55** | **79 (+24)** | **89 (+34)** |
| **Parent Jobs in `discovery_jobs`** | **5** | **7 (+2)** | **7 (+2)** |

---

## 8. Verification Sign-Off & Execution Stop

- **Review Status:** **INTEGRITY AUDIT COMPLETE.**
- **Generated Artifacts:**
  - [phase5_final_integrity_review.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase5_final_integrity_review.md)
  - [phase5_final_integrity_review.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase5_final_integrity_review.csv)
- **Active Database Status:** `storage/dispatches.db` remains 100% untouched and preserved (exactly 125 active rows).
- **Execution State:** **STOPPED.**

No database records will be modified until explicit operator instructions are received on whether to proceed with **Scenario A (24 clean candidates)** or **Scenario B (34 candidates with rectified URLs/codes)**.
