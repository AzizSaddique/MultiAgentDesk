"""
AgentDesk Security Foundation Module.
Provides centralized SSRF protection and local bearer token authentication.
"""
from .url_validator import (
    validate_target_url,
    validate_outbound_url,
    is_prohibited_ip,
    resolve_domain_ips,
    canonicalize_host,
    safe_fetch_get,
    create_pinned_transport,
    PinnedAsyncNetworkBackend,
    SSRFSecurityError,
    SSRFRedirectError,
)
from .auth import (
    get_session_token,
    get_or_create_session_token,
    require_session_token,
    verify_token_value,
    harden_token_file_permissions,
)

__all__ = [
    "validate_target_url",
    "validate_outbound_url",
    "is_prohibited_ip",
    "resolve_domain_ips",
    "canonicalize_host",
    "safe_fetch_get",
    "create_pinned_transport",
    "PinnedAsyncNetworkBackend",
    "SSRFSecurityError",
    "SSRFRedirectError",
    "get_session_token",
    "get_or_create_session_token",
    "require_session_token",
    "verify_token_value",
    "harden_token_file_permissions",
]

