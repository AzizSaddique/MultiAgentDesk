# AgentDesk — Phase A.2.1: Adversarial Security Audit

**Assessment Date:** 2026-11-05  
**Audit Scope:** Independent Adversarial Verification of Phase A.2 Security Foundation  
**Audited Target:** `C:\Users\azize\source\AgentDesk`  
**Execution Mode:** Verification Only (Zero Code Modifications, Zero Database Writes)  
**Final Verdict:** `FAILED — CRITICAL SECURITY VULNERABILITY FOUND`

---

## 1. Executive Summary

An adversarial security audit was conducted against the security controls introduced in Phase A.2 (SSRF Protection & Local FastAPI Bearer Token Authentication).

While Phase A.2 successfully introduced centralized IP address filtering, timing-safe cryptographic bearer token validation, and full test suite regression compatibility (169 passing tests), adversarial inspection of the underlying transport mechanisms, browser automation hooks, and development endpoints revealed **1 Critical**, **2 High**, **2 Medium**, and **2 Low** severity security gaps.

Most significantly:
1. **Critical:** DNS pre-resolution without socket connection pinning in `safe_fetch_get` leaves an exploitable Time-Of-Check to Time-Of-Use (TOCTOU) DNS-rebinding vulnerability.
2. **High:** Playwright's route interception calls `validate_target_url` with `resolve_dns=False`, allowing domain names resolving to internal IP addresses (e.g., `127.0.0.1` or `169.254.169.254`) to be loaded in the headless Chromium browser.
3. **High:** Alternate IP representations (integer/dword `2130706433`, octal `0177.0.0.1`, hexadecimal `0x7f000001`, and shortened `127.1`) bypass the format-only validator and are normalized to loopback by Chromium.

Remediation is required before Phase A.2 security can be certified as fully production-hardened.

---

## 2. Comprehensive Findings Register

| ID | Finding Title | Severity | Affected Component | Status |
| :--- | :--- | :--- | :--- | :--- |
| **ADV-SEC-01** | DNS Rebinding TOCTOU via Unpinned HTTP Client Connection | **CRITICAL** | `backend/security/url_validator.py:244-275` | **CONFIRMED** |
| **ADV-SEC-02** | Playwright Route Interception Defaults to `resolve_dns=False` | **HIGH** | `backend/providers/playwright_scraper.py:407-418` | **CONFIRMED** |
| **ADV-SEC-03** | Alternate IP Formats (Dword/Hex/Octal) Bypass Format Validator | **HIGH** | `backend/security/url_validator.py:196-207` | **CONFIRMED** |
| **ADV-SEC-04** | Vite Dev Server Middleware Exposes Session Token Cross-Origin | **MEDIUM** | `vite.config.ts:13-27` | **CONFIRMED** |
| **ADV-SEC-05** | SSRF Test Suite Re-Implements Logic Rather than Invoking SUT | **MEDIUM** | `backend/tests/test_ssrf_protection.py:240-292` | **CONFIRMED** |
| **ADV-SEC-06** | Windows NTFS ACLs Not Hardened on `storage/.session_token` | **LOW** | `backend/security/auth.py:70-76` | **CONFIRMED** |
| **ADV-SEC-07** | Absence of Content Security Policy in Tauri Configuration | **LOW** | `src-tauri/tauri.conf.json:26` | **CONFIRMED** |

---

## 3. Detailed Technical Analysis

### ADV-SEC-01: DNS Rebinding TOCTOU via Unpinned HTTP Client Connection
- **Severity:** **CRITICAL**
- **Affected File & Lines:** `backend/security/url_validator.py`, lines 244–275 (`safe_fetch_get`)
- **Evidence:**
  ```python
  is_valid, current_url, err_msg = validate_outbound_url(url, custom_dns_resolver=custom_dns_resolver)
  if not is_valid:
      raise SSRFSecurityError(...)
  ...
  async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
      while True:
          resp = await client.get(current_url, headers=req_headers)
  ```
  `validate_outbound_url()` performs DNS resolution via `resolve_domain_ips()`. However, the resulting IP address is discarded after validation. `httpx.AsyncClient().get(current_url)` receives the raw string URL with the original hostname, forcing HTTPX to perform its own second DNS resolution during TCP socket connection.
- **Exploit Scenario:**
  An attacker hosts an authoritative DNS server for `rebind.attacker.com` with a Time-To-Live (TTL) of 0 seconds.
  1. The Python backend executes `validate_outbound_url("https://rebind.attacker.com")`. The attacker's DNS server returns a benign public IP `93.184.216.34`. Validation passes.
  2. Milliseconds later, `httpx.AsyncClient().get("https://rebind.attacker.com")` resolves the domain name again to open the TCP connection. The attacker's DNS server returns `169.254.169.254` (cloud metadata) or `127.0.0.1`.
  3. The client establishes a direct TCP socket connection to the prohibited internal address.
- **Rule Verification:** "DNS pre-resolution without connection pinning or an equivalent safe transport mechanism must NOT be reported as complete DNS-rebinding protection."
- **Remediation:** Implement connection pinning. In HTTPX, use a custom `httpx.AsyncHTTPTransport` or socket connection wrapper that connects directly to the pre-validated IP address while setting the `Host` header and TLS Server Name Indication (SNI) to the hostname.

---

### ADV-SEC-02: Playwright Route Interception Defaults to `resolve_dns=False`
- **Severity:** **HIGH**
- **Affected File & Lines:** `backend/providers/playwright_scraper.py`, lines 407–418 & lines 513–520
- **Evidence:**
  ```python
  async def _safe_route_filter(route):
      try:
          req_url = route.request.url
          is_valid, _, _ = validate_target_url(req_url)
          if not is_valid:
              await route.abort("blockedbyclient")
          else:
              await route.continue_()
  ```
  `validate_target_url()` defines default parameter `resolve_dns: bool = False`. `_safe_route_filter` invokes `validate_target_url(req_url)` without setting `resolve_dns=True`.
- **Exploit Scenario:**
  An attacker registers a public-looking domain (e.g. `legit-firm.xyz`) whose A-record points directly to `127.0.0.1` or `169.254.169.254`.
  1. User or discovery candidate triggers a crawl of `https://legit-firm.xyz`.
  2. `validate_target_url("https://legit-firm.xyz")` validates the scheme (`https`), hostname syntax, and port (`443`). Because `resolve_dns=False`, it does not check DNS and returns `is_valid=True`.
  3. `_safe_route_filter` calls `await route.continue_()`.
  4. Headless Chromium navigates directly to `127.0.0.1:8000` or `169.254.169.254`, bypassing the route filter completely.
- **Remediation:** In `_safe_route_filter`, call `validate_outbound_url(req_url)` or configure Chromium command-line flags with `--host-resolver-rules` or an authenticated proxy that enforces outbound IP filtering at the network level.

---

### ADV-SEC-03: Alternate IP Formats Bypass Format-Only Validator
- **Severity:** **HIGH**
- **Affected File & Lines:** `backend/security/url_validator.py`, lines 196–207
- **Evidence:**
  ```python
  # 4. Check if hostname is an IP literal
  is_ip_literal = False
  try:
      ip_obj = ipaddress.ip_address(hostname_lower)
      is_ip_literal = True
  except ValueError:
      is_ip_literal = False

  if is_ip_literal:
      prohibited, reason = is_prohibited_ip(ip_obj)
      ...
  ```
  `ipaddress.ip_address()` expects canonical dot-decimal (`127.0.0.1`) or standard IPv6.
  When passed alternate integer or octal/hex notations:
  - `http://2130706433` -> integer representation of `127.0.0.1` -> `validate_target_url` returns `True`
  - `http://0177.0.0.1` -> octal representation of `127.0.0.1` -> `validate_target_url` returns `True`
  - `http://0x7f000001` -> hex representation of `127.0.0.1` -> `validate_target_url` returns `True`
  - `http://127.1` -> shortened representation of `127.0.0.1` -> `validate_target_url` returns `True`
- **Exploit Scenario:**
  Chromium's internal URL parser (Google GURL) normalizes all these alternate representations to `127.0.0.1`. If an attacker supplies `http://2130706433/`, `validate_target_url` permits it, and Chromium connects directly to loopback `127.0.0.1`.
- **Remediation:** Normalize hostnames before evaluation. Detect integer hosts, leading zeros (octal), and hex prefixes, converting them to canonical IPv4 before running `is_prohibited_ip()`.

---

### ADV-SEC-04: Vite Dev Server Middleware Exposes Session Token Cross-Origin
- **Severity:** **MEDIUM**
- **Affected File & Lines:** `vite.config.ts`, lines 13–27 (`authDevPlugin`)
- **Evidence:**
  ```typescript
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
  The endpoint performs zero authentication, zero origin checking, and zero referer validation. In Vite, `server.cors` defaults to `true` (enabling wildcard cross-origin access).
- **Exploit Scenario:**
  While a developer is running `npm run dev` in the background, they visit a malicious site on the internet in their standard browser. The malicious site executes `fetch("http://localhost:1420/__agentdesk_auth_token")`. The token is exfiltrated, and the attacker uses it to make authenticated requests to `http://127.0.0.1:8000/api/*`.
- **Remediation:** Remove the dev token server endpoint, or strictly enforce `req.headers.origin === "http://localhost:1420"` and disable CORS on the middleware route.

---

### ADV-SEC-05: SSRF Test Suite Re-Implements Logic Rather than Invoking SUT
- **Severity:** **MEDIUM**
- **Affected File & Lines:** `backend/tests/test_ssrf_protection.py`, lines 240–256 & 276–292
- **Evidence:**
  `test_safe_fetch_blocks_redirect_to_prohibited_destination` and `test_safe_fetch_caps_redirect_limit` define local `run_fetch()` and `run_loop()` functions inside the test bodies. They NEVER invoke `safe_fetch_get()` from `backend.security.url_validator`.
- **Exploit Scenario:**
  Regressions or logic flaws in `safe_fetch_get()` (such as unhandled redirect status codes or header propagation issues) will pass automated testing unnoticed because the actual production function is bypassed in the test suite.
- **Remediation:** Refactor `safe_fetch_get()` to accept a pluggable transport / client and execute `await safe_fetch_get(...)` directly in all redirect test cases.

---

### ADV-SEC-06: Windows NTFS ACLs Not Hardened on `storage/.session_token`
- **Severity:** **LOW**
- **Affected File & Lines:** `backend/security/auth.py`, lines 70–76
- **Evidence:**
  `if hasattr(os, "chmod") and os.name != "nt": os.chmod(token_file, 0o600)`
  On Windows systems (`os.name == 'nt'`), POSIX permissions are a no-op and skipped. The token file is created with inherited NTFS DACLs.
- **Exploit Scenario:**
  On a shared multi-user Windows desktop, any other non-administrator local user with read access to the project directory can read `.session_token`.
- **Remediation:** Use Windows `icacls` command or `win32security` to explicitly grant access only to the current user SID and SYSTEM.

---

### ADV-SEC-07: Absence of Content Security Policy in Tauri Configuration
- **Severity:** **LOW**
- **Affected File & Lines:** `src-tauri/tauri.conf.json`, line 26
- **Evidence:**
  `"security": { "csp": null }`
- **Exploit Scenario:**
  If an XSS vulnerability exists in rendered lead evidence or outreach drafts, the absence of CSP allows scripts to invoke `window.__TAURI__.core.invoke('get_session_token')` and exfiltrate the token to an external domain.
- **Remediation:** Define a strict CSP in `tauri.conf.json`:
  `"csp": "default-src 'self'; connect-src 'self' http://127.0.0.1:8000; style-src 'self' 'unsafe-inline';"`

