# Phase 6: Evidentiary Gaps & Quality Deficiencies Report
## Analysis of Active Production Database & New Candidate Discoveries

**Audit Date:** November 2, 2026  
**Workspace:** `C:\Users\azize\source\AgentDesk`  
**Active Production Database:** `storage/dispatches.db` (Queried strictly read-only: `file:storage/dispatches.db?mode=ro`)  
**Production Integrity:** Pristine (149 total rows, 6 discovery jobs intact)  
**Deliverables:**
- [phase6_evidence_gaps.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase6_evidence_gaps.md)
- [phase6_solar_quality_audit.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase6_solar_quality_audit.md)
- [phase6_solar_quality_audit.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase6_solar_quality_audit.csv)
- [phase6_new_candidates.csv](file:///C:/Users/azize/source/AgentDesk/audit_output/phase6_new_candidates.csv)
- [phase6_coverage_report.md](file:///C:/Users/azize/source/AgentDesk/audit_output/phase6_coverage_report.md)

---

## 1. Executive Summary

This report documents all evidentiary gaps, missing attributes, quality deficiencies, and disqualification rationales identified across two distinct datasets:
1. **The Active Production Database (149 Records):** Identifying unconfirmed seed records, rejected live records, contact validation boundaries, and referential integrity anomalies.
2. **Phase 6 Candidate Pool (35 Newly Evaluated Companies):** Providing detailed justifications for the **6 candidates held for manual review** and the **5 candidates permanently excluded**.

---

## 2. Active Database Evidentiary Gaps (149 Records)

### 2.1 Unconfirmed Historical Seed Solar Records (43 Records in `job-lahore-solar-c-and-i`)
In the initial historical seed job `job-lahore-solar-c-and-i` (70 total records), exactly 27 records were validated and marked `confirmed`. The remaining **43 records** remain unconfirmed due to lack of live HTTP verification, ambiguous physical facilities, or residential-only focus:

- **`partially_confirmed` (20 Records):** These entities possess documented business names and claimed Lahore presence, but lack corroborated live HTTP verification, verified C&I project portfolios, or confirmed physical street addresses.
  - Examples: `lead-solar-007` (Ningbo Green Light), `lead-solar-010` (Pak Solar Services), `lead-solar-013` (Solis Solar), `lead-solar-014` (Power Zone Engineering), `lead-solar-017` (PentaH Energy), `lead-solar-021` (Solar Maxx), `lead-solar-022` (Green Point Solar), `lead-solar-024` (SunPower Tech).
- **`needs_review` (22 Records):** These entities exhibit unresolved flags such as conflicting corporate names, uncorroborated Lahore phone numbers, or generic residential installer scopes without commercial net-metering proof.
  - Examples: `lead-solar-018` (Adaptive Technologies), `lead-solar-019` (Green Power Energy), `lead-solar-025` (Inverex Solar), `lead-solar-030` (SkyElectric Residential), `lead-solar-037` (Zonergy Solar), `lead-solar-047` (Beacon Energy).
- **`unsupported` (1 Record):** `lead-solar-068` (Sheikh Solar Corp) was marked unsupported due to defunct web endpoints and lack of verifiable commercial engineering activity.

### 2.2 Unconfirmed Live Discovery Records (3 Records in `job-31700f20dc`)
Within the first live discovery job `job-31700f20dc` (19 total records), 16 records are `completed` and qualified. Exactly 3 records remain unconfirmed:
- `lead-6101c5108b` (Adaptive Technologies / SolarMax): Classified as `needs_review` due to shared corporate identity with distributor SolarMax and lack of standalone commercial EPC portfolio.
- `lead-69f828a58a` (Solis Energy): Classified as `unsupported` (inadequate commercial EPC proof).
- `lead-f67152eed0` (Solar Citizen): Classified as `unsupported` (blog/aggregator directory, not an engineering contractor).

### 2.3 Contact Freshness & Outreach Blackout Directive
- All 149 records have their telephone numbers and emails categorized as `publicly_listed`.
- In strict adherence to the project's **Safety Outreach Blackout**, none of these contact details have been dialed, pinged via SMTP handshake, or utilized for outreach drafts.

### 2.4 Pre-Existing Referential Foreign-Key Gap
- `PRAGMA foreign_key_check;` reports exactly **2 violations**:
  - Row 124 (`lead-p3-multiline-001`, Multiline Engineering Co.)
  - Row 125 (`lead-p3-wattey-001`, Wattey Energy)
- Both rows reference `job_id = 'job-phase3-live-expansion'`, which was never registered in `discovery_jobs` during Phase 3 migration. Per explicit project safety rules, this historical anomaly was left unrepaired.

---

## 3. Phase 6 Candidate Evidentiary Gaps (Held & Excluded Candidates)

During the Phase 6 coverage expansion, 35 new candidate entities from the authoritative PPIB registers were audited. While **24 candidates were fully verified and approved** (`cand-p6-001` through `cand-p6-024`), **11 candidates** exhibited specific evidentiary deficiencies.

### 3.1 Candidates Held for Manual Review (6 Candidates)

The following 6 candidates possess verified official PPIB registrations and verifiable physical Lahore addresses, but exhibited transient web server errors or DNS resolution failures during automated HTTP probing:

| Candidate ID | Company Name | PPIB Registration Code | Verified Physical Address | Evidentiary Gap / Review Flag | Required Operator Action |
|:---|:---|:---|:---|:---|:---|
| `cand-p6-025` | **Green Volts Energy (Pvt) Ltd** | `CR/21/022/C-1 (Rev-1)` | 219-F, Street 1, Phase 8 (Ex-Park View), DHA, Lahore | Official domain `greenvolts.com.pk` returned `HTTP 500 Internal Error` during automated probe. | Manual check of corporate website server recovery before approval. |
| `cand-p6-026` | **JKS (Pvt) Ltd (JKS Solar)** | `CR/24/023/C-1 (Rev-2)` | Office 278, Block-D, OPF Society Phase-1, Raiwind Road, Lahore | Official domain `jks-int.com` returned `HTTP 500 Internal Error` during automated probe. | Manual inspection of web portal or secondary URL. |
| `cand-p6-027` | **Green Industrial Solutions (Pvt) Ltd** | `CR/24/077/C-1 (Rev-2)` | 104-J, Johar Town, Near Expo Center, Lahore | Official domain `greenindsol.com` returned `HTTP 500 Internal Error` during automated probe. | Manual verification of web portal availability. |
| `cand-p6-028` | **Energy Conscious Engineering (Pvt) Ltd (ECE)** | `CR/22/130/C-1` | Office 1114, Al-Hafeez Heights, Ghalib Road, Gulberg-III, Lahore | Official domain `ece.com.pk` returned `HTTP 500 Internal Error` during automated probe. | Manual check of web endpoint and portfolio page. |
| `cand-p6-029` | **Grace Solar Pakistan** | `CR/23/015/C-1 (Rev-2)` | 31/10, Abu Bakar Block, New Garden Town, Lahore | Domain `gracesolar.pk` failed DNS resolution during automated probe. Company operates via corporate Gmail and phone. | Confirm whether company has updated canonical domain or uses secondary landing page. |
| `cand-p6-030` | **STZ Engineers & Consultants** | `CR/24/079/C-1 (Rev-3)` | Suite 2-B, Kiran Plaza, Civic Center, Model Town Ext, Lahore | Domain `stzengineers.com` failed DNS resolution during automated probe. | Confirm active corporate domain or server migration. |

### 3.2 Candidates Excluded from Consideration (5 Candidates)

The following 5 candidates were audited and permanently **excluded** from the qualified C&I solar EPC pool due to fundamental operational or structural misalignments:

1. **`cand-p6-031`: Aliz International**
   - *Domain:* `alizpk.com` (SSL Handshake Failed / HTTP 525)
   - *PPIB Code:* `CR/24/175/C-3`
   - *Address:* Office 39, 1st Floor, Sadiq Plaza, 69 The Mall Road, Lahore
   - *Disqualification Rationale:* Investigation confirmed that Aliz International operates primarily as a commercial indenting and import trading house for electrical hardware and solar components. The company lacks dedicated in-house solar engineering, design, and turnkey EPC installation capabilities.
   - *Verdict:* **EXCLUDED** (Commercial Indenter / Trader).

2. **`cand-p6-032`: Faiz Traders**
   - *Domain:* None listed
   - *PPIB Code:* `CR/23/111/C-3`
   - *Address:* Shop 4, Al-Waris Market, Ratta Road, Rawalpindi / Lahore sub-office
   - *Disqualification Rationale:* Candidate is a retail equipment supplier and hardware merchant headquartered in Rawalpindi without a verified physical engineering facility in Lahore and without documented commercial/industrial net-metered EPC project execution.
   - *Verdict:* **EXCLUDED** (Hardware Retailer / Geographic Mismatch).

3. **`cand-p6-033`: Shamsi Bijli (Pvt) Ltd**
   - *Domain:* `shamsibijli.pk` (DNS Unresolvable)
   - *PPIB Code:* `CR/22/053/C-3`
   - *Address:* 77-D/1, 1st Floor, Lahore Center, Main Boulevard Gulberg, Lahore
   - *Disqualification Rationale:* Corporate entity matching revealed that Shamsi Bijli shares the exact physical office address, telephone number (`042-35782610`), and executive management with Four Brothers Group (Four Brothers Energy). Excluded to prevent corporate group duplication.
   - *Verdict:* **EXCLUDED** (Corporate Group Duplicate / Subsidiary).

4. **`cand-p6-034`: Zahid & Company**
   - *Domain:* `rsenergy.com.pk` (HTTP 200 OK)
   - *PPIB Code:* `CR/24/003/C-1 (Rev-1)`
   - *Address:* 113-D, Sukh Chain, Near Bahria Town, Multan Road, Lahore
   - *Disqualification Rationale:* Corporate entity matching confirmed that Zahid & Company is the legal parent registrant of **RS Energy** (`cand-p4-001`), utilizing the exact same corporate domain (`rsenergy.com.pk`) and primary executive contact details. Excluded to avoid double-counting.
   - *Verdict:* **EXCLUDED** (Parent Entity Duplicate of RS Energy).

5. **`cand-p6-035`: Growatt PK (Pvt) Ltd**
   - *Domain:* `growattpk.com` (HTTP 200 OK)
   - *PPIB Code:* `CR/24/024/C-3 (Rev-3)`
   - *Address:* Office 5, 2nd Floor, Rehmania Mansion, Shahrah-e-Liaquat, Lahore
   - *Disqualification Rationale:* Growatt PK operates as the authorized manufacturer representative, warranty service center, and equipment distributor for Growatt solar inverters in Pakistan. It is not an independent turnkey C&I solar EPC contractor.
   - *Verdict:* **EXCLUDED** (Equipment Manufacturer / Distributor Representative).

---

## 4. Recommended Remediation & Next Steps

1. **Prioritize 24 Fully Verified Candidates:** Proceed with operator review for the **24 verified qualified candidates** (`cand-p6-001` through `cand-p6-024`), which provide more than enough qualified leads (+24) to close the remaining 21-company gap to 100 ($79 + 24 = 103$).
2. **Retain 6 Held Candidates on Watchlist:** Keep `cand-p6-025` through `cand-p6-030` on an administrative watchlist for manual domain/DNS re-checks during subsequent maintenance phases.
3. **Preserve Exclusion Boundaries:** Maintain strict exclusion of equipment traders, retailers, and corporate group duplicates to ensure database purity.
