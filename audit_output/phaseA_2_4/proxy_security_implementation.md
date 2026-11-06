# Phase A.2.4 — Proxy Security Implementation Details

**Date:** November 6, 2026  
**Component:** `backend/security/egress_proxy.py` (`SecureEgressProxy`)  
**Status:** IMPLEMENTED AND TESTED  

---

## 1. Technical Implementation Overview

`SecureEgressProxy` is a specialized asynchronous forward proxy written with standard library `asyncio` and wired directly to AgentDesk's centralized URL and network security service (`backend/security/url_validator.py`).

### 1.1 Source Location & Exports
- **File:** `backend/security/egress_proxy.py`
- **Exported In:** `backend/security/__init__.py`
- **Class:** `SecureEgressProxy`

---

## 2. Core Security Subsystems

### 2.1 Dynamic Cryptographic Authentication
To ensure that unauthorized processes running on the local machine cannot abuse the local proxy to pivot or scan internal services:
1. When `SecureEgressProxy` initializes, it generates a fresh random credential pair:
   ```python
   self.username = username or "agentdesk_egress"
   self._password = password or secrets.token_hex(24)
   self.expected_auth = "Basic " + base64.b64encode(f"{self.username}:{self._password}".encode()).decode()
   ```
2. Every incoming request must contain the `Proxy-Authorization` header matching `self.expected_auth`.
3. Validation uses `secrets.compare_digest()` to eliminate timing attack vectors.
4. If missing or invalid, the proxy immediately returns:
   ```http
   HTTP/1.1 407 Proxy Authentication Required
   Proxy-Authenticate: Basic realm="AgentDesk Egress"
   Content-Length: 0
   Connection: close
   ```
5. Passwords and credentials are never printed in logs or `__repr__`.

### 2.2 HTTPS & WebSocket CONNECT Tunneling
When Chromium accesses HTTPS websites or initiates secure WebSocket connections (`wss://`):
1. Chromium sends an HTTP `CONNECT` command:
   ```http
   CONNECT example.com:443 HTTP/1.1
   Host: example.com:443
   Proxy-Authorization: Basic <credentials>
   ```
2. **SSRF Pre-Validation:**
   The proxy extracts `host_str` and `dest_port` and executes `validate_outbound_url(f"https://{host_str}:{dest_port}")`.
   - Rejects non-standard ports (outside 80, 443).
   - Rejects internal domain suffixes (`.local`, `.internal`, `localhost`).
   - Rejects IP literals targeting loopback, RFC 1918 private, link-local, carrier-grade NAT, or cloud metadata ranges.
   - Canonicalizes alternate IP formats (integer, octal, hex, shortened).
3. **Dual-Record DNS Inspection:**
   The proxy resolves all A and AAAA records via `resolve_domain_ips()`. If ANY returned IP is prohibited, the request is aborted with `HTTP/1.1 403 Forbidden`.
4. **Socket-Level Connection Pinning:**
   The proxy establishes a direct TCP socket connection to the first validated IP:
   ```python
   remote_reader, remote_writer = await asyncio.wait_for(
       asyncio.open_connection(pinned_ip, dest_port),
       timeout=8.0,
   )
   ```
   **Crucial Security Guarantee:** Upstream TCP connection targets `pinned_ip`, NOT `host_str`. Even if the authoritative DNS changes immediately afterward, the connection is already bound to the pre-validated public IP address.
5. **Raw Byte Piping (Non-MITM):**
   The proxy sends `HTTP/1.1 200 Connection Established\r\n\r\n` and pipes raw bytes bi-directionally between Chromium and the upstream socket. Chromium negotiates TLS directly through the tunnel.

### 2.3 Plain HTTP Forwarding
For plain HTTP requests:
1. The proxy parses the absolute URI (`GET http://example.com/path HTTP/1.1`).
2. Validates safety via `validate_outbound_url(target)`.
3. Resolves and pins the upstream TCP connection to `pinned_ip:80`.
4. Rewrites the request line to a relative path (`GET /path HTTP/1.1`) and strips proxy-specific headers (`Proxy-Authorization`, `Proxy-Connection`).
5. Pipes data bi-directionally with safe error termination.

### 2.4 Lifecycle Management
- `await proxy.start() -> int`: Binds to `127.0.0.1` on an OS-assigned ephemeral port (preventing port collisions) and starts the TCP listener.
- `await proxy.stop()`: Closes the server and cleanly terminates all open client and upstream socket streams.
- `get_playwright_proxy_config() -> dict`: Returns the exact configuration structure consumed by `playwright.chromium.launch()`.
- `get_chromium_launch_args() -> list[str]`: Returns required command-line arguments.

---

## 3. Threat Mitigation Coverage

| Threat Vector | Proxy Mitigation Mechanism | Verified Status |
| :--- | :--- | :--- |
| **DNS Rebinding TOCTOU** | Upstream socket is pinned to `pinned_ip` resolved during validation. | **MITIGATED** |
| **Cloud Metadata Theft** | `validate_outbound_url` rejects `169.254.169.254` and `2852039166`. Proxy returns 403. | **MITIGATED** |
| **Local Port Scanning** | Loopback and RFC 1918 addresses rejected. Non-standard ports (22, 3389, etc.) rejected. | **MITIGATED** |
| **WebSocket SSRF Bypass** | `CONNECT` tunnels used by WebSockets undergo identical destination validation. | **MITIGATED** |
| **Unauthorized Proxy Use** | Basic Auth with 256-bit dynamic secret required on all requests. | **MITIGATED** |
| **Proxy Failure Direct Leak** | Chromium configured with strict `--proxy-server` and no bypass list; fails closed on proxy crash. | **MITIGATED** |

