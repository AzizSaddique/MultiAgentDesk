# Phase 6.2 — Comprehensive Duplicate & Corporate Group Analysis

**Execution Mode:** STRICT READ-ONLY AUDIT & INDEPENDENT DEDUPLICATION  
**Active Database:** `storage/dispatches.db` (149 total leads, 6 discovery jobs)  
**Production Status:** Read-Only Verified (`file:storage/dispatches.db?mode=ro`); ZERO writes  
**Audit Completion Date:** November 3, 2026  
**Final Verdict:** `TARGET REACHED — READY FOR FINAL IMPORT SAFETY GATE`

---

## 1. Executive Summary

This document details the independent, multi-factor deduplication audit for **Phase 6.2**, confirming:
1. **The Active Database Baseline (79 Distinct Qualified Companies):** Independently reproduced from the 149 database records across 6 discovery jobs in `storage/dispatches.db`.
2. **Phase 6.2 Candidate Deduplication:** Rigorously cross-matching the review queue candidates (`cand-p6-029`, `cand-p6-026`, `cand-p6-025`) against all 149 active database leads and against all 20 Phase 6.1 approved candidates.
3. **Mutual Pairwise Collision Analysis:** Cross-matching the Phase 6.2 candidates against each other to guarantee total corporate independence.

### Key Deduplication Findings
- **Baseline Qualified Rows:** Exactly **83 qualified rows** across 5 solar discovery jobs.
- **Baseline Cross-Job Duplicate Pairs:** Exactly **4 pairs** (BrightArc Solutions, Premier Energy, ELCO, EBR Energy Pakistan).
- **Reproduced Active Baseline:** Exactly **79 distinct qualified companies** ($83 - 4 = 79$).
- **Active Database Collisions for Phase 6.2 Candidates:** Exactly **0 collisions**.
- **Phase 6.1 Collisions for Phase 6.2 Candidates:** Exactly **0 collisions**.
- **Mutual Collisions Among Phase 6.2 Candidates:** Exactly **0 collisions**.
- **Newly Qualified Independent Candidate:** Exactly **1 distinct company (`cand-p6-029` Grace Solar Pakistan)**.
- **Projected Qualified Total:** Exactly **100 distinct qualified companies** ($79 + 20 + 1 = 100$).

---

## 2. Deduplication Methodology & Matching Filters

To prevent duplicate corporate entities or shared management structures from entering the database, six independent deduplication filters were applied across all records:

1. **Normalized Legal Name Comparison:** Stripping corporate legal affixes (*Pvt, Ltd, Limited, (Pvt) Ltd, (Private) Limited, LLC, Inc, Corp, Co*) and generic industry noise tokens (*Solar, Energy, Engineering, Solutions, Pakistan, Technologies, Systems*), followed by token-sort Levenshtein and exact substring analysis.
2. **Canonical Domain Comparison:** Normalizing web addresses by stripping protocols (`http://`, `https://`), `www.` prefixes, paths, query strings, and port numbers to evaluate root domain identities (e.g., `gracesolarpk.com`, `jks-int.com`).
3. **National Telephone Digit Comparison:** Extracting the terminal 7 digits of landline and mobile phone numbers (e.g., `+92 42 35913431` $\rightarrow$ `5913431`) to catch matching corporate switchboards and PBX lines regardless of country code or separator formatting.
4. **Corporate Email Comparison:** Lowercasing and extracting full email strings and host domains (e.g., `gracesolarpk@gmail.com`, `info@gracesolarpk.com`).
5. **PPIB / AEDB Registration Code Comparison:** Exact string matching against official government certification codes (e.g., `CR/23/015/C-1`).
6. **Physical Address & Commercial Facility Verification:** Cross-referencing registered premises, commercial plazas, and parent-subsidiary affiliations to detect shared office spaces or corporate group umbrellas.

---

## 3. Active Database Baseline Reproduction (79 Distinct Companies)

A direct SQL audit of `storage/dispatches.db` was executed via Python using `sqlite3.connect('file:storage/dispatches.db?mode=ro', uri=True)`. Full query results confirm the active baseline composition:

### 3.1 Breakdown by Discovery Job

| Job ID | Total Rows | Solar Rows | Non-Solar Rows | Qualified Status Criteria | Qualified Rows |
| :--- | :---: | :---: | :---: | :--- | :---: |
| `job-893d08794b` | 7 | 0 | 7 | Excluded: European B2B SaaS scrapers (`completed`) | 0 |
| `job-a7389689e2` | 13 | 0 | 13 | Excluded: German IoT scrapers (`completed`) | 0 |
| `job-lahore-solar-c-and-i` | 70 | 70 | 0 | `research_status = 'confirmed'` (27 of 70) | 27 |
| `job-31700f20dc` | 19 | 19 | 0 | `research_status = 'completed'` (16 of 19) | 16 |
| `job-live-expansion-lahore` | 14 | 14 | 0 | `research_status = 'completed'` (14 of 14) | 14 |
| `job-phase3-live-expansion` | 2 | 2 | 0 | `research_status = 'completed'` (2 of 2; historical FK anomaly) | 2 |
| `job-phase4-live-expansion` | 24 | 24 | 0 | `research_status = 'completed'` (24 of 24; Phase 5.3 import) | 24 |
| **Total Production Baseline** | **149** | **129** | **20** | | **83** |

### 3.2 The Four Cross-Job Duplicate Pairs
Among the 83 qualified rows across the five solar jobs, an exhaustive pairwise comparison identified exactly four cross-job duplicate pairs:
1. **BrightArc Solutions:** `lead-solar-006` (`job-lahore-solar-c-and-i`) and `lead-448eb552b5` (`job-31700f20dc`) (shared domain `brightarc.pk`, phone `03213993897`, email `info@brightarc.pk`).
2. **Premier Energy:** `lead-solar-001` (`job-lahore-solar-c-and-i`) and `lead-83c89a62d3` (`job-31700f20dc`) (shared canonical domain `premierenergy.com.pk`).
3. **ELCO:** `lead-solar-008` (`job-lahore-solar-c-and-i`) and `lead-bbb10addef` (`job-31700f20dc`) (shared canonical domain `elco.pk`).
4. **EBR Energy Pakistan:** `lead-solar-036` (`job-lahore-solar-c-and-i`) and `lead-994a46d0e7` (`job-31700f20dc`) (shared corporate group identity, root domain `ebrenergy.com` / `ebr-energy.pk`).

$$\mathbf{\text{Reproduced Qualified Baseline}} = 83\text{ Qualified Rows} - 4\text{ Cross-Job Duplicates} = \mathbf{79\text{ Distinct Companies}}$$

---

## 4. Phase 6.2 Candidate Collisions Check Against Active Database

Each of the three review queue candidates was cross-checked against all 149 database records across name, domain, phone, email, and registration code.

### 4.1 Candidate `cand-p6-029` (Grace Solar Pakistan) vs. Active DB
- **Normalized Legal Name:** `Grace Solar Pakistan` / `Grace Solar` / `Grace Energy`.
- **Domain:** `gracesolarpk.com` (prior probe: `gracesolar.pk`).
- **Phones:** `042-35913431`, `042-35884175-77`, `0321-4083040`, `0320-8444888`.
- **Emails:** `info@gracesolarpk.com`, `sales@gracesolarpk.com`, `gracesolarpk@gmail.com`.
- **Address:** `31/10-B, Abu Bakar Block, New Garden Town, Lahore`.
- **PPIB Code:** `CR/23/015/C-1 (Rev-2)`.

#### Special Investigation: Substring Match with `lead-29e335f4c1`
During automated matching, candidate `cand-p6-029` triggered an automated string match against active database lead `lead-29e335f4c1` due to the generic substring `"Solar Pakistan"`. A detailed manual investigation of `lead-29e335f4c1` was conducted:

| Dimension | `cand-p6-029` (Grace Solar Pakistan) | `lead-29e335f4c1` (Active DB Lead) | Collision Analysis |
| :--- | :--- | :--- | :--- |
| **Record Name** | Grace Solar Pakistan | Solar Pakistan | Coincidental substring ("Solar Pakistan") |
| **Business Scope** | Turnkey Commercial & Industrial Solar EPC | Annual Solar Energy & Renewable Expo / B2B Trade Exhibition | Completely different industries (EPC vs. Event Organizer) |
| **Official Website** | `https://www.gracesolarpk.com` | `https://solarfairpakistan.com/` | Distinct domains and server infrastructures |
| **Corporate Email** | `info@gracesolarpk.com` | `enquiry@solarfairpakistan.com` | Completely distinct email hosts |
| **Corporate Phone** | `+92 42 35913431` (Lahore landline) | `+92 21 35810635-39` (Karachi landline) | Different cities / area codes |
| **City & Address** | New Garden Town, Lahore | Karachi Expo Centre / PECHS Karachi | No physical overlap |

**Conclusion:** `lead-29e335f4c1` is the B2B trade exhibition "Solar Fair Pakistan" based in Karachi. There is **zero corporate, domain, telephone, physical, or leadership overlap** with Grace Solar Pakistan. Candidate `cand-p6-029` is confirmed as **100% clean with zero database collisions**.

### 4.2 Candidate `cand-p6-026` (JKS (Pvt) Ltd) vs. Active DB
- **Normalized Legal Name:** `JKS (Private) Limited` / `JKS Solar`.
- **Domain:** `jks-int.com` / `www.jks-int.com`.
- **Phones:** `042-35230701-3`, `0321-7280088`.
- **Emails:** `info@jks-int.com`, `ali@jks-int.com`.
- **Address:** `Office No. 278, Block-D, Phase 1, OPF Society, Raiwind Road, Lahore`.
- **PPIB Code:** `CR/24/023/C-1 (Rev-2)`.
- **Collision Finding:** **0 collisions** in active DB across all 149 records.

### 4.3 Candidate `cand-p6-025` (Green Volts Energy (Pvt) Ltd) vs. Active DB
- **Normalized Legal Name:** `Green Volts Energy (Private) Limited` / `Green Volts Group`.
- **Domain:** `greenvolts.com.pk`.
- **Phones:** `042-37175680`, `0321-8088890`.
- **Emails:** `info@greenvolts.com.pk`, `juniad.arshad@greenvolts.com.pk`.
- **Address:** `Plaza 14CCA, Phase 8 (Ex-Park View), DHA, Lahore`.
- **PPIB Code:** `CR/21/022/C-1 (Rev-1)`.
- **Collision Finding:** **0 collisions** in active DB across all 149 records.

---

## 5. Phase 6.2 Candidate Collisions Check Against 20 Phase 6.1 Candidates

Each Phase 6.2 candidate was cross-checked against all 20 verified candidates approved in Phase 6.1 (`cand-p6-002` through `cand-p6-024` in `audit_output/phase6_1_import_preview.csv`):

| Phase 6.2 Candidate | Tested Attributes | Collisions with Phase 6.1 Staging Pool | Deduplication Result |
| :--- | :--- | :---: | :--- |
| **`cand-p6-029` (Grace Solar Pakistan)** | Name, `gracesolarpk.com`, `042-35913431`, `CR/23/015/C-1`, Garden Town office | **0** | **CLEAN:** 100% distinct from all 20 Phase 6.1 candidates |
| **`cand-p6-026` (JKS (Pvt) Ltd)** | Name, `jks-int.com`, `042-35230701`, `CR/24/023/C-1`, OPF Society office | **0** | **CLEAN:** 100% distinct from all 20 Phase 6.1 candidates |
| **`cand-p6-025` (Green Volts Energy)** | Name, `greenvolts.com.pk`, `042-37175680`, `CR/21/022/C-1`, DHA Phase 8 office | **0** | **CLEAN:** 100% distinct from all 20 Phase 6.1 candidates |

---

## 6. Mutual Pairwise Collision Analysis (Phase 6.2 Candidates)

An all-pairs comparison between the three Phase 6.2 candidates confirmed zero overlap:

1. **`cand-p6-029` (Grace Solar) vs. `cand-p6-026` (JKS):**
   - Distinct legal entities (Grace Solar vs. JKS / UCC Group).
   - Distinct canonical domains (`gracesolarpk.com` vs. `jks-int.com`).
   - Distinct phone lines (`042-35913431` vs. `042-35230701`).
   - Distinct physical premises (New Garden Town vs. OPF Society Raiwind Road).
   - Distinct PPIB codes (`CR/23/015/C-1` vs. `CR/24/023/C-1`).
2. **`cand-p6-029` (Grace Solar) vs. `cand-p6-025` (Green Volts Energy):**
   - Distinct legal entities (Grace Solar vs. Green Volts Energy).
   - Distinct canonical domains (`gracesolarpk.com` vs. `greenvolts.com.pk`).
   - Distinct phone lines (`042-35913431` vs. `042-37175680`).
   - Distinct physical premises (New Garden Town vs. DHA Phase 8).
   - Distinct PPIB codes (`CR/23/015/C-1` vs. `CR/21/022/C-1`).
3. **`cand-p6-026` (JKS) vs. `cand-p6-025` (Green Volts Energy):**
   - Distinct legal entities (JKS vs. Green Volts Energy).
   - Distinct canonical domains (`jks-int.com` vs. `greenvolts.com.pk`).
   - Distinct phone lines (`042-35230701` vs. `042-37175680`).
   - Distinct physical premises (OPF Society Raiwind Road vs. DHA Phase 8).
   - Distinct PPIB codes (`CR/24/023/C-1` vs. `CR/21/022/C-1`).

---

## 7. Deduplication Summary Matrix

| Candidate ID | Proposed Company Name | Verification Status | Deduplication Finding | Staging Action |
| :--- | :--- | :---: | :--- | :--- |
| **`cand-p6-029`** | **Grace Solar Pakistan** | **`verified_qualified`** | **CLEAN:** 0 DB collisions, 0 Phase 6.1 collisions, 0 peer collisions | **Approve for Staging (Milestone 100/100 Reached)** |
| `cand-p6-026` | JKS (Pvt) Ltd (JKS Solar) | `manual_review` | **CLEAN:** 0 DB collisions, 0 Phase 6.1 collisions, 0 peer collisions | Retain in Review Queue as Secondary Backup |
| `cand-p6-025` | Green Volts Energy (Pvt) Ltd | `manual_review` | **CLEAN:** 0 DB collisions, 0 Phase 6.1 collisions, 0 peer collisions | Retain in Review Queue Pending Web Server Recovery |

### Deduplication Final Verdict
**ZERO DUPLICATES INTRODUCED.** Candidate `cand-p6-029` (Grace Solar Pakistan) represents a 100% distinct, independent Commercial & Industrial Solar EPC contractor operating in Lahore, bringing the total projected count of distinct qualified solar companies to exactly **100**.
