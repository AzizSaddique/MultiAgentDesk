# Phase A.2.5 — Remaining Security Gaps

**Project:** AgentDesk  
**Target Path:** `C:\Users\azize\source\AgentDesk`  
**Audit Phase:** A.2.5 — Independent Adversarial Security Verification  
**Audit Date:** 2026-11-06  
**Auditor:** Independent Adversarial Security Agent  

---

## 1. Executive Summary

Phase A.2 (encompassing Phases A.2 through A.2.5) successfully delivered and verified the critical SSRF and local authentication foundations:
- Local FastAPI Bearer Token authentication with high-entropy session tokens and Windows ACL protection.
- DNS rebinding immunity and upstream socket pinning for HTTPX client calls.
- `SecureEgressProxy` implementation providing loopback proxying, authentication, SSRF prevention, and fail-closed isolation for Playwright Chromium.
- Sanitized `robots.txt` retrieval utilizing `safe_fetch_get_sync`, eliminating unpinned `urllib.request.urlopen`.

This document tracks all remaining security gaps, architecture considerations, and technical debt prior to entering Phase A.3.

---

## 2. Comprehensive Security Gaps Ledger

### Gap 1: Absence of OS-Level Packet Filtering (Windows Firewall)
- **Severity:** Medium
- **Location:** Host OS / Installer Boundary
- **Description:** 
  Windows Defender Firewall currently has zero outbound block rules. While Chromium strictly obeys proxy flags during normal operation, the Windows kernel does not drop packets if a process executes outside Chromium's flag constraints (e.g., following an RCE sandbox escape or if an unmanaged subprocess is spawned).
- **Remediation Recommendation:**
  Integrate an automated setup script or Tauri Windows installer action (NSIS / WiX) that registers a Windows Defender Firewall rule explicitly blocking outbound traffic for the Playwright Chromium executable (`chrome.exe`) except to `127.0.0.1` on the dynamic proxy port.

---

### Gap 2: SQLite Database Encryption at Rest
- **Severity:** Medium
- **Location:** `storage/dispatches.db`
- **Description:**
  The SQLite database file `storage/dispatches.db` is stored unencrypted on the filesystem. While access is limited by NTFS filesystem permissions, an attacker with local file read permissions (or malware scanning user directories) can extract discovered leads, outreach drafts, and dispatch histories directly from disk.
- **Remediation Recommendation:**
  In a future phase, evaluate SQLite encryption extensions (such as SQLCipher) or application-level field encryption for sensitive contact and credential data.

---

### Gap 3: Windows Pytest Runner Event Loop Configuration
- **Severity:** Low (Test Harness / CI Nuance)
- **Location:** `backend/tests/test_playwright_egress.py`
- **Description:**
  Running `pytest backend/tests` without explicit event loop policy flags causes `anyio` to default to `SelectorEventLoop` on Windows, which lacks `_make_subprocess_transport`. This caused two tests in `test_playwright_egress.py` to raise `NotImplementedError` during global suite runs, despite passing 100% when run under Python's native `ProactorEventLoop`.
- **Remediation Recommendation:**
  Add a `pytest.ini` or `conftest.py` fixture setting `asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())` on Windows platforms to ensure seamless CI/CD test execution.

---

### Gap 4: Content Security Policy (CSP) & CORS Headers in FastAPI
- **Severity:** Low
- **Location:** `backend/api/main.py`
- **Description:**
  While bearer token authentication protects endpoints from unauthorized third-party scripts, response headers do not currently include hardened CSP headers (`Content-Security-Policy`), `X-Content-Type-Options: nosniff`, or `X-Frame-Options: DENY`.
- **Remediation Recommendation:**
  Incorporate security middleware in `backend/api/main.py` adding standard OWASP secure HTTP headers to all API responses.

---

### Gap 5: Lead Dispatch Human-in-the-Loop Audit Trails (Phase A.3 Scope)
- **Severity:** Info / Planned Phase A.3
- **Location:** Outreach Workflow & Dispatch Manager
- **Description:**
  As documented in Phase A.1, the application must enforce strict human approval prior to email or outreach transmission, complete with non-repudiation logs.
- **Remediation Recommendation:**
  Address in Phase A.3 as planned in the architectural backlog.

---

## 3. Residual Risk Matrix

| Risk ID | Title | Likelihood | Impact | Current Mitigation | Recommended Target Phase |
| :---: | :--- | :---: | :---: | :--- | :---: |
| **GAP-01** | OS-Level Egress Bypass | Low | High | Userspace Chromium CLI flags + fail-closed proxy | Phase A.3 / Installer |
| **GAP-02** | Database Unencrypted at Rest | Low | Medium | NTFS File Permissions | Phase B (Enterprise) |
| **GAP-03** | Pytest anyio Loop Driver Nuance | Medium | Low | Run under ProactorEventLoop | Phase A.3 (Refactor) |
| **GAP-04** | Missing OWASP Security Headers | Low | Low | Bearer token auth required | Phase A.3 (Security) |
| **GAP-05** | Human Approval Audit Logging | Medium | Medium | UI approval gate | Phase A.3 (Outreach) |

---

## 4. Conclusion & Next Phase Readiness

All P0 security controls specified for Phase A.2 (SSRF prevention, local authentication, DNS rebinding protection, and Playwright egress proxying) have been implemented and independently verified. The application is in a stable, secure posture to proceed to Phase A.3 once the user reviews the Phase A.2.5 audit findings.

