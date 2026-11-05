# AgentDesk — Phase A.1: Executive Technical Audit Report

**Date of Audit:** November 5, 2026  
**Auditor:** Antigravity AI Systems Architecture Team  
**Workspace Path:** `C:\Users\azize\source\AgentDesk`  
**Phase Identifier:** Phase A.1 (Technical Audit & Implementation Backlog)  
**Execution Mode:** STRICT READ-ONLY AUDIT (Zero writes, zero leads imported, zero outbound emails dispatched, zero credentials altered)

---

## 1. Executive Summary

AgentDesk has undergone an exhaustive, evidence-based technical audit to establish its readiness for transformation from a desktop proof-of-concept lead generator into an **AI-powered Agency + SaaS Business Operating System**. 

The current application consists of:
- A desktop frontend powered by **Tauri v2** + **React 18** + **TypeScript 5.7** + **Vite 6.1**.
- A local backend powered by **Python 3.13** + **FastAPI 0.115** + **Uvicorn**, persisting to **SQLite** (`storage/dispatches.db`).
- An initial **Agent Manager** displaying four agent slots:
  - **Slot 1 (Lead Researcher):** Functional end-to-end prototype supporting manual crawl, automated multi-provider discovery, contact extraction, AI draft generation, an explicit human approval gate, and dispatch via simulation/SMTP/Resend.
  - **Slots 2, 3, and 4 (Competitor Intelligence, Customer Service/FAQ Engine, Multi-Channel Dispatcher):** Visual UI placeholders with zero backend integration, zero endpoints, and zero logic.
- An **Automated Lead Discovery Engine** integrating live DuckDuckGo web search, a fallback 23-entry public directory, and optional commercial APIs (Tavily, Google, Bing), backed by Playwright web scraping, canonical domain deduplication, and heuristic relevance scoring.
- An **Outreach & Approval Subsystem** with duplicate-send protection (SHA-256 content hashing and draft ID locking), SQLite durability, and an outreach history audit trail.

All **118 automated backend tests** pass cleanly (`pytest backend/tests`), and TypeScript compiles with zero errors (`tsc --noEmit`). The SQLite database is structurally sound (`PRAGMA integrity_check` = `ok`), preserving 149 leads and 6 discovery jobs, with exactly two known historical foreign-key violations on orphaned rows (124 and 125 from Phase 3) that remain untouched.

---

## 2. High-Level System Assessment

| Dimension | Current State | Production Readiness Score (1-10) | Key Constraint / Risk |
| :--- | :--- | :---: | :--- |
| **Desktop Shell (Tauri v2)** | Basic webview container; CSP disabled (`csp: null`). Backend not managed as a Tauri sidecar. | 4/10 | Requires manual terminal launch (`start-backend.ps1`); no binary bundling of Python environment. |
| **Backend Core (FastAPI)** | Clean modular endpoints, Pydantic validation, asyncio event loop policy for Windows. | 7/10 | No API authentication; any local process on `127.0.0.1` can trigger dispatches or delete records. |
| **Database Persistence (SQLite)** | Thread-safe locks (`threading.Lock()`), normalized tables, pagination. | 6/10 | WAL mode not enabled; no database migrations framework (Alembic/SQLAlchemy); 2 orphaned legacy FKs. |
| **Agent Architecture** | 1 of 4 agents operational (Lead Researcher). | 3/10 | Agents 2, 3, and 4 are hardcoded UI stubs (`stages: []`). No generic Agent Base Class or execution runner. |
| **Lead Discovery** | DuckDuckGo live search + Directory fallback + Tavily/Google/Bing stubs. | 7/10 | DuckDuckGo HTML scraping is brittle to markup changes; cross-job deduplication is missing. |
| **Verification & Scoring** | Syntactic regex validation for email and phone; keyword matching for industry/city. | 4/10 | No live MX/SMTP handshake verification; no phone line ping; no 100-point qualification model. |
| **Website & Tech Auditor** | Basic HTML title, meta tag, and Schema.org scraper via Playwright / httpx. | 3/10 | No tech stack detector (Wappalyzer equivalent); no SEO audits; no Core Web Vitals; SSRF filter bypassable. |
| **CRM & Sales Pipeline** | Draft review console, approve/discard actions, dispatch history log. | 3/10 | No accounts/contacts separation; no deal stages; no follow-up scheduling; no suppression lists. |
| **Gmail / Email Integration** | Simulation mode, raw SMTP, and Resend HTTP API. | 3/10 | **Zero Gmail API / OAuth2 integration**. No inbox reading, no reply matching, no email threading. |
| **Security & Privacy** | Credential masking in logs (`sanitize_log_message`), duplicate-send lock. | 4/10 | Plaintext `.env` credentials, unauthenticated HTTP API, bypassable SSRF check, Tauri `csp: null`. |

---

## 3. Final Verdict

### **READY FOR PHASE A IMPLEMENTATION**

#### **Evidence and Justification:**
1. **Core Runtime Stability:** The core Python/FastAPI backend and React frontend are completely runnable and stable. All 118 unit and integration tests pass without error (`118 passed in 42.74s`).
2. **Database Integrity:** `storage/dispatches.db` is physically healthy (`PRAGMA integrity_check` returns `ok`). The 149 existing leads and 6 discovery jobs are intact and uncorrupted. The Phase 6.3 safety gate prevented premature writes.
3. **Safety Gate Verification:** The outbound dispatch gate enforces hard human-in-the-loop approval (`approved: true`), verified public email checks, and duplicate-send hash locking, preventing accidental live email leakage.
4. **Implementation Scope Alignment:** The purpose of Phase A is to systematically construct the missing Agency + SaaS OS layers. The foundational plumbing (Playwright extraction, draft persistence, provider factories, search pipeline) provides a solid architectural base upon which Phase A features can be implemented.
5. **No Blockers to Engineering Work:** There are no active database deadlocks, no corrupt binary blobs, and no unresolvable circular dependencies that would prevent Phase A development from starting immediately under the Master Implementation Backlog.

---

## 4. Architectural Summary

```
+-------------------------------------------------------------------------------+
|                             AgentDesk Tauri v2 Desktop Shell                  |
|  +-------------------------------------------------------------------------+  |
|  |                     React 18 + TypeScript SPA Frontend                  |  |
|  |  +-------------------+  +-------------------+  +---------------------+  |  |
|  |  | Lead Discovery UI |  | Outreach Console  |  | History & Audit Log |  |  |
|  |  +---------+---------+  +---------+---------+  +----------+----------+  |  |
|  +------------|----------------------|-----------------------|-------------+  |
+---------------|----------------------|-----------------------|----------------+
                | HTTP Fetch (localhost:8000)                  |
                v                                              v
+-------------------------------------------------------------------------------+
|                         FastAPI Backend (Python 3.13)                         |
|  +-------------------------------------------------------------------------+  |
|  | /api/discovery/*         /api/outreach/*           /api/research/*      |  |
|  +-------------------+-------------------+-------------------+-------------+  |
|                      |                   |                   |                |
|  +-------------------+---+       +-------+-------+   +-------+-------+        |
|  | LeadDiscoveryService  |       | Dispatcher    |   | Playwright    |        |
|  | - Plan Parser         |       | - Idempotency |   | - Headless    |        |
|  | - Multi-query builder |       | - SMTP/Resend |   | - Robots.txt  |        |
|  | - Domain Dedup        |       | - Simulation  |   | - Contact Ext |        |
|  +-----------+-----------+       +-------+-------+   +---------------+        |
|              |                           |                                    |
|  +-----------+---------------------------+---------------------------------+  |
|  |             DispatchTracker (Thread-safe SQLite Data Layer)             |  |
|  |                     storage/dispatches.db (149 leads)                   |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
```

---

## 5. Comprehensive System Breakdown

### A. What is Genuinely Working?
1. **Automated Lead Discovery Pipeline:** Natural language parsing (`parse_natural_language_request`), query synthesis, search provider execution, candidate website retrieval, Playwright HTML inspection, and result persistence.
2. **DuckDuckGo Live Search Provider:** Authentic unauthenticated live web queries against `https://html.duckduckgo.com/html/` with 0.5s rate pacing, redirect resolution, and tracking parameter stripping.
3. **Public Business Directory Fallback:** Offline fixture search against 23 pre-verified enterprise records.
4. **Duplicate-Send Protection:** SHA-256 message content hashing (`recipient::subject::body`) and draft ID locking in `DispatchTracker` to prevent duplicate email transmissions across restarts.
5. **Human Approval Safety Gate:** Strict enforcement requiring `approved: true` and verified public email status before any dispatch is processed.
6. **Outreach Draft Generation:** Grounded template drafter and LLM provider interfaces (Template, Ollama, Cloud OpenAI-compatible).
7. **Draft Review & Editing:** Full CRUD persistence for drafts (fetch, edit subject/body, approve, unapprove, discard, delete) in SQLite.
8. **Outreach History & CSV Export:** Paginated, filterable audit history with RFC 4180 compliant CSV export for both leads and history records.
9. **Automated Test Suite:** 118 comprehensive test cases in `backend/tests/` verifying models, discovery, quality classification, and dispatch workflows.

### B. What is Partially Working?
1. **Search Provider Factory:** DuckDuckGo and Directory work out-of-the-box, but `auto` mode fallback contains an internal logic inconsistency (defaults to Directory instead of DDG if `ENABLE_DDG_AUTO_FALLBACK` is omitted). Tavily, Google, and Bing require external keys.
2. **Contact Extraction:** Regular expressions extract `mailto:` and `tel:` strings from homepages and contact subpages, but fail to extract person identities (names/roles) and lack deliverability verification.
3. **Lead Relevance Scoring:** Computes a 0.10–0.98 score based on simple industry and city keyword matches, but lacks deep multi-factor scoring (no technical audit, financial health, or decision-maker weighting).
4. **Outreach Email Dispatcher:** Supports live SMTP and Resend API, but defaults to offline simulation mode; lacks email threading headers (`Message-ID`, `In-Reply-To`).
5. **SSRF Filtering:** Blocks obvious IP strings (`127.0.0.1`, `localhost`, `10.x`, `192.168.x`), but does not resolve DNS before fetching, leaving the crawler vulnerable to DNS rebinding attacks and alternative private ranges (`172.17.0.0/12`, `169.254.169.254`, `::1`).

### C. What is Only UI or a Placeholder?
1. **Agent 2 (Competitor Intelligence):** 100% UI placeholder. Listed in sidebar and hero banner; has zero backend models, routes, or scrapers.
2. **Agent 3 (Customer Service & FAQ Engine):** 100% UI placeholder. Zero RAG pipelines, zero vector databases, zero knowledge base ingestion.
3. **Agent 4 (Multi-Channel Dispatcher):** 100% UI placeholder. Zero social or messaging integrations (no LinkedIn, Twitter/X, WhatsApp, or Slack).
4. **CRM Pipeline / Deal Tracking:** Zero CRM pipeline UI or database tables. No stage kanban, no deal sizes, no customer accounts.
5. **Gmail Inbox Integration:** **Non-existent**. No OAuth2 flow, no message polling, no inbox synchronization.

### D. What is Broken?
1. **Orphaned Database Rows (Rows 124 & 125):** Two records in `discovered_leads` reference parent `job_id = 'job-phase3-live-expansion'`, which was never created in `discovery_jobs`, causing `PRAGMA foreign_key_check` to report 2 foreign-key violations.
2. **Tauri Backend Lifecycle Management:** Tauri is not configured to spawn or manage the Python backend process (`tauri.conf.json` lacks sidecar configuration). If launched as a standalone `.exe`, the UI shows a backend disconnect error unless `start-backend.ps1` is run manually.
3. **Tauri Content Security Policy:** `tauri.conf.json` explicitly sets `"csp": null`, disabling webview origin restrictions.
4. **Sort Parameters Ignored:** In `backend/main.py`, the `list_discovered_leads` endpoint accepts `sort_by` and `sort_order`, but `query_discovered_leads` in `dispatch_tracker.py` hardcodes `ORDER BY relevance_score DESC, discovered_at DESC`.

### E. What Must Be Built First? (P0 Critical Path)
1. **Security & SSRF Hardening:** Implement full DNS pre-resolution SSRF protection with complete RFC 1918 / IPv6 / link-local CIDR blocking.
2. **Backend Authentication & Local API Token:** Secure the FastAPI backend with a shared secret / bearer token generated by Tauri or stored locally, preventing arbitrary local processes from calling dispatch or discovery endpoints.
3. **Tauri Sidecar & Process Bundling:** Configure Tauri v2 to spawn and terminate the Python backend process as a managed sidecar.
4. **SQLite Transaction Robustness & WAL Mode:** Enable WAL mode (`PRAGMA journal_mode = WAL`) and implement atomic database transaction helpers to eliminate orphan foreign-key risks.
5. **Live MX & DNS Email Deliverability Check:** Upgrade email verification from naive regex to include DNS MX record lookups and SMTP handshake checks (without sending emails).

### F. What Should Not Be Built Yet?
1. **Autonomous Email Sending (Auto-pilot):** Keep the strict human approval gate intact; do not build unsupervised autonomous emailing.
2. **Agent 4 Multi-Channel Social Automation (LinkedIn/Twitter/WhatsApp):** Social channel automation introduces severe anti-scraping and account-ban risks; focus on email and web intelligence first.
3. **Complex Multi-Tenant SaaS Billing & Stripe:** The single-tenant desktop operating system must be fully stabilized with client value and sales conversion before abstracting multi-tenancy and SaaS billing.
4. **Autonomous Robotics / IoT Fleet Control:** Advanced edge device actuation and PLC control belongs in Phase 4 backlog, far downstream from agency revenue operations.

