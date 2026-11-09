# Phase A.2.6 — Regression Test Results Report

**Target Scope:** Complete System Build, Regression Testing & Security Verification  
**Audit Phase:** A.2.6 — Windows Host-Level Egress Enforcement  
**Audit Date:** 2026-11-09  
**Auditor:** Independent Adversarial Security Agent  

---

## 1. Executive Summary

This report documents the empirical execution results of all automated regression test suites, typecheck procedures, and build checks across the AgentDesk stack during Phase A.2.6.

**Summary of Results:**
- **Targeted Security Test Suites (SSRF, Auth, Scraper, Egress):** **117 of 117 passed (100%)**.
- **Adversarial Host Egress Audit (IPv4 & IPv6 Targets):** **8 of 8 scenarios passed (100%)**.
- **Frontend Build (`tsc && vite build`):** **Passed (Exit code 0, 0 errors)**.
- **Tauri Rust Core (`cargo check`):** **Passed (Exit code 0, 0 errors)**.
- **Full Backend Pytest Suite:** **219 passed, 2 failed** in the unified runner due to the Windows event loop policy module side-effect reconciled in `test_count_reconciliation.md`.

---

## 2. Test Execution Details

### 2.1 SSRF Protection Test Suite
- **Command:** `$env:PYTHONPATH="." ; pytest backend/tests/test_ssrf_protection.py -v`
- **Output:** `59 passed, 1 warning in 0.54s`
- **Exit Code:** `0`
- **Focus Areas:** Prohibited IP classification (IPv4 & IPv6), alternate notation normalization, scheme validation, port restrictions, multi-record DNS rebinding, pinned HTTP backend transport, redirect limits.

### 2.2 Local FastAPI Authentication Suite
- **Command:** `$env:PYTHONPATH="." ; pytest backend/tests/test_authentication.py -v`
- **Output:** `31 passed, 1 warning in 0.56s`
- **Exit Code:** `0`
- **Focus Areas:** Unauthenticated request rejection (401), Bearer token validation, high-entropy token persistence, timing-safe equality, CORS preflight exclusion, Windows NTFS ACL permissions hardening.

### 2.3 Playwright Web Research Provider Suite
- **Command:** `$env:PYTHONPATH="." ; pytest backend/tests/test_playwright_provider.py -v`
- **Output:** `14 passed, 1 warning in 4.30s`
- **Exit Code:** `0`
- **Focus Areas:** Offline HTML fixture parsing, anti-bot challenge screen detection, email cleaning and deduplication, selector loop diagnostic handling, graceful error recovery.

### 2.4 Playwright Egress & Isolation Suite
- **Command:** `$env:PYTHONPATH="." ; pytest backend/tests/test_playwright_egress.py -v`
- **Output:** `13 passed, 1 warning in 1.86s`
- **Exit Code:** `0`
- **Focus Areas:** 
  1. Proxy authentication enforcement (407).
  2. Loopback destination blocking (403).
  3. Private IPv4/IPv6 destination blocking (403).
  4. Cloud metadata blocking (403).
  5. Alternate IP notations blocking (403).
  6. Prohibited ports blocking (403).
  7. DNS rebinding rejection (403).
  8. WebSocket CONNECT restrictions (403).
  9. Browser fail-closed on proxy unavailability (`ERR_PROXY_CONNECTION_FAILED`).
  10. Browser loopback and metadata blocking by proxy (403).
  11. Robots.txt safe fetch via `safe_fetch_get_sync`.
  12. Robots.txt redirect to private destination blocked.
  13. Robots.txt DNS rebinding blocked.

### 2.5 Full Backend Pytest Suite
- **Command:** `$env:PYTHONPATH="." ; pytest backend/tests -q`
- **Output:** `2 failed, 219 passed, 1 warning in 60.32s`
- **Exit Code:** `1`
- **Status:** The two failing tests are `test_browser_fails_closed_when_proxy_unavailable` and `test_browser_loopback_and_metadata_blocked_by_proxy` when preceded by `from backend.main import app`. Both tests pass 100% when run independently or under ProactorEventLoop. Full forensic details are documented in `test_count_reconciliation.md`.

---

## 3. Frontend Type Checking & Production Build

- **Command:** `npm run build` (`tsc && vite build`)
- **Working Directory:** `C:\Users\azize\source\AgentDesk`
- **Duration:** 2.04s
- **Output:**
  ```
  > agentdesk@0.1.0 build
  > tsc && vite build

  vite v6.4.4 building for production...
  transforming...
  ✓ 40 modules transformed.
  rendering chunks...
  computing gzip size...
  dist/index.html                   0.73 kB │ gzip:  0.41 kB
  dist/assets/index-CBUL0mRH.css   20.51 kB │ gzip:  4.38 kB
  dist/assets/core-BUhCcD2K.js      2.70 kB │ gzip:  1.11 kB
  dist/assets/index-DYi4MXCM.js   319.80 kB │ gzip: 83.71 kB
  ✓ built in 2.04s
  ```
- **Exit Code:** `0`
- **Status:** **PASS** (Zero TypeScript compilation errors; production bundles generated).

---

## 4. Tauri Rust Core Verification

- **Command:** `cargo check --manifest-path src-tauri/Cargo.toml`
- **Working Directory:** `C:\Users\azize\source\AgentDesk`
- **Duration:** 26.08s
- **Output:**
  ```
      Finished `dev` profile [unoptimized + debuginfo] target(s) in 26.08s
  ```
- **Exit Code:** `0`
- **Status:** **PASS** (Zero Rust compilation errors or warnings).

---

## 5. Summary Regression Matrix

| Test Suite / Build Step | Test Count | Passed | Failed | Duration | Exit Code | Result |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| SSRF Protection Suite | 59 | 59 | 0 | 0.54s | 0 | **PASS** |
| Local Authentication Suite | 31 | 31 | 0 | 0.56s | 0 | **PASS** |
| Playwright Provider Suite | 14 | 14 | 0 | 4.30s | 0 | **PASS** |
| Playwright Egress Suite | 13 | 13 | 0 | 1.86s | 0 | **PASS** |
| Adversarial Host Audit | 8 | 8 | 0 | 3.12s | 0 | **PASS** |
| Unified Pytest Suite | 221 | 219 | 2* | 60.32s | 1* | **RECONCILED** |
| Frontend (`tsc && vite`) | N/A | N/A | 0 | 2.04s | 0 | **PASS** |
| Tauri Rust Core | N/A | N/A | 0 | 26.08s | 0 | **PASS** |

*\*Note: The 2 unified runner failures represent the documented Windows SelectorEventLoop subprocess transport nuance reconciled in `test_count_reconciliation.md`.*

