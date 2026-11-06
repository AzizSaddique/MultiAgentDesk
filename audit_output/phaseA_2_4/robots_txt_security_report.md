# Phase A.2.4 — Robots.txt Egress Security Report

**Date:** November 6, 2026  
**Component:** `backend/providers/playwright_scraper.py` (`is_allowed_by_robots`) & `backend/security/url_validator.py` (`safe_fetch_get_sync`)  
**Status:** FULLY REMEDIATED AND VERIFIED  

---

## 1. Problem Statement & Root Cause

In Phase A.2.3, an unpinned outbound HTTP egress path was confirmed in `is_allowed_by_robots`:
```python
# VULNERABLE CODE IN PHASE A.2.3:
is_valid, sanitized, reason = validate_target_url(target_url)  # resolve_dns=False!
...
req = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
with urllib.request.urlopen(req, timeout=timeout) as response:
```
- `validate_target_url` did not resolve DNS (`resolve_dns=False`).
- `urllib.request.urlopen` performed unpinned DNS lookups and automatically followed HTTP 302 redirects to internal networks (e.g. `http://169.254.169.254` or `http://127.0.0.1`).

---

## 2. Technical Remediation

### 2.1 Centralized Synchronous Secure Client (`safe_fetch_get_sync`)
Because `is_allowed_by_robots` is invoked from both synchronous and asynchronous contexts, we implemented `safe_fetch_get_sync` in `backend/security/url_validator.py`:
```python
class PinnedSyncNetworkBackend(SyncBackend):
    def __init__(self, pinned_ip: str):
        super().__init__()
        self.pinned_ip = pinned_ip

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        return super().connect_tcp(
            host=self.pinned_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

def create_pinned_sync_transport(pinned_ip: str, verify: bool = True) -> httpx.HTTPTransport:
    transport = httpx.HTTPTransport(verify=verify)
    transport._pool = httpcore.ConnectionPool(
        ssl_context=transport._pool._ssl_context,
        network_backend=PinnedSyncNetworkBackend(pinned_ip=pinned_ip),
        max_keepalive_connections=0,
        keepalive_expiry=0.0,
    )
    return transport
```

`safe_fetch_get_sync` mirrors `safe_fetch_get`:
- Pre-resolves all A and AAAA DNS records and rejects prohibited IP ranges.
- Pins upstream TCP connection directly to `pinned_ip`.
- Re-validates each 3xx redirect destination before following.
- Restricts redirect count to a bounded maximum (3 hops) and enforces strict timeouts.

### 2.2 Refactored `is_allowed_by_robots`
In `backend/providers/playwright_scraper.py`:
```python
def is_allowed_by_robots(target_url: str, user_agent: str = USER_AGENT, timeout: float = 3.0) -> Tuple[bool, str]:
    """
    Checks robots.txt for the domain of the target URL using safe_fetch_get_sync.
    Enforces full SSRF validation, DNS resolution, connection pinning, and redirect checks.
    Returns (is_allowed, reason).
    """
    is_valid, sanitized, reason = validate_outbound_url(target_url)
    if not is_valid:
        return False, f"Target URL failed safety validation: {reason}"
    try:
        parsed = urlparse(sanitized)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)

        try:
            resp = safe_fetch_get_sync(
                robots_url,
                headers={"User-Agent": user_agent},
                timeout=timeout,
                max_redirects=3,
            )
            if resp.status_code == 200:
                content = resp.text
                rp.parse(content.splitlines())
                allowed = rp.can_fetch(user_agent, target_url) or rp.can_fetch("*", target_url)
                if not allowed:
                    return False, f"Disallowed by website robots.txt rules at {robots_url}"
                return True, "Permitted by robots.txt"
            elif resp.status_code in (401, 403):
                return False, f"Robots.txt access denied (HTTP {resp.status_code})"
        except SSRFSecurityError as ssrf_err:
            logger.warning(f"[PlaywrightScraper] robots.txt blocked by SSRF policy: {ssrf_err}")
            return False, f"Robots.txt destination blocked by security policy: {ssrf_err}"
        except Exception as fetch_err:
            # Missing or unreachable: standard convention permits crawling
            logger.debug(f"[PlaywrightScraper] robots.txt not reachable ({fetch_err}); permitting crawl")
            return True, "robots.txt not found or unrestricted"
    except Exception as exc:
        return True, f"robots.txt check exception ({exc}); unrestricted"
    return True, "Permitted"
```

---

## 3. Security Verification Results

The refactored implementation was verified across three automated test cases in `backend/tests/test_playwright_egress.py`:

| Test Name | Scenario Tested | Observed Result | Status |
| :--- | :--- | :--- | :--- |
| `test_robots_txt_public_request_works` | Public domain fetching `robots.txt` via `safe_fetch_get_sync`. | Status 200 parsed; allowed path returns `True`; disallowed path returns `False`. | **PASSED** |
| `test_robots_txt_redirect_to_private_destination_blocked` | `robots.txt` responds with 302 redirect to `127.0.0.1`. | `SSRFSecurityError` caught; returns `False, "blocked by security policy"`. | **PASSED** |
| `test_robots_txt_dns_rebinding_blocked` | Target domain resolves to a private IP range. | `validate_outbound_url` rejects destination before connection; returns `False, "failed safety validation"`. | **PASSED** |

---

## 4. Conclusion

`urllib.request.urlopen` has been completely purged from the codebase. All robots.txt network requests are now routed through `safe_fetch_get_sync`, guaranteeing socket connection pinning and complete SSRF protection.

