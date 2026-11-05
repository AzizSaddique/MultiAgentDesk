# AgentDesk — Phase A.1: Existing Agent Capability Matrix

**Audit Date:** November 5, 2026  
**Auditor:** Antigravity AI Systems Architecture Team  
**Evaluation Standard:** Evidence-based inspection against backend controllers, data schemas, test coverage, and execution capabilities.

---

## 1. Multi-Agent Overview

The AgentDesk frontend interface defines four agent slots in `src/App.tsx`. However, backend verification demonstrates that only **Agent 1 (Lead Researcher)** possesses an actual underlying implementation. Agents 2, 3, and 4 are frontend-only placeholders without backend support.

| Slot | Agent Title | Declared Status | Audited Status | Backend Endpoints | Test Coverage | Production Readiness |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **1** | **Lead Researcher** | Active | Functional Prototype | 23 endpoints | 118 tests | **Conditional Prototype (7/10)** |
| **2** | **Competitor Intelligence** | Coming Soon | UI Placeholder | 0 endpoints | 0 tests | **Non-Existent (0/10)** |
| **3** | **Customer Service & FAQ Engine** | Coming Soon | UI Placeholder | 0 endpoints | 0 tests | **Non-Existent (0/10)** |
| **4** | **Multi-Channel Dispatcher** | Coming Soon | UI Placeholder | 0 endpoints | 0 tests | **Non-Existent (0/10)** |

---

## 2. Detailed Audit by Agent Slot

### Slot 1: Agent 1 — Lead Researcher

#### A. Current Implementation Status
- **Status:** **Functional Prototype (Pre-Production)**.
- **Frontend View:** Embedded in `src/components/AgentDetail.tsx` (Manual Research & Scraping), `src/components/LeadDiscovery.tsx` (Automated Discovery Engine), and `src/components/OutreachConsole.tsx` (Drafting & Review).
- **Backend Service:** Powered by `LeadDiscoveryService` (`backend/services/lead_discovery.py`), `PlaywrightResearchProvider` (`backend/providers/playwright_scraper.py`), `MockResearchProvider` (`backend/providers/mock.py`), and `DispatchTracker` (`backend/dispatch_tracker.py`).

#### B. Existing Capabilities
1. **Interactive URL Research:** Accepts targeted URLs or search keywords; launches headless Playwright or Mock provider to inspect pages.
2. **Automated Lead Discovery:** Parses natural language prompts into structured `DiscoveryPlan` instances (identifies industry, target counts, locations).
3. **Pluggable Search Retrieval:** Executes queries via DuckDuckGo Live Search, Public Business Directory, or commercial search APIs (Tavily, Google, Bing).
4. **Public Web Fact Extraction:** Extracts Schema.org JSON-LD organizations, OpenGraph tags, title, meta descriptions, emails, and phone numbers.
5. **Polite Crawling:** Enforces per-domain request intervals (0.4s) and parses target `robots.txt` using `urllib.robotparser`.
6. **Rule-Based Industry Classification:** Evaluates text against a 11-industry regex taxonomy (`INDUSTRY_TAXONOMY`) to assign industry labels and confidence scores.
7. **Contact Verification Heuristics:** Validates email syntax and filters out image assets (`.png`, `.svg`) and placeholder domains; validates phone digits and detects scientific notation corruption (`9.23E+11`).
8. **Relevance Scoring:** Computes an evidence-backed score (0.10–0.98) evaluating industry match, city/country match, and description depth.
9. **AI Outreach Drafting:** Generates personalized outreach drafts grounded strictly in discovered metadata using Template, Ollama, or Cloud OpenAI providers.
10. **Human-in-the-Loop Review Console:** Allows operators to review, edit, approve, reject, or delete drafts.
11. **Safety Gate & Duplicate-Send Protection:** Enforces explicit approval before dispatch; locks dispatches using SHA-256 message hashing.
12. **Outreach History & CSV Export:** Records all dispatch attempts in SQLite and exports datasets to RFC 4180 CSV.

#### C. Actual Backend Integration
- Integrated into 23 REST endpoints under `/api/research/*`, `/api/discovery/*`, and `/api/outreach/*` in `backend/main.py`.
- Persists data to `storage/dispatches.db` across tables: `discovery_jobs`, `discovered_leads`, `outreach_drafts`, `outreach_history`, `dispatched_records`.

#### D. Tools Available
- **Playwright (Chromium headless)** for browser execution.
- **BeautifulSoup4** for DOM parsing.
- **httpx** for asynchronous HTTP calls.
- **smtplib / Resend** for email transmission.
- **hashlib (SHA-256)** for message fingerprinting.

#### E. Permission Boundaries
- Strictly limited to public web scraping.
- Blocked from private networks via `validate_target_url` (though vulnerable to DNS rebinding).
- Outbound emails cannot be sent autonomously; hard-blocked unless `approved: true` is supplied in the request body.

#### F. Input/Output Schemas
- **Inputs:** `ResearchRequest`, `DiscoveryPlanRequest`, `DiscoveryJobCreateRequest`, `OutreachDraftRequest`, `SendOutreachRequest`.
- **Outputs:** `ResearchResponse`, `DiscoveryPlan`, `DiscoveryJobResponse`, `DiscoveredLeadsResponse`, `OutreachDraftResponse`, `SendOutreachResponse`.

#### G. Error Handling
- Catches crawler errors, records crawl diagnostics (`CrawlDiagnostic`), updates job status to `failed` or `cancelled`.
- Catches dispatch errors (`DispatchConfigurationError`, `DispatchDeliveryError`), logs failures in `outreach_history`, and sanitizes sensitive tokens before returning HTTP 500/502.

#### H. Test Coverage
- **118 automated test cases** across `backend/tests/`:
  - `test_lead_discovery.py` (25 tests)
  - `test_lead_quality.py` (10 tests)
  - `test_lead_transfer_workflow.py` (13 tests)
  - `test_live_solar_discovery.py` (5 tests)
  - `test_outreach.py` (29 tests)
  - `test_outreach_history.py` (12 tests)
  - `test_playwright_provider.py` (14 tests)
  - `test_research_api.py` (10 tests)

#### I. Missing Functionality (Gaps)
- No deep website technical audit (cannot detect tech stack, CMS, frameworks, performance, or SEO).
- No decision-maker identification (cannot discover executives or LinkedIn profiles).
- No live MX record lookup or SMTP deliverability verification.
- No cross-job lead deduplication at the search query stage.
- No Gmail inbox reply tracking.

---

### Slot 2: Agent 2 — Competitor Intelligence

#### A. Current Implementation Status
- **Status:** **UI Placeholder Only (0% Implemented)**.
- **Frontend:** Registered in `INITIAL_AGENTS` array in `src/App.tsx`. Clicking Agent 2 in the sidebar displays an empty workspace shell with category "Market Analytics" and badge "Coming Soon". `stages: []`.
- **Backend:** **Zero backend files, zero routes, zero models, zero database tables.**

#### B. Existing Capabilities
- Declared in UI: `"Competitor monitoring"`, `"Price change alerts"`.
- Real operational capability: **None.**

#### C. Actual Backend Integration
- None.

#### D. Tools Available
- None.

#### E. Permission Boundaries
- N/A.

#### F. Input/Output Schemas
- None.

#### G. Error Handling
- None.

#### H. Test Coverage
- **0%** (zero test cases).

#### I. Missing Functionality to Implement
- Competitor domain tracking registry.
- Automated daily/weekly page difference crawler (DOM snapshot comparison).
- Pricing table parser and change detector.
- New feature / changelog extraction engine.
- Alert dispatch pipeline (desktop notifications, email summaries).

---

### Slot 3: Agent 3 — Customer Service & FAQ Engine

#### A. Current Implementation Status
- **Status:** **UI Placeholder Only (0% Implemented)**.
- **Frontend:** Registered in `INITIAL_AGENTS` array in `src/App.tsx`. Category "Support Automation", badge "Coming Soon". `stages: []`.
- **Backend:** **Zero backend files, zero routes, zero models, zero database tables.**

#### B. Existing Capabilities
- Declared in UI: `"FAQ ingestion"`, `"Contextual draft synthesis"`.
- Real operational capability: **None.**

#### C. Actual Backend Integration
- None.

#### D. Tools Available
- None.

#### E. Permission Boundaries
- N/A.

#### F. Input/Output Schemas
- None.

#### G. Error Handling
- None.

#### H. Test Coverage
- **0%** (zero test cases).

#### I. Missing Functionality to Implement
- Knowledge base ingestion engine (PDF, Markdown, Notion, URL scraping).
- Vector embedding pipeline and local vector storage (e.g. ChromaDB, SQLite-VSS, or FAISS).
- Semantic retrieval and RAG prompt synthesizer.
- Human review and escalation interface for draft customer replies.
- Ticket tracking data models and audit logs.

---

### Slot 4: Agent 4 — Multi-Channel Dispatcher

#### A. Current Implementation Status
- **Status:** **UI Placeholder Only (0% Implemented)**.
- **Frontend:** Registered in `INITIAL_AGENTS` array in `src/App.tsx`. Category "Communications", badge "Coming Soon". `stages: []`.
- **Backend:** **Zero backend files, zero routes, zero models, zero database tables.**

#### B. Existing Capabilities
- Declared in UI: `"Multi-channel queueing"`, `"Rate limit manager"`.
- Real operational capability: **None.** (Note: Single-channel email dispatch exists under Agent 1, but multi-channel coordination does not exist).

#### C. Actual Backend Integration
- None.

#### D. Tools Available
- None.

#### E. Permission Boundaries
- N/A.

#### F. Input/Output Schemas
- None.

#### G. Error Handling
- None.

#### H. Test Coverage
- **0%** (zero test cases).

#### I. Missing Functionality to Implement
- Social and messaging API connectors (LinkedIn Messaging, Twitter/X DMs, WhatsApp Business, Slack).
- Unified multi-channel queue manager with channel-specific pacing and rate limits.
- Centralized consent and suppression registry across all channels.
- Cross-channel conversational thread tracking.

---

## 3. Comparative Capability Summary

| Capability Matrix | Agent 1 (Lead Researcher) | Agent 2 (Competitor Intel) | Agent 3 (FAQ / Support) | Agent 4 (Multi-Channel) |
| :--- | :---: | :---: | :---: | :---: |
| **UI Workspace** | Full Interactive Console | Banner Placeholder | Banner Placeholder | Banner Placeholder |
| **Backend Service Layer** | Yes (`LeadDiscoveryService`) | No | No | No |
| **API Endpoints** | 23 REST Endpoints | 0 | 0 | 0 |
| **Database Persistence** | 5 SQLite Tables | 0 | 0 | 0 |
| **Headless Crawler** | Playwright Active | None | None | None |
| **AI LLM Integration** | Template, Ollama, OpenAI | None | None | None |
| **Human Approval Gate** | Yes (Strict Enforcement) | N/A | N/A | N/A |
| **Unit Test Coverage** | 118 Passing Tests | 0 Tests | 0 Tests | 0 Tests |
| **Production Ready?** | No (Conditional Prototype) | No (Unbuilt) | No (Unbuilt) | No (Unbuilt) |

