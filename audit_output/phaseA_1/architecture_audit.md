# AgentDesk — Phase A.1: Project Architecture Audit

**Target System:** AgentDesk AI Business Operating System  
**Audit Date:** November 5, 2026  
**Auditor:** Antigravity AI Systems Architecture Team  
**Scope:** Full-stack source inspection across Frontend, Backend, Tauri v2 Desktop Shell, and SQLite Persistence

---

## 1. System Overview & Technology Stack

AgentDesk is structured as a hybrid desktop application utilizing Tauri v2 as a native window wrapper around a React SPA, communicating over HTTP loopback with a Python FastAPI backend.

```
+---------------------------------------------------------------------------------------------+
|                                    DESKTOP SHELL (Tauri v2)                                 |
|                                                                                             |
|  +---------------------------------------------------------------------------------------+  |
|  |                            FRONTEND (React 18 + Vite 6)                               |  |
|  |                                                                                       |  |
|  |   [App.tsx] ---> [Sidebar.tsx] ---> [Header.tsx]                                      |  |
|  |        |                                                                              |  |
|  |        +---> [LeadDiscovery.tsx]     (View: 'discovery')                              |  |
|  |        +---> [AgentDetail.tsx]       (View: 'agent' - Agent 1)                        |  |
|  |        |        +---> [OutreachConsole.tsx]                                           |  |
|  |        +---> [OutreachHistory.tsx]   (View: 'history')                                |  |
|  |        +---> [EnvironmentStatus.tsx] (View: 'environment')                            |  |
|  |                                                                                       |  |
|  |   Service Layer: [src/services/api.ts] (Direct fetch to http://127.0.0.1:8000)        |  |
|  +---------------------------------------------------------------------------------------+  |
|                                         |                                                   |
|                                  HTTP (JSON/REST)                                           |
|                                         v                                                   |
|  +---------------------------------------------------------------------------------------+  |
|  |                          BACKEND (FastAPI + Python 3.13)                              |  |
|  |                                                                                       |  |
|  |   [backend/main.py]                                                                   |  |
|  |      |                                                                                |  |
|  |      +---> [services/lead_discovery.py]                                               |  |
|  |      |        |---> Pluggable Search Providers ([providers/search/*])                 |  |
|  |      |        |---> Playwright Browser Scraper ([providers/playwright_scraper.py])    |  |
|  |      |                                                                                |  |
|  |      +---> [providers/llm.py] (Template, Ollama, OpenAI)                              |  |
|  |      +---> [providers/email_dispatcher.py] (Simulation, SMTP, Resend)                  |  |
|  |      |                                                                                |  |
|  |      +---> [dispatch_tracker.py] (Thread-safe Singleton Data Layer)                   |  |
|  |               |                                                                       |  |
|  |               v                                                                       |  |
|  |     [storage/dispatches.db] (SQLite: leads, jobs, drafts, history, idempotency)       |  |
|  +---------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------+
```

---

## 2. Codebase Folder Structures

### 2.1 Frontend Folder Structure (`src/`)
```
src/
├── App.tsx                     # Primary shell, view router ('agent'|'discovery'|'history'|'env')
├── index.css                   # Global dark-themed styling, variables, layout definitions
├── main.tsx                    # React DOM entrypoint
├── components/
│   ├── AgentDetail.tsx         # Agent 1 workspace: research execution, presets, crawl log
│   ├── EnvironmentStatus.tsx   # Diagnostic status of Python, Playwright, SQLite, and network
│   ├── Header.tsx              # Application header with backend health pill and agent context
│   ├── icons.tsx               # Minimalist inline SVG icons (feather-style)
│   ├── LeadDiscovery.tsx       # Automated discovery UI: prompt input, job status, lead tables
│   ├── OutreachConsole.tsx     # Draft review, edit modal, approval gate, and dispatch controls
│   ├── OutreachHistory.tsx     # Dispatched and drafted outreach audit table, search, CSV export
│   └── Sidebar.tsx             # Navigation drawer, agent list selector, status badges
├── hooks/
│   └── useBackendStatus.ts     # Health polling hook (GET /health every 5000ms)
├── services/
│   └── api.ts                  # Typed client service for all FastAPI REST endpoints
└── types/
    └── agent.ts                # TypeScript interfaces (LeadRecord, DiscoveryJob, OutreachDraft, etc.)
```

### 2.2 Backend Folder Structure (`backend/`)
```
backend/
├── dispatch_tracker.py         # Thread-safe SQLite persistence layer and idempotency registry
├── env_loader.py               # Robust root .env parser with fallback search paths
├── exporter.py                 # RFC 4180 CSV serializer for lead records
├── main.py                     # FastAPI application definition, CORS middleware, API route handlers
├── models.py                   # Pydantic v2 schemas for all requests, responses, and records
├── requirements.txt            # Python dependencies (fastapi, uvicorn, httpx, playwright, etc.)
├── start-backend.ps1           # PowerShell backend launcher (port 8000, loop none, reload)
├── __init__.py                 # Package marker
├── providers/
│   ├── base.py                 # Abstract BaseResearchProvider interface
│   ├── email_dispatcher.py     # Outbound dispatch engine (Simulation, SMTP, Resend)
│   ├── llm.py                  # AI drafting providers (Template, Ollama, OpenAI)
│   ├── mock.py                 # MockResearchProvider generating simulated demo records
│   ├── playwright_scraper.py   # Headless Chromium crawler, robots.txt evaluator, contact regex
│   ├── __init__.py             # Package marker
│   └── search/
│       ├── base.py             # SearchProvider abstract base class and SearchResult dataclass
│       ├── bing_search.py      # Azure Bing Web Search API provider
│       ├── directory_search.py # 23-entry static public business registry fixture
│       ├── duckduckgo_search.py# Live HTML DuckDuckGo search parser with rate limiter
│       ├── factory.py          # Provider factory and resolution logic
│       ├── google_search.py    # Google Custom Search JSON API provider
│       ├── tavily_search.py    # Tavily AI Search API provider
│       └── __init__.py         # Package marker
├── services/
│   ├── lead_discovery.py       # LeadDiscoveryService singleton, pipeline runner, scoring engine
│   └── __init__.py             # Package marker
└── tests/
    ├── test_lead_discovery.py  # Unit tests for query generation, plan parser, directory search
    ├── test_lead_quality.py    # Tests for industry taxonomy and lead relevance scoring
    ├── test_lead_transfer_workflow.py # Tests for discovered lead to draft conversion
    ├── test_live_solar_discovery.py   # Regression tests for Lahore solar data fixtures
    ├── test_outreach.py        # Tests for drafting, approval safety gate, duplicate prevention
    ├── test_outreach_history.py# Tests for history pagination, status filtering, CSV export
    ├── test_playwright_provider.py # Tests for URL validation, robots.txt parser, HTML extraction
    └── test_research_api.py    # FastAPI endpoint integration tests
```

### 2.3 Desktop Shell Folder Structure (`src-tauri/`)
```
src-tauri/
├── build.rs                    # Tauri cargo build script
├── Cargo.toml                  # Rust dependencies (tauri v2, tauri-plugin-opener, serde)
├── tauri.conf.json             # Tauri configuration (window size, CSP, bundle metadata)
├── capabilities/
│   └── default.json            # Tauri v2 security capability manifest (core:default, opener:default)
└── src/
    ├── lib.rs                  # Rust plugin initialization and get_agentdesk_status command
    └── main.rs                 # Desktop application entrypoint
```

---

## 3. Component Deep Dive & Data Flow

### 3.1 Request & Execution Flow

```
1. Operator Input:
   Operator types natural language prompt in LeadDiscovery UI
   |
2. Plan Formulation:
   POST /api/discovery/plan -> parse_natural_language_request()
   Returns structured DiscoveryPlan (industry, location, keywords, target_count)
   |
3. Job Initiation:
   POST /api/discovery/jobs -> LeadDiscoveryService.start_job()
   Job record created in SQLite (status='pending')
   Non-blocking asyncio.create_task launched in background
   |
4. Search Execution:
   get_search_provider() resolves active provider (e.g., DuckDuckGo)
   Queries executed (e.g. "solar installation Lahore", "commercial industrial solar EPC Lahore")
   Candidate URLs gathered and deduplicated by canonical domain
   |
5. Public Source Crawl & Inspection:
   Playwright / httpx inspects candidate website homepage
   Robots.txt verified; domain pacing delay enforced (0.4s)
   HTML parsed: Schema.org name, meta description, regex emails, regex phones
   Subpage crawled (/about or /contact) if email is absent
   |
6. Fact Grounding & Classification:
   classify_company_industry() tests text against regex taxonomy
   calculate_lead_relevance() generates dynamic 0.10–0.98 score
   DiscoveredLeadRecord persisted to SQLite 'discovered_leads' table
   |
7. Transfer to Outreach:
   POST /api/discovery/transfer-outreach -> converts lead into OutreachDraft
   Subject and body synthesized strictly from grounded facts
   Draft persisted to 'outreach_drafts' table (status='drafted')
   |
8. Human-in-the-Loop Approval:
   Operator inspects draft in OutreachConsole
   Edits subject/body if needed (PUT /api/outreach/drafts/{id})
   Approves draft (POST /api/outreach/drafts/{id}/approve)
   Draft status updated to 'approved'
   |
9. Dispatch Execution:
   Operator confirms send (POST /api/outreach/send)
   Safety gate enforces: approved == True AND has_verified_email == True
   Duplicate-send protection claims lock (SHA-256 content hash check)
   Dispatched via configured provider (Simulation / SMTP / Resend)
   Dispatched record logged to 'dispatches.db' ('outreach_history' table)
```

---

## 4. API Routes Inventory

All routes are hosted on the local FastAPI instance (`http://127.0.0.1:8000`).

| Route | HTTP Method | Handler Function | Purpose | Input Schema | Output Schema |
| :--- | :---: | :--- | :--- | :--- | :--- |
| `/health` | GET | `health_check()` | Service health & active provider info | None | JSON |
| `/api/research/leads` | POST | `research_leads()` | Manual lead research via Mock or Playwright | `ResearchRequest` | `ResearchResponse` |
| `/api/research/export-csv` | POST | `export_leads_csv()` | Streams RFC 4180 CSV of research leads | `CSVExportRequest` | CSV stream |
| `/api/outreach/providers` | GET | `get_outreach_providers()` | Available AI drafting providers & dispatch status | None | `ProvidersResponse` |
| `/api/outreach/draft` | POST | `draft_outreach()` | Generates AI email drafts for leads | `OutreachDraftRequest` | `OutreachDraftResponse` |
| `/api/outreach/send` | POST | `send_outreach()` | Explicit human approval gate & dispatch | `SendOutreachRequest` | `SendOutreachResponse` |
| `/api/outreach/history` | GET | `get_outreach_history()` | Paginated & filtered outreach history | Query params | `OutreachHistoryResponse` |
| `/api/outreach/history/export-csv` | GET | `export_outreach_history_csv()` | Streams CSV of filtered outreach history | Query params | CSV stream |
| `/api/discovery/plan` | POST | `generate_discovery_plan()` | Parses prompt into structured DiscoveryPlan | `DiscoveryPlanRequest` | `DiscoveryPlan` |
| `/api/discovery/providers` | GET | `get_discovery_providers()` | Lists status of search discovery sources | None | `SearchProvidersResponse` |
| `/api/discovery/jobs` | POST | `create_discovery_job()` | Queues & starts background discovery job | `DiscoveryJobCreateRequest` | `DiscoveryJob` |
| `/api/discovery/jobs/{job_id}` | GET | `get_discovery_job()` | Retrieves job status and discovered leads | Path: `job_id` | `DiscoveryJobResponse` |
| `/api/discovery/jobs/{job_id}/cancel` | POST | `cancel_discovery_job()` | Cooperatively halts running discovery job | Path: `job_id` | `DiscoveryJob` |
| `/api/discovery/jobs/{job_id}/leads` | GET | `list_discovered_leads()` | Paginated, filtered discovered leads | Path & Query params | `DiscoveredLeadsResponse` |
| `/api/discovery/jobs/{job_id}/export-csv` | GET | `export_discovered_leads_csv()`| Streams CSV of job discovered leads | Path & Query params | CSV stream |
| `/api/discovery/transfer-outreach` | POST | `transfer_leads_to_outreach()` | Converts discovered leads to outreach drafts | `TransferToOutreachRequest` | `LeadTransferResponse` |
| `/api/outreach/drafts` | GET | `list_outreach_drafts()` | Lists paginated drafts by status/search | Query params | `OutreachDraftsListResponse` |
| `/api/outreach/drafts/{draft_id}` | GET | `get_outreach_draft()` | Fetches individual draft by ID | Path: `draft_id` | `OutreachDraft` |
| `/api/outreach/drafts/{draft_id}` | PUT | `update_outreach_draft()` | Edits subject, body, or recipient | Path & `UpdateDraftRequest` | `OutreachDraft` |
| `/api/outreach/drafts/{draft_id}/approve` | POST | `approve_outreach_draft()` | Marks draft as approved (requires email) | Path: `draft_id` | `OutreachDraft` |
| `/api/outreach/drafts/{draft_id}/unapprove` | POST | `unapprove_outreach_draft()` | Reverts approved draft back to drafted | Path: `draft_id` | `OutreachDraft` |
| `/api/outreach/drafts/{draft_id}/discard` | POST | `discard_outreach_draft()` | Rejects/discards outreach draft | Path & `DiscardDraftRequest`| `OutreachDraft` |
| `/api/outreach/drafts/{draft_id}` | DELETE | `delete_outreach_draft()` | Deletes draft record from SQLite | Path: `draft_id` | JSON status |

---

## 5. Architectural Deficiencies & Coupling Analysis

1. **Frontend-Backend Direct Coupling:** The frontend makes raw HTTP calls to `http://127.0.0.1:8000` hardcoded in `api.ts`. There is no proxying through Tauri IPC (`invoke()`), meaning the webview must have unrestricted loopback networking capabilities.
2. **Missing Tauri Process Supervision:** Tauri is entirely uncoupled from the Python backend process. There is no `externalBin` sidecar definition in `src-tauri/tauri.conf.json`. If the user opens the compiled desktop app without manually executing `start-backend.ps1` in PowerShell, the frontend fails with a connection error.
3. **Absence of a Formal Agent Abstraction:** While the UI depicts four distinct agents, the backend code has no `Agent` base class, registry, or runtime orchestrator. The "Lead Researcher" is implemented as hardwired endpoints (`/api/research/*`, `/api/discovery/*`, `/api/outreach/*`).
4. **Redundant Persistence Layers:** Drafts are stored in two separate tables in `dispatches.db`: `draft_records` (storing raw JSON strings) and `outreach_drafts` (storing relational columns plus `raw_json`). Additionally, an in-memory dictionary (`DRAFT_REGISTRY`) is maintained in `backend/main.py`.
5. **No Database Migration Framework:** Schema is initialized using inline `CREATE TABLE IF NOT EXISTS` blocks in `dispatch_tracker.py`. There is no Alembic or schema version tracking table. Any schema modification requires error-prone inline SQL checks.
6. **Lack of Authentication/Authorization:** The FastAPI backend does not implement Bearer token, session cookie, or API key validation for incoming requests. Any program on the host OS can communicate with `127.0.0.1:8000`.

