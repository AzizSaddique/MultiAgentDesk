# Phase A.2.4 — Playwright Network Isolation Report

**Date:** November 6, 2026  
**Component:** `backend/providers/playwright_scraper.py`  
**Status:** IMPLEMENTED AND VERIFIED  

---

## 1. Overview

In Phase A.2.4, `PlaywrightScraper` was refactored to enforce complete network isolation for headless browser crawling. Chromium is no longer permitted to establish direct socket connections to the internet or local network; all network egress is routed through `SecureEgressProxy`.

---

## 2. Playwright Integration Details

### 2.1 Egress Proxy Lifecycle in `_execute_search`
In `backend/providers/playwright_scraper.py` (lines 380–405 and lines 640–655):
```python
browser = None
context = None
egress_proxy = None

try:
    from playwright.async_api import async_playwright

    # 1. Start dedicated local egress proxy on loopback
    egress_proxy = SecureEgressProxy()
    await egress_proxy.start()
    proxy_config = egress_proxy.get_playwright_proxy_config()
    launch_args = [
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-webrtc",
        *egress_proxy.get_chromium_launch_args(),
    ]

    async with async_playwright() as p:
        try:
            # 2. Launch Chromium with enforced authenticated proxy
            browser = await p.chromium.launch(
                headless=True,
                proxy=proxy_config,
                args=launch_args,
            )
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
            )
            ...
        finally:
            if context is not None:
                await context.close()
            if browser is not None:
                await browser.close()
            if egress_proxy is not None:
                await egress_proxy.stop()
```

### 2.2 Security Guarantees of Launch Configuration
1. **`proxy=proxy_config`:**
   Provides Playwright with the proxy endpoint (`http://127.0.0.1:{port}`) and the dynamic authentication credentials (`username` and `_password`). Playwright's internal networking engine automatically attaches the `Proxy-Authorization` header to all outgoing requests.
2. **`--proxy-server=http://127.0.0.1:{port}`:**
   Instructs Chromium's Network Service that all network protocols (HTTP, HTTPS, WS, WSS) must route through the proxy server.
3. **`--proxy-bypass-list=<-loopback>`:**
   By default, Chromium bypasses proxies for localhost/loopback requests. Setting `--proxy-bypass-list=<-loopback>` **explicitly disables this bypass**, forcing Chromium to send loopback requests to the proxy so the proxy can reject them with `403 Forbidden`.
4. **`--disable-webrtc`:**
   Suppresses WebRTC peer-to-peer networking, preventing STUN/ICE UDP probes from bypassing the proxy tunnel.

### 2.3 Inheritance Across Web Elements
Because the proxy is configured at the Chromium process level (`browser.launch`):
- All browser tabs and pages (`context.new_page()`) inherit proxy routing.
- All iframes, sub-frames, and popup windows inherit proxy routing.
- All sub-resources (scripts, stylesheets, fonts, fetch/XHR calls, images) inherit proxy routing.
- All WebSocket connections (`ws://`, `wss://`) inherit proxy routing.

### 2.4 Credential Privacy & Redaction
- The proxy password is generated in memory via `secrets.token_hex(24)`.
- It is never written to disk, never included in `CrawlDiagnostic` objects, and never logged in application logs.
- The `SecureEgressProxy.__repr__` explicitly masks the password.

---

## 3. Defense-in-Depth: Retained Route Filtering

In addition to socket-level proxy enforcement, `_safe_route_filter` remains active on every page:
```python
await page.route("**/*", _safe_route_filter)
```
This provides multi-layered defense:
1. **Layer 1 (Browser Request Layer):** `_safe_route_filter` aborts requests before transmission if their URL fails `validate_outbound_url`.
2. **Layer 2 (Network Socket Layer):** If a malicious website attempts an evasion or race condition that bypasses Layer 1, `SecureEgressProxy` catches the connection at the TCP level, validates destination safety, pins the socket to the pre-validated IP, and rejects prohibited targets with `403 Forbidden`.

---

## 4. Verification Evidence

In `backend/tests/test_playwright_egress.py`:
- `test_browser_fails_closed_when_proxy_unavailable`: Confirms that if the proxy is terminated, Chromium immediately aborts navigation (`ERR_PROXY_CONNECTION_FAILED`) and cannot fall back to direct internet connections.
- `test_browser_loopback_and_metadata_blocked_by_proxy`: Confirms that Chromium navigation to `http://127.0.0.1:8000` and `http://169.254.169.254/latest/meta-data` is intercepted and blocked with `HTTP 403`.
- Both tests passed cleanly.

