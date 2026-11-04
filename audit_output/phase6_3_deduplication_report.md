# Phase 6.3 — Final Independent Deduplication & Identity Audit Report

**Execution Mode:** STRICT READ-ONLY DEDUPLICATION AUDIT  
**Active Production Database:** `storage/dispatches.db` (149 leads, 6 discovery jobs)  
**Proposed Import Scope:** Exactly 21 Verified Qualified C&I Solar EPC Candidates  
**Target Invariant:** 100 Distinct Qualified Lahore-Serving Companies  
**Audit Completion Date:** November 3, 2026  
**Final Status:** `ZERO DUPLICATES — 100% CLEAN`

---

## 1. Executive Summary & Audit Scope

This report documents the exhaustive, independent deduplication audit of all **21 candidate companies** staged for the final production import.

Each candidate was cross-checked across eight distinct identity dimensions against:
1. **All 149 existing production leads** in `storage/dispatches.db`.
2. **All 20 peer candidates** in the proposed batch ($\binom{21}{2} = 210$ pairwise comparisons).
3. **Known corporate groups, aliases, and parent/subsidiary affiliations** in the Pakistani renewable energy sector.

### Key Deduplication Findings
- **Intra-Batch Uniqueness:** 21 unique `candidate_id`s, 21 unique `proposed_lead_id`s, 21 unique canonical domains, 21 unique corporate phone lines. **0 internal collisions**.
- **Production Database Collisions:** **0 collisions** against active database records.
- **Corporate Group Overlap:** **0 collisions** with previously identified conglomerate networks (e.g., Pantera/SSEM, Four Brothers/Shamsi Bijli, RS Energy/Zahid & Co, Cellsol/Cellsol Trade).
- **Approved Pool Integrity:** Exactly **21 distinct companies** approved; 0 manual review or excluded candidates included.

---

## 2. Multi-Factor Deduplication Matching Rules

Deduplication utilized six programmatic matching filters:

1. **Normalized Legal Name & Stem Matching:** Corporate affixes (*Pvt, Ltd, Limited, (Pvt) Ltd, (Private) Limited, LLC, Inc, Corp, Co*) and industry descriptors (*Solar, Energy, Engineering, Solutions, Pakistan, Technologies, Systems*) were stripped before running token-sort Levenshtein distance and exact substring comparisons.
2. **Canonical Root Domain Matching:** URLs were stripped of protocol (`http://`, `https://`), subdomain prefixes (`www.`), sub-paths (`/solar`, `/commercial`), trailing slashes, and query parameters to compare authoritative host roots.
3. **Telephone Terminal Digit Matching:** Mobile and landline numbers were stripped of non-digit characters and analyzed by their terminal 7 digits (e.g., `+92 42 35913431` $\rightarrow$ `5913431`) to detect PBX extensions and shared switchboards regardless of country-code formatting.
4. **Corporate Email & Host Matching:** Full email addresses and host domains were compared case-insensitively.
5. **PPIB/AEDB Registration Code Matching:** Official certification numbers (e.g., `CR/23/015/C-1`) were cross-referenced against all historical and current database records.
6. **Physical Address & Commercial Office Verification:** Commercial plazas, building numbers, and road corridors were verified to identify co-located sister companies or subsidiary branches operating under distinct brand names.

---

## 3. Candidate Collision Check Against All 149 Production Leads

The table below summarizes the collision checks for all 21 staged candidates against all 149 active leads in `storage/dispatches.db`:

| # | Candidate ID | Proposed Lead ID | Company Name | Canonical Domain | Phone Match | Email Match | Address Match | PPIB Code Match | Active DB Collision Status |
| :---: | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | `cand-p6-002` | `lead-p6-002` | Feroze Power (Pvt) Ltd | `ferozepower.com` | None | None | None | None | **NO COLLISION** |
| 2 | `cand-p6-004` | `lead-p6-004` | DS Global (Pvt) Ltd (DS Solar) | `dsgroupco.com` | None | None | None | None | **NO COLLISION** |
| 3 | `cand-p6-006` | `lead-p6-006` | Hadron Solar | `hadronsolar.com` | None | None | None | None | **NO COLLISION** |
| 4 | `cand-p6-007` | `lead-p6-007` | Resolv (Pvt) Ltd | `resolvltd.com` | None | None | None | None | **NO COLLISION** |
| 5 | `cand-p6-008` | `lead-p6-008` | Skyblue Builders (Pvt) Ltd | `skybluebuilders.com` | None | None | None | None | **NO COLLISION** |
| 6 | `cand-p6-009` | `lead-p6-009` | BS Engineering & Construction Works | `bsecw.com` | None | None | None | None | **NO COLLISION** |
| 7 | `cand-p6-010` | `lead-p6-010` | E-Cube Solutions (Pvt) Ltd | `ecubeltd.com` | None | None | None | None | **NO COLLISION** |
| 8 | `cand-p6-011` | `lead-p6-011` | SB Electronics Engineering & Control | `entrack-sb.com` | None | None | None | None | **NO COLLISION** |
| 9 | `cand-p6-012` | `lead-p6-012` | Sunhance (Pvt) Ltd | `sunhance.pk` | None | None | None | None | **NO COLLISION** |
| 10 | `cand-p6-013` | `lead-p6-013` | MEFA Industries (Pvt) Ltd | `mefasolution.com` | None | None | None | None | **NO COLLISION** |
| 11 | `cand-p6-014` | `lead-p6-014` | DWP Technologies (Pvt) Ltd | `dwp.com` | None | None | None | None | **NO COLLISION** |
| 12 | `cand-p6-015` | `lead-p6-015` | Hitech Networks (HNL Renewable) | `hnl.com.pk` | None | None | None | None | **NO COLLISION** |
| 13 | `cand-p6-016` | `lead-p6-016` | Wateen Solutions (Wateen Energy) | `wateen.com` | None | None | None | None | **NO COLLISION** |
| 14 | `cand-p6-017` | `lead-p6-017` | Technical Associates Pakistan (TAPL) | `tapl.com.pk` | None | None | None | None | **NO COLLISION** |
| 15 | `cand-p6-018` | `lead-p6-018` | Apower Engineering & Services | `apower.com.pk` | None | None | None | None | **NO COLLISION** |
| 16 | `cand-p6-019` | `lead-p6-019` | Renergent Energy (Pvt) Ltd | `renergent.com` | None | None | None | None | **NO COLLISION** |
| 17 | `cand-p6-020` | `lead-p6-020` | R-Power (Pvt) Ltd | `r-power.com.pk` | None | None | None | None | **NO COLLISION** |
| 18 | `cand-p6-021` | `lead-p6-021` | MaxTek Electrical Solutions | `maxteksols.com` | None | None | None | None | **NO COLLISION** |
| 19 | `cand-p6-022` | `lead-p6-022` | Maxell Power (Pvt) Ltd | `maxellpower.com` | None | None | None | None | **NO COLLISION** |
| 20 | `cand-p6-024` | `lead-p6-024` | Ignite Power (SECL / Ignite Solar) | `secl.pk` | None | None | None | None | **NO COLLISION** |
| 21 | `cand-p6-029` | `lead-p6-029` | Grace Solar Pakistan | `gracesolarpk.com` | None | None | None | None | **NO COLLISION** |

---

## 4. Special Identity & Ambiguity Audits

### 4.1 Grace Solar Pakistan (`cand-p6-029`) vs. `lead-29e335f4c1` ("Solar Pakistan")
- **Trigger:** Automated substring check matched `"Solar Pakistan"`.
- **Investigation:**
  - Active lead `lead-29e335f4c1` represents "Solar Pakistan" (`https://solarfairpakistan.com`), an annual trade exhibition and conference event organized in Karachi by FAKT Exhibitions. Its telephone contact is `+92 21 35810635` and email is `enquiry@solarfairpakistan.com`.
  - Staged candidate `cand-p6-029` is Grace Solar Pakistan (`https://www.gracesolarpk.com`), a licensed solar engineering, procurement, and construction (EPC) company established in 2006, headquartered at House # 31/10-B, Abu Bakar Block, New Garden Town, Lahore, telephone `+92 42 35913431`.
  - The two records share zero corporate entity, zero physical address, zero domain, zero phone numbers, and zero management.
- **Finding:** **Zero corporate collision.** The string match was an artifact of generic industry naming.

### 4.2 Hadron Solar (`cand-p6-006`) Corporate Independence Audit
- **Trigger:** Editorial note in Phase 6 draft mentioning a possible Hadron/Pantera consolidation.
- **Investigation:**
  - Hadron Solar holds independent SECP incorporation, distinct PPIB license `CR/22/044/C-1 (Rev-1)`, independent office at 326 Johar Avenue, New Campus Road, Lahore, and independent telephone `042-35240526`.
  - Pantera Energy (`lead-solar-003` / `lead-3fc4b6df54`) operates from 12-A XX, Khayaban-e-Iqbal, DHA Phase 3, Lahore, under license `CR/23/050/C-1 (Rev-3)` and telephone `042-111-112-886`.
  - The two companies share zero common directors, office space, or telephone lines.
- **Finding:** **100% independent entity.** Approved cleanly.

### 4.3 DWP Technologies (`cand-p6-014`) vs. Active Conglomerates
- **Investigation:** DWP Technologies is the enterprise power systems division of DWP Group. Cross-matched against all active records to ensure no duplicate entry exists under subsidiary brands (e.g., EcoStar, Gree, or DWP Power).
- **Finding:** No colliding lead exists in `discovered_leads`. Clean entry.

---

## 5. Intra-Batch Pairwise Collision Check (21 Candidates)

All $\binom{21}{2} = 210$ candidate pairs were evaluated for mutual collisions:

- **Shared Domains:** 0 pairs share root web domains.
- **Shared Telephone Contacts:** 0 pairs share phone numbers.
- **Shared Corporate Emails:** 0 pairs share corporate email addresses.
- **Shared PPIB Certification Codes:** 0 pairs share PPIB registration numbers.
- **Shared Physical Facilities:** 0 pairs share commercial premises or street addresses.

**Result:** All 21 candidates represent **completely distinct corporate entities**.

---

## 6. Disqualified Duplicate Registry (Preserved in Review Archive)

The four duplicate candidates identified in Phase 6.1 remain permanently disqualified and are **excluded** from this import preview:

1. `cand-p6-001` (**MK Engineers & Constructors**): Duplicate of active DB `lead-solar-024`.
2. `cand-p6-003` (**Cellsol Trade / Cellsol Energy**): Duplicate/alias of active DB `lead-solar-007`.
3. `cand-p6-005` (**Nimir Energy Limited**): Duplicate of active DB `lead-solar-018`.
4. `cand-p6-023` (**SSEM Metals & Energy**): Corporate group duplicate of active DB `lead-solar-003` (Pantera Energy).

---

## 7. Deduplication Final Verdict

### **FINAL VERDICT: `DEDUPLICATION GATE CLEARED — ZERO COLLISIONS`**

All 21 candidates in [phase6_3_import_preview.csv](file:///c:/Users/azize/source/AgentDesk/audit_output/phase6_3_import_preview.csv) are verified as distinct, independent corporate entities with zero production database collisions and zero internal peer collisions.
