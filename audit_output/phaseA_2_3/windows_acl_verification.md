# Phase A.2.3 — Windows File ACL Protection Verification

**Date:** November 6, 2026  
**Audited Component:** `backend/security/auth.py` (`harden_token_file_permissions`, `get_or_create_session_token`)  
**Target Vulnerability:** `ADV-SEC-06` (LOW — Windows Token File Permissive Default Access Control Lists)  
**Status:** FULLY VERIFIED AND SECURED  

---

## 1. Audit Objective

The objective of this audit was to inspect the implementation of `harden_token_file_permissions` in `backend/security/auth.py` and confirm on the live Windows operating system that:
1. NTFS discretionary access control list (DACL) inheritance is disabled.
2. Broad default user groups (such as `BUILTIN\Users` or `Authenticated Users`) are completely stripped.
3. Access is restricted strictly to the active logged-in Windows user account and the Windows `SYSTEM` principal.
4. Token retrieval and generation functions continue operating without interruption.
5. Permission modification failures do not cause application crashes.

*(Note: In compliance with strict safety rules, no session token strings or credential secrets are printed or disclosed in this report).*

---

## 2. Implementation Inspection (`backend/security/auth.py`)

In `backend/security/auth.py` (lines 26–60):
```python
def harden_token_file_permissions(token_path: str) -> bool:
    """
    Applies restrictive file system permissions to storage/.session_token:
    - POSIX (Linux/macOS): chmod 0600 (owner read/write only).
    - Windows (NTFS): uses icacls to reset inheritance and grant (R,W)
      strictly to the active Windows user and SYSTEM.
    Never prints or logs the token or credentials.
    """
    if not token_path or not os.path.isfile(token_path):
        return False

    if os.name != "nt":
        try:
            os.chmod(token_path, 0o600)
            return True
        except Exception:
            return False
    else:
        try:
            username = os.environ.get("USERNAME", "").strip()
            if not username:
                return False

            cmd = ["icacls", token_path, "/inheritance:r", "/grant:r", f"{username}:(R,W)", "SYSTEM:(F)"]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return res.returncode == 0
        except Exception:
            return False
```

### Key Technical Aspects:
1. **Inheritance Removal (`/inheritance:r`):**
   Removes inherited access control entries from parent directories (`storage/` and the workspace root).
2. **Explicit User Grant (`/grant:r %USERNAME%:(R,W)`):**
   Grants Read and Write permissions specifically to the active Windows user account.
3. **SYSTEM Grant (`SYSTEM:(F)`):**
   Grants Full Control to `NT AUTHORITY\SYSTEM` to ensure system-level services and OS processes can manage the file without permission collisions.
4. **POSIX Support (`chmod 0600`):**
   On Linux and macOS, the function applies mode `0600` (read/write by owner only).
5. **Safe Failure Handling:**
   `subprocess.run(check=False)` and broad `try...except` ensure that if permission modification encounters an error (e.g. read-only filesystem or restricted domain policy), the function returns `False` without raising an unhandled exception or crashing the backend.

---

## 3. Live Operating System Verification

The live file permissions on the active session token file (`storage/.session_token`) were inspected using the Windows `icacls` utility:

### Command:
```powershell
icacls storage\.session_token
```

### Observed Output:
```
storage\.session_token NT AUTHORITY\SYSTEM:(F)
                       DESKTOP-BP78RO7\azize:(R,W)

Successfully processed 1 files; Failed processing 0 files
```

### Analysis:
- **Inherited Permissions:** None. The file has an explicit, non-inherited security descriptor.
- **Authorized Accounts:**
  - `NT AUTHORITY\SYSTEM`: Full Control `(F)`.
  - `DESKTOP-BP78RO7\azize`: Read and Write `(R,W)`.
- **Unauthorized Accounts:** All other standard users, guest users, and non-elevated background services on the host machine are denied access.

---

## 4. Integration Verification

- `get_or_create_session_token()` calls `harden_token_file_permissions(token_file)` whenever the token is read or generated.
- In `backend/tests/test_authentication.py`, unit tests verify:
  - `test_harden_token_file_permissions_success`: Verifies execution on temporary test files.
  - `test_harden_token_file_permissions_nonexistent_path`: Verifies safe return code on missing files.
- Automated tests pass with zero errors.

---

## 5. Conclusion

The Windows session-token file ACL protection is **VERIFIED AND SECURED**. The token file on disk is protected against unauthorized local access on multi-user Windows workstations.

