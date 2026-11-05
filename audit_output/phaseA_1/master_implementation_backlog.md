# AgentDesk — Phase A.1: Master Implementation Backlog

**Document Purpose:** Prioritized, ticket-by-ticket engineering roadmap for transforming AgentDesk from a desktop prototype into an AI-powered Agency + SaaS Business Operating System.  
**Audit Date:** November 5, 2026  
**Auditor:** Antigravity AI Systems Architecture Team  

---

## 1. Feature State Categorization

Before detailing the engineering tickets, the entire system capability map is separated into three distinct states:

### 1.1 Existing Working Features (Keep & Enhance)
- **DuckDuckGo Live Search Engine:** Unauthenticated web search with rate pacing (`duckduckgo_search.py`).
- **Playwright Headless Web Scraper:** Browser automation, robots.txt compliance, Schema.org parsing (`playwright_scraper.py`).
- **Grounded Outreach Generator:** Zero-hallucination email drafting grounded in verified facts (`llm.py`).
- **Human Approval Safety Gate:** Hard enforcement of `approved: true` and verified email checks (`main.py`).
- **Duplicate-Send Protection:** SHA-256 message fingerprinting and in-flight draft claims (`dispatch_tracker.py`).
- **Outreach History & CSV Export:** SQLite-persisted audit trails and RFC 4180 CSV exports (`exporter.py`).
- **Comprehensive Backend Tests:** 118 unit and integration tests passing (`backend/tests/`).

### 1.2 Incomplete Features (Fix in P0 / P1)
- **Lead Relevance Scoring:** Uses an ad-hoc 0.10–0.98 keyword score without technical audit, buying signals, or decision-maker weighting.
- **Email & Phone Verification:** Naive regex checks; lacks DNS MX lookup, SMTP handshake check, and carrier validation.
- **Provider Auto-Selection:** Inconsistency in `factory.py` routing `auto` to static directory rather than live DuckDuckGo.
- **SSRF URL Guard:** String-based IP check lacking DNS pre-resolution and complete CIDR range coverage.
- **Cross-Job Deduplication:** Only deduplicates leads within the same active job, not across past discovery jobs.

### 1.3 Proposed Features (Implement in P0 — P4)
- **Tauri Sidecar Process Supervision:** Native bundling and lifecycle management of Python FastAPI.
- **100-Point Explainable Lead Scoring Engine:** Multi-factor qualification model allocating 25/25/15/15/10/10 points.
- **Website & Technology Auditor Engine:** CMS, tech stack, Core Web Vitals, and automation gap diagnosis.
- **Bidirectional Gmail API Integration:** Google OAuth2 login, message reading, threading, and reply matching.
- **Relational CRM Pipeline:** Organizations, Contacts, Opportunities, Pipeline Stages, and Global Suppression Lists.
- **Agents 2, 3, and 4:** Competitor Intelligence, FAQ/Customer Support RAG Engine, Multi-Channel Dispatcher.
- **Agency Operations & SaaS Expansion:** Client audit report generator, multi-tenancy, Stripe billing, and IoT telemetry.

---

## 2. Priority 0 (P0) — Critical Foundation (Required Before Acquisition)

---

### Ticket P0-SEC-01: DNS Pre-Resolution SSRF & CIDR Hardening
- **Module:** Security / Crawler Subsystem
- **Problem:** `validate_target_url()` in `playwright_scraper.py` only performs string checks on `hostname`. It fails to block alternative private ranges (`172.17.0.0/12`), cloud metadata (`169.254.169.254`), IPv6 loopbacks (`::1`), and is vulnerable to DNS rebinding attacks.
- **Proposed Solution:** Implement mandatory pre-crawl DNS resolution using `socket.getaddrinfo()`. Parse all resolved IPv4 and IPv6 addresses with Python's `ipaddress` module and reject private, loopback, link-local, multicast, or reserved IPs. Hook into Playwright's `page.route()` to inspect redirected IP addresses.
- **Files Likely to Change:**
  - `backend/providers/playwright_scraper.py`
  - `backend/services/lead_discovery.py`
  - `backend/tests/test_playwright_provider.py`
- **Dependencies:** Python built-in `ipaddress`, `socket`.
- **Implementation Steps:**
  1. Add `is_safe_ip(ip_str: str) -> bool` using `ipaddress.ip_address()`.
  2. Update `validate_target_url()` to perform `socket.getaddrinfo(hostname, None)` and assert all resolved IPs are safe.
  3. Add redirect URL validation listener in Playwright route handling.
  4. Write comprehensive SSRF test fixtures.
- **Security Considerations:** Prevents local network compromise and cloud instance metadata theft.
- **Tests:** Unit tests with `127.0.0.1`, `169.254.169.254`, `[::1]`, `172.20.1.1`, octal IPs, and mock DNS rebinding domains.
- **Acceptance Criteria:** Any target URL resolving to an internal, link-local, or private IP is rejected with HTTP 422 before any network connection is opened.
- **Priority:** **P0 (Blocker)** | **Complexity:** Medium (3 SP)

---

### Ticket P0-SEC-02: Local FastAPI Bearer Token Authentication
- **Module:** Security / API Gateway
- **Problem:** FastAPI endpoints bind to `127.0.0.1:8000` without authentication. Any software or compromised browser tab on the host machine can query leads, approve drafts, or trigger emails.
- **Proposed Solution:** Generate a cryptographically secure ephemeral token (`secrets.token_hex(32)`) upon backend startup. Write the token to a restricted local session file in `storage/` or pass it via CLI argument. Require `Authorization: Bearer <token>` on all FastAPI routes via a dependency `get_current_token()`. Configure Vite and Tauri to inject this token in all `src/services/api.ts` requests.
- **Files Likely to Change:**
  - `backend/main.py`
  - `backend/env_loader.py`
  - `src/services/api.ts`
  - `start-backend.ps1`
  - `backend/tests/conftest.py`
- **Dependencies:** `secrets`, FastAPI `HTTPBearer`.
- **Implementation Steps:**
  1. Implement `backend/auth.py` with session token generation and validation dependency.
  2. Apply `Depends(verify_session_token)` to all FastAPI routers.
  3. Update `start-backend.ps1` to generate or pass session token.
  4. Update `src/services/api.ts` to include `Authorization` header.
- **Security Considerations:** Closes unauthenticated local loopback vulnerability.
- **Tests:** Test requests with missing, invalid, and valid bearer tokens.
- **Acceptance Criteria:** Requests without a valid bearer token receive HTTP 401 Unauthorized; frontend functions seamlessly with token injected.
- **Priority:** **P0 (Blocker)** | **Complexity:** Medium (3 SP)

---

### Ticket P0-TAURI-01: Tauri v2 Backend Sidecar Process Supervision & Strict CSP
- **Module:** Desktop Shell / Packaging
- **Problem:** Tauri does not manage the Python backend process (`tauri.conf.json` lacks sidecar configuration), and Content Security Policy is disabled (`"csp": null`).
- **Proposed Solution:** Configure Tauri v2 `externalBin` to package and spawn the Python executable/uvicorn server as a supervised child process on startup and terminate it on window close. Enforce a strict Content Security Policy restricting scripts to `'self'` and network connections to `http://127.0.0.1:8000`.
- **Files Likely to Change:**
  - `src-tauri/tauri.conf.json`
  - `src-tauri/Cargo.toml`
  - `src-tauri/src/lib.rs`
  - `package.json`
- **Dependencies:** `@tauri-apps/plugin-shell`, `tauri-plugin-process`.
- **Implementation Steps:**
  1. Add `tauri-plugin-shell` to `Cargo.toml`.
  2. Define sidecar binary configuration in `tauri.conf.json`.
  3. In `src-tauri/src/lib.rs`, spawn sidecar process during app setup and attach shutdown hook.
  4. Replace `"csp": null` with strict CSP policy string.
- **Security Considerations:** Eliminates XSS injection risks and ensures desktop application is self-contained.
- **Tests:** Launch desktop app binary without PowerShell; verify backend starts automatically and shuts down on window exit.
- **Acceptance Criteria:** Standalone desktop application launches backend automatically with no orphan background processes remaining upon closing.
- **Priority:** **P0 (Blocker)** | **Complexity:** High (5 SP)

---

### Ticket P0-DB-01: SQLite WAL Mode, Foreign Key Enforcement & Atomic Transactions
- **Module:** Persistence / Database
- **Problem:** Database runs in default journal mode (prone to `database is locked` during concurrent crawler writes) and foreign keys are not enforced by default. Two historical orphaned rows exist.
- **Proposed Solution:** Enable WAL mode (`PRAGMA journal_mode = WAL;`) and synchronous normal (`PRAGMA synchronous = NORMAL;`) on connection initialization. Enable `PRAGMA foreign_keys = ON;`. Wrap multi-table operations (such as lead-to-draft transfer) in explicit atomic transactions (`with conn:`).
- **Files Likely to Change:**
  - `backend/dispatch_tracker.py`
  - `backend/main.py`
- **Dependencies:** Python built-in `sqlite3`.
- **Implementation Steps:**
  1. Add connection factory `_get_connection()` in `dispatch_tracker.py` executing WAL pragmas and foreign-key pragma.
  2. Implement context-managed atomic transaction helper.
  3. Refactor `update_discovery_job` to whitelist allowed column names.
- **Security Considerations:** Prevents database corruption, lock deadlocks, and orphan foreign key creation.
- **Tests:** Concurrency stress test writing 100 simultaneous lead records while querying history.
- **Acceptance Criteria:** Zero `database is locked` errors under concurrent operations; `PRAGMA foreign_keys = ON` enforced on all write connections.
- **Priority:** **P0** | **Complexity:** Low-Medium (2 SP)

---

### Ticket P0-VERIF-01: Live DNS MX & SMTP Handshake Deliverability Checker
- **Module:** Lead Qualification / Verification
- **Problem:** The current system relies on regex validation and flags generic `info@` emails as verified without testing mailbox existence or deliverability.
- **Proposed Solution:** Implement an asynchronous email deliverability validator that queries DNS MX records for the domain and initiates a non-sending SMTP handshake (`HELO` -> `MAIL FROM:<>` -> `RCPT TO:<target>`). Flag catch-all mailboxes, disposable domains, and nonexistent addresses without transmitting real email.
- **Files Likely to Change:**
  - `backend/services/lead_discovery.py`
  - `backend/providers/email_dispatcher.py`
  - `backend/models.py`
  - `backend/requirements.txt`
- **Dependencies:** `aiodns`, `dnspython`.
- **Implementation Steps:**
  1. Add `dnspython` to `requirements.txt`.
  2. Implement `verify_email_deliverability(email: str) -> Tuple[str, str]` in `services/lead_discovery.py`.
  3. Query MX records for the recipient domain.
  4. Attempt socket connection to lowest-preference MX server and evaluate SMTP response codes (250 OK vs 550 User Unknown).
  5. Store status: `deliverable`, `undeliverable`, `catch_all`, `no_mx_record`.
- **Security Considerations:** Must respect timeouts (3.0s) and never send message body (`DATA` command is never executed).
- **Tests:** Mock SMTP responses for valid, invalid, and catch-all domains.
- **Acceptance Criteria:** Discovered emails receive true deliverability status; zero positive points awarded to domains with missing MX records.
- **Priority:** **P0** | **Complexity:** Medium (3 SP)

---

### Ticket P0-DISC-01: Resolve DDG Auto-Fallback Bug & Cross-Job Domain Deduplication
- **Module:** Automated Lead Discovery
- **Problem:** `factory.py` routes `auto` mode to static directory fixture instead of live DuckDuckGo if `ENABLE_DDG_AUTO_FALLBACK` is absent. Candidate deduplication only works within the same job, allowing identical companies to be re-crawled across different jobs.
- **Proposed Solution:** Fix `factory.py` so `auto` routes to `DuckDuckGoLiveSearchProvider` when commercial API keys are missing. Update `_execute_pipeline` in `lead_discovery.py` to query `SELECT canonical_domain FROM discovered_leads` and skip domains already discovered in prior jobs.
- **Files Likely to Change:**
  - `backend/providers/search/factory.py`
  - `backend/services/lead_discovery.py`
  - `backend/tests/test_lead_discovery.py`
- **Dependencies:** None.
- **Implementation Steps:**
  1. Update `factory.py` line 58 to default to DuckDuckGo when unkeyed.
  2. Add `get_existing_domains() -> Set[str]` in `dispatch_tracker.py`.
  3. Filter incoming search candidate URLs against both active-job and historical domain sets.
- **Security Considerations:** Conserves bandwidth and prevents redundant web crawling.
- **Tests:** Verify unconfigured `auto` returns DuckDuckGo; verify second job with same query skips previously saved domains.
- **Acceptance Criteria:** "Auto-Select" performs authentic live search out-of-the-box; past discovered domains are skipped across jobs.
- **Priority:** **P0** | **Complexity:** Low (2 SP)

---

## 3. Priority 1 (P1) — Sales Conversion Engine

---

### Ticket P1-SCORE-01: Implement 100-Point Explainable Lead Scoring Engine
- **Module:** Lead Qualification / Scoring
- **Problem:** The current 0.10–0.98 score lacks multi-factor qualification criteria (technical need, buying signals, decision-maker reach).
- **Proposed Solution:** Implement the 100-point scoring algorithm designed in Task 4: Business Relevance (25), Technical Need (25), Decision-Maker Reach (15), Buying Signals (15), Contact Verification (10), and Evidence Quality (10). Missing evidence receives strictly 0 points. Classify leads into Tier 1 (75–100), Tier 2 (50–74), and Tier 3 (<50).
- **Files Likely to Change:**
  - `backend/services/lead_discovery.py`
  - `backend/models.py`
  - `src/components/LeadDiscovery.tsx`
  - `src/types/agent.ts`
  - `backend/tests/test_lead_quality.py`
- **Dependencies:** None.
- **Implementation Steps:**
  1. Create `calculate_qualification_score(lead, audit_data, plan) -> Tuple[int, str, str, Dict]`.
  2. Implement sub-scorers for each of the 6 dimensions.
  3. Store `qualification_score` (0–100) and `qualification_tier` in `discovered_leads`.
  4. Expose score breakdown tooltip in React frontend.
- **Security Considerations:** Transparent mathematical scoring prevents hallucinated qualification.
- **Tests:** Test cases for pure Tier 1 enterprise lead, incomplete lead, and disqualified residential lead.
- **Acceptance Criteria:** Every discovered lead receives an explainable 0–100 score and tier; missing fields score 0 points.
- **Priority:** **P1** | **Complexity:** Medium (3 SP)

---

### Ticket P1-AUDIT-01: Build Automated Website & Technology Auditor Subsystem
- **Module:** Agent 1 / Tech Auditor
- **Problem:** Agent 1 cannot evaluate prospective clients' tech stacks, web performance, or digital gaps, leaving outreach generic.
- **Proposed Solution:** Build `backend/services/website_auditor.py` using Playwright and httpx. Analyze: 1) SSL certificate validity and security headers, 2) Core Web Vitals (LCP, TTFB, CLS), 3) Technology stack signatures (WordPress, Shopify, React, jQuery, analytics pixels), 4) Conversion assets (contact forms, booking widgets, WhatsApp links), and 5) Automation gaps (missing quote calculators, manual PDF downloads).
- **Files Likely to Change:**
  - `backend/services/website_auditor.py` (New file)
  - `backend/models.py`
  - `backend/main.py`
  - `src/components/AgentDetail.tsx`
  - `src/components/LeadDiscovery.tsx`
- **Dependencies:** `playwright`, `httpx`, `beautifulsoup4`.
- **Implementation Steps:**
  1. Implement tech signature pattern database (`TECH_SIGNATURES`).
  2. Create audit runner using Playwright measuring performance metrics.
  3. Add endpoint `POST /api/audit/website`.
  4. Integrate audit findings into `OutreachDraft` generator to auto-pitch identified modernization gaps.
- **Security Considerations:** Enforces SSRF pre-check before auditing; caps execution time at 10.0s.
- **Tests:** Run audit against local test fixture and mock HTTP server.
- **Acceptance Criteria:** Auditor returns structured technical report and digital health grade (A–F) for any public domain within 10s.
- **Priority:** **P1** | **Complexity:** High (5 SP)

---

### Ticket P1-CRM-01: Relational CRM Core: Organizations, Contacts, Pipelines & Suppression
- **Module:** CRM Subsystem
- **Problem:** Data is stored in denormalized flat tables without account/contact separation, deal pipelines, or global suppression lists.
- **Proposed Solution:** Implement relational CRM tables in `storage/dispatches.db`: `organizations`, `contacts`, `opportunities`, `pipeline_stages`, and `suppression_list`. Build CRUD API endpoints and a Kanban board view in the frontend.
- **Files Likely to Change:**
  - `backend/dispatch_tracker.py`
  - `backend/models.py`
  - `backend/main.py`
  - `src/App.tsx`
  - `src/components/Sidebar.tsx`
  - `src/components/CRM/KanbanPipeline.tsx` (New file)
  - `src/components/CRM/AccountDetail.tsx` (New file)
- **Dependencies:** None.
- **Implementation Steps:**
  1. Create schema tables in `dispatch_tracker.py` with foreign keys and cascade rules.
  2. Implement repository methods for Accounts, Contacts, Deals, and Suppression.
  3. Build FastAPI router `/api/crm/*`.
  4. Add CRM pipeline Kanban view to React frontend.
- **Security Considerations:** Global suppression list checked before every outreach transfer and dispatch.
- **Tests:** Verify account creation with multiple contacts; verify suppression list prevents draft generation.
- **Acceptance Criteria:** Operators can manage deals across 6 pipeline stages and link multiple contacts to a single company.
- **Priority:** **P1** | **Complexity:** High (5 SP)

---

### Ticket P1-EMAIL-01: Bidirectional Gmail API Integration, OAuth2 & Reply Matching
- **Module:** Communications / Email Subsystem
- **Problem:** AgentDesk has zero native Gmail API code, cannot read incoming messages, and cannot match prospect replies to sent campaigns.
- **Proposed Solution:** Implement official Google OAuth2 Desktop loopback authentication flow. Store refresh tokens securely in the OS keyring. Use Gmail REST API v1 (`users.messages.send`, `users.messages.list`). Inject and track RFC 2822 `Message-ID` on outbound dispatches; poll unread messages to match `In-Reply-To` headers and update CRM lead stage to "Replied".
- **Files Likely to Change:**
  - `backend/providers/gmail_client.py` (New file)
  - `backend/providers/email_dispatcher.py`
  - `backend/main.py`
  - `backend/requirements.txt`
  - `src/components/OutreachConsole.tsx`
- **Dependencies:** `google-api-python-client`, `google-auth-oauthlib`, `keyring`.
- **Implementation Steps:**
  1. Add Google API libraries to `requirements.txt`.
  2. Build `GmailOAuthManager` initiating local browser OAuth consent flow.
  3. Store tokens using Python `keyring`.
  4. Add background polling worker checking for replies every 5 minutes.
  5. Update deal stage to "Replied" when an inbound match is detected.
- **Security Considerations:** Scopes restricted to `gmail.send` and `gmail.readonly`. Tokens never saved to disk in plaintext.
- **Tests:** Mock OAuth code exchange and mock Gmail API message retrieval.
- **Acceptance Criteria:** Operator connects Gmail via 1-click browser auth; outbound emails send via Gmail API; prospect replies automatically match in CRM.
- **Priority:** **P1** | **Complexity:** High (5 SP)

---

### Ticket P1-AGENT2-01: Agent 2 Competitor Intelligence Implementation
- **Module:** Agent 2 (Market Analytics)
- **Problem:** Agent 2 is currently an empty UI placeholder.
- **Proposed Solution:** Build the backend engine for Agent 2: monitor competitor website pricing, new service launches, and team changes. Crawl target domains weekly using Playwright, compute DOM diffs against previous snapshots, and highlight pricing/offering updates on a dedicated Competitor Intelligence dashboard.
- **Files Likely to Change:**
  - `backend/services/competitor_intelligence.py` (New file)
  - `backend/main.py`
  - `backend/models.py`
  - `src/components/AgentDetail.tsx`
  - `src/components/CompetitorDashboard.tsx` (New file)
- **Dependencies:** `playwright`, `beautifulsoup4`.
- **Implementation Steps:**
  1. Define database tables `competitor_profiles` and `competitor_snapshots`.
  2. Implement snapshot comparison diff engine.
  3. Add REST routes `/api/competitor/*`.
  4. Build interactive Competitor Dashboard in React.
- **Security Considerations:** Respect competitor `robots.txt` and rate limits.
- **Tests:** Snapshot diff comparison test verifying detection of price changes.
- **Acceptance Criteria:** Agent 2 displays monitored competitors, detects website changes, and flags updated service offerings.
- **Priority:** **P1** | **Complexity:** Medium (3 SP)

---

## 4. Priority 2 (P2) — Agency Operations

- **Ticket P2-AGY-01: Interactive Agency Client Portal & White-Label PDF/HTML Audit Report Generator**  
  Generates client-ready, branded digital audit reports (PDF/HTML) diagnosing website vulnerabilities and pitch proposals. (Complexity: 5 SP)
- **Ticket P2-SEQ-01: Automated Multi-Touch Sales Sequences with Sentiment-Aware Follow-ups**  
  Implements 3-step cadence workflows with automated pause when prospect replies or meeting is booked. (Complexity: 4 SP)
- **Ticket P2-TASK-01: Operator Task Reminders, Calendar Integration & Call Logging**  
  Follow-up reminders, task queues, and manual call log entries integrated into the CRM sidebar. (Complexity: 3 SP)

---

## 5. Priority 3 (P3) — SaaS Expansion

- **Ticket P3-SAAS-01: Multi-Tenancy Architecture, User Roles & Workspace Isolation**  
  Transforms single-tenant desktop app into team workspace with Admin, Sales Rep, and Viewer roles. (Complexity: 8 SP)
- **Ticket P3-BILL-01: Stripe Subscription Billing & Usage-Based Credit Metering**  
  Integrates Stripe checkout for tiered SaaS plans (Starter, Growth, Agency Pro) with lead discovery credit limits. (Complexity: 5 SP)
- **Ticket P3-API-01: Public Agency REST API & Webhook Dispatcher**  
  Exposes documented API endpoints and outbound webhooks for Zapier/Make integrations. (Complexity: 5 SP)

---

## 6. Priority 4 (P4) — Advanced IoT & Robotics Capabilities

- **Ticket P4-IOT-01: Industrial IoT Telemetry Ingestion, MQTT Broker & Edge Device Fleet Monitor**  
  Connects AgentDesk to smart energy inverters and edge sensors via MQTT, displaying live telemetry on solar installations. (Complexity: 8 SP)
- **Ticket P4-ROB-01: Robotics Hardware Telemetry & Automated Industrial Safety Alerting**  
  Telemetry pipeline for automated robotic inspection units, logging equipment faults and dispatching maintenance tickets. (Complexity: 8 SP)

