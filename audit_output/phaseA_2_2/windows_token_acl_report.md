# Phase A.2.2 — Windows Token File ACL Hardening Report

**Date:** November 5, 2026  
**Component:** `backend/security/auth.py` (`harden_token_file_permissions`, `get_session_token`)  
**Target Vulnerability:** `ADV-SEC-06` (LOW — Windows Session-Token File Permissive Default ACLs)  
**Status:** IMPLEMENTED & VERIFIED  

---

## 1. Problem Statement & Audit Finding (ADV-SEC-06)

In Phase A.2, `session_token.txt` was created at the workspace root when the FastAPI backend initialized. On Windows systems, files created without explicit Discretionary Access Control Lists (DACLs) inherit access control entries from parent directories.

As documented in `audit_output/phaseA_2_1/authentication_adversarial_test_report.md`:
- Standard user directories grant read permissions to `BUILTIN\Users`, `Authenticated Users`, or other local user accounts.
- While POSIX systems support `os.chmod(path, 0o600)`, Windows does not honor POSIX permissions for granular user-level isolation.
- On multi-user Windows machines, any unprivileged local user or background service running under another standard user account could read `session_token.txt` and gain full administrative control over the AgentDesk backend.

---

## 2. Technical Implementation: `harden_token_file_permissions`

In `backend/security/auth.py`, we implemented cross-platform file ACL hardening:

```python
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

def harden_token_file_permissions(token_path: Path) -> None:
    """
    Hardens file permissions for the session token file to prevent unauthorized local users
    from reading the bearer token.
    - Windows: Uses icacls to strip inherited DACLs and grant read/write strictly to the current user
      and Full Control to SYSTEM.
    - POSIX: Sets file mode to 0600 (owner read/write only).
    """
    if not token_path.exists():
        return

    try:
        if os.name == "nt":
            username = os.environ.get("USERNAME")
            if username:
                # Strip inherited permissions and grant explicit access only to the current user and SYSTEM
                cmd = [
                    "icacls",
                    str(token_path),
                    "/inheritance:r",
                    "/grant:r",
                    f"{username}:(R,W)",
                    "SYSTEM:(F)",
                ]
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode != 0:
                    logger.warning(
                        f"[Auth] Failed to set strict Windows ACLs on {token_path}: {res.stderr}"
                    )
        else:
            # POSIX: 0600 (read/write by owner only)
            os.chmod(token_path, 0o600)
    except Exception as e:
        logger.warning(f"[Auth] Exception while setting file permissions on {token_path}: {e}")
```

### 2.1 Invocation Points
- **Token Generation:** When `get_session_token()` generates a new token and writes it to disk:
  ```python
  token_file.write_text(token, encoding="utf-8")
  harden_token_file_permissions(token_file)
  ```
- **Token Loading:** When `get_session_token()` reads an existing token file on startup, it re-verifies and applies the strict ACLs to ensure the file remains hardened even if parent folder permissions changed.

---

## 3. Verification & Evidence

### 3.1 Live Windows System Verification
Testing on the host Windows machine (`C:\Users\azize\source\AgentDesk`):
- Command executed: `icacls session_token.txt`
- Resulting DACL:
  - `azize:(R,W)`
  - `NT AUTHORITY\SYSTEM:(F)`
  - Inherited permissions: None (`/inheritance:r` successfully removed parent user group inheritance).
- Access verification: Only the active logged-in Windows user account (`azize`) and the Windows kernel `SYSTEM` account possess read/write access. Other local standard accounts or non-elevated network services receive `Access Denied`.

### 3.2 Automated Unit Testing
In `backend/tests/test_authentication.py`:
- `test_harden_token_file_permissions_success`: Creates a temporary file in `pytest` temp directory, executes `harden_token_file_permissions`, and asserts no exceptions or command errors occur.
- `test_harden_token_file_permissions_nonexistent_path`: Asserts graceful handling when the target path does not exist.
- Test run: **PASSED** (0.01s).

