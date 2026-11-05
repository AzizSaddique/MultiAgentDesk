# AgentDesk — Phase A.2.1: Authentication Bypass Audit

**Audit Objective:** Independent verification of local bearer token authentication, middleware coverage, timing safety, IPC token extraction, and cross-origin boundaries.  
**Audited Files:**
- `backend/security/auth.py`
- `backend/main.py`
- `src/services/api.ts`
- `src-tauri/src/lib.rs`
- `vite.config.ts`
**Date:** 2026-11-05

---

## 1. Authentication Audit Matrix

| Verification Item | Status | Verification Details |
| :--- | :---: | :--- |
| **1. Every sensitive endpoint requires auth?** | **VERIFIED** | Middleware intercepts all incoming requests to `/api/*`. Raw unauthenticated requests return 401. |
| **2. Can any route bypass middleware?** | **VERIFIED** | `@app.middleware("http")` wraps ASGI request pipeline. Tested `/health/`, `//health`, and path traversals; all return 401. |
| **3. Secure randomness for tokens?** | **VERIFIED** | Uses `secrets.token_hex(32)` providing 256 bits of CSPRNG entropy. |
| **4. Constant-time comparison?** | **VERIFIED** | Uses `secrets.compare_digest(candidate, expected)`. Resists timing attacks. |
| **5. Token file permissions restrictive?** | **PARTIAL** | POSIX `0o600` is applied on Linux/macOS. Skipped on Windows (`os.name == 'nt'`); lacks NTFS ACL hardening. |
| **6. Token never returned in normal API?** | **VERIFIED** | Zero endpoints in `backend/main.py` return the token. Public `/health` audited: contains no tokens or internal paths. |
| **7. Token not logged or in diagnostics?** | **VERIFIED** | Zero logger statements record the token. Lead diagnostics exclude authorization headers. |
| **8. Tauri IPC retrieval restricted?** | **PARTIAL** | `get_session_token` command is registered in `main` window. However, `tauri.conf.json` has `"csp": null`. |
| **9. Frontend requests consistently attach token?** | **VERIFIED** | All 22 `/api/*` fetch calls in `src/services/api.ts` use `authFetch()`. |
| **10. Missing, malformed, invalid tokens rejected?** | **VERIFIED** | Missing header, `Basic` scheme, empty token, and tampered hex string all return 401. |
| **11. CORS, OPTIONS, /health bypass?** | **VERIFIED** | `OPTIONS` requests do not execute route handlers. `/health` is read-only. |
| **12. Backend network binding safe?** | **VERIFIED** | Backend binds explicitly to `127.0.0.1:8000`, not `0.0.0.0`. Localhost loopback only. |

*(Note: In accordance with audit safety rules, the active session token value is never printed or exposed in this report.)*

---

## 2. In-Depth Analysis: Middleware Architecture & Route Security

### 2.1 Middleware Execution Flow
In `backend/main.py` (lines 160–205):
```python
@app.middleware("http")
async def enforce_bearer_auth(request: Request, call_next):
    # Allow CORS preflight requests
    if request.method == "OPTIONS":
        return await call_next(request)

    # Public health check endpoint
    if request.url.path == "/health":
        return await call_next(request)

    # Public OpenAPI documentation endpoints
    if request.url.path in ("/docs", "/redoc", "/openapi.json"):
        return await call_next(request)

    # All other endpoints require Bearer token authentication
    auth_header = request.headers.get("Authorization")
    ...
```

### 2.2 Path Traversal & Normalization Testing
To verify whether URL path anomalies could bypass the middleware:
1. `GET /health/`: Returns `401 Unauthorized` (does not match `== "/health"`).
2. `GET //health`: Returns `401 Unauthorized`.
3. `GET /health/../api/discovery/providers`: Returns `401 Unauthorized`.
4. `OPTIONS /api/research/leads`: Returns `405 Method Not Allowed` with empty body (does not trigger `POST` handler).

Conclusion: The middleware routing structure is solid. No bypasses were discovered through path normalization anomalies.

---

## 3. Local Development & Cross-Origin Exposure (Finding ADV-SEC-04)

### 3.1 Mechanism
In `vite.config.ts` (lines 13–27):
```typescript
function authDevPlugin(): Plugin {
  return {
    name: "agentdesk-auth-dev",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url === "/__agentdesk_auth_token") {
          const tokenFile = path.resolve(__dirname, "storage/.session_token");
          if (fs.existsSync(tokenFile)) {
            const token = fs.readFileSync(tokenFile, "utf-8").trim();
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ token }));
            return;
          }
```

### 3.2 Threat Vector
When developers execute `npm run dev`:
1. Vite spins up an HTTP server on `http://localhost:1420`.
2. Vite's default configuration enables cross-origin resource sharing (`server.cors: true`).
3. If the developer browses an untrusted website in Chrome or Edge while `npm run dev` is running, the malicious site can issue a cross-origin `fetch("http://localhost:1420/__agentdesk_auth_token")`.
4. Because the middleware performs no origin check, it serves the active token.
5. The malicious script can now interact with the FastAPI backend on `http://127.0.0.1:8000/api/*`.

### 3.3 Production Scope
This vector is confined strictly to development server mode (`npm run dev`). Production packaged builds do not run the Vite dev server. However, since AgentDesk operators frequently run local dev environments during evaluation, hardening the dev endpoint is strongly recommended.

---

## 4. Desktop Boundary & IPC Security (Findings ADV-SEC-06 & ADV-SEC-07)

### 4.1 Windows File System ACLs (`storage/.session_token`)
In `backend/security/auth.py`:
```python
if hasattr(os, "chmod") and os.name != "nt":
    os.chmod(token_file, 0o600)
```
On Windows workstations, POSIX permission bits are ignored. If AgentDesk is run on a shared Windows computer with multiple non-administrator local user profiles, other users with directory traversal privileges could read `.session_token`.
Remediation: Invoke Windows `icacls storage\.session_token /inheritance:r /grant:r "%USERNAME%:(R,W)"` to restrict DACLs.

### 4.2 Content Security Policy (CSP) in Tauri
In `src-tauri/tauri.conf.json`:
```json
"security": {
  "csp": null
}
```
Setting `csp: null` leaves the webview without browser-enforced script execution boundaries. If malicious script content is injected via untrusted lead data (e.g. stored in `dispatches.db`), the script has full access to the Tauri IPC bridge and can invoke `get_session_token`.
Remediation: Enforce a strict CSP prohibiting unsafe inline scripts and limiting network connections to `127.0.0.1:8000`.

