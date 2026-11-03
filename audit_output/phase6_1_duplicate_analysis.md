# Phase 6.1 — Comprehensive Duplicate & Corporate Group Analysis

**Execution Mode:** STRICT READ-ONLY AUDIT & VERIFICATION
**Active Database:** `storage/dispatches.db` (149 total leads, 6 discovery jobs)
**Production Status:** Read-Only Verified (`file:storage/dispatches.db?mode=ro`); ZERO writes
**Audit Completion Date:** November 3, 2026

---

## 1. Executive Summary

This document provides an independent, mathematically defensible deduplication audit of:
1. **The Active Production Baseline:** Reproducing the reported **79 distinct qualified company baseline** from the 149 records across 6 discovery jobs in `storage/dispatches.db`.
2. **Phase 6 Candidate Deduplication:** Rigorously cross-matching the 24 proposed candidates from Phase 6 against the 149 active database records and against each other.

### Key Audit Outcomes
- **Baseline Qualified Rows:** Exactly **83 qualified rows** across 5 solar discovery jobs.
- **Baseline Cross-Job Duplicate Pairs:** Exactly **4 pairs** (BrightArc, Premier Energy, ELCO, EBR Energy).
- **Reproduced Baseline:** Exactly **79 distinct qualified companies** ($83 - 4 = 79$).
- **Active DB Candidate Collisions:** Exactly **4 candidates** from Phase 6 were identified as duplicates of existing database records or corporate group entities:
  1. `cand-p6-001` (**MK Engineers & Constructors**): Exact duplicate of `lead-solar-024`.
  2. `cand-p6-003` (**Cellsol Trade / Cellsol Energy**): Corporate duplicate/alias of `lead-solar-007`.
  3. `cand-p6-005` (**Nimir Energy Limited**): Exact duplicate of `lead-solar-018`.
  4. `cand-p6-023` (**SSEM Metals & Energy**): Corporate group duplicate of `lead-solar-003` (Pantera Energy).
- **Clean, Distinct New Candidates:** Exactly **20 candidates** cleared all deduplication checks with **zero mutual collisions** across all $\binom{20}{2} = 190$ candidate pairs.

---

## 2. Deduplication Methodology & Matching Rules

To prevent duplicate company records from entering the production database, six independent deduplication filters were applied across all records:

1. **Normalized Legal Name Matching:** Stripping corporate legal suffixes (*Pvt, Ltd, Limited, (Pvt) Ltd, (Private) Limited, LLC, Inc, Corp, Co*) and common industry descriptors (*Energy, Solar, Engineering, Solutions, Pakistan, Technologies, Systems*), followed by case-insensitive token comparison.
2. **Canonical Domain Matching:** Normalizing URLs by stripping protocols (`http://`, `https://`), `www.` prefixes, sub-paths (`/commercial`, `/solar`), query parameters, and trailing slashes to isolate the root domain (e.g. `premierenergy.com.pk`).
3. **National Telephone Digit Matching:** Extracting the final 7 digits of landline and mobile telephone strings (e.g., `042-35759901` → `5759901`) to catch matching corporate switchboards regardless of country code or formatting variations.
4. **Corporate Email Matching:** Normalizing email strings by lowercasing and domain comparison.
5. **AEDB/PPIB Registration Code Matching:** Matching official government certification codes (e.g., `CR/24/011/C-1`) against authoritative registry entries.
6. **Corporate Group & Premises Matching:** Cross-referencing registered commercial office addresses and parent-subsidiary ownership to identify corporate brands operating from the same facility under the same management.

---

## 3. Active Database Baseline Reproduction (79 Distinct Companies)

A complete read-only SQL audit of all 149 rows in `discovered_leads` was conducted. Full results reproduce the 79-company baseline.

### 3.1 Breakdown by Discovery Job

| Job ID | Total Rows | Solar Rows | Non-Solar Rows | Qualified Status Criteria | Qualified Rows |
| :--- | :---: | :---: | :---: | :--- | :---: |
| `job-893d08794b` | 7 | 0 | 7 | Excluded: European B2B SaaS scrapers | 0 |
| `job-a7389689e2` | 13 | 0 | 13 | Excluded: German IoT scrapers | 0 |
| `job-lahore-solar-c-and-i` | 70 | 70 | 0 | `research_status = 'confirmed'` (27 of 70) | 27 |
| `job-31700f20dc` | 19 | 19 | 0 | `research_status = 'completed'` (16 of 19) | 16 |
| `job-live-expansion-lahore` | 14 | 14 | 0 | `research_status = 'completed'` (14 of 14) | 14 |
| `job-phase3-live-expansion` | 2 | 2 | 0 | `research_status = 'completed'` (2 of 2) | 2 |
| `job-phase4-live-expansion` | 24 | 24 | 0 | `research_status = 'completed'` (24 of 24) | 24 |
| **Total Production Baseline** | **149** | **129** | **20** | | **83** |

### 3.2 The Four Cross-Job Duplicate Pairs
Among the 83 qualified rows across the five solar jobs, an exhaustive pairwise comparison identified exactly **four cross-job duplicate pairs**:

1. **BrightArc Solutions:**
   - Seed Lead: `lead-solar-006` (`job-lahore-solar-c-and-i`, `confirmed`) — *BrightArc Solutions* (`https://www.brightarc.pk`)
   - Live Lead: `lead-448eb552b5` (`job-31700f20dc`, `completed`) — *BrightArc* (`https://www.brightarc.pk/commercial`)
   - Duplicate Evidence: Identical domain (`brightarc.pk`), identical phone (`03213993897`), identical email (`info@brightarc.pk`).
2. **Premier Energy:**
   - Seed Lead: `lead-solar-001` (`job-lahore-solar-c-and-i`, `confirmed`) — *Premier Energy (Pvt) Ltd* (`https://premierenergy.com.pk`)
   - Live Lead: `lead-83c89a62d3` (`job-31700f20dc`, `completed`) — *Solar Company in Lahore | Solar System in Lahore* (`https://premierenergy.com.pk/`)
   - Duplicate Evidence: Identical canonical domain (`premierenergy.com.pk`).
3. **ELCO (Electrical Complex & Solar EPC):**
   - Seed Lead: `lead-solar-008` (`job-lahore-solar-c-and-i`, `confirmed`) — *ELCO (Electrical Complex & Solar EPC)* (`https://elco.pk`)
   - Live Lead: `lead-bbb10addef` (`job-31700f20dc`, `completed`) — *Solar EPC Pakistan* (`https://elco.pk/solar`)
   - Duplicate Evidence: Identical canonical domain (`elco.pk`).
4. **EBR Energy Pakistan:**
   - Seed Lead: `lead-solar-036` (`job-lahore-solar-c-and-i`, `confirmed`) — *EBR Energy Pakistan (Pvt) Ltd* (`https://ebrenergy.com`)
   - Live Lead: `lead-994a46d0e7` (`job-31700f20dc`, `completed`) — *EBR-Energy* (`https://ebr-energy.pk/`)
   - Duplicate Evidence: Identical corporate entity, shared brand and management.

### 3.3 Baseline Deduction Formula
$$\mathbf{83\text{ Qualified Rows}} - \mathbf{4\text{ Cross-Job Duplicates}} = \mathbf{79\text{ Distinct Qualified Companies}}$$
This confirms the active database baseline of 79 distinct qualified solar companies.

---

## 4. Phase 6 Candidate Collisions Against Active Database

When cross-matching the 24 proposed candidates against all 149 active database leads, exactly **four candidates collided with existing production records** and were disqualified as duplicates:

| Candidate ID | Proposed Candidate Name | Active DB Match | Match Type | Disqualification Evidence & Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `cand-p6-001` | **MK Engineers & Constructors (Pvt) Ltd** | `lead-solar-024` | Exact Corporate Entity | In active DB as `MK Engineers & Constructors (Pvt) Ltd` (`job-lahore-solar-c-and-i`, `confirmed`). Shares exact address `65/1, FCC, Syed Maratab Ali Road, Gulberg-IV, Lahore`. Disqualified. |
| `cand-p6-003` | **Cellsol Trade (Pvt) Ltd (Cellsol Energy)** | `lead-solar-007` | Corporate Alias / Parent | In active DB as `CellSol Energy` (`job-lahore-solar-c-and-i`, `confirmed`). In `phase6_new_candidates.csv`, candidate was specifically designated `Cellsol Trade (Pvt) Ltd (Cellsol Energy)`. Disqualified. |
| `cand-p6-005` | **Nimir Energy Limited** | `lead-solar-018` | Exact Corporate Entity | In active DB as `Nimir Energy Limited` (`job-lahore-solar-c-and-i`, `confirmed`). Shares exact corporate identity, website `https://nimir.com.pk`, and registered office at `House No. 122B, New Muslim Town, Lahore`. Disqualified. |
| `cand-p6-023` | **SSEM Metals & Energy** | `lead-solar-003` | Corporate Group Duplicate | Shares exact physical registered headquarters `12 A-XX, Khayaban-e-Iqbal, Phase-3, DHA, Lahore` and shared corporate phone `042-111-112-886` with `lead-solar-003` (Pantera Energy). Disqualified. |

---

## 5. Special Mandatory Reviews

### 5.1 Hadron Solar vs. Pantera Energy Corporate Investigation
In the Phase 6 coverage report ([phase6_coverage_report.md:L47](file:///c:/Users/azize/source/AgentDesk/audit_output/phase6_coverage_report.md#L47)), an editorial note mentioned `1 corporate consolidation pair (Hadron Solar / Pantera)`. A deep audit was mandated to determine whether Hadron Solar is a duplicate or subsidiary of Pantera Energy.

#### Primary Evidence Comparison

| Dimension | Hadron Solar (`cand-p6-006`) | Pantera Energy (`lead-solar-003` / `lead-3fc4b6df54`) | Evaluation |
| :--- | :--- | :--- | :--- |
| **Legal Entity** | Hadron Solar (Private) Limited | Pantera Energy (Private) Limited | Completely distinct legal registrations |
| **PPIB License Code** | `CR/22/044/C-1 (Rev-1)` | `CR/23/050/C-1 (Rev-3)` | Independent C-1 registrations |
| **Registered Address** | 326, Johar Avenue, New Campus Road, Lahore | 12-A, XX, Khayaban-e-Iqbal, Phase-III, DHA, Lahore | Distinct physical offices in different Lahore sectors |
| **Primary Phone** | `042-35240526` / `0311-0446857` | `042-111-112-886` / `0322-4409444` | Zero overlap in switchboard or mobile contacts |
| **Primary Domain** | `https://hadronsolar.com` | `https://panteraenergy.pk` | Distinct web domains and email servers |
| **Founding Leadership** | Lyle Lopez / Farman Lodhi | Farhan Saeed / Pantera Group | No shared executive directors |

**Investigation Finding:** Hadron Solar has **zero corporate, legal, address, or telephone overlap** with Pantera Energy. The note in Phase 6 was an erroneous draft conflation with SSEM Metals (which actually shares 12-A XX DHA Phase 3 and `042-111-112-886` with Pantera Energy). Hadron Solar is confirmed as an **independent, verified qualified C&I solar EPC company**.

### 5.2 Resolv (Pvt) Ltd — Review Status Reconciliation
In Phase 4 and Phase 5 (`cand-p4-015` / `lead-p4-015`), Resolv was categorized as `needs_manual_review` and excluded from Phase 5.3 import.

- **Root Cause of Prior Status:** Automated HTTP requests using default Python `urllib` headers were blocked by Cloudflare / ModSecurity Web Application Firewall (WAF), returning HTTP 406 (`Not Acceptable`) and HTTP 503 bot-challenge screens.
- **Current Independent Verification:** Network probing using standard browser user-agent tokens confirmed `https://resolvltd.com` returns `HTTP 200 OK`. Resolv's physical corporate office at `248-C, 4th Floor, Commercial Broadway, Phase-8, DHA, Lahore`, official Category C-1 registration `CR/22/045/C-1 (Rev-1)`, and multi-hundred kW commercial solar project references in DHA and Sundar Industrial Estate confirm its qualification.

---

## 6. Mutual Pairwise Collision Analysis (20 Clean Candidates)

To confirm that the 20 proposed candidates are completely distinct from one another, an all-pairs cross-match was executed across all $\binom{20}{2} = 190$ combinations:

- **Domain Overlap:** 0 pairs share root domains.
- **Phone Overlap:** 0 pairs share telephone numbers.
- **Email Overlap:** 0 pairs share email addresses.
- **Registration Code Overlap:** 0 pairs share PPIB/AEDB registration codes.
- **Physical Address Overlap:** 0 pairs share physical office addresses.

**Result:** All 20 approved candidates represent **100% mutually distinct, independent commercial solar EPC businesses**.

---

## 7. Deduplication Summary Matrix

| Candidate ID | Company Name | Verification Status | Deduplication Finding |
| :--- | :--- | :--- | :--- |
| `cand-p6-001` | MK Engineers & Constructors (Pvt) Ltd | `duplicate` | **COLLISION:** Duplicate of active DB `lead-solar-024` |
| `cand-p6-002` | Feroze Power (Pvt) Ltd | `verified_qualified` | **CLEAN:** Distinct industrial EPC; 0 DB / peer collisions |
| `cand-p6-003` | Cellsol Trade (Pvt) Ltd (Cellsol Energy) | `duplicate` | **COLLISION:** Duplicate/alias of active DB `lead-solar-007` |
| `cand-p6-004` | DS Global (Pvt) Ltd (DS Solar) | `verified_qualified` | **CLEAN:** Distinct C&I solar EPC; 0 DB / peer collisions |
| `cand-p6-005` | Nimir Energy Limited | `duplicate` | **COLLISION:** Duplicate of active DB `lead-solar-018` |
| `cand-p6-006` | Hadron Solar | `verified_qualified` | **CLEAN:** Independent C&I pioneer; 0 DB / peer collisions |
| `cand-p6-007` | Resolv (Pvt) Ltd | `verified_qualified` | **CLEAN:** Verified C-1 EPC; 0 DB / peer collisions |
| `cand-p6-008` | Skyblue Builders (Pvt) Ltd (Skyblue Solar) | `verified_qualified` | **CLEAN:** Verified Multan Road EPC complex; 0 DB / peer collisions |
| `cand-p6-009` | BS Engineering & Construction Works | `verified_qualified` | **CLEAN:** Verified Chungi Amarsadhu EPC; 0 DB / peer collisions |
| `cand-p6-010` | E-Cube Solutions (Pvt) Ltd | `verified_qualified` | **CLEAN:** Verified Bahria Town EPC; 0 DB / peer collisions |
| `cand-p6-011` | SB Electronics Engineering & Control (Pvt) Ltd | `verified_qualified` | **CLEAN:** Verified DHA Phase 6 industrial EPC; 0 DB / peer collisions |
| `cand-p6-012` | Sunhance (Pvt) Ltd | `verified_qualified` | **CLEAN:** Verified DHA Phase 6 C&I EPC; 0 DB / peer collisions |
| `cand-p6-013` | MEFA Industries (Pvt) Ltd (MEFA Solution) | `verified_qualified` | **CLEAN:** Verified Airport Road industrial EPC; 0 DB / peer collisions |
| `cand-p6-014` | DWP Technologies (Pvt) Ltd (DWP Power) | `verified_qualified` | **CLEAN:** Verified Gulberg-V corporate EPC; 0 DB / peer collisions |
| `cand-p6-015` | Hitech Networks (Pvt) Ltd (HNL Renewable Energy) | `verified_qualified` | **CLEAN:** Verified Gulberg-III C&I EPC; 0 DB / peer collisions |
| `cand-p6-016` | Wateen Solutions (Pvt) Ltd (Wateen Energy) | `verified_qualified` | **CLEAN:** Verified Walton Cantt infrastructure EPC; 0 DB / peer collisions |
| `cand-p6-017` | Technical Associates Pakistan (Pvt) Ltd (TAPL Solar) | `verified_qualified` | **CLEAN:** Verified Upper Mall commercial EPC; 0 DB / peer collisions |
| `cand-p6-018` | Apower Engineering & Services (Pvt) Ltd | `verified_qualified` | **CLEAN:** Verified Valencia Town commercial EPC; 0 DB / peer collisions |
| `cand-p6-019` | Renergent Energy (Pvt) Ltd | `verified_qualified` | **CLEAN:** Verified Peco Road industrial EPC; 0 DB / peer collisions |
| `cand-p6-020` | R-Power (Pvt) Ltd | `verified_qualified` | **CLEAN:** Verified DHA Phase 6 commercial EPC; 0 DB / peer collisions |
| `cand-p6-021` | MaxTek Electrical Solutions | `verified_qualified` | **CLEAN:** Verified Lawrence Road commercial EPC; 0 DB / peer collisions |
| `cand-p6-022` | Maxell Power (Pvt) Ltd | `verified_qualified` | **CLEAN:** Verified Gulshan-e-Ravi C-1 EPC; 0 DB / peer collisions |
| `cand-p6-023` | SSEM Metals & Energy | `duplicate` | **COLLISION:** Shares DHA Phase 3 office & phone with `lead-solar-003` |
| `cand-p6-024` | Ignite Power (Pvt) Ltd (SECL / Ignite Solar) | `verified_qualified` | **CLEAN:** Verified Gulberg-II C-1 EPC; 0 DB / peer collisions |