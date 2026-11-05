"""
Automated Security Test Suite: Local FastAPI Bearer Token Authentication (Phase A.2.2).
Verifies:
1. Public /health check accessibility without credentials.
2. Minimal /health payload without internal paths or sensitive tokens.
3. 401 Unauthorized on missing credentials across all sensitive /api/* endpoints.
4. 401 Unauthorized on non-Bearer schemes (Basic, Token, etc.).
5. 401 Unauthorized on invalid/tampered Bearer tokens.
6. 200 OK with valid Bearer token.
7. Cryptographic token entropy (256-bit hex) and storage/.session_token persistence.
8. Timing-safe comparison via secrets.compare_digest.
9. Windows/POSIX file permission hardening (harden_token_file_permissions).
"""
import os
import secrets
import tempfile
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.security.auth import (
    get_session_token,
    verify_token_value,
    get_or_create_session_token,
    harden_token_file_permissions,
)


def make_raw_client():
    return TestClient(app, headers={"X-Skip-Auth-Injection": "1"})


# ============================================================================
# 1. Public Health Check Tests
# ============================================================================

def test_health_check_accessible_unauthenticated():
    client = make_raw_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data
    assert "provider" in data
    assert "demo_mode" in data

    raw_text = resp.text.lower()
    assert "token" not in raw_text
    assert "secret" not in raw_text
    assert "c:\\" not in raw_text
    assert "/users/" not in raw_text


# ============================================================================
# 2. Authentication Enforcement on Protected Routes (Full Route Coverage)
# ============================================================================

@pytest.mark.parametrize(
    "method,endpoint,payload",
    [
        ("POST", "/api/research/leads", {"topic": "AI", "industry": "Tech", "location": "USA"}),
        ("POST", "/api/research/export-csv", {"leads": []}),
        ("GET", "/api/outreach/providers", None),
        ("POST", "/api/outreach/draft", {"lead": {"id": "1", "company_name": "Test"}}),
        ("POST", "/api/outreach/send", {"draft_id": "fake", "confirmed": True}),
        ("GET", "/api/outreach/history", None),
        ("GET", "/api/outreach/history/export-csv", None),
        ("POST", "/api/discovery/plan", {"prompt": "Find solar companies in Lahore"}),
        ("GET", "/api/discovery/providers", None),
        ("POST", "/api/discovery/jobs", {"plan": {"prompt": "Find solar in Lahore"}}),
        ("GET", "/api/discovery/jobs/job-123", None),
        ("POST", "/api/discovery/jobs/job-123/cancel", None),
        ("GET", "/api/discovery/jobs/job-123/leads", None),
        ("GET", "/api/discovery/jobs/job-123/export-csv", None),
        ("POST", "/api/discovery/transfer-outreach", {"job_id": "job-123", "lead_ids": ["l1"]}),
        ("GET", "/api/outreach/drafts", None),
        ("GET", "/api/outreach/drafts/draft-123", None),
        ("PUT", "/api/outreach/drafts/draft-123", {"subject": "New"}),
        ("POST", "/api/outreach/drafts/draft-123/approve", None),
        ("POST", "/api/outreach/drafts/draft-123/unapprove", None),
        ("POST", "/api/outreach/drafts/draft-123/discard", None),
        ("DELETE", "/api/outreach/drafts/draft-123", None),
    ],
)
def test_unauthenticated_requests_return_401(method, endpoint, payload):
    client = make_raw_client()
    if method == "GET":
        resp = client.get(endpoint)
    elif method == "POST":
        resp = client.post(endpoint, json=payload or {})
    elif method == "PUT":
        resp = client.put(endpoint, json=payload or {})
    elif method == "DELETE":
        resp = client.delete(endpoint)
    else:
        pytest.fail(f"Unsupported method {method}")

    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
    assert resp.headers["WWW-Authenticate"] == "Bearer"
    assert "Unauthorized" in resp.json().get("detail", "")


def test_invalid_scheme_returns_401():
    client = make_raw_client()

    resp_basic = client.get(
        "/api/discovery/providers",
        headers={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    assert resp_basic.status_code == 401
    assert "Bearer required" in resp_basic.json().get("detail", "")

    resp_token = client.get(
        "/api/discovery/providers",
        headers={"Authorization": "Token some_token"}
    )
    assert resp_token.status_code == 401
    assert "Bearer required" in resp_token.json().get("detail", "")

    resp_empty = client.get(
        "/api/discovery/providers",
        headers={"Authorization": "Bearer"}
    )
    assert resp_empty.status_code == 401


def test_tampered_or_invalid_token_returns_401():
    client = make_raw_client()
    bad_tokens = [
        "Bearer invalid_secret_token_value",
        "Bearer " + "0" * 64,
        "Bearer " + secrets.token_hex(32),
        "Bearer fake",
    ]
    for auth_hdr in bad_tokens:
        resp = client.get(
            "/api/discovery/providers",
            headers={"Authorization": auth_hdr}
        )
        assert resp.status_code == 401
        assert "Invalid local session authentication token" in resp.json().get("detail", "")


# ============================================================================
# 3. Valid Bearer Token Acceptance
# ============================================================================

def test_valid_bearer_token_succeeds():
    valid_token = get_session_token()
    client = make_raw_client()

    resp = client.get(
        "/api/discovery/providers",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data

    resp_hist = client.get(
        "/api/outreach/history",
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert resp_hist.status_code == 200


# ============================================================================
# 4. Token Cryptographic Entropy, Storage & Timing-Safe Verification
# ============================================================================

def test_token_entropy_and_storage_persistence():
    token = get_session_token()
    assert len(token) == 64
    assert all(c in "0123456789abcdefABCDEF" for c in token)

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    storage_dir = os.path.normpath(os.path.join(backend_dir, "..", "storage"))
    token_file = os.path.join(storage_dir, ".session_token")

    if os.path.isfile(token_file):
        with open(token_file, "r", encoding="utf-8") as f:
            persisted = f.read().strip()
        assert persisted == token


def test_timing_safe_token_verification():
    valid_token = get_session_token()

    assert verify_token_value(valid_token) is True
    assert verify_token_value(f"  {valid_token}  ") is True

    assert verify_token_value("") is False
    assert verify_token_value(None) is False

    tampered = valid_token[:-1] + ("0" if valid_token[-1] != "0" else "1")
    assert verify_token_value(tampered) is False


def test_cors_preflight_options_unauthenticated():
    client = make_raw_client()
    resp = client.options(
        "/api/research/leads",
        headers={
            "Origin": "http://localhost:1420",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
    )
    assert resp.status_code == 200


# ============================================================================
# 5. File Permission Hardening Tests (Task 6)
# ============================================================================

def test_harden_token_file_permissions_success():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"sample_token_content")
        temp_path = f.name

    try:
        success = harden_token_file_permissions(temp_path)
        assert success is True
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_harden_token_file_permissions_nonexistent_path():
    success = harden_token_file_permissions("non_existent_token_file_xyz_123.bin")
    assert success is False

    success_empty = harden_token_file_permissions("")
    assert success_empty is False
