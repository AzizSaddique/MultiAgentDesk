# AgentDesk — Phase A.2.1: SSRF & Connection Binding Audit

**Audit Objective:** Detailed evaluation of SSRF controls, DNS rebinding susceptibility, connection pinning, redirect handling, and Playwright browser interception.  
**Audited Files:**
- `backend/security/url_validator.py`
- `backend/services/lead_discovery.py`
- `backend/providers/playwright_scraper.py`
- `backend/providers/search/tavily_search.py`
**Date:** 2026-11-05

---

## 1. Audit Checklist & Verification Matrix

| Verification Item | Assessment | Details |
| :--- | :---: | :--- |
| **1. Connects to exact validated IP?** | **NO** | `safe_fetch_get` passes the hostname to HTTPX; HTTPX performs independent DNS resolution. |
| **2. Can DNS change between check and connection?** | **YES** | Classic TOCTOU window: attacker authoritative DNS server can answer public IP on check, private IP on connection. |
| **3. Are all A and AAAA records checked?** | **YES** | `resolve_domain_ips()` resolves both IPv4 and IPv6 via `socket.AF_UNSPEC` and iterates all returned records. |
| **4. Are IPv4-mapped IPv6 addresses handled?** | **YES** | `is_prohibited_ip()` unpacks `ip.ipv4_mapped` and re-evaluates all IPv4 prohibited CIDRs. |
| **5. Are redirects validated before each hop?** | **YES** | `safe_fetch_get()` extracts `Location`, resolves target via `urljoin`, and calls `validate_outbound_url()` prior to GET. |
| **6. Are redirect limits enforced?** | **YES** | Maximum redirect count is tracked (`redirect_count > max_redirects`), raising `SSRFRedirectError` if exceeded. |
| **7. Are relative redirects resolved safely?** | **YES** | Uses `urllib.parse.urljoin(current_url, location)` to normalize relative paths before re-validation. |
| **8. Malformed URLs, unusual ports, credentials rejected?** | **PARTIAL** | Malformed URLs, ports outside 80/443, and embedded credentials are rejected. However, **alternate IP notations** (integer/hex/octal) bypass format validation. |
| **9. Are all Playwright requests intercepted?** | **PARTIAL** | Main document and subpages register `page.route("**/*")`, but validation runs with `resolve_dns=False`. WebSockets and WebRTC are not intercepted. |
| **10. Can any client bypass the centralized validator?** | **YES** | Any direct use of `httpx.AsyncClient` or external SDKs that does not invoke `validate_outbound_url` bypasses validation. |

---

## 2. In-Depth Analysis: The DNS Rebinding TOCTOU Gap (Finding ADV-SEC-01)

### 2.1 The Critical Rule
> **"Critical rule: DNS pre-resolution without connection pinning or an equivalent safe transport mechanism must NOT be reported as complete DNS-rebinding protection."**

### 2.2 Mechanism Failure Analysis
In `backend/security/url_validator.py`:
```python
def validate_outbound_url(raw_url: str, ...) -> Tuple[bool, str, str]:
    return validate_target_url(raw_url, resolve_dns=True, ...)
```
When `validate_outbound_url("https://rebind.attacker.com")` is invoked:
1. `resolve_domain_ips("rebind.attacker.com")` executes `socket.getaddrinfo("rebind.attacker.com", None, ...)`.
2. The attacker's authoritative name server returns `A: 93.184.216.34` (TTL: 0s).
3. `is_prohibited_ip(93.184.216.34)` returns `(False, "")`.
4. `validate_outbound_url` returns `(True, "https://rebind.attacker.com", "")`.

Immediately following this check in `safe_fetch_get()`:
```python
async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
    while True:
        resp = await client.get(current_url, headers=req_headers)
```
1. `httpx` ignores the resolved IP from step 1.
2. `httpx` delegates connection establishment to its internal `httpcore` backend.
3. `httpcore` performs its own fresh DNS resolution for `rebind.attacker.com`.
4. The attacker's name server now responds with `A: 169.254.169.254` (or `127.0.0.1`).
5. HTTPX establishes a TCP socket connection directly to `169.254.169.254` or `127.0.0.1`!

### 2.3 Required Remediation Architecture: Custom Pinned Async Transport
To achieve 100% DNS-rebinding protection, the HTTP client must connect directly to the pre-validated socket address:
```python
import httpcore
import httpx

class PinnedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    def __init__(self, target_ip: str, *args, **kwargs):
        self.pinned_ip = target_ip
        super().__init__(*args, **kwargs)

    # Override connection pool to route TCP connection to self.pinned_ip
    # while retaining original Host header and TLS SNI hostname.
```
Alternatively, rewrite the URL to connect to the IP directly with standard `httpx` headers:
- Target URL: `https://<pinned_ip>:<port>/path`
- Header: `Host: <original_hostname>`
- SSL Context: `server_hostname=<original_hostname>` for TLS SNI validation.

---

## 3. Playwright Route Interception Audit (Finding ADV-SEC-02)

### 3.1 Implementation in `backend/providers/playwright_scraper.py`
Lines 407–418:
```python
async def _safe_route_filter(route):
    try:
        req_url = route.request.url
        is_valid, _, _ = validate_target_url(req_url)
        if not is_valid:
            await route.abort("blockedbyclient")
        else:
            await route.continue_()
    except Exception:
        try:
            await route.abort("blockedbyclient")
        except Exception:
            pass
```

### 3.2 Vulnerability Path
1. `validate_target_url(req_url)` is called with `resolve_dns=False` (the default).
2. For an input URL like `https://attacker-domain.com/page`:
   - Scheme is `https` (allowed).
   - Port is 443 (allowed).
   - Hostname does not match `.local`, `.internal`, `.lan`.
   - Hostname is not an IP literal.
   - **DNS is NOT checked.**
3. `validate_target_url` returns `(True, sanitized, "")`.
4. The route handler calls `await route.continue_()`.
5. Chromium resolves `attacker-domain.com` directly. If the A-record points to `127.0.0.1`, Chromium loads content from `http://127.0.0.1:8000` or cloud metadata.

### 3.3 Protocol Gap
`page.route("**/*")` intercepts standard HTTP/HTTPS document, image, script, stylesheet, and fetch/XHR requests.
It does **NOT** intercept:
- Direct WebRTC peer connections (which can probe local network IPs for STUN/TURN).
- WebSockets initialized via non-standard APIs unless explicitly hooked.

---

## 4. Alternate IP Formats & Parser Differential (Finding ADV-SEC-03)

### 4.1 Parser Discrepancy
Python's `ipaddress` module conforms to strict RFC specifications:
```python
ipaddress.ip_address("2130706433") # Raises ValueError: '2130706433' is not an IP address
ipaddress.ip_address("0177.0.0.1")  # Raises ValueError: leading zeros are not allowed
ipaddress.ip_address("0x7f000001")  # Raises ValueError: '0x7f000001' is not an IP address
ipaddress.ip_address("127.1")       # Raises ValueError: only two octets
```
However, Chromium's URL parser (`GURL` / `url::CanonHost`) normalizes all standard alternate representations:
- Dword `http://2130706433/` -> Chromium connects to `127.0.0.1`
- Octal `http://0177.0.0.1/` -> Chromium connects to `127.0.0.1`
- Hexadecimal `http://0x7f000001/` -> Chromium connects to `127.0.0.1`
- Shortened `http://127.1/` -> Chromium connects to `127.0.0.1`

Because `validate_target_url` assumes `is_ip_literal = False` when `ValueError` is raised, these alternate formats pass format validation without rejection.
Remediation requires canonicalizing IP strings using `socket.inet_aton` or custom regular expressions before evaluation.

