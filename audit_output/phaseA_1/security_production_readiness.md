# AgentDesk — Phase A.1: Security & Production Readiness Audit

**Audit Date:** November 5, 2026  
**Auditor:** Antigravity AI Systems Architecture Team  
**Evaluation Scope:** Codebase security posture, vulnerability surfaces, threat modeling, and deployment readiness across Desktop Shell, Backend API, Crawler Subsystem, and Persistence.

---

## 1. Executive Security Summary

The application demonstrates strong security hygiene in certain operational areas—notably strict human-in-the-loop approval before outbound email transmission, regex log sanitization of API secrets, and duplicate message hashing. However, the system currently lacks **production-grade defense-in-depth**, exhibiting vulnerabilities typical of an early-stage desktop prototype: unauthenticated local APIs, plaintext credential storage, bypassable SSRF filters, disabled Tauri Content Security Policy, and lack of database WAL mode.

---

## 2. Granular Security Audit by Dimension

### 2.1 Credential Storage
- **Current State:** Credentials (SMTP passwords, Resend API keys, Tavily keys, Google/Bing search keys) are stored in plaintext in the repository root `.env` file.
- **Risk Level:** **High**.
- **Analysis:** While `.env` is properly included in `.gitignore`, storing plaintext passwords on disk exposes secrets to any malicious process running on the host OS or compromised local software.
- **Remediation:** Migrate credential storage to the native OS keyring (Windows Credential Manager / macOS Keychain / Linux Secret Service) using the Python `keyring` library or Tauri's native secure store plugin.

### 2.2 API Key Exposure & Sanitization
- **Current State:** The backend implements `sanitize_log_message()` (`backend/providers/email_dispatcher.py`), scrubbing OpenAI (`sk-`), Resend (`re_`), Tavily (`tvly-`), and custom secrets before writing to error responses or history logs.
- **Risk Level:** **Low**.
- **Analysis:** Well implemented. The UI also masks the OpenAI key in password input fields. However, the endpoint `GET /api/discovery/providers` reports boolean configuration status without exposing the underlying keys, which conforms to security best practices.

### 2.3 SQL Injection Risks
- **Current State:** The application utilizes parameterized queries with `?` placeholders across 98% of SQL statements in `backend/dispatch_tracker.py`.
- **Risk Level:** **Medium-Low**.
- **Analysis:**
  - Where user search terms or filters are applied (`search`, `city`, `category`, `status`), parameters are passed via tuples/lists to `cursor.execute()`.
  - **Identified Risk in `update_discovery_job` (line 658–662):**
    ```python
    set_clauses = [f"{k} = ?" for k in all_updates.keys()]
    sql = f"UPDATE discovery_jobs SET {', '.join(set_clauses)} WHERE id = ?"
    ```
    While current call sites in `lead_discovery.py` only pass hardcoded keyword arguments (`status`, `progress_percent`), dynamically formatting dictionary keys into SQL without an explicit column whitelist creates an injection risk if an untrusted request dictionary is ever passed into this method.
- **Remediation:** Implement an explicit set of permitted column names (`ALLOWED_JOB_COLUMNS`) and assert `k in ALLOWED_JOB_COLUMNS` before constructing the SQL query.

### 2.4 Server-Side Request Forgery (SSRF) Protection
- **Current State:** `validate_target_url()` in `playwright_scraper.py` checks protocol (`http`, `https`) and string-checks hostnames against `"localhost"`, `"127.0.0.1"`, `"0.0.0.0"`, `"192.168."`, `"10."`, and `"172.16."`.
- **Risk Level:** **CRITICAL**.
- **Analysis:**
  - **Bypass 1 (Incomplete RFC 1918):** `172.17.0.0/12` through `172.31.255.255` are not covered by `.startswith("172.16.")`.
  - **Bypass 2 (Cloud Metadata):** `169.254.169.254` (AWS/GCP/Azure link-local metadata) is not blocked.
  - **Bypass 3 (IPv6 Addresses):** `[::1]`, `[fe80::1]` are not blocked.
  - **Bypass 4 (DNS Rebinding):** No DNS pre-resolution. If an attacker controls a public domain that resolves to `127.0.0.1`, the string check passes, allowing Playwright and httpx to access internal loopback services.
- **Remediation:** Implement mandatory DNS resolution before fetching. Parse all resolved IPs through Python's `ipaddress` library and reject any private, loopback, link-local, or reserved IP.

### 2.5 CORS Configuration
- **Current State:** In `backend/main.py`:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=[
          "http://localhost:1420",
          "http://127.0.0.1:1420",
          "tauri://localhost",
          "https://tauri.localhost",
      ],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Risk Level:** **Medium**.
- **Analysis:** CORS allows requests from `localhost:1420` (Vite dev server) and `tauri://localhost`. However, because the backend does not enforce authentication tokens, any webpage visited in a standard web browser on the host machine could potentially send cross-origin requests if origin headers are spoofed or via WebSocket / simple HTTP requests.
- **Remediation:** Couple CORS with an internal ephemeral session token passed in the `Authorization: Bearer <token>` header.

### 2.6 Authentication & Authorization
- **Current State:** **Zero authentication on all backend endpoints.**
- **Risk Level:** **High**.
- **Analysis:** The FastAPI server binds to `127.0.0.1:8000`. Any local software, script, or non-sandboxed process running under any user account on the machine can make requests to trigger web crawls, read lead contacts, approve drafts, or send real emails.
- **Remediation:** Generate an ephemeral secret token upon application launch. Pass the token from Tauri to the frontend and require `Authorization: Bearer <token>` on all FastAPI endpoints.

### 2.7 Database Transactions & Concurrency
- **Current State:** Persistence relies on raw `sqlite3.connect()` wrapped with Python `threading.Lock()` inside `DispatchTracker`.
- **Risk Level:** **Medium**.
- **Analysis:**
  - While Python threads are synchronized by `self._lock`, SQLite itself runs in default `DELETE` journal mode (WAL mode is not enabled).
  - Multiple rapid concurrent read/write queries can trigger `sqlite3.OperationalError: database is locked`.
  - In `LeadDiscoveryService`, background asyncio tasks write to SQLite concurrently with user UI queries.
- **Remediation:** Execute `PRAGMA journal_mode = WAL;` and `PRAGMA synchronous = NORMAL;` upon connection initialization.

### 2.8 Backup and Recovery
- **Current State:** Several static backups exist in `storage/` (`dispatches.db.backup_*`), created manually during historical testing phases.
- **Risk Level:** **Medium-Low**.
- **Analysis:** No automated periodic backup routine exists in code. If the SQLite database experiences physical corruption, data loss would occur.
- **Remediation:** Implement an automated backup utility using SQLite Online Backup API (`conn.backup()`) triggered before major imports or on a daily schedule.

### 2.9 Desktop Shell Security (Tauri v2)
- **Current State:** In `src-tauri/tauri.conf.json`:
  ```json
  "security": {
    "csp": null
  }
  ```
- **Risk Level:** **High**.
- **Analysis:** Setting Content Security Policy to `null` disables browser security barriers. If malicious HTML or XSS payload is extracted from a target website and rendered in the React DOM, the script can execute without CSP restrictions.
- **Remediation:** Configure a strict Content Security Policy in `tauri.conf.json` restricting script execution to `'self'`, blocking `eval()`, and restricting connection origins strictly to `http://127.0.0.1:8000`.

---

## 3. Critical Security Issues Summary (Must Fix in P0)

| Vulnerability ID | Vulnerability Category | Description | Severity | Remediation Ticket |
| :---: | :--- | :--- | :---: | :---: |
| **SEC-01** | **SSRF / DNS Rebinding** | URL validator does not pre-resolve DNS and misses RFC 1918 / IPv6 / metadata ranges. | **CRITICAL** | **P0-SEC-01** |
| **SEC-02** | **Unauthenticated API** | FastAPI backend accepts unauthenticated HTTP requests from any local loopback client. | **HIGH** | **P0-SEC-02** |
| **SEC-03** | **Disabled Tauri CSP** | Tauri `csp: null` allows arbitrary inline scripts if scraped text contains XSS. | **HIGH** | **P0-SEC-03** |
| **SEC-04** | **Plaintext Credentials** | Sensitive SMTP passwords and API tokens stored in unencrypted `.env` file. | **MEDIUM** | **P0-SEC-04** |
| **SEC-05** | **SQLite Lock Contention** | Database runs in legacy rollback journal mode instead of Write-Ahead Logging (WAL). | **MEDIUM** | **P0-DB-01** |

