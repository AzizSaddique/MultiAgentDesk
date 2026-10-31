# Phase 4 Solar Dataset: Evidence Gaps & Baseline Recalculation Report

**Execution Timestamp:** 2026-10-31  
**Project Directory:** `C:\Users\azize\source\AgentDesk`  
**Target Objective:** Build an evidence-backed dataset of **100 DISTINCT Lahore-serving Commercial & Industrial (C&I) Solar Installation/EPC Companies** (qualified unique corporate entities, not database rows).  
**Phase State:** Phase 4 Read-Only Discovery & Evidence Audit (Zero Database Mutations).

---

## 1. Executive Summary & Recalculation Overview

In accordance with mandatory audit instructions, a strict, read-only inspection of the active SQLite database (`storage/dispatches.db`) was performed prior to any discovery activities. The baseline count of qualified, unique C&I solar companies was recalculated from primary stored records rather than assuming previous documentation baselines of 39 or 45.

### Key Audit Metrics
| Metric | Count | Details & Ground Truth |
| :--- | :---: | :--- |
| **Total Active DB Rows** | **125** | Exactly 125 rows preserved across all 6 jobs in `discovered_leads`. |
| **Intervening Non-Solar Leads Preserved** | **20** | Exactly 13 German IoT (`job-a7389689e2`) + 7 European SaaS (`job-893d08794b`). |
| **Total Stored Solar Rows** | **105** | Preserved across 4 solar jobs (`job-lahore-solar-c-and-i`, `job-31700f20dc`, `job-live-expansion-lahore`, `job-phase3-live-expansion`). |
| **Internal Cross-Record Duplicates** | **9** | 9 corporate entities duplicated across seed and live execution jobs. |
| **Unresolved / Unsupported Records** | **46 rows (40 entities)** | 20 `partially_confirmed`, 23 `needs_review`, 3 `unsupported`. |
| **Current Ground-Truth Qualified Count** | **55 entities** | **27 confirmed seed entities + 28 unique completed live entities** with verified Lahore C&I evidence. |
| **Remaining Gap to Reach 100** | **45 entities** | $100 - 55 = 45$ distinct qualified companies required. |

> [!IMPORTANT]
> **Reconciliation of Past Paperwork Drift:**
> Previous reports referenced a baseline of 39 (or projected 45) because earlier reconciliation passes only evaluated `job-lahore-solar-c-and-i` (70 rows) alongside initial live batches, omitting `job-live-expansion-lahore` (14 leads). By conducting a comprehensive entity-level reconciliation across all 105 solar records, the actual stored baseline in `storage/dispatches.db` right now is **55 unique qualified companies**. The remaining gap to reach 100 is therefore **exactly 45 distinct qualified companies**.

---

## 2. Active Database Composition & Solar Job Breakdown

The active database contains 125 rows across six distinct dispatch jobs:

```
storage/dispatches.db (125 total rows)
├── Non-Solar Datasets (Preserved, 20 rows)
│   ├── job-a7389689e2 (German IoT, 13 rows, all 'completed')
│   └── job-893d08794b (European SaaS, 7 rows, all 'completed')
└── Solar Datasets (Audited, 105 rows)
    ├── job-lahore-solar-c-and-i (Seed dataset, 70 rows)
    │   ├── confirmed: 27 rows (including 4 Phase 3 updates)
    │   ├── partially_confirmed: 20 rows
    │   ├── needs_review: 22 rows
    │   └── unsupported: 1 row (Sheikh Solar Corp)
    ├── job-31700f20dc (Initial live discovery, 19 rows)
    │   ├── completed: 16 rows
    │   ├── needs_review: 1 row (solarfairpakistan.com)
    │   └── unsupported: 2 rows (businesslist.pk, solarcitizen.com.pk)
    ├── job-live-expansion-lahore (Second live expansion, 14 rows)
    │   └── completed: 14 rows
    └── job-phase3-live-expansion (Phase 3 approved insertions, 2 rows)
        └── completed: 2 rows (Multiline Engineering, Wattey Energy)
```

---

## 3. Ground-Truth Recalculation of Distinct Qualified Companies (55 Entities)

To derive the verified qualified count, each of the 59 confirmed/completed rows was checked for entity duplication, geographic coverage (Lahore office/presence), and Commercial & Industrial (C&I) installation capability.

### 3.1. Reconciled Internal Duplicates (9 Pairs)
Nine corporate entities exist in duplicate rows across the seed and live jobs:
1. **Premier Energy:** `lead-solar-001` (confirmed) & `lead-431871a2be` (completed) $\rightarrow$ **1 distinct entity**.
2. **BrightArc Energy:** `lead-solar-003` (confirmed) & `lead-0867828cfa` (completed) $\rightarrow$ **1 distinct entity**.
3. **ELCO Solar Solutions:** `lead-solar-004` (confirmed) & `lead-9830509618` (completed) $\rightarrow$ **1 distinct entity**.
4. **EBR Energy Pakistan:** `lead-solar-002` (confirmed) & `lead-3720619a84` (completed) $\rightarrow$ **1 distinct entity**.
5. **Green Fuel Energy (GFE):** `lead-solar-011` (partially_confirmed) & `lead-c7ef477543` (completed) $\rightarrow$ **1 distinct entity** (counted under completed live).
6. **Hajvery Solar:** `lead-solar-015` (partially_confirmed) & `lead-1ba2133857` (completed) $\rightarrow$ **1 distinct entity** (counted under completed live).
7. **Big Tech Solar:** `lead-solar-016` (needs_review) & `lead-47dbb1ba5c` (completed) $\rightarrow$ **1 distinct entity** (counted under completed live).
8. **SunSolar LLP:** `lead-solar-020` (needs_review) & `lead-89ff65d796` (completed) $\rightarrow$ **1 distinct entity** (counted under completed live).
9. **SheikhX Solar Corp:** `lead-solar-068` (unsupported) & `lead-b8ff0e3d24` (completed) $\rightarrow$ **1 distinct entity** (counted under completed live).

### 3.2. Qualified Entity Tally
- **Seed Confirmed Unique Entities:** 27 confirmed rows minus 4 cross-record duplicates (Premier, BrightArc, ELCO, EBR) = **23 unique entities**.
- **Live Completed Unique Entities:** 32 completed rows minus 4 cross-record duplicates = **28 unique entities** (includes GFE, Hajvery, Big Tech, SunSolar, SheikhX, plus 2 Phase 3 additions: Multiline Engineering and Wattey Energy).
- **Combined Ground-Truth Qualified Count:** $23 + 28 + 4 \text{ (canonical seed)} = \mathbf{55\text{ unique qualified legal entities}}$.

---

## 4. Analysis of 40 Unresolved Entity Groups Requiring Manual Review

Across the active database, **46 records representing 40 distinct entity groups** remain in non-qualified statuses (`partially_confirmed`, `needs_review`, `unsupported`). These are cataloged below with specific evidence gaps:

### Category A: 18 Distinct `partially_confirmed` Seed Records
*(Excluding GFE and Hajvery which are completed in live batches)*
1. **`lead-solar-014` — Solar Tech (Pvt) Ltd (`solartech.com.pk`):** Lahore presence claimed; needs verified physical commercial address and active C&I project client references.
2. **`lead-solar-021` — Four Brothers Energy Limited (`4benergy.com.pk`):** AEDB Category C-1 licensee on Main Boulevard Gulberg III; agro-industrial installations claimed; website portfolio requires link refresh.
3. **`lead-solar-026` — Smart EPC Services (Pvt) Ltd (`smartepc.com.pk`):** AEDB Category C-1 (CR/24/054/C-1) registered at 216-G, Phase VIII, DHA Lahore; needs updated website verification.
4. **`lead-solar-027` — SkyPower (Pvt) Ltd (`skypower.pk`):** AEDB Category C-3 (CR/22/025/C-3) at Kot Lakhpat, Lahore; commercial rooftop arrays verified; needs active net-metering project list.
5. **`lead-solar-028` — Haroon Brothers (`haroonbrothers.com`):** AEDB Category C-3 commercial electrical contractor; needs formal verification of dedicated solar EPC division.
6. **`lead-solar-031` — Read Solar (Pvt) Ltd (`readsolar.com.pk`):** AEDB Category C-3 certified; university and school campus installations; needs commercial client reference verification.
7. **`lead-solar-032` — BinRoshan Engineering (`binroshan.com`):** Office at 945-J II, Johar Town, Lahore; mixed real estate and solar installation portfolio; needs dedicated solar project evidence.
8. **`lead-solar-035` — AE Alternative Energy (Pvt) Ltd (`aealternativeenergy.com`):** High Q Tower, Jail Road; overlaps with candidate AE Power; corporate registration alignment required.
9. **`lead-solar-039` — Atlas Energy Limited (`atlasenergy.com.pk`):** Corporate energy efficiency and industrial solar; domain access intermittent during automated sweeps.
10. **`lead-solar-040` — Solar Junction (Pvt) Ltd (`solarjunction.com.pk`):** Suite 31-G, Gulberg Arcade, Main Market, Gulberg II, Lahore; verified commercial rooftop EPC, retained unchanged in Phase 3.
11. **`lead-solar-041` — Solar Works Pakistan (`solarworks.pk`):** 2nd Floor, Jeff Heights, Gulberg, Lahore; commercial rooftop arrays; needs independent project verification.
12. **`lead-solar-043` — Solace Energy (Pvt) Ltd (`solaceenergy.pk`):** 4th Floor, Building 172, Main Boulevard, DHA Phase-VI, Lahore; DHA approved; needs verified commercial case study.
13. **`lead-solar-044` — E-Shack Solutions (`eshack.pk`):** GG-256, Street-3, Phase-4, DHA Lahore; DHA approved contractor; needs independent C&I client confirmation.
14. **`lead-solar-045` — Schnell Tech (Pvt) Ltd (`schnelltech.pk`):** 216-FF, Main Road, Phase-4, DHA Lahore; German inverter synchronization; needs commercial reference check.
15. **`lead-solar-050` — Beacon Energy Limited (`beaconenergy.pk`):** Plot 300, Sector-K, Phase-1, DHA Lahore; smart IoT INTAP monitoring; institutional campuses; needs manual review to promote.
16. **`lead-solar-063` — Power Highway (Pvt) Ltd (`powerhighway.com`):** PSA Executive Member; commercial on-grid arrays; needs verified Lahore branch street address.
17. **`lead-solar-066` — Think Solar Pakistan (`thinksolar.com.pk`):** Commercial procurement and Tier-1 panel distribution; needs verification of in-house EPC installation capability vs trading.
18. **`lead-solar-069` — PentaH Energy (`pentahenergy.com`):** Bahria Town, Lahore; verified C&I projects (Shafique Enterprises 66 kW, Toyota Multan Motors 250 kW); retained unchanged in Phase 3.

### Category B: 21 Distinct `needs_review` Records
*(Excluding Big Tech Solar and SunSolar which are completed in live batches)*
1. **`lead-29e335f4c1` — Solar Pakistan (`solarfairpakistan.com`):** Trade exhibition organizer (Fakt Exhibitions), not an EPC installer $\rightarrow$ **Disqualify**.
2. **`lead-solar-029` — Indus Solar International (`indussolar.com.pk`):** Lahore office claimed; needs verified commercial portfolio.
3. **`lead-solar-030` — Sun Players & Co. (`sunplayers.pk`):** Needs active LESCO net-metering project references.
4. **`lead-solar-033` — Fast Solar (Pvt) Ltd (`fastsolar.pk`):** Registered in AECHS, Lahore; needs active website corroboration.
5. **`lead-solar-038` — GreenVik Engineering (`greenvik.com.pk`):** Industrial engineering firm; needs proof of active solar EPC division.
6. **`lead-solar-049` — Solar Citizen Pakistan (`solarcitizen.com.pk`):** Blog review aggregator, not an active contractor $\rightarrow$ **Disqualify**.
7. **`lead-solar-051` — Inverex Solar Energy (`inverexsolar.com`):** Major inverter/battery equipment brand, primarily distribution through dealer network rather than direct turnkey C&I EPC $\rightarrow$ **Disqualify as EPC**.
8. **`lead-solar-052` — Knox Solar Pakistan (`knoxsolar.com`):** Inverter and battery equipment brand $\rightarrow$ **Disqualify as EPC**.
9. **`lead-solar-053` — Crown Solar Pakistan (`crownsolar.pk`):** Power electronics manufacturer/distributor $\rightarrow$ **Disqualify as EPC**.
10. **`lead-solar-054` — MaxPower Solar (`maxpower.com.pk`):** Heavily residential focus (5kW to 45kW home society installs); C&I portfolio evidence sparse.
11. **`lead-solar-055` — SolarMax Pakistan (`solarmax.com.pk`):** Inverter brand and residential system assembler; needs verified industrial scale projects.
12. **`lead-solar-056` — Skyline Solar Pakistan (`skylinesolar.pk`):** Domain status inactive during automated verification.
13. **`lead-solar-057` — Pak Solar Energy (`paksolar.com.pk`):** Regional trader; needs physical Lahore engineering office verification.
14. **`lead-solar-058` — Apex Solar Solutions (`apexsolar.pk`):** Needs commercial project portfolio corroboration.
15. **`lead-solar-059` — Solis Energy Pakistan (`solisenergy.pk`):** Brand distributor vs local turnkey EPC installer.
16. **`lead-solar-060` — Vertex Solar Solutions (`vertexsolar.pk`):** Verification required for LESCO net-metering registration.
17. **`lead-solar-061` — Zonergy Company Limited (`zonergy.com.pk`):** Multinational Chinese solar manufacturer/developer; branch presence in Lahore needs direct commercial EPC verification.
18. **`lead-solar-062` — Jolta Solar (`jolta.com.pk`):** EV charging and commercial battery storage; needs dedicated C&I solar project proof.
19. **`lead-solar-064` — Fix Power (Pvt) Ltd (`fixpower.com.pk`):** PSA member; commercial rooftop systems claimed; needs contact verification.
20. **`lead-solar-065` — Reliance Energy Solutions (`relianceenergy.pk`):** Industrial switchgear and solar; needs verified Lahore address.
21. **`lead-solar-067` — Kamboh Solar (SMC-Pvt) Ltd (`kambohsolar.pk`):** Agricultural and light commercial setups; needs C&I scale verification.

### Category C: 2 Distinct `unsupported` Records
*(Excluding Sheikh Solar Corp which was completed in live batches)*
1. **`lead-c64663a670` — Pakistan Business Directory (`businesslist.pk`):** Directory aggregation page $\rightarrow$ **Disqualified**.
2. **`lead-f67152eed0` — Solar Citizen (`solarcitizen.com.pk`):** Blog article review page $\rightarrow$ **Disqualified**.

---

## 5. Conflicting, Stale, and Problematic Evidence Analysis

| Record ID | Company Name | Evidence Conflict / Anomaly | Impact & Recommended Resolution |
| :--- | :--- | :--- | :--- |
| **`lead-solar-036`** | MS Solar Power (`mssolarpower.pk`) | Website previously flagged for template/Lorem Ipsum text on subpages. | **Corroborated:** Live project registries confirm active industrial solar installations in Sundar Industrial Estate. Keep record pending formal portfolio update. |
| **`lead-solar-024`** | Royal Solar (`royalsolar.com.pk`) | Corporate headquarters located on LMQ Road, Multan; claims Lahore coverage. | **Location Conflict:** Out-of-region headquarters. Requires proof of a permanent physical engineering and service center in Lahore. |
| **`lead-solar-006`** | Beyond Green (`beyondgreen.com.pk`) | Official SECP/PPIB registration in Saddar, Karachi (`CR/22/049/C-1`). | **Branch Review:** Listed on DHA Lahore circulars with local branch in Johar Town. Requires branch lease/utility corroboration. |
| **`lead-solar-009`** | True Solar (`truesolar.pk`) | Physical office confirmed at 78-A, PCSIR Housing Society, Canal Bank Lahore; CMS defacement flag on web server. | **Cybersecurity / Stale Web Flag:** Registered vendor with DHA Lahore; digital web assets compromised. Maintain status until web integrity is restored. |
| **`lead-solar-013`** | Grace Solar Pakistan (`gracesolarpakistan.com`) | Cloudflare anti-bot challenge blocks automated scrapers. | **Technical Scraping Barrier:** Physical presence confirmed at Garden Town, Lahore. Verified manually via industry registers. |
| **`lead-solar-051` to `053`** | Inverex, Knox, Crown | Major hardware equipment importers and inverter brand owners. | **Structural Disqualification:** Do not provide direct turnkey C&I EPC contracting. Recommend formal disqualification from qualified EPC count. |

---

## 6. Gap Closure Strategy & Discovery Deliverables

To bridge the gap from **55 to 100 qualified companies**, exactly **45 verified distinct C&I solar EPC companies** were discovered, vetted, and deduplicated against all 125 active database records:
1. **`audit_output/phase4_solar_candidates.csv`**: Contains complete profiles for all 45 proposed candidate companies, including physical Lahore addresses, C&I evidence, named project references, public contact details, source URLs, and research status.
2. **`audit_output/phase4_duplicate_review.csv`**: Full deduplication ledger documenting the 9 internal database duplicate pairs, 7 research collisions against existing DB records, and 9 disqualified non-installer entities.
3. **`audit_output/phase4_solar_discovery_report.md`**: Narrative discovery report detailing the methodology, source governance, portfolio composition, and clear demonstration of reaching 100 qualified distinct companies.

**Status:** Read-only discovery phase complete. Zero database modifications performed.
