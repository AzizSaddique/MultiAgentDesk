# AgentDesk — Phase A.1: Lead Verification & Scoring Gap Analysis

**Audit Date:** November 5, 2026  
**Auditor:** Antigravity AI Systems Architecture Team  
**Evaluation Standard:** Rigorous verification against `backend/services/lead_discovery.py`, `backend/providers/playwright_scraper.py`, `backend/models.py`, and database records.

---

## 1. Existing System Verification Capabilities vs. Gaps

The existing system provides an initial rules-based heuristic scoring and verification framework. Below is an audit of capabilities against commercial lead qualification standards.

| Verification Dimension | Existing Support Level | Technical Implementation | Identified Gaps & Deficiencies |
| :--- | :---: | :--- | :--- |
| **Company Identity** | Partial | Scrapes `<title>`, `og:site_name`, and Schema.org `Organization.name`. Normalizes name separators (`\|`, `-`). | Fails on complex websites lacking Schema.org; does not cross-reference government corporate registries (SECP, Companies House, Handelsregister). |
| **Domain Verification** | Partial | Validates HTTP/HTTPS syntax and extracts canonical domain (`netloc`). | Does not check domain age (WHOIS), SSL certificate validity, DNS resolution latency, or parked domain status. |
| **Public Email Verification** | Low / Partial | Regex extraction from `mailto:` links and page text. Evaluates syntax (`@`, `.`, no banned extensions). Status: `publicly_listed`, `syntax_valid`, `invalid`, `not_found`. | **Zero deliverability check.** No DNS MX record check; no SMTP handshake check. Naive regex flags support/info emails as valid without verifying mailbox existence. |
| **Phone Verification** | Low / Partial | Regex extraction from `tel:` links and page text. Filters spreadsheet scientific notation corruption (`9.23E+11`). Requires >=7 digits. | No telephony carrier lookup; no HLR lookup (active vs. disconnected line); no WhatsApp business account detection. |
| **Physical Business Presence** | Low / Keyword | Matches city/area keywords in page text (e.g., "Lahore", "Gulberg", "Sundar Industrial Estate"). | No physical address parsing, postal code validation, or Google Maps Place API verification. |
| **Decision-Maker Identification** | **None** | Default fallback to `"(Not published on page)"` or `"Team"`. | **Zero executive identification.** No LinkedIn profile extraction, corporate leadership page parsing, or executive contact enrichment. |
| **Evidence Quality** | Medium | Tracks populated attributes in `verified_fields` JSON list and retains source page URLs in `source_urls`. | Does not calculate an evidence confidence score; does not detect stale or outdated pages. |
| **Qualification Status** | Low | Categorizes into `research_status` (`completed`, `skipped`, `failed`). | No B2B sales qualification tiers (e.g., MQL, SQL, Tier 1 ICP, Tier 2, Disqualified). |
| **Duplicate Detection** | Medium | Deduplicates by canonical domain and stripped company name within active job; hashes email/subject/body for dispatches. | **No cross-job deduplication at discovery time.** Duplicate leads discovered across different jobs are only blocked during outreach transfer. |
| **Explainable Scoring** | Medium | `calculate_lead_relevance()` generates a 0.10–0.98 score with an explanation string citing matched criteria. | Scoring weights are ad-hoc (e.g. +0.35 for industry, +0.20 for city) and do not evaluate buying signals, budget, tech stack, or decision-makers. |

---

## 2. Deep Dive: Current Relevance Scoring Mechanics

In `backend/services/lead_discovery.py` (`calculate_lead_relevance`, lines 446–558):
```python
score = 0.20 # Base score
# 1. Industry Alignment: +0.35 * confidence (or -0.15 for mismatch)
# 2. Location Alignment: +0.20 for city, +0.10 for country
# 3. Description Depth: +0.15 for >=100 chars, +0.08 for >=35 chars, -0.15 for <35 chars
# 4. Contact Verifiability: +0.12 for public email, +0.08 for phone
# 5. Keyword Matches: up to +0.12 bonus for matching plan keywords
# Clamping: capped between 0.10 and 0.98
```

### Critical Flaws in Current Scoring:
1. **No Technical Need Assessment:** A company with a modern website and a company with an abandoned 2012 HTTP site score identically if both match industry and city keywords.
2. **No Decision-Maker Weighting:** A generic `info@` email receives full contact points (+0.12), despite having a lower sales conversion rate than a verified decision-maker email.
3. **Keyword Stuffing Bias:** Long text with repeated keywords automatically receives the maximum +0.12 keyword bonus and +0.15 description depth bonus, regardless of actual company scale or authority.
4. **No Disqualification Penalties:** Unregistered freelancers or micro-contractors without commercial capacity score as high as 10 MW industrial EPC contractors.

---

## 3. Architecture for Proposed 100-Point Lead Score

To transform AgentDesk into an Agency + SaaS Business OS, the scoring model must evaluate technical need, commercial fit, and decision-maker access.

### Proposed 100-Point Score Allocation

```
+-----------------------------------------------------------------------------------+
|                           PROPOSED 100-POINT LEAD SCORE                           |
|                                                                                   |
|  [25 pts] Business Relevance & ICP Alignment                                      |
|  [25 pts] Technical Need & Digital Modernization Gap                              |
|  [15 pts] Decision-Maker Accessibility & Direct Reach                             |
|  [15 pts] Commercial Buying Signals & Expansion Indicators                        |
|  [10 pts] Multi-Channel Contact Deliverability                                    |
|  [10 pts] Evidence Rigor & Registry Cross-Verification                            |
+-----------------------------------------------------------------------------------+
```

### Detailed Factor Breakdown

#### Dimension 1: Business Relevance & ICP Alignment (25 Points)
- **Primary Industry Fit (10 pts):** Verified commercial/industrial EPC or target enterprise sector (0 pts if divergent).
- **Service Scope & Scale (8 pts):** Evidence of multi-kilowatt/megawatt turnkey projects, industrial clients, or enterprise solutions (0 pts if residential only).
- **Geographic Service Capacity (7 pts):** Verified physical operational headquarters or branch in target territory (0 pts if remote directory listing).

#### Dimension 2: Technical Need & Digital Modernization Gap (25 Points)
- **Website Technology Deficits (10 pts):** Outdated CMS/framework, unminified assets, lack of HTTPS/SSL, or poor mobile responsiveness (signals software/agency need).
- **Automation & Conversion Gaps (8 pts):** Absence of automated quotation calculators, customer portals, or online booking systems (direct agency opportunity).
- **SEO & Performance Bottlenecks (7 pts):** Core Web Vitals failure (LCP > 4.0s, CLS > 0.25), missing Schema.org structured data, missing OpenGraph tags.

#### Dimension 3: Decision-Maker Accessibility (15 Points)
- **Identified Decision-Maker (7 pts):** Named executive discovered (CEO, Managing Director, Head of Engineering, CTO, Procurement Director).
- **Direct Executive Reach (5 pts):** Personal executive email (`first.last@domain.com`) or direct telephone extension discovered (0 pts if only generic `info@`).
- **Professional Social Profile (3 pts):** Verified LinkedIn personal profile or corporate leadership page link.

#### Dimension 4: Commercial Buying Signals (15 Points)
- **Active Expansion / Hiring (6 pts):** Active job postings for technical or sales staff on careers page or LinkedIn.
- **Recent Project / Capital Activity (5 pts):** Press releases or project showcase items added within the last 90 days.
- **Regulatory / Market Mandates (4 pts):** Net-metering license accreditation, authorized EPC certification, or ISO compliance.

#### Dimension 5: Contact Verification & Deliverability (10 Points)
- **Email MX & SMTP Handshake (5 pts):** Valid MX DNS record + SMTP `RCPT TO` handshake verified without bounces (0 pts if unverified or catch-all).
- **Telephony Validation (3 pts):** Valid E.164 country code, carrier-valid routing format, active telephone line (0 pts if corrupted or scientific notation).
- **Physical Address Verifiability (2 pts):** Valid street address verified against postal databases or Google Maps.

#### Dimension 6: Evidence Quality & Grounding (10 Points)
- **Multi-Source Confirmation (5 pts):** Facts confirmed across at least two independent authoritative sources (e.g., website + government registry).
- **Zero Evidence Contradictions (3 pts):** Domain, company name, and phone match consistently across all source pages.
- **Page Freshness & Accessibility (2 pts):** Target pages load cleanly with HTTP 200 within 4.0s and zero bot-detection block screens.

---

## 4. Strict Safety Rule: Zero Points for Missing Evidence

In accordance with strict qualification rules:
- **Missing or unconfirmed evidence must receive 0 points.**
- No default or imputed scores for absent fields.
- Example: If no decision-maker name is discovered, the Decision-Maker dimension scores `0 / 15`.
- A lead with generic `info@` email, no named executive, and no hiring signals will score a maximum of `40 / 100`, accurately categorizing it as **Tier 3 (Held / Disqualified)**.

### Proposed Qualification Tiers
- **Tier 1 (High Priority / Qualified):** `75 – 100 points` -> Ready for personalized outreach.
- **Tier 2 (Moderate / Manual Review Required):** `50 – 74 points` -> Operator enrichment needed.
- **Tier 3 (Disqualified / Archive):** `< 50 points` -> Suppressed from outreach queue.

