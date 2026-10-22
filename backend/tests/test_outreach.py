"""
Tests for AI-Powered Personalized Outreach Drafting Agent and Human Approval Gate.
All tests are 100% independent of live external AI services and network availability.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import (
    LeadRecord,
    OutreachDraftRequest,
    SendOutreachRequest,
    AIProviderConfig,
)
from backend.providers.llm import (
    TemplateLLMProvider,
    OllamaLLMProvider,
    CloudOpenAICompatibleProvider,
    get_llm_provider,
    _sanitize_recipient_name,
    _has_genuine_email,
)

client = TestClient(app)

SAMPLE_VERIFIED_LEAD = LeadRecord(
    id="live-lead-acme",
    company_name="Acme Grid Solutions",
    contact_name="Elena Vance",
    contact_role="Head of Energy Storage",
    email="elena.vance@acmegrid.test",
    website="https://www.acmegrid.test",
    industry="CleanTech & Energy",
    location="Austin, TX",
    source_note="[VERIFIED PUBLIC WEB] Extracted from https://www.acmegrid.test/team",
    created_at="2026-10-21T12:00:00Z",
    source_url="https://www.acmegrid.test/team",
    description="Developing modular commercial battery storage systems and grid frequency regulation software.",
    verified_fields=["company_name (title)", "description (meta)", "email (subpage)"],
    is_live=True,
)

SAMPLE_UNVERIFIED_EMAIL_LEAD = LeadRecord(
    id="live-lead-minimal",
    company_name="Minimal Tech Works",
    contact_name="(Not published on page)",
    contact_role="(Not published on page)",
    email="(No public email listed)",
    website="https://minimal.test",
    industry="Software Infrastructure",
    location="Remote",
    source_note="[VERIFIED PUBLIC WEB] Extracted from https://minimal.test",
    created_at="2026-10-21T12:00:00Z",
    source_url="https://minimal.test",
    description="Building resilient microservices and distributed queue infrastructure.",
    verified_fields=["company_name (title)", "description (body)"],
    is_live=True,
)

SAMPLE_SPARSE_LEAD = LeadRecord(
    id="lead-sparse",
    company_name="Sparse Corp",
    contact_name="",
    contact_role="",
    email="",
    website="https://sparse.test",
    industry="General Services",
    location="Denver, CO",
    source_note="Sparse note",
    created_at="2026-10-21T12:00:00Z",
    source_url="https://sparse.test",
    description="",
    verified_fields=[],
    is_live=False,
)

def test_sanitize_recipient_name_prevents_hallucination():
    assert _sanitize_recipient_name("Elena Vance", "Acme") == "Elena Vance"
    assert _sanitize_recipient_name("(Not published on page)", "Acme") == "Acme Team"
    assert _sanitize_recipient_name("unknown", "Acme") == "Acme Team"
    assert _sanitize_recipient_name("", "Acme") == "Acme Team"
    assert _sanitize_recipient_name(None, "Acme") == "Acme Team"

def test_has_genuine_email():
    assert _has_genuine_email("elena@company.com") is True
    assert _has_genuine_email("(No public email listed)") is False
    assert _has_genuine_email("") is False
    assert _has_genuine_email(None) is False
    assert _has_genuine_email("invalid-email") is False

def test_outreach_draft_with_verified_email_success():
    payload = {
        "leads": [SAMPLE_VERIFIED_LEAD.model_dump()],
        "service_offering": "AI Workflow Automation and Operations Consulting",
        "tone": "professional",
        "sender_name": "Jordan Lee",
        "sender_company": "AgentDesk Solutions",
        "ai_config": {"provider_type": "template"},
    }
    response = client.post("/api/outreach/draft", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["verified_email_count"] == 1
    assert data["missing_email_count"] == 0

    draft = data["drafts"][0]
    assert draft["company_name"] == "Acme Grid Solutions"
    assert draft["recipient_name"] == "Elena Vance"
    assert draft["recipient_email"] == "elena.vance@acmegrid.test"
    assert draft["has_verified_email"] is True
    assert "Elena Vance" in draft["body"]
    assert "Acme Grid Solutions" in draft["subject"]
    assert "battery storage" in draft["body"]
    assert "Jordan Lee" in draft["body"]
    assert "AgentDesk Solutions" in draft["body"]
    assert draft["status"] == "drafted"

def test_outreach_draft_with_missing_email_flags_correctly():
    payload = {
        "leads": [SAMPLE_UNVERIFIED_EMAIL_LEAD.model_dump()],
        "service_offering": "DevOps Optimization",
        "tone": "consultative",
        "sender_name": "Jordan Lee",
        "sender_company": "AgentDesk Solutions",
        "ai_config": {"provider_type": "template"},
    }
    response = client.post("/api/outreach/draft", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["verified_email_count"] == 0
    assert data["missing_email_count"] == 1

    draft = data["drafts"][0]
    assert draft["company_name"] == "Minimal Tech Works"
    # Never invent a person's name when not published on page!
    assert draft["recipient_name"] == "Minimal Tech Works Team"
    assert "Hi Minimal Tech Works Team," in draft["body"]
    assert draft["has_verified_email"] is False
    assert draft["recipient_email"] == "(No public email listed)"
    assert "Grounded exclusively in verified public metadata" in draft["grounding_notes"]

def test_outreach_draft_with_sparse_lead_no_crash_no_hallucination():
    payload = {
        "leads": [SAMPLE_SPARSE_LEAD.model_dump()],
        "service_offering": "Quality Engineering",
        "tone": "concise",
    }
    response = client.post("/api/outreach/draft", json=payload)
    assert response.status_code == 200
    data = response.json()
    draft = data["drafts"][0]
    assert draft["company_name"] == "Sparse Corp"
    assert draft["recipient_name"] == "Sparse Corp Team"
    assert "Hi Sparse Corp Team," in draft["body"]
    assert draft["has_verified_email"] is False

def test_human_approval_gate_blocks_unapproved_sending():
    """Verify transmission is strictly rejected if operator approval is false."""
    payload = {
        "draft_id": "draft-123",
        "approved": False,
        "recipient_email": "elena.vance@acmegrid.test",
        "subject": "Quick inquiry",
        "body": "Hello Elena...",
    }
    response = client.post("/api/outreach/send", json=payload)
    assert response.status_code == 400
    assert "Safety Gate: Outreach transmission requires explicit operator approval" in response.json()["detail"]

def test_sending_blocked_for_leads_without_verified_email():
    """Verify sending is blocked even if approved when email is unverified or placeholder."""
    payload = {
        "draft_id": "draft-123",
        "approved": True,
        "recipient_email": "(No public email listed)",
        "subject": "Quick inquiry",
        "body": "Hello...",
    }
    response = client.post("/api/outreach/send", json=payload)
    assert response.status_code == 422
    assert "Dispatch Blocked: Target lead lacks a verified public email address" in response.json()["detail"]

    # Also test empty email string
    payload["recipient_email"] = ""
    response_empty = client.post("/api/outreach/send", json=payload)
    assert response_empty.status_code == 422

def test_sending_succeeds_when_approved_with_verified_email():
    """Verify dispatch in simulation mode explicitly labels result as simulated and does not claim real delivery."""
    payload = {
        "draft_id": "draft-valid-1",
        "approved": True,
        "recipient_email": "elena.vance@acmegrid.test",
        "subject": "Exploring AI Automation for Acme Grid Solutions",
        "body": "Hi Elena,\n\nI came across Acme Grid Solutions...",
    }
    response = client.post("/api/outreach/send", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "simulated"
    assert data["is_simulated"] is True
    assert data["provider"] == "simulation"
    assert data["draft_id"] == "draft-valid-1"
    assert data["recipient_email"] == "elena.vance@acmegrid.test"
    assert "Simulation Mode" in data["message"]
    assert "No real email was delivered" in data["message"]
    assert data["dispatched_at"] != ""

def test_outreach_send_validates_non_empty_content():
    payload = {
        "draft_id": "draft-1",
        "approved": True,
        "recipient_email": "contact@example.com",
        "subject": "   ",
        "body": "Body text",
    }
    response = client.post("/api/outreach/send", json=payload)
    assert response.status_code == 422
    assert "Subject and email body must not be empty" in response.json()["detail"]

def test_get_outreach_providers_endpoint():
    response = client.get("/api/outreach/providers")
    assert response.status_code == 200
    data = response.json()
    providers = data["providers"]
    assert len(providers) >= 3
    ids = [p["id"] for p in providers]
    assert "template" in ids
    assert "ollama" in ids
    assert "openai" in ids
    # Verify safe dispatch metadata is returned without credentials
    assert "dispatch" in data
    assert data["dispatch"]["mode"] in ("simulation", "smtp", "resend")
    assert "password" not in str(data).lower()
    assert "secret" not in str(data).lower()

def test_ollama_provider_connection_error_handling():
    """Verify clear error diagnostic is returned when local Ollama is offline."""
    payload = {
        "leads": [SAMPLE_VERIFIED_LEAD.model_dump()],
        "service_offering": "Cloud Architecture",
        "ai_config": {
            "provider_type": "ollama",
            "api_base": "http://127.0.0.1:9999", # Non-existent port
            "model_name": "llama3"
        }
    }
    response = client.post("/api/outreach/draft", json=payload)
    assert response.status_code == 502
    data = response.json()
    assert "Local Ollama provider failure" in data["detail"]
    assert "Ensure Ollama is running" in data["detail"]

def test_cloud_ai_provider_missing_key_error():
    """Verify clear error message when cloud AI is selected without providing an API key."""
    payload = {
        "leads": [SAMPLE_VERIFIED_LEAD.model_dump()],
        "service_offering": "Cloud Architecture",
        "ai_config": {
            "provider_type": "openai",
            "model_name": "gpt-4o-mini",
            "api_key": ""
        }
    }
    with patch.dict("os.environ", {}, clear=True):
        response = client.post("/api/outreach/draft", json=payload)
        assert response.status_code == 502
        assert "Cloud AI provider requires an API key" in response.json()["detail"]

def test_cloud_ai_successful_mocked_response():
    """Verify cloud provider correctly parses OpenAI-compatible JSON responses."""
    provider = CloudOpenAICompatibleProvider(
        api_base="https://api.openai.com/v1",
        model_name="gpt-4o-mini",
        api_key="test-key-mock"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"subject": "Custom Cloud Proposal for Acme", "body": "Hi Elena,\\n\\nCustom proposal..."}'
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        draft = pytest.importorskip("asyncio").run(
            provider.draft_lead_outreach(
                lead=SAMPLE_VERIFIED_LEAD,
                service_offering="Cloud Architecture"
            )
        )
        assert draft.subject == "Custom Cloud Proposal for Acme"
        assert "Custom proposal" in draft.body
        assert draft.recipient_name == "Elena Vance"
        assert draft.has_verified_email is True

def test_smtp_dispatch_successful_mocked(monkeypatch):
    """Verify live SMTP dispatch succeeds when mocked, setting correct status and provider."""
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "smtp")
    monkeypatch.setenv("AGENTDESK_SMTP_HOST", "smtp.testserver.local")
    monkeypatch.setenv("AGENTDESK_SMTP_PORT", "587")
    monkeypatch.setenv("AGENTDESK_SMTP_USER", "user@test.local")
    monkeypatch.setenv("AGENTDESK_SMTP_PASSWORD", "secret-smtp-password")
    monkeypatch.setenv("AGENTDESK_SMTP_FROM_EMAIL", "outreach@agentdesk.test")

    payload = {
        "draft_id": "draft-smtp-1",
        "approved": True,
        "recipient_email": "target@client.test",
        "subject": "AI Pipeline Proposal",
        "body": "Hi Client Team,\n\nHere is our verified proposal.",
    }

    mock_smtp_instance = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp_instance) as mock_smtp_cls:
        response = client.post("/api/outreach/send", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        assert data["is_simulated"] is False
        assert "smtp" in data["provider"]
        assert "target@client.test" in data["recipient_email"]
        assert "accepted by SMTP gateway" in data["message"]

        # Verify SMTP server calls
        mock_smtp_cls.assert_called_once_with("smtp.testserver.local", 587, timeout=12)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("user@test.local", "secret-smtp-password")
        mock_smtp_instance.send_message.assert_called_once()
        mock_smtp_instance.quit.assert_called_once()

def test_smtp_dispatch_missing_config_error(monkeypatch):
    """Verify missing SMTP configuration returns a clear 500 error."""
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "smtp")
    monkeypatch.delenv("AGENTDESK_SMTP_HOST", raising=False)
    monkeypatch.delenv("AGENTDESK_SMTP_FROM_EMAIL", raising=False)

    payload = {
        "draft_id": "draft-smtp-missing",
        "approved": True,
        "recipient_email": "target@client.test",
        "subject": "Subject",
        "body": "Body",
    }
    response = client.post("/api/outreach/send", json=payload)
    assert response.status_code == 500
    assert "SMTP dispatch configuration incomplete" in response.json()["detail"]

def test_smtp_dispatch_provider_failure_sanitized(monkeypatch):
    """Verify SMTP exceptions are caught and sanitized so passwords are never exposed in error details."""
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "smtp")
    monkeypatch.setenv("AGENTDESK_SMTP_HOST", "smtp.testserver.local")
    monkeypatch.setenv("AGENTDESK_SMTP_PASSWORD", "secret-pass-12345")
    monkeypatch.setenv("AGENTDESK_SMTP_FROM_EMAIL", "outreach@agentdesk.test")

    payload = {
        "draft_id": "draft-smtp-fail",
        "approved": True,
        "recipient_email": "target@client.test",
        "subject": "Subject",
        "body": "Body",
    }

    import smtplib
    with patch("smtplib.SMTP", side_effect=smtplib.SMTPAuthenticationError(535, b"Auth failed for secret-pass-12345")):
        response = client.post("/api/outreach/send", json=payload)
        assert response.status_code == 502
        detail = response.json()["detail"]
        assert "SMTP delivery failed" in detail
        # Verify secret password was not exposed
        assert "secret-pass-12345" not in detail

def test_resend_dispatch_successful_mocked(monkeypatch):
    """Verify Resend HTTP provider dispatch succeeds when mocked."""
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "resend")
    monkeypatch.setenv("AGENTDESK_RESEND_API_KEY", "re_testkey123")
    monkeypatch.setenv("AGENTDESK_RESEND_FROM_EMAIL", "outreach@agentdesk.test")

    payload = {
        "draft_id": "draft-resend-1",
        "approved": True,
        "recipient_email": "target@client.test",
        "subject": "Resend Subject",
        "body": "Resend Body",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "resend_msg_abc123"}

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_resp

    with patch("backend.providers.email_dispatcher.httpx.Client", return_value=mock_client):
        response = client.post("/api/outreach/send", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        assert data["is_simulated"] is False
        assert data["provider"] == "resend"
        assert "accepted by Resend API" in data["message"]

def test_resend_dispatch_api_error_sanitized(monkeypatch):
    """Verify Resend API failure returns 502 and scrubs the API key."""
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "resend")
    monkeypatch.setenv("AGENTDESK_RESEND_API_KEY", "re_supersecretkey999")
    monkeypatch.setenv("AGENTDESK_RESEND_FROM_EMAIL", "outreach@agentdesk.test")

    payload = {
        "draft_id": "draft-resend-fail",
        "approved": True,
        "recipient_email": "target@client.test",
        "subject": "Subject",
        "body": "Body",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"message": "Invalid API key re_supersecretkey999"}'

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_resp

    with patch("backend.providers.email_dispatcher.httpx.Client", return_value=mock_client):
        response = client.post("/api/outreach/send", json=payload)
        assert response.status_code == 502
        detail = response.json()["detail"]
        assert "Resend API returned status 401" in detail
        assert "re_supersecretkey999" not in detail
        assert "[REDACTED" in detail

def test_sanitize_log_message_scrubs_all_credentials():
    from backend.providers.email_dispatcher import sanitize_log_message
    raw = "Failed with key re_abc123456 and sk-proj-9999 and password=SuperSecretPassword123"
    sanitized = sanitize_log_message(raw)
    assert "re_abc123456" not in sanitized
    assert "sk-proj-9999" not in sanitized
    assert "SuperSecretPassword123" not in sanitized
    assert "[REDACTED" in sanitized

def test_env_loader_zero_dependency_parsing(tmp_path):
    """Verify env_loader parses key-value pairs, comments, quotes, and whitespace without third-party dependencies."""
    from backend.env_loader import parse_env_file
    sample_env = tmp_path / ".env.test"
    sample_env.write_text(
        "# Comment line\n"
        "AGENTDESK_SMTP_HOST=smtp.custom.io\n"
        "AGENTDESK_SMTP_PORT=\"587\"\n"
        "AGENTDESK_SMTP_USER='user@custom.io'\n"
        "EMPTY_VAL=\n"
        "WITH_INLINE=some_value # Trailing comment\n",
        encoding="utf-8"
    )
    parsed = parse_env_file(str(sample_env))
    assert parsed["AGENTDESK_SMTP_HOST"] == "smtp.custom.io"
    assert parsed["AGENTDESK_SMTP_PORT"] == "587"
    assert parsed["AGENTDESK_SMTP_USER"] == "user@custom.io"
    assert parsed["WITH_INLINE"] == "some_value"
    assert "EMPTY_VAL" in parsed

def test_duplicate_send_blocks_repeated_transmission():
    """Verify duplicate-send protection rejects repeated requests with 409 Conflict."""
    from backend.dispatch_tracker import global_dispatch_tracker
    global_dispatch_tracker.clear()

    payload = {
        "draft_id": "draft-dup-test-1",
        "approved": True,
        "recipient_email": "target@client.test",
        "subject": "Unique Subject For Duplicate Test",
        "body": "Unique body content for duplicate test.",
    }

    # First send: succeeds
    res1 = client.post("/api/outreach/send", json=payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "simulated"

    # Repeated send with same draft_id: blocked with 409 Conflict
    res2 = client.post("/api/outreach/send", json=payload)
    assert res2.status_code == 409
    assert "Duplicate Send Blocked" in res2.json()["detail"]
    assert "draft-dup-test-1" in res2.json()["detail"]

def test_duplicate_send_identical_content_blocks_repeated_transmission():
    """Verify duplicate-send protection rejects identical email content even under a different draft_id."""
    from backend.dispatch_tracker import global_dispatch_tracker
    global_dispatch_tracker.clear()

    payload1 = {
        "draft_id": "draft-idem-1",
        "approved": True,
        "recipient_email": "sarah@biotech.test",
        "subject": "Idempotent Proposal",
        "body": "Identical proposal text for Sarah.",
    }
    payload2 = {
        "draft_id": "draft-idem-2",  # Different draft ID
        "approved": True,
        "recipient_email": "sarah@biotech.test",  # Same recipient
        "subject": "Idempotent Proposal",         # Same subject
        "body": "Identical proposal text for Sarah.", # Same body
    }

    res1 = client.post("/api/outreach/send", json=payload1)
    assert res1.status_code == 200

    # Second send with identical recipient & content: blocked with 409 Conflict
    res2 = client.post("/api/outreach/send", json=payload2)
    assert res2.status_code == 409
    assert "Duplicate Send Blocked" in res2.json()["detail"]

def test_syntactically_valid_unverified_email_blocked_from_dispatch():
    """
    CRITICAL REQUIREMENT: A syntactically valid email alone must NOT count as verified.
    When a lead was researched without a verified public email, drafting it produces
    has_verified_email=False. Any subsequent attempt to dispatch outreach to that draft
    (even if an attacker or caller injects a syntactically valid email) MUST be blocked.
    """
    from backend.dispatch_tracker import global_dispatch_tracker
    global_dispatch_tracker.clear()

    # 1. Draft outreach for a lead that lacks verified public email
    draft_res = client.post("/api/outreach/draft", json={
        "leads": [SAMPLE_UNVERIFIED_EMAIL_LEAD.model_dump()],
        "service_offering": "AI Workflows",
    })
    assert draft_res.status_code == 200
    draft_data = draft_res.json()["drafts"][0]
    unverified_draft_id = draft_data["id"]
    assert draft_data["has_verified_email"] is False

    # 2. Attempt to dispatch by injecting a syntactically valid email (e.g. attacker@domain.com)
    send_payload = {
        "draft_id": unverified_draft_id,
        "approved": True,
        "recipient_email": "injected.valid.syntax@enterprise.com",
        "subject": "Injected proposal",
        "body": "Trying to bypass verification with a valid syntax email.",
    }
    send_res = client.post("/api/outreach/send", json=send_payload)
    assert send_res.status_code == 422
    detail = send_res.json()["detail"]
    assert "Dispatch Blocked" in detail
    assert "A syntactically valid email alone does not count as verified" in detail

def test_explicitly_unverified_payload_blocked():
    """Verify that passing has_verified_email=False blocks dispatch even with syntactically valid email."""
    from backend.dispatch_tracker import global_dispatch_tracker
    global_dispatch_tracker.clear()

    payload = {
        "draft_id": "draft-unverified-flag",
        "approved": True,
        "recipient_email": "valid.syntax.unverified@company.com",
        "subject": "Subject",
        "body": "Body text",
        "has_verified_email": False,
    }
    res = client.post("/api/outreach/send", json=payload)
    assert res.status_code == 422
    assert "A syntactically valid email alone does not count as verified" in res.json()["detail"]

def test_verified_draft_blocks_recipient_tampering():
    """Verify that for a verified lead, dispatch blocks if the recipient email was tampered with."""
    from backend.dispatch_tracker import global_dispatch_tracker
    global_dispatch_tracker.clear()

    # Draft for verified lead
    draft_res = client.post("/api/outreach/draft", json={
        "leads": [SAMPLE_VERIFIED_LEAD.model_dump()],
        "service_offering": "CleanTech Automation",
    })
    assert draft_res.status_code == 200
    draft = draft_res.json()["drafts"][0]
    assert draft["has_verified_email"] is True
    assert draft["recipient_email"] == "elena.vance@acmegrid.test"

    # Attempt to send to an altered/tampered address
    tampered_payload = {
        "draft_id": draft["id"],
        "approved": True,
        "recipient_email": "tampered.recipient@othercompany.com",
        "subject": draft["subject"],
        "body": draft["body"],
    }
    tampered_res = client.post("/api/outreach/send", json=tampered_payload)
    assert tampered_res.status_code == 422
    assert "Recipient address does not match the verified public email recorded for this draft" in tampered_res.json()["detail"]

    # Sending to the genuine verified email succeeds
    legit_payload = {
        "draft_id": draft["id"],
        "approved": True,
        "recipient_email": "elena.vance@acmegrid.test",
        "subject": draft["subject"],
        "body": draft["body"],
    }
    legit_res = client.post("/api/outreach/send", json=legit_payload)
    assert legit_res.status_code == 200
    assert legit_res.json()["status"] == "simulated"

def test_in_flight_concurrent_duplicate_send_is_blocked():
    """Verify concurrent / in-flight duplicate requests are blocked with 409 Conflict."""
    from backend.dispatch_tracker import global_dispatch_tracker
    global_dispatch_tracker.clear()

    payload = {
        "draft_id": "draft-concurrent-test",
        "approved": True,
        "recipient_email": "concurrent@enterprise.test",
        "subject": "Concurrent Test",
        "body": "Body for concurrent test.",
    }

    # Simulate an active in-flight request claiming the lock
    allowed, reason, dup = global_dispatch_tracker.claim_dispatch(
        draft_id=payload["draft_id"],
        recipient_email=payload["recipient_email"],
        subject=payload["subject"],
        body=payload["body"],
    )
    assert allowed is True
    assert global_dispatch_tracker.is_in_flight(payload["draft_id"])

    # A concurrent request arriving while the first is in-flight MUST be blocked
    res = client.post("/api/outreach/send", json=payload)
    assert res.status_code == 409
    assert "currently in-flight" in res.json()["detail"]

    # Release the simulated claim
    global_dispatch_tracker.release_claim(
        draft_id=payload["draft_id"],
        recipient_email=payload["recipient_email"],
        subject=payload["subject"],
        body=payload["body"],
    )
    assert not global_dispatch_tracker.is_in_flight(payload["draft_id"])

def test_dispatch_claim_released_on_delivery_failure():
    """Verify that when a delivery error occurs, the in-flight claim is released so the user can retry."""
    from backend.dispatch_tracker import global_dispatch_tracker
    global_dispatch_tracker.clear()

    payload = {
        "draft_id": "draft-fail-release-test",
        "approved": True,
        "recipient_email": "target@failover.test",
        "subject": "Failover Test",
        "body": "Body content for failover test.",
    }

    with patch("backend.main.dispatch_outreach_email") as mock_dispatch:
        from backend.providers.email_dispatcher import DispatchDeliveryError
        mock_dispatch.side_effect = DispatchDeliveryError("Simulated provider outage")

        res = client.post("/api/outreach/send", json=payload)
        assert res.status_code == 502
        assert "Simulated provider outage" in res.json()["detail"]

    # In-flight lock must be cleanly released
    assert not global_dispatch_tracker.is_in_flight(payload["draft_id"])
    assert not global_dispatch_tracker.is_dispatched(payload["draft_id"])

def test_dispatch_tracker_sqlite_persistence_across_instances(tmp_path):
    """Verify that dispatched records survive across restarts via SQLite."""
    from backend.dispatch_tracker import DispatchTracker
    test_db = str(tmp_path / "test_dispatches.db")

    # Instance 1: record a dispatch
    tracker1 = DispatchTracker(db_path=test_db)
    tracker1.record_dispatch(
        draft_id="draft-persist-1",
        recipient_email="ceo@target.test",
        subject="Important proposal",
        body="Body text",
        status="sent",
        provider="smtp",
    )
    assert tracker1.is_dispatched("draft-persist-1")

    # Instance 2 (simulating service restart): reads from the same DB
    tracker2 = DispatchTracker(db_path=test_db)
    assert tracker2.is_dispatched("draft-persist-1")

    # Duplicate check on Instance 2 blocks duplicate
    dup = tracker2.check_duplicate(
        draft_id="draft-persist-1",
        recipient_email="ceo@target.test",
        subject="Important proposal",
        body="Body text",
    )
    assert dup is not None
    assert dup.draft_id == "draft-persist-1"

def test_dynamic_env_reload_in_get_dispatch_config(tmp_path, monkeypatch):
    """Verify that get_dispatch_config dynamically reloads configuration on invocation."""
    from backend.providers.email_dispatcher import get_dispatch_status_info

    # 1. Initially simulation mode
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "simulation")
    monkeypatch.delenv("AGENTDESK_SMTP_HOST", raising=False)
    info1 = get_dispatch_status_info()
    assert info1["mode"] == "simulation"
    assert info1["is_live"] is False

    # 2. Update environment to SMTP
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "smtp")
    monkeypatch.setenv("AGENTDESK_SMTP_HOST", "mail.enterprise.test")
    monkeypatch.setenv("AGENTDESK_SMTP_FROM_EMAIL", "outreach@enterprise.test")
    info2 = get_dispatch_status_info()
    assert info2["mode"] == "smtp"
    assert info2["is_live"] is True
    assert "mail.enterprise.test" in info2["display_name"]


