# Phase A.2.4 — Changed Files Manifest

**Date:** November 6, 2026  
**Status:** IMPLEMENTED AND VERIFIED  

---

## 1. Summary of Changes

A total of 7 files were modified or created to implement local forward egress proxying for Playwright, eliminate unpinned `urllib.request.urlopen` calls in robots.txt handling, and correct the regression test in `test_lead_quality.py`. No database records or schemas were modified.

```
 backend/providers/playwright_scraper.py   |  63 +++++++++++++----
 backend/security/__init__.py              |   8 +++
 backend/security/url_validator.py         | 114 ++++++++++++++++++++++++++++++
 backend/tests/test_lead_quality.py        |  17 +++--
 backend/tests/test_playwright_provider.py |  36 +++++-----
 backend/security/egress_proxy.py          | 296 ++++++++++++++++++++++++++++++
 backend/tests/test_playwright_egress.py   | 335 ++++++++++++++++++++++++++++++
 7 files changed, 831 insertions(+), 38 deletions(-)
```

---

## 2. Detailed File Descriptions

### 2.1 `backend/security/egress_proxy.py` (New File)
- **Lines:** 296
- **Purpose:** Implements `SecureEgressProxy`, a lightweight asyncio forward proxy binding to `127.0.0.1` on an ephemeral port. Enforces Basic authentication via `secrets.token_hex(24)`. Pre-validates destination URLs with `validate_outbound_url()`. Pins upstream TCP sockets to pre-validated IP addresses. Provides non-MITM transparent CONNECT tunneling for HTTPS and WebSocket endpoints. Exposes Playwright launch configuration helpers.

### 2.2 `backend/security/url_validator.py` (Modified)
- **Lines Changed:** +114, -0
- **Purpose:** Added `PinnedSyncNetworkBackend(SyncBackend)`, `create_pinned_sync_transport(pinned_ip, verify=True)`, and `safe_fetch_get_sync(url, headers, timeout, max_redirects, custom_dns_resolver)`. Provides a synchronous connection-pinned HTTP client with hop-by-hop redirect re-validation.

### 2.3 `backend/security/__init__.py` (Modified)
- **Lines Changed:** +8, -0
- **Purpose:** Exported `PinnedSyncNetworkBackend`, `create_pinned_sync_transport`, `safe_fetch_get_sync`, and `SecureEgressProxy`.

### 2.4 `backend/providers/playwright_scraper.py` (Modified)
- **Lines Changed:** +63, -15
- **Purpose:**
  - Added module logger instantiation.
  - Refactored `is_allowed_by_robots` to use `safe_fetch_get_sync`, completely eliminating `urllib.request.urlopen`.
  - Updated `PlaywrightScraper._execute_search` to instantiate, start, and stop `SecureEgressProxy`.
  - Configured Chromium to use the local authenticated proxy with `--proxy-bypass-list=<-loopback>` and `--disable-webrtc`.

### 2.5 `backend/tests/test_playwright_egress.py` (New File)
- **Lines:** 335
- **Purpose:** Comprehensive security test suite covering proxy authentication, loopback blocking, private IP/cloud metadata rejection, alternate IP normalization, port filtering, DNS rebinding, WebSocket restrictions, browser fail-closed behavior, and robots.txt SSRF protection (13 automated tests).

### 2.6 `backend/tests/test_lead_quality.py` (Modified)
- **Lines Changed:** +9, -8
- **Purpose:** Corrected `test_source_evidence_distinguishes_website_and_directory` to mock `safe_fetch_get` with an offline fixture, eliminating the uncontrolled live internet dependency to `https://panteraenergy.pk` while preserving all original assertions.

### 2.7 `backend/tests/test_playwright_provider.py` (Modified)
- **Lines Changed:** +18, -18
- **Purpose:** Updated `test_robots_txt_disallowed_fixture` to mock `safe_fetch_get_sync` instead of the legacy `urllib.request.urlopen`.

---

## 3. Database & Version Control Integrity

- **Database:** `storage/dispatches.db`
  - Unmodified (read-only verification confirmed 149 leads, 6 discovery jobs, integrity check `ok`, FK violations 124 & 125 preserved).
- **Git Working Tree:**
  - Changes staged/unstaged strictly within working tree.
  - Zero commits or pushes to GitHub.

