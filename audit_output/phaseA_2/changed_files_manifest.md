# AgentDesk — Phase A.2: Changed Files Manifest

**Phase:** Phase A.2: Critical Security Foundation (P0-SEC-01 & P0-SEC-02)  
**Date:** 2026-11-05  
**Total Modified Files:** 6  
**Total Created Files:** 5 (source & tests) + 5 (audit reports)  
**Total Deleted Files:** 0  

---

## 1. Summary of Changes

| Path | Status | Purpose | Lines Changed |
| :--- | :--- | :--- | :--- |
| `backend/security/__init__.py` | **Created** | Security package initializer exporting URL validator and auth utilities | +16 |
| `backend/security/url_validator.py` | **Created** | Comprehensive SSRF protection service (IP range classification, DNS pre-resolution, redirect inspector) | +291 |
| `backend/security/auth.py` | **Created** | Cryptographic session token generation, storage, constant-time verification, and FastAPI dependency | +120 |
| `backend/main.py` | **Modified** | Wired Bearer authentication middleware, public health preservation, auth imports | +47, -1 |
| `backend/providers/playwright_scraper.py` | **Modified** | Replaced naive validator with `backend.security.url_validator`, added browser route abortion | +22, -8 |
| `backend/services/lead_discovery.py` | **Modified** | Integrated `safe_fetch_get` and `SSRFSecurityError` handling for primary candidate and subpage fetching | +37, -35 |
| `src-tauri/src/lib.rs` | **Modified** | Added `get_session_token` Tauri IPC command to safely pass token to frontend | +26, -1 |
| `vite.config.ts` | **Modified** | Added `authDevPlugin()` middleware serving `/__agentdesk_auth_token` for local web development | +28, -2 |
| `src/services/api.ts` | **Modified** | Added `getSessionToken()`, `setSessionToken()`, and `authFetch()`; attached Bearer auth to all 22 API calls | +74, -22 |
| `backend/tests/conftest.py` | **Created** | Pytest fixture wrapping `TestClient` to auto-inject Bearer auth for full regression test compatibility | +24 |
| `backend/tests/test_ssrf_protection.py` | **Created** | 38 automated test cases covering all SSRF vectors, prohibited IPs, DNS rebinding, and redirects | +224 |
| `backend/tests/test_authentication.py` | **Created** | 13 automated test cases covering public `/health`, 401 on protected routes, scheme validation, token verification | +152 |
| `storage/.session_token` | **Created** | 256-bit cryptographically generated session token (persisted on disk) | 1 token |

---

## 2. File-by-File Detailed Manifest

### 2.1 `backend/security/url_validator.py` (New File)
- **Functions Defined:**
  - `is_prohibited_ip(ip)`: Classifies loopback, private, link-local, cloud metadata, carrier-grade NAT, multicast, unspecified, reserved, and IPv4-mapped IPv6 ranges.
  - `resolve_domain_ips(hostname, custom_resolver)`: Performs pre-connection DNS resolution of all A and AAAA records with dependency injection for testing.
  - `validate_target_url(raw_url, resolve_dns, custom_dns_resolver)`: Enforces protocol (HTTP/HTTPS), standard ports (80/443), credential absence, host suffix restrictions, and IP literal guards.
  - `validate_outbound_url(raw_url, custom_dns_resolver)`: Enforces full DNS resolution and verifies that all resolved IP addresses are public and safe.
  - `safe_fetch_get(url, headers, timeout, max_redirects, custom_dns_resolver)`: Asynchronous manual redirect client that re-resolves and re-validates each redirect hop.
- **Exceptions Defined:**
  - `SSRFSecurityError`: Raised on prohibited IP/domain/scheme targets.
  - `SSRFRedirectError`: Raised on exceeding redirect hop limits (>5).

### 2.2 `backend/security/auth.py` (New File)
- **Functions Defined:**
  - `get_or_create_session_token()`: Reads `AGENTDESK_SESSION_TOKEN` environment variable or `storage/.session_token`. If absent, generates 256 bits of entropy (`secrets.token_hex(32)`) and persists to disk.
  - `get_session_token()`: Returns active session token.
  - `verify_token_value(candidate)`: Constant-time comparison using `secrets.compare_digest`.
  - `require_session_token(credentials)`: FastAPI dependency raising `HTTPException(status_code=401)` on missing or invalid Bearer tokens.

### 2.3 `backend/main.py` (Modified)
- Added imports for `Request`, `status`, `Depends`, `JSONResponse`, and auth helpers.
- Initialized active session token at startup (`_active_token = get_session_token()`).
- Added `@app.middleware("http") enforce_bearer_auth(request, call_next)` to protect all routes except `/health`, `OPTIONS` preflight, and docs.

### 2.4 `backend/providers/playwright_scraper.py` (Modified)
- Updated imports to load `validate_target_url`, `validate_outbound_url`, `is_prohibited_ip`, and `safe_fetch_get` from `backend.security.url_validator`.
- Added `page.route("**/*", _safe_route_filter)` and `sub_page.route("**/*", _safe_route_filter)` in `_execute_search` to abort prohibited network requests with `"blockedbyclient"`.

### 2.5 `backend/services/lead_discovery.py` (Modified)
- Replaced raw unvalidated `httpx.AsyncClient` calls in `_inspect_candidate` with `safe_fetch_get(sanitized_url, headers, timeout=6.0, max_redirects=5)`.
- Replaced subpage raw `httpx.AsyncClient` with `safe_fetch_get(s_sub, headers, timeout=5.0, max_redirects=3)`.
- Added logger initialization and explicit `SSRFSecurityError` exception handling.

### 2.6 `src-tauri/src/lib.rs` (Modified)
- Added `#[tauri::command] fn get_session_token() -> Result<String, String>`.
- Registered `get_session_token` in `tauri::generate_handler![get_agentdesk_status, get_session_token]`.

### 2.7 `vite.config.ts` (Modified)
- Added `authDevPlugin()` Vite middleware responding to `GET /__agentdesk_auth_token` by reading `storage/.session_token`.

### 2.8 `src/services/api.ts` (Modified)
- Added `getSessionToken()`, `setSessionToken()`, and `authFetch()`.
- Updated all 22 `/api/*` endpoints to use `authFetch` instead of raw `fetch`.
- Kept `fetchHealth()` unauthenticated.

### 2.9 `backend/tests/conftest.py` (New File)
- Implemented `StarletteTestClient` init wrapper that injects `Authorization: Bearer <token>` by default, with opt-out support via `X-Skip-Auth-Injection: 1`.

### 2.10 `backend/tests/test_ssrf_protection.py` (New File)
- 38 automated test cases for SSRF protection.

### 2.11 `backend/tests/test_authentication.py` (New File)
- 13 automated test cases for local bearer token authentication.

