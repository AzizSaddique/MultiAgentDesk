# Phase A.2.4 — Playwright Egress Architecture Report

**Date:** November 6, 2026  
**Component:** `backend/security/egress_proxy.py` & `backend/providers/playwright_scraper.py`  
**Phase:** Phase A.2.4 — Playwright Egress Isolation  
**Status:** ARCHITECTURE DESIGNED, IMPLEMENTED & VERIFIED  

---

## 1. Executive Summary

In Phase A.2.3, an independent security audit confirmed two unresolved security gaps in browser automation:
1. **ADV-SEC-02:** Chromium managed its own socket connections and DNS resolution independently from Python. Route callbacks (`page.route`) intercepted requests at the browser application layer but could not prevent Time-Of-Check to Time-Of-Use (TOCTOU) DNS rebinding, nor did they intercept WebSocket traffic.
2. **Unpinned robots.txt requests:** `is_allowed_by_robots` used Python's `urllib.request.urlopen` with `resolve_dns=False`, creating an unpinned and unvalidated egress path.

Phase A.2.4 designed and deployed a comprehensive, lightweight, authenticated local forward egress proxy (`SecureEgressProxy`) that forces 100% of Chromium's outbound network traffic through an enforced security checkpoint on loopback.

---

## 2. Egress Architecture & Data Flow

```
+-----------------------------------------------------------------------------------+
|                              AgentDesk Desktop Host                               |
|                                                                                   |
|  +-----------------------------+                  +----------------------------+  |
|  |     Playwright Chromium     |                  |     SecureEgressProxy      |  |
|  |                             |                  |     (127.0.0.1:EPHEMERAL)  |  |
|  | --proxy-server=127.0.0.1    |  Basic Auth      |                            |  |
|  | --proxy-bypass-list=<-loop> | ---------------> | 1. Check Proxy-Auth        |  |
|  | --disable-webrtc            |  CONNECT tunnel  | 2. validate_outbound_url() |  |
|  |                             |  or HTTP proxy   |    (Format, Port, SSRF)    |  |
|  | [Direct egress blocked:     |                  | 3. Pre-resolve all DNS     |  |
|  |  Fails closed on error]     |                  | 4. is_prohibited_ip()      |  |
|  +-----------------------------+                  +--------------+-------------+  |
|                                                                  |                |
+------------------------------------------------------------------|----------------+
                                                                   | TCP Socket Pinned
                                                                   | to Validated IP
                                                                   v
                                                    +----------------------------+
                                                    | Verified Public Target     |
                                                    | (Standard Port 80/443)     |
                                                    | End-to-End TLS / Real Cert |
                                                    +----------------------------+
```

### Key Architectural Tenets:
1. **No Alternative Direct Path:**
   Chromium is launched with `--proxy-server=http://127.0.0.1:{actual_port}` and `--proxy-bypass-list=<-loopback>`. Chromium's internal Network Service sends every single HTTP, HTTPS, and WebSocket connection attempt to the local proxy.
2. **Cryptographic Authentication:**
   Every connection to the proxy requires `Proxy-Authorization: Basic <credentials>` using a 256-bit entropy password generated dynamically at proxy startup via `secrets.token_hex(24)`. Unauthorized processes on the machine receive `407 Proxy Authentication Required`.
3. **SSRF Destination Pre-Validation:**
   Before establishing an upstream connection, the proxy evaluates the destination using the centralized `validate_outbound_url()` service:
   - Prohibits non-standard ports (allows only 80 and 443).
   - Prohibits loopback (`127.0.0.0/8`), private networks (RFC 1918 `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), Unique Local IPv6 (`fc00::/7`), link-local (`169.254.0.0/16`), cloud metadata (`169.254.169.254`), multicast, and reserved spaces.
   - Canonicalizes alternate IP formats (dword integer, hex, octal, shortened, percent-encoded).
4. **Socket-Level Connection Pinning:**
   The proxy resolves all A and AAAA DNS records. If all records are public and valid, the proxy connects its upstream TCP socket **directly to the pre-validated IP address**. Chromium never resolves DNS for external domains, completely eliminating DNS rebinding at both the browser and proxy layers.
5. **Non-MITM Transparent Tunneling:**
   For HTTPS and WSS, the proxy uses standard HTTP `CONNECT` tunneling. The proxy creates the TCP tunnel to the pinned IP and forwards raw bytes. Chromium negotiates TLS directly with the remote server, preserving standard Server Name Indication (SNI) and x509 certificate verification without requiring custom root CA certificates.
6. **WebRTC & Media Hardening:**
   Chromium launch flags include `--disable-webrtc`, preventing UDP STUN/ICE probing from bypassing proxy routing.

---

## 3. Evaluation of Proxy Alternatives

| Solution | Maintainability & Suitability | Security & SSRF Control | Assessment |
| :--- | :--- | :--- | :--- |
| **mitmproxy** | Heavyweight (~50MB+ dependencies); requires generating and trusting a local root CA; MITM decryption unnecessary for scraping. | Good, but complex configuration and high performance overhead. | Rejected (over-engineered, breaks native TLS trust). |
| **External binary (Squid / Envoy)** | Requires bundling platform-specific native binaries (C++/Go); complex packaging on Windows; difficult lifecycle management in Tauri. | High. | Rejected for local desktop deployment (packaging friction). |
| **`proxy.py` (PyPI)** | Python package; requires external pip dependency; unmaintained plugins for strict socket pinning. | Moderate. | Rejected (external dependency). |
| **Native Asyncio `SecureEgressProxy`** | Zero external dependencies; built directly into `backend/security/egress_proxy.py`; binds to standard Python `asyncio`; <5ms startup. | Maximum: directly invokes centralized `validate_outbound_url`, socket pinning, and dynamic auth. | **SELECTED & IMPLEMENTED** |

---

## 4. Fail-Closed Verification

If `SecureEgressProxy` is unavailable or crashes:
- Chromium cannot fall back to direct internet connections.
- Chromium immediately aborts navigation with `net::ERR_PROXY_CONNECTION_FAILED`.
- Automated tests (`test_browser_fails_closed_when_proxy_unavailable`) verify that navigation fails closed and direct egress is strictly prevented.

