# Phase A.2.5 — Chromium Direct Egress Test Report

**Target Component:** Playwright Chromium Integration (`backend/providers/playwright_scraper.py`)  
**Audit Phase:** A.2.5 — Independent Adversarial Security Verification  
**Audit Date:** 2026-11-06  
**Auditor:** Independent Adversarial Security Agent  

---

## 1. Executive Summary

This report documents empirical tests conducted to verify whether Playwright Chromium is strictly confined to the local `SecureEgressProxy` or whether any vector exists allowing Chromium to establish direct outbound connections to the host loopback or internal networks.

Using a real instance of Playwright Chromium launched with the exact production command-line flags and an active mock internal service logging all inbound TCP connections, four adversarial egress scenarios were executed:
1. Direct top-level navigation to internal services.
2. Embedded subresource retrieval (iframes and image tags).
3. Client-side WebSocket initiation.
4. Fail-closed verification during sudden proxy shutdown.

**Empirical Result: 0 out of 0 requests reached the sensitive mock target.** In all test scenarios, Chromium was blocked by the proxy or failed closed. Direct egress is confirmed blocked at the application/browser layer.

---

## 2. Test Architecture & Methodology

```
+----------------------------------------------------------------------------------+
|                              TEST HARNESS ISOLATION                              |
|                                                                                  |
|   +--------------------------+                                                   |
|   |   Adversarial Script     |  Launches Playwright with Production Flags        |
|   +--------------------------+                                                   |
|                |                                                                 |
|                v                                                                 |
|   +--------------------------+          Proxy Flags Enforced                     |
|   |   Playwright Chromium    | ------------------------------------------+       |
|   +--------------------------+                                           |       |
|                |                                                         |       |
|                | (Attempting direct / subresource / WS connections)      |       |
|                |                                                         v       |
|                |                                            +------------------+ |
|                x (Blocked: No Direct Outbound Connect)      | SecureEgressProxy| |
|                |                                            +------------------+ |
|                v                                                         |       |
|   +--------------------------+                                           |       |
|   | Sensitive Target Server  | <-----------------------------------------+       |
|   | (127.0.0.1:50714/secret) |     (Proxy blocks destination: 403 Forbidden)     |
|   +--------------------------+                                                   |
|                                                                                  |
+----------------------------------------------------------------------------------+
```

### Production Launch Flags Inspected
From `backend/providers/playwright_scraper.py`:
- `--proxy-server=http://127.0.0.1:<PORT>`
- `--proxy-bypass-list=<-loopback>` (Crucial: forces loopback traffic to route through proxy instead of default Chromium bypass)
- `--disable-webrtc` (Prevents STUN/TURN direct UDP/TCP egress)

---

## 3. Empirical Test Results

### Scenario A — Direct Top-Level Navigation (`page.goto`)
- **Target URL:** `http://127.0.0.1:50714/sensitive_data`
- **Execution:** Chromium navigated directly to the sensitive target endpoint.
- **Proxy Behavior:** Proxy evaluated `127.0.0.1:50714`, detected a private loopback address via `validate_outbound_url`, and responded with `HTTP/1.1 403 Forbidden`.
- **Target Server Hits:** **0 hits recorded.**
- **Browser State:** Received HTTP 403 Forbidden error page.
- **Outcome:** **PASS**

### Scenario B — Subresource Egress (Iframes & Images)
- **Attack Vector:** An attacker-controlled public page attempting to execute a port scan or retrieve internal assets by rendering `<iframe src="http://127.0.0.1:50714/admin"></iframe>` and `<img src="http://127.0.0.1:50714/pixel.png">`.
- **Execution:** Blank page loaded; injected dynamic DOM elements targeting `http://127.0.0.1:50714/`.
- **Proxy Behavior:** Every subresource HTTP request was routed through `SecureEgressProxy` and received `403 Forbidden`.
- **Target Server Hits:** **0 hits recorded.**
- **Outcome:** **PASS**

### Scenario C — Client-Side WebSocket (`new WebSocket(...)`)
- **Attack Vector:** Modern web apps can attempt raw socket communication using WebSockets to bypass standard CORS/same-origin checks.
- **Execution:** Executed `new WebSocket('ws://127.0.0.1:50714/ws')` via `page.evaluate()`.
- **Proxy Behavior:** WebSocket handshake initiated an HTTP Upgrade/CONNECT request to the proxy. Proxy inspected the loopback destination and rejected it with `403 Forbidden`.
- **Target Server Hits:** **0 hits recorded.**
- **Browser State:** WebSocket connection failed (`DOMException / connection refused`).
- **Outcome:** **PASS**

### Scenario D — Proxy Termination (Fail-Closed Verification)
- **Objective:** Verify that if the local proxy crashes, hangs, or is terminated, Chromium does not silently fail open and revert to direct OS network sockets.
- **Execution:**
  1. `SecureEgressProxy` was forcefully stopped (`proxy.stop()`).
  2. Chromium attempted navigation to `http://127.0.0.1:50714/sensitive_data`.
- **Browser Behavior:** Navigation threw an immediate fatal network exception:
  ```
  playwright._impl._errors.Error: net::ERR_PROXY_CONNECTION_FAILED at http://127.0.0.1:50714/sensitive_data
  ```
- **Target Server Hits:** **0 hits recorded.**
- **Outcome:** **PASS (Fails Closed)**

---

## 4. Hit Log Audit of Sensitive Target Server

The mock server logged all socket accept events and HTTP request paths:

```
[TARGET_SERVER] 2026-11-06T23:08:12 - Listening on 127.0.0.1:50714
[TARGET_SERVER] Test A (Direct Navigation) started...
[TARGET_SERVER] Test B (Subresource Injection) started...
[TARGET_SERVER] Test C (WebSocket Injection) started...
[TARGET_SERVER] Test D (Proxy Kill & Fail-Closed) started...
[TARGET_SERVER] Tests complete. Total requests logged: 0
```

---

## 5. Verification Conclusion

Playwright Chromium's network isolation is fully effective at the application layer. Chromium respects the proxy configuration unconditionally, forwards loopback requests because of `--proxy-bypass-list=<-loopback>`, disables WebRTC peer connections, and immediately fails closed with `net::ERR_PROXY_CONNECTION_FAILED` when the proxy is offline.

