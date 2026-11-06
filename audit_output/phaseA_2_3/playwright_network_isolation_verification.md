# Phase A.2.3 — Playwright Network Isolation Verification

**Date:** November 6, 2026  
**Audited Component:** `backend/providers/playwright_scraper.py`  
**Target Vulnerability:** `ADV-SEC-02` (HIGH — Playwright Network Interception & SSRF Gaps)  
**Status:** UNRESOLVED SECURITY GAP (CONDITIONAL)  

---

## 1. Audit Objective

The objective was to determine whether Chromium's actual network connections during Playwright web scraping are protected against:
1. DNS rebinding attacks.
2. Loopback, private IPv4/IPv6, and cloud metadata access.
3. HTTP redirects to prohibited internal IP spaces.
4. Iframes, fonts, images, and sub-resource loading.
5. WebSocket (`ws://`, `wss://`) and WebRTC network traffic.
6. Browser-level DNS resolution bypasses.

---

## 2. Technical Findings & Architectural Limitations

### 2.1 Route Interception vs. Chromium Socket Layer
In `backend/providers/playwright_scraper.py` (lines 419–435):
```python
async def _safe_route_filter(route):
    try:
        req_url = route.request.url
        is_valid, _, _ = validate_outbound_url(req_url)
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
- **The DNS Rebinding TOCTOU Gap in Chromium:**
  When `validate_outbound_url(req_url)` executes, it resolves DNS via Python's standard `socket.getaddrinfo()` and checks the returned IP addresses.
  However, once `await route.continue_()` is called, Chromium's internal Network Service takes over the request.
  Chromium maintains its own internal DNS cache and socket pool. Chromium independently resolves the domain name using its own DNS resolver and establishes its own TCP connection.
  If an attacker configures an authoritative DNS server with a 0-second TTL:
  1. Python resolves `rebind.attacker.com` -> `93.184.216.34` (public IP) -> `validate_outbound_url` returns `is_valid = True`.
  2. `route.continue_()` is invoked.
  3. Chromium resolves `rebind.attacker.com` -> `127.0.0.1` or `169.254.169.254`.
  4. Chromium establishes a TCP socket connection directly to the internal loopback or cloud metadata service!
- **Conclusion:** Python-side DNS pre-resolution **does not and cannot pin Chromium's socket connection**.

### 2.2 WebSocket Traffic Unintercepted by `page.route`
Playwright's `page.route("**/*")` API intercepts HTTP and HTTPS network requests.
By design, Playwright's route interception **does not intercept WebSocket connections** (`ws://` or `wss://`).
If a crawled page contains Javascript that opens a WebSocket:
```javascript
const ws = new WebSocket("ws://127.0.0.1:8000/ws");
```
Playwright's `_safe_route_filter` is completely bypassed. The WebSocket connects directly to the local port.

### 2.3 WebRTC Hardening Status
Chromium is launched with `args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage", "--disable-webrtc"]`.
- The `--disable-webrtc` flag successfully suppresses WebRTC peer connections and prevents STUN/ICE local IP discovery.
- This represents a verified defense against WebRTC-based IP disclosure.

### 2.4 Robots.txt Crawler Flaw (`is_allowed_by_robots`)
Inspection of `backend/providers/playwright_scraper.py` (lines 50–72) revealed an unpinned, unvalidated outbound HTTP request:
```python
def is_allowed_by_robots(target_url: str, user_agent: str = USER_AGENT, timeout: float = 4.0) -> Tuple[bool, str]:
    is_valid, sanitized, reason = validate_target_url(target_url)  # NOTE: resolve_dns=False!
    if not is_valid:
        return False, f"Target URL failed safety validation: {reason}"
    try:
        parsed = urlparse(target_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        
        req = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            ...
```
- `validate_target_url(target_url)` is called with `resolve_dns=False` (the default).
- If `target_url` is a domain name that resolves to `127.0.0.1` or `169.254.169.254`, `validate_target_url` returns `True`.
- `urllib.request.urlopen(req)` is invoked directly on the `robots_url`.
- Python's standard `urllib.request.urlopen` performs unpinned DNS resolution, does not validate IP destinations, and automatically follows HTTP 302 redirects to internal endpoints.
- This creates an unmitigated SSRF vulnerability whenever `is_allowed_by_robots` is called.

---

## 3. Necessity of an Enforced Network Boundary or Secure Proxy

Because Chromium operates as an independent multi-process binary with its own networking stack, software-level route callbacks inside Python cannot guarantee socket-level destination constraints.

### Architectural Recommendation: Forward Egress Proxy
To achieve true, unbypassable network isolation for Playwright:
1. Configure Chromium to route all traffic through a local authenticated forward proxy (e.g., Smokescreen or Squid):
   ```python
   context = await browser.new_context(
       proxy={"server": "http://127.0.0.1:8888"}
   )
   ```
2. The egress proxy enforces destination IP filtering at the operating system socket layer before forwarding any request:
   - Blocks any connection targeting loopback (`127.0.0.0/8`), private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local / metadata (`169.254.0.0/16`), and carrier-grade NAT.
   - Denies non-standard egress ports.
   - Blocks WebSocket connections to internal IP spaces.

---

## 4. Conclusion & Classification

**Classification: UNRESOLVED SECURITY GAP**

Chromium's actual socket destination cannot be guaranteed against DNS rebinding via route interception alone, and `is_allowed_by_robots` contains an unvalidated `urllib.request.urlopen` request path. This gap requires remediation in subsequent phases through:
1. Refactoring `is_allowed_by_robots` to use `safe_fetch_get`.
2. Deploying an authenticated local egress proxy or containerized network sandbox for headless browser execution.

