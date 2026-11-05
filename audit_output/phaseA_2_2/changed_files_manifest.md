# Phase A.2.2 — Changed Files Manifest

**Date:** November 5, 2026  
**Phase:** Phase A.2.2 Critical Security Remediation  
**Status:** COMPLETED & VERIFIED  

---

## 1. Summary of Changes

A total of 7 files were modified to remediate the vulnerabilities confirmed during the Phase A.2.1 adversarial security audit. No database files were modified.

```
 backend/providers/playwright_scraper.py |  29 ++-
 backend/security/__init__.py            |   8 +
 backend/security/auth.py                |  46 ++++-
 backend/security/url_validator.py       | 223 +++++++++++++++++------
 backend/tests/test_authentication.py    |  75 ++++++--
 backend/tests/test_ssrf_protection.py   | 314 ++++++++++++++++++++++++++------
 vite.config.ts                          |  72 +++++++-
 7 files changed, 626 insertions(+), 141 deletions(-)
```

---

## 2. Detailed File Modifications

### 2.1 `backend/security/url_validator.py`
- **Lines Changed:** +223, -50
- **Purpose:** 
  - Implemented `canonicalize_host(raw_host)`: Unquotes hostnames, rejects embedded `%` characters, parses IPv6 / IPv4-mapped IPv6, and uses OS socket `socket.inet_aton` and `socket.inet_ntoa` to canonicalize integer, octal, hex, and shortened IP notations to standard dotted-decimal IPv4.
  - Implemented `PinnedAsyncNetworkBackend(AutoBackend)`: Subclasses HTTPCore's `AutoBackend` to intercept `connect_tcp` and connect TCP sockets directly to the pre-validated IP address while leaving the HTTP Host header and TLS SNI intact.
  - Implemented `create_pinned_transport(pinned_ip, verify=True)`: Creates an `httpx.AsyncHTTPTransport` with a dedicated `httpcore.AsyncConnectionPool` wired to `PinnedAsyncNetworkBackend` with `max_keepalive_connections=0` and `keepalive_expiry=0.0`.
  - Refactored `safe_fetch_get(...)`: Connects using pinned transports for both initial target and all 3xx redirect locations; re-validates each redirect hop; safely resolves relative URLs with `urllib.parse.urljoin`; accepts pluggable `transport` parameter for unit testing.

### 2.2 `backend/security/auth.py`
- **Lines Changed:** +46, -1
- **Purpose:**
  - Implemented `harden_token_file_permissions(token_path)`: Uses Windows `icacls` to strip inherited DACLs (`/inheritance:r`) and grant explicit Read/Write access strictly to the active `%USERNAME%` and Full Control to `SYSTEM`. Sets `0600` permissions on POSIX platforms.
  - Integrated `harden_token_file_permissions` into `get_session_token()` during token generation and token loading.

### 2.3 `backend/security/__init__.py`
- **Lines Changed:** +8, -0
- **Purpose:**
  - Exported newly introduced functions and classes: `canonicalize_host`, `create_pinned_transport`, `PinnedAsyncNetworkBackend`, and `harden_token_file_permissions`.

### 2.4 `backend/providers/playwright_scraper.py`
- **Lines Changed:** +29, -1
- **Purpose:**
  - Added Chromium launch argument `"--disable-webrtc"` to prevent WebRTC local network discovery and STUN/ICE leaks.
  - Refactored `_safe_route_filter(route, request)` to execute `validate_outbound_url(req_url)` on all intercepted requests, ensuring active DNS resolution and IP blocklisting before resources are loaded.
  - Added pre-navigation validation checks for `target_url` and subpage `sub_url` in `_execute_search`.

### 2.5 `vite.config.ts`
- **Lines Changed:** +72, -9
- **Purpose:**
  - Hardened `authDevPlugin()` middleware for `/api/dev-token`:
    - Enforced `GET` method only (returning 405 otherwise).
    - Validated `Host` header strictly against `localhost:1420` and `127.0.0.1:1420` (returning 403 otherwise).
    - Enforced `Origin` whitelist (`localhost:1420`, `127.0.0.1:1420`, `tauri://localhost`, `http://tauri.localhost`).
    - Enforced `Sec-Fetch-Site` header (rejecting `cross-site` with 403).
    - Replaced wildcard `*` with exact origin matching.
    - Added `Cache-Control: no-store, no-cache, must-revalidate` and `Vary: Origin`.

### 2.6 `backend/tests/test_ssrf_protection.py`
- **Lines Changed:** +314, -60
- **Purpose:**
  - Completely eliminated synthetic test loops (`run_fetch` and `run_loop`).
  - Added test cases directly calling production `safe_fetch_get` across all redirect scenarios (loopback redirect, private IPv4 redirect, cloud metadata redirect, relative redirects, multi-hop chains, redirect limits).
  - Added comprehensive unit tests for `canonicalize_host` covering integer, octal, hex, shortened, percent-encoded, and IPv4-mapped IPv6 formats.
  - Added unit tests for `PinnedAsyncNetworkBackend` verifying socket destination interception.

### 2.7 `backend/tests/test_authentication.py`
- **Lines Changed:** +75, -20
- **Purpose:**
  - Added unit tests for `harden_token_file_permissions` (verifying temporary file permissions and error handling on nonexistent files).
  - Expanded unauthenticated route parametrization to test all 22 sensitive endpoints under `/api/*` across research, discovery, and outreach modules.

---

## 3. Production Database & File Integrity

- **Database:** `storage/dispatches.db`
  - Record count in `discovered_leads`: **149** (Pristine, 0 modifications).
  - Record count in `discovery_jobs`: **6** (Pristine, 0 modifications).
  - `PRAGMA integrity_check`: `ok`.
  - Foreign key check violations on rows 124 & 125 preserved intact.
- **Git Repository:**
  - Working directory clean of unauthorized commits or branch changes.
  - All changes reside in working tree.

