"""
AgentDesk Local Session Authentication Service.
Generates, stores, and validates cryptographically secure local session tokens
for the desktop application's loopback backend service.

Guarantees:
- Tokens are 256-bit entropy generated via secrets.token_hex(32).
- Never hardcoded in source.
- Never returned through public or normal API responses.
- Protected against timing attacks via secrets.compare_digest.
- Stored in storage/.session_token with restricted permissions.
"""
import os
import secrets
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_ACTIVE_SESSION_TOKEN: Optional[str] = None

# HTTPBearer scheme (auto_error=False allows custom 401 error payloads)
bearer_scheme = HTTPBearer(auto_error=False)


def _get_storage_token_path() -> str:
    """Resolves absolute path to storage/.session_token."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_dir = os.path.normpath(os.path.join(backend_dir, ".."))
    storage_dir = os.path.join(root_dir, "storage")
    if not os.path.isdir(storage_dir):
        os.makedirs(storage_dir, exist_ok=True)
    return os.path.join(storage_dir, ".session_token")


def get_or_create_session_token() -> str:
    """
    Initializes or retrieves the active local session token.
    1. Checks AGENTDESK_SESSION_TOKEN environment variable.
    2. Checks storage/.session_token file.
    3. If neither exists, generates a fresh 256-bit token and persists it.
    """
    global _ACTIVE_SESSION_TOKEN

    if _ACTIVE_SESSION_TOKEN:
        return _ACTIVE_SESSION_TOKEN

    # 1. Environment variable check
    env_token = (os.environ.get("AGENTDESK_SESSION_TOKEN") or "").strip()
    if env_token and len(env_token) >= 32:
        _ACTIVE_SESSION_TOKEN = env_token
        return _ACTIVE_SESSION_TOKEN

    # 2. File storage check
    token_file = _get_storage_token_path()
    if os.path.isfile(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                saved_token = f.read().strip()
            if saved_token and len(saved_token) >= 32:
                _ACTIVE_SESSION_TOKEN = saved_token
                return _ACTIVE_SESSION_TOKEN
        except Exception:
            pass

    # 3. Generate fresh token
    new_token = secrets.token_hex(32)  # 64 hexadecimal characters (256 bits)
    try:
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(new_token)
        # Apply restrictive permissions on POSIX
        if hasattr(os, "chmod") and os.name != "nt":
            try:
                os.chmod(token_file, 0o600)
            except Exception:
                pass
    except Exception:
        pass

    _ACTIVE_SESSION_TOKEN = new_token
    return _ACTIVE_SESSION_TOKEN


def get_session_token() -> str:
    """Returns the active session token, generating one if not yet initialized."""
    return get_or_create_session_token()


def verify_token_value(candidate_token: Optional[str]) -> bool:
    """
    Constant-time token comparison against the active session token.
    Protects against timing attacks.
    """
    if not candidate_token or not isinstance(candidate_token, str):
        return False
    expected = get_session_token()
    return secrets.compare_digest(candidate_token.strip(), expected)


async def require_session_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> str:
    """
    FastAPI dependency enforcing local session bearer token authentication.
    Rejects missing or invalid tokens with HTTP 401 Unauthorized.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing local session authentication token in Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_token_value(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid local session authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials

