import pytest
from starlette.testclient import TestClient as StarletteTestClient
from backend.security.auth import get_session_token

# Ensure TestClient instances created across test modules automatically include
# valid Bearer authorization by default to maintain full regression compatibility.
_original_testclient_init = StarletteTestClient.__init__

def _authenticated_testclient_init(self, *args, **kwargs):
    headers = kwargs.get("headers")
    if headers is None:
        headers = {}
    else:
        headers = dict(headers)

    # Allow security tests to explicitly opt out of default token injection
    if headers.get("X-Skip-Auth-Injection") == "1":
        del headers["X-Skip-Auth-Injection"]
    elif "Authorization" not in headers:
        token = get_session_token()
        headers["Authorization"] = f"Bearer {token}"

    kwargs["headers"] = headers
    _original_testclient_init(self, *args, **kwargs)

StarletteTestClient.__init__ = _authenticated_testclient_init

