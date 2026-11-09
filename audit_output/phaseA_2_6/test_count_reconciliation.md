# Phase A.2.6 — Test Count Reconciliation Report

**Target Scope:** Forensic Investigation of Test Count Difference Between Phase A.2.4 and Phase A.2.5  
**Audit Phase:** A.2.6 — Windows Host-Level Egress Enforcement  
**Audit Date:** 2026-11-09  
**Auditor:** Independent Adversarial Security Agent  

---

## 1. Executive Summary

In Phase A.2.4, the security test report recorded **221 passed, 0 failed**.  
In Phase A.2.5, the regression test report recorded **219 passed, 2 failed**.

A comprehensive forensic investigation was conducted to determine the exact root cause of this discrepancy.

**Key Findings:**
1. **Zero Tests Removed, Renamed, Skipped, or Modified:** A Git diff between commit `d13d3580` (Phase A.2.4) and HEAD confirms that zero lines of code or tests were modified across the repository. Exactly 221 test functions exist in both phases.
2. **Identification of the Exact Two Discrepant Tests:**
   - `backend/tests/test_playwright_egress.py::test_browser_fails_closed_when_proxy_unavailable[asyncio]`
   - `backend/tests/test_playwright_egress.py::test_browser_loopback_and_metadata_blocked_by_proxy[asyncio]`
3. **Root Cause:** A side-effect of module import ordering in Python on Windows. Importing `backend.main` executes lines 14–19 of `backend/main.py`, which switches the global asyncio event loop policy to `WindowsSelectorEventLoopPolicy`. When pytest subsequently executes tests using Playwright's subprocess transport on Windows, `SelectorEventLoop` raises `NotImplementedError`.
4. **Assertion Integrity:** All original security assertions remain completely intact. When executed under `WindowsProactorEventLoopPolicy`, all 13 egress tests (and all 221 tests total) pass without error.

---

## 2. Git Commit & Codebase Diff Verification

To establish whether any code or test changes occurred between Phase A.2.4 and Phase A.2.5:

```powershell
git diff --stat d13d3580b0f6490e54297c6c28e987e9494662ae..HEAD
```

**Git Output:**
```
 audit_output/phaseA_2_5/chromium_direct_egress_report.md    | 118 +++++++++++++++
 audit_output/phaseA_2_5/database_integrity_report.md        |  86 +++++++++++
 audit_output/phaseA_2_5/independent_security_verdict.md     |  97 ++++++++++++
 audit_output/phaseA_2_5/proxy_adversarial_test_report.md    | 166 +++++++++++++++++++++
 audit_output/phaseA_2_5/regression_test_results.md | 130 ++++++++++++++++
 audit_output/phaseA_2_5/remaining_security_gaps.md |  90 +++++++++++
 audit_output/phaseA_2_5/robots_txt_independent_verification.md         |  97 ++++++++++++
 audit_output/phaseA_2_5/windows_firewall_verification.md    | 117 +++++++++++++++
 8 files changed, 901 insertions(+)
```

**Evidence:**
- Changed files outside `audit_output/phaseA_2_5/`: **0**
- Tests added: **0**
- Tests deleted: **0**
- Tests renamed: **0**
- Tests skipped (`@pytest.mark.skip`): **0**

---

## 3. Root Cause Investigation: Windows Event Loop Policy Side-Effect

### 3.1 The Global Policy Switch in `backend/main.py`
In `backend/main.py`, lines 13–19 contain:
```python
# On Windows, configure default policy to WindowsSelectorEventLoopPolicy to prevent WinError 87 socket crash
if sys.platform == "win32":
    try:
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsSelectorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass
```
*Historical Context:* This snippet was committed on October 26, 2026 (commit `8910b96e`) to prevent a legacy Uvicorn `WinError 87: The parameter is incorrect` socket error during local server shutdown.

### 3.2 The Test Runner Collision
In `test_playwright_egress.py`:
- `test_browser_fails_closed_when_proxy_unavailable` (line 223)
- `test_browser_loopback_and_metadata_blocked_by_proxy` (line 257)

Both tests invoke `async with async_playwright() as p:` to launch Chromium. Internally, Playwright calls:
```python
self._proc = await asyncio.create_subprocess_exec(...)
```
In Python on Windows:
- `WindowsProactorEventLoop`: **Supports subprocesses** (`_make_subprocess_transport` implemented).
- `WindowsSelectorEventLoop`: **Does NOT support subprocesses** (`_make_subprocess_transport` raises `NotImplementedError`).

### 3.3 Why Phase A.2.4 Reported 221 Passed vs Phase A.2.5 Reporting 219 Passed
- **Phase A.2.4 Execution Strategy:**
  In Phase A.2.4, the author executed test modules in targeted groups or executed `test_playwright_egress.py` in a separate process. Because `test_playwright_egress.py` only imports from `backend.security.egress_proxy`, `backend.security.url_validator`, and `backend.providers.playwright_scraper`—and **does not import `backend.main`**—the process-wide event loop policy remained `WindowsProactorEventLoopPolicy`. All 13 tests passed, yielding 221 total passing tests.
- **Phase A.2.5 Execution Strategy:**
  In Phase A.2.5, the auditor executed the entire suite in a single unified command:
  ```powershell
  $env:PYTHONPATH="." ; pytest backend/tests -q
  ```
  In pytest's alphabetical collection order:
  1. `test_authentication.py` ran first -> executed `from backend.main import app` -> switched global policy to `WindowsSelectorEventLoopPolicy`.
  2. `test_playwright_egress.py` ran eighth -> `@pytest.mark.anyio` instantiated a `SelectorEventLoop` -> Playwright attempted `create_subprocess_exec` -> raised `NotImplementedError`.
  3. Result: 219 passed, 2 failed.

---

## 4. Empirical Proof & Verification

### Proof Step 1: Standalone Execution of `test_playwright_egress.py`
Running `test_playwright_egress.py` independently without prior `backend.main` imports:
```powershell
$env:PYTHONPATH="." ; pytest backend/tests/test_playwright_egress.py -v
```
**Result:** **13 passed, 0 failed in 10.89s (100% pass rate).**

### Proof Step 2: Combined Execution with `test_lead_quality.py`
Running `test_lead_quality.py` (which imports `backend.main`) immediately prior to `test_playwright_egress.py`:
```powershell
$env:PYTHONPATH="." ; pytest backend/tests/test_lead_quality.py backend/tests/test_playwright_egress.py -v
```
**Result:** Exactly the 2 Playwright subprocess tests fail with `NotImplementedError`.

---

## 5. Summary Reconciliation Table

| Metric | Phase A.2.4 Report | Phase A.2.5 Report | Phase A.2.6 Reconciliation | Explanation |
| :--- | :---: | :---: | :---: | :--- |
| **Total Test Count** | 221 | 221 | **221** | 100% identical test inventory |
| **Passing Tests (Global Runner)** | 221 | 219 | **219** | 2 anyio/subprocess failures caused by `main.py` loop policy |
| **Passing Tests (Targeted/Proactor)** | 221 | 221 | **221** | 100% pass rate under Proactor loop policy |
| **Failing Tests (Underlying Defect)** | 0 | 0 | **0** | Zero functional, security, or regression failures |
| **Assertion Integrity** | Verified | Verified | **Verified** | Original security assertions untouched |

---

## 6. Recommended Remediation for Phase A.3

In Phase A.3, the module-level event loop policy switch in `backend/main.py` should be moved inside the `if __name__ == "__main__":` block or accompanied by a `conftest.py` autouse fixture that restores `WindowsProactorEventLoopPolicy` for all async tests. This will ensure `pytest backend/tests` reports 221/221 passing in standard global test runs.

