# AgentDesk — Phase A: Master Acceptance Criteria & Quality Gates

**Document Purpose:** Definitive, testable criteria for validating the completion of Phase A development milestones before production deployment or live outreach execution.  
**Audit Reference:** Phase A.1 Technical Audit  
**Date:** November 5, 2026  
**Auditor:** Antigravity AI Systems Architecture Team  

---

## 1. Quality Gate Framework

Phase A development must pass five sequential quality gates:

```
[Gate 0: Foundation & Security] 
         | Passed
         v
[Gate 1: Conversion Engine & Tech Auditor]
         | Passed
         v
[Gate 2: Agency Operations & Sequences]
         | Passed
         v
[Gate 3: SaaS Multi-Tenancy & Billing]
         | Passed
         v
[Gate 4: IoT & Advanced Telemetry]
```

No feature from a downstream tier may be released to production until the preceding gate has been verified with 100% test passage and security approval.

---

## 2. Gate 0: Foundation, Security & Packaging Criteria (P0)

### 2.1 Security & SSRF Protection (`P0-SEC-01`)
- [ ] **DNS Pre-Resolution:** All target URLs submitted to the scraper or discovery engine must undergo DNS pre-resolution via `socket.getaddrinfo()` before opening any socket connection.
- [ ] **Complete Private Range Blocking:** All resolved IP addresses must be verified against `ipaddress.ip_address()`. Requests must be aborted with HTTP 422 if the IP belongs to:
  - `127.0.0.0/8` (Loopback)
  - `10.0.0.0/8` (Private Class A)
  - `172.16.0.0/12` (Private Class B — covering `172.16.0.0` through `172.31.255.255`)
  - `192.168.0.0/16` (Private Class C)
  - `169.254.0.0/16` (Link-Local / Cloud Metadata)
  - `::1`, `fe80::/10`, `fc00::/7` (IPv6 Loopback and Unique Local)
- [ ] **Redirect Interception:** Playwright route listeners must intercept all HTTP 3xx redirects and validate intermediate host IPs against the SSRF filter before navigation continues.

### 2.2 Local API Authentication (`P0-SEC-02`)
- [ ] **Session Token Generation:** FastAPI must generate an ephemeral 256-bit cryptographically secure session token on startup.
- [ ] **Bearer Header Enforcement:** Every endpoint under `/api/*` (excluding `/health`) must require `Authorization: Bearer <session_token>`.
- [ ] **Rejection of Unauthenticated Requests:** Unauthenticated requests or requests from unauthorized origins must return HTTP 401 Unauthorized within 10ms.
- [ ] **Frontend Handshake:** The Tauri desktop shell must securely pass the session token to the React frontend at launch.

### 2.3 Desktop Shell Supervision & CSP (`P0-TAURI-01`)
- [ ] **Managed Sidecar:** Launching the Tauri desktop executable must automatically spawn the Python FastAPI backend as a child process.
- [ ] **Clean Process Termination:** Closing the desktop window must terminate the backend process with zero orphaned Python or Chromium instances left running.
- [ ] **Strict CSP:** `tauri.conf.json` must enforce a Content Security Policy restricting script execution to `'self'`, blocking `eval()`, and restricting connection endpoints strictly to `http://127.0.0.1:8000`.

### 2.4 Database Safety & Concurrency (`P0-DB-01`)
- [ ] **WAL Mode Active:** Inspecting the database must confirm `PRAGMA journal_mode` = `'wal'` and `PRAGMA synchronous` = `1` (NORMAL).
- [ ] **Foreign Key Enforcement:** All database connections must execute `PRAGMA foreign_keys = ON;`. Attempting to insert an orphan lead with an invalid `job_id` must immediately raise a foreign-key constraint violation.
- [ ] **Zero Lock Deadlocks:** 50 concurrent simulated writes executed alongside 50 concurrent reads must complete with 0 `database is locked` errors.

### 2.5 Live Email Deliverability Verification (`P0-VERIF-01`)
- [ ] **DNS MX Check:** The system must query DNS MX records for all prospective lead domains. Domains with 0 MX records must be marked `no_mx_record` and receive 0 deliverability points.
- [ ] **SMTP Handshake Check:** Discovered emails must undergo a non-sending SMTP handshake (`HELO` -> `MAIL FROM:<>` -> `RCPT TO:<email>`).
- [ ] **Zero Delivery Guarantee:** Handshake verification must disconnect immediately after `RCPT TO` and never issue the `DATA` command.

---

## 3. Gate 1: Sales Conversion Engine Criteria (P1)

### 3.1 100-Point Explainable Lead Scoring (`P1-SCORE-01`)
- [ ] **Strict Weight Distribution:** Every lead must be evaluated across the 6 dimensions:
  - Business Relevance: 0–25 points
  - Technical Need: 0–25 points
  - Decision-Maker Accessibility: 0–15 points
  - Buying Signals: 0–15 points
  - Contact Verification: 0–10 points
  - Evidence Rigor: 0–10 points
- [ ] **Zero Imputation Invariant:** Any missing evidence field (e.g., missing executive name, missing tech audit) must receive strictly 0 points.
- [ ] **Transparent Explanation:** The UI must display an audit tooltip explaining exact point deductions and awards for all 6 categories.
- [ ] **Tier Assignment:**
  - Tier 1: 75–100 points
  - Tier 2: 50–74 points
  - Tier 3: <50 points

### 3.2 Automated Website & Technology Auditor (`P1-AUDIT-01`)
- [ ] **Execution Speed:** Complete website audit must execute and return structured JSON in under 10.0 seconds.
- [ ] **Tech Stack Identification:** Must accurately detect CMS (WordPress, Shopify, Webflow), web servers (Nginx, Apache), frontend libraries (React, Vue, jQuery), and tracking pixels (GA4, Meta).
- [ ] **Core Web Vitals:** Must report TTFB (ms), LCP (seconds), CLS, and total payload size (KB).
- [ ] **Agency Proposal Hook:** Generates at least 2 grounded modernization gaps that are automatically injected into outreach draft proposals.

### 3.3 Relational CRM Pipeline Core (`P1-CRM-01`)
- [ ] **Data Normalization:** Verified companies exist as unique records in `organizations`; multiple stakeholders can be linked under `contacts`.
- [ ] **Kanban Board:** Frontend displays an interactive CRM Kanban board with 6 stages (`Lead`, `Contacted`, `Replied`, `Demo Scheduled`, `Closed Won`, `Closed Lost`).
- [ ] **Global Suppression:** Dispatches to any email or domain present in `suppression_list` must be blocked at both the draft generation and transmission layers.

### 3.4 Bidirectional Gmail API Integration (`P1-EMAIL-01`)
- [ ] **OAuth2 Flow:** Operator can connect their Gmail account via 1-click browser authorization without exposing client secrets or entering passwords in plaintext.
- [ ] **OS Keyring Storage:** OAuth2 tokens must be stored in the native OS keychain via Python `keyring`.
- [ ] **Threading Headers:** All outbound emails sent via Gmail API must include a unique `Message-ID` stored in the database.
- [ ] **Automatic Reply Matching:** Inbound polling must match `In-Reply-To` and `References` headers, updating the associated CRM opportunity stage to "Replied" within 5 minutes of receipt.

---

## 4. Gate 2: Agency Operations Criteria (P2)

### 4.1 Client Audit Report Generator (`P2-AGY-01`)
- [ ] **Branded Export:** Must generate professional, white-labeled PDF and standalone HTML audit reports from website audit datasets.
- [ ] **Executive Presentation:** Reports must include an overall Letter Grade (A–F), visual performance breakdowns, security warnings, and proposed software modernization roadmaps.

### 4.2 Multi-Touch Sales Sequences (`P2-SEQ-01`)
- [ ] **Sequence Cadence:** Supports automated 3-step outreach cadences (Initial Email -> 3-day pause -> Follow-up 1 -> 4-day pause -> Follow-up 2).
- [ ] **Auto-Halt on Reply:** Any incoming reply or manual opt-out must immediately cancel all subsequent scheduled follow-up steps for that contact.

---

## 5. Gate 3: SaaS Expansion Criteria (P3)

### 5.1 Workspace Isolation & Roles (`P3-SAAS-01`)
- [ ] **Multi-Tenant Schema:** All database records must include a `workspace_id` foreign key.
- [ ] **Role Permissions:** Enforces RBAC permissions:
  - `Admin`: Full access, billing, user management.
  - `Operator`: Discovery, draft editing, manual approvals, CRM updates.
  - `Viewer`: Read-only reporting and dashboard access.

### 5.2 Stripe Billing Integration (`P3-BILL-01`)
- [ ] **Subscription Gating:** Limits discovery search credits and active CRM contacts based on active Stripe subscription tier.
- [ ] **Webhook Handling:** Stripe webhooks (`customer.subscription.deleted`, `invoice.payment_succeeded`) accurately adjust account entitlement quotas.

---

## 6. Gate 4: Advanced IoT & Robotics Criteria (P4)

### 6.1 Industrial Telemetry Ingestion (`P4-IOT-01`)
- [ ] **MQTT Connectivity:** Connects to standard industrial MQTT brokers (e.g. Mosquitto, AWS IoT Core) with TLS authentication.
- [ ] **Inverter Telemetry:** Ingests live power output (kW), daily energy (kWh), and fault codes from solar inverters, displaying live status in the AgentDesk dashboard.

---

## 7. Rollback Protocol & Production Invariants

If any quality gate fails during implementation:
1. **Immediate Rollback:** Database migrations must support atomic rollback (`down()` scripts).
2. **Pristine Lead Invariant:** The existing 149 production leads and 6 discovery jobs must never be overwritten, modified, or deleted.
3. **Outreach Blackout:** If an unhandled error occurs during email dispatch, the transaction must rollback, the in-flight lock must be released, and no partial email may be transmitted.

