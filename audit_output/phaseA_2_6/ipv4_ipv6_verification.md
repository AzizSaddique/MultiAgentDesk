# Phase A.2.6 — Dual-Stack IPv4 & IPv6 Security Verification Report

**Target Scope:** Dual-Stack IP Canonicalization, SSRF Filtering, and Proxy Routing  
**Audit Phase:** A.2.6 — Windows Host-Level Egress Enforcement  
**Audit Date:** 2026-11-09  
**Auditor:** Independent Adversarial Security Agent  

---

## 1. Executive Summary

A critical vulnerability in modern egress isolation systems is "IPv6 blind-spotting", where security controls strictly filter IPv4 addresses (such as `127.0.0.1` and `169.254.169.254`) but neglect IPv6 loopback (`::1`), Unique Local Addresses (`fc00::/7`), or IPv4-mapped IPv6 encodings (`::ffff:127.0.0.1`).

This report independently verifies that AgentDesk enforces comprehensive, deterministic dual-stack protection across all components:
1. `backend/security/url_validator.py` (`is_prohibited_ip`, `canonicalize_host`, `validate_outbound_url`)
2. `backend/security/egress_proxy.py` (`SecureEgressProxy`)
3. `backend/providers/playwright_scraper.py` (`is_allowed_by_robots` and Chromium launch parameters)

---

## 2. Dual-Stack IP Classification & Coverage Matrix

Every IP address evaluated by `validate_outbound_url` is normalized via Python's native `ipaddress.ip_address` module. IPv4-mapped IPv6 addresses are explicitly unwrapped to their underlying IPv4 representations before classification.

| Address / Range | Protocol | RFC Standard | Security Classification | Evaluator Action | Test Status |
| :--- | :---: | :--- | :--- | :---: | :---: |
| `127.0.0.1` | IPv4 | RFC 1122 | Loopback | **BLOCKED (403)** | **PASS** |
| `127.0.0.100` | IPv4 | RFC 1122 | Loopback /8 | **BLOCKED (403)** | **PASS** |
| `::1` | IPv6 | RFC 4291 | Loopback | **BLOCKED (403)** | **PASS** |
| `10.0.0.1` | IPv4 | RFC 1918 | Private Class A | **BLOCKED (403)** | **PASS** |
| `172.16.0.1` | IPv4 | RFC 1918 | Private Class B | **BLOCKED (403)** | **PASS** |
| `192.168.1.1` | IPv4 | RFC 1918 | Private Class C | **BLOCKED (403)** | **PASS** |
| `fc00::1` | IPv6 | RFC 4193 | Unique Local Address (ULA) | **BLOCKED (403)** | **PASS** |
| `fd12:3456::1` | IPv6 | RFC 4193 | Unique Local Address (ULA) | **BLOCKED (403)** | **PASS** |
| `169.254.169.254` | IPv4 | RFC 3927 | Cloud Metadata / Link-Local | **BLOCKED (403)** | **PASS** |
| `fe80::1` | IPv6 | RFC 4291 | Link-Local Unicast | **BLOCKED (403)** | **PASS** |
| `::ffff:127.0.0.1` | IPv6 | RFC 4291 | IPv4-Mapped Loopback | **BLOCKED (403)** | **PASS** |
| `::ffff:10.0.0.1` | IPv6 | RFC 4291 | IPv4-Mapped Private | **BLOCKED (403)** | **PASS** |
| `::ffff:169.254.169.254` | IPv6 | RFC 4291 | IPv4-Mapped Metadata | **BLOCKED (403)** | **PASS** |
| `0.0.0.0` | IPv4 | RFC 1122 | Unspecified / Current Host | **BLOCKED (403)** | **PASS** |
| `::` | IPv6 | RFC 4291 | Unspecified | **BLOCKED (403)** | **PASS** |
| `100.64.0.1` | IPv4 | RFC 6598 | Carrier-Grade NAT (CGNAT) | **BLOCKED (403)** | **PASS** |
| `224.0.0.1` | IPv4 | RFC 1112 | Multicast | **BLOCKED (403)** | **PASS** |
| `ff02::1` | IPv6 | RFC 4291 | Multicast | **BLOCKED (403)** | **PASS** |
| `240.0.0.1` | IPv4 | RFC 1112 | Reserved / Future Use | **BLOCKED (403)** | **PASS** |
| `255.255.255.255` | IPv4 | RFC 919 | Limited Broadcast | **BLOCKED (403)** | **PASS** |
| `93.184.216.34` | IPv4 | Public | Legitimate Public Host | **ALLOWED (200)** | **PASS** |
| `2606:4700:4700::1111` | IPv6 | Public | Cloudflare Public DNS | **ALLOWED (200)** | **PASS** |

---

## 3. Empirical Test Execution Log

The following automated validation was executed against the production validator in Phase A.2.6:

```python
from backend.security.url_validator import validate_outbound_url

probes = [
    ("127.0.0.1", "IPv4 Loopback"),
    ("[::1]", "IPv6 Loopback"),
    ("10.0.0.1", "IPv4 Private"),
    ("[fc00::1]", "IPv6 Unique Local"),
    ("[fe80::1]", "IPv6 Link-Local"),
    ("169.254.169.254", "IPv4 Cloud Metadata"),
    ("[::ffff:127.0.0.1]", "IPv4-Mapped IPv6 Loopback"),
]

for host, label in probes:
    is_valid, url, err = validate_outbound_url(f"http://{host}/")
    print(f"[{label}] {host} -> Valid: {is_valid} | Reason: {err}")
```

**Output:**
```
[IPv4 Loopback] 127.0.0.1 -> Valid: False | Reason: Internal / private network URLs are restricted: Loopback address '127.0.0.1' is restricted.
[IPv6 Loopback] [::1] -> Valid: False | Reason: Internal / private network URLs are restricted: Loopback address '::1' is restricted.
[IPv4 Private] 10.0.0.1 -> Valid: False | Reason: Internal / private network URLs are restricted: Private network address '10.0.0.1' is restricted.
[IPv6 Unique Local] [fc00::1] -> Valid: False | Reason: Internal / private network URLs are restricted: Private network address 'fc00::1' is restricted.
[IPv6 Link-Local] [fe80::1] -> Valid: False | Reason: Internal / private network URLs are restricted: Link-local / cloud metadata address 'fe80::1' is restricted.
[IPv4 Cloud Metadata] 169.254.169.254 -> Valid: False | Reason: Internal / private network URLs are restricted: Cloud metadata endpoint '169.254.169.254' is restricted.
[IPv4-Mapped IPv6 Loopback] [::ffff:127.0.0.1] -> Valid: False | Reason: Internal / private network URLs are restricted: Loopback address '127.0.0.1' is restricted.
```

---

## 4. Dual-Stack Proxy Tunnel Verification

In addition to static URL validation, live HTTP CONNECT tunnels and HTTP proxy requests were tested through `SecureEgressProxy`:

1. **IPv6 Loopback CONNECT Tunnel:**
   - Request: `CONNECT [::1]:8000 HTTP/1.1\r\nHost: [::1]:8000\r\nProxy-Authorization: <auth>\r\n\r\n`
   - Response: `HTTP/1.1 403 Forbidden (Blocked by AgentDesk Egress Policy)`
   - Server Log: `[EgressProxy] Blocked prohibited CONNECT destination: https://[::1]:8000 (Internal / private network URLs are restricted: Loopback address '::1' is restricted.)`
2. **IPv6 ULA CONNECT Tunnel:**
   - Request: `CONNECT [fc00::1]:443 HTTP/1.1\r\nHost: [fc00::1]:443\r\nProxy-Authorization: <auth>\r\n\r\n`
   - Response: `HTTP/1.1 403 Forbidden (Blocked by AgentDesk Egress Policy)`
   - Server Log: `[EgressProxy] Blocked prohibited CONNECT destination: https://[fc00::1]:443 (Internal / private network URLs are restricted: Private network address 'fc00::1' is restricted.)`

---

## 5. Dual-Stack Verification Conclusion

Dual-stack egress controls are comprehensive and deterministic. Both IPv4 and IPv6 loopback, private, link-local, multicast, reserved, and IPv4-mapped IPv6 encodings are intercepted and blocked prior to any network socket connection.

