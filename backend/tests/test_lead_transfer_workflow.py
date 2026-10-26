"""
Comprehensive Tests for Lead Transfer to Outreach Draft Workflow,
Personalized Generation Grounding, Duplicate Prevention, and Human Approval Safety Gates.
All external providers are mocked/simulated; no real credentials or network calls required.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app, DRAFT_REGISTRY
from backend.dispatch_tracker import global_dispatch_tracker
from backend.models import (
    DiscoveredLeadRecord,
    TransferToOutreachRequest,
    UpdateDraftRequest,
    DiscardDraftRequest,
    SendOutreachRequest,
    AIProviderConfig,
)


@pytest.fixture(autouse=True)
def clean_test_environment(tmp_path):
    """Isolates each test with a clean SQLite test database and in-memory registry."""
    DRAFT_REGISTRY.clear()
    test_db = str(tmp_path / "test_transfer_workflow.db")
    orig_path = global_dispatch_tracker._db_path
    global_dispatch_tracker._db_path = test_db
    global_dispatch_tracker._init_sqlite()
    global_dispatch_tracker.clear()
    yield
    global_dispatch_tracker.clear()
    global_dispatch_tracker._db_path = orig_path
    DRAFT_REGISTRY.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _seed_discovered_leads():
    """Seeds verified and unverified discovered leads with varying evidence levels."""
    # 1. High evidence, verified public email
    lead_rich = DiscoveredLeadRecord(
        id="lead-rich-1",
        job_id="job-test-workflow",
        company_name="Acme Health Platforms",
        website="https://acmehealth.example.com",
        industry="Healthcare Technology",
        city="Austin",
        country="USA",
        services_description="Enterprise telemedicine portal, patient data synchronization, and HIPAA-compliant clinical APIs.",
        email="contact@acmehealth.example.com",
        email_verification_status="verified_public",
        phone="+1-512-555-0101",
        phone_verification_status="verified_public",
        source_urls=["https://acmehealth.example.com/about", "https://acmehealth.example.com/contact"],
        discovery_source="web_search",
        discovery_query="healthcare telemedicine clinical APIs Austin",
        discovered_at="2026-10-25T12:00:00Z",
        relevance_score=0.94,
        relevance_explanation="High match for telemedicine and clinical API infrastructure.",
        research_status="completed",
        verified_fields=["company_name", "website", "email", "phone", "services_description"],
        is_live=True,
    )

    # 2. Insufficient evidence, verified public email
    lead_sparse = DiscoveredLeadRecord(
        id="lead-sparse-2",
        job_id="job-test-workflow",
        company_name="Quantum Holdings",
        website="https://quantumholdings.example.com",
        industry="",
        city="Denver",
        country="USA",
        services_description="",  # Insufficient public business evidence
        email="info@quantumholdings.example.com",
        email_verification_status="verified_public",
        phone="",
        phone_verification_status="not_found",
        source_urls=["https://quantumholdings.example.com"],
        discovery_source="directory",
        discovery_query="holdings Denver",
        discovered_at="2026-10-25T12:01:00Z",
        relevance_score=0.45,
        relevance_explanation="Minimal public data found on target page.",
        research_status="completed",
        verified_fields=["company_name", "website", "email"],
        is_live=True,
    )

    # 3. Rich evidence, unverified / missing email
    lead_unverified = DiscoveredLeadRecord(
        id="lead-unverified-3",
        job_id="job-test-workflow",
        company_name="LogiRoute Logistics",
        website="https://logiroute.example.com",
        industry="Supply Chain & Freight",
        city="Chicago",
        country="USA",
        services_description="Real-time route optimization algorithms, fleet dispatch dashboards, and warehouse inventory tracking.",
        email="",
        email_verification_status="not_found",
        phone="+1-312-555-0199",
        phone_verification_status="verified_public",
        source_urls=["https://logiroute.example.com"],
        discovery_source="web_search",
        discovery_query="fleet dispatch freight Chicago",
        discovered_at="2026-10-25T12:02:00Z",
        relevance_score=0.88,
        relevance_explanation="Direct match for automated route tracking software.",
        research_status="completed",
        verified_fields=["company_name", "website", "phone", "services_description"],
        is_live=True,
    )

    global_dispatch_tracker.save_discovered_lead(lead_rich)
    global_dispatch_tracker.save_discovered_lead(lead_sparse)
    global_dispatch_tracker.save_discovered_lead(lead_unverified)
    return lead_rich, lead_sparse, lead_unverified


# ==============================================================================
# 1. Lead Transfer Tests
# ==============================================================================

def test_single_lead_transfer_to_outreach(client):
    """Tests transferring a single discovered lead to an outreach draft."""
    lead_rich, _, _ = _seed_discovered_leads()

    res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1"],
        "service_offering": "Full-stack web application development and cloud modernization",
        "tone": "consultative",
        "sender_name": "Dev Team",
        "sender_company": "AgentDesk Solutions",
    })

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["created_count"] == 1
    assert data["skipped_count"] == 0
    assert data["failed_count"] == 0
    assert data["verified_email_count"] == 1
    assert data["missing_email_count"] == 0

    draft = data["drafts"][0]
    assert draft["company_name"] == "Acme Health Platforms"
    assert draft["recipient_email"] == "contact@acmehealth.example.com"
    assert draft["has_verified_email"] is True
    assert draft["status"] == "drafted"
    assert "https://acmehealth.example.com" in draft["source_url"]
    assert draft["discovery_source"] == "web_search"
    assert "Full-stack web application development" in draft["body"]
    assert "telemedicine" in draft["body"] or "Acme Health Platforms" in draft["body"]


def test_bulk_lead_transfer_with_counts(client):
    """Tests bulk transfer of multiple leads, verifying success and email verification breakdown."""
    _seed_discovered_leads()

    res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1", "lead-sparse-2", "lead-unverified-3"],
        "prevent_duplicates": True,
    })

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert data["created_count"] == 3
    assert data["skipped_count"] == 0
    assert data["failed_count"] == 0
    assert data["verified_email_count"] == 2
    assert data["missing_email_count"] == 1

    # Verify unverified lead has safe placeholder and blocked email status
    drafts = {d["lead_id"]: d for d in data["drafts"]}
    unverified_draft = drafts["disc-lead-unverified-3"]
    assert unverified_draft["has_verified_email"] is False
    assert unverified_draft["recipient_email"] == "(No public email listed)"


def test_duplicate_lead_transfer_prevention(client):
    """Tests that transferring the same lead twice is prevented when prevent_duplicates is True."""
    _seed_discovered_leads()

    # 1. First transfer -> created
    res1 = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1"],
        "prevent_duplicates": True,
    })
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["created_count"] == 1
    assert data1["skipped_count"] == 0

    # 2. Second transfer of same lead -> skipped duplicate
    res2 = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1"],
        "prevent_duplicates": True,
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["created_count"] == 0
    assert data2["skipped_count"] == 1
    assert "Skipped Acme Health Platforms: draft already exists" in data2["messages"][0]

    # Verify no second draft was added to database
    list_res = client.get("/api/outreach/drafts")
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1


def test_lead_transfer_missing_lead_handling(client):
    """Tests transfer error handling when an invalid/missing lead ID is passed."""
    _seed_discovered_leads()

    res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1", "nonexistent-lead-999"],
        "prevent_duplicates": True,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["created_count"] == 1
    assert data["failed_count"] == 1
    assert any("not found" in msg for msg in data["messages"])


# ==============================================================================
# 2. Personalized Generation & Insufficient Evidence Grounding Tests
# ==============================================================================

def test_flagged_for_manual_research_when_insufficient_evidence(client):
    """Tests that leads lacking public description/industry are flagged for manual research."""
    _seed_discovered_leads()

    res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-sparse-2"],
    })
    assert res.status_code == 200
    data = res.json()
    draft = data["drafts"][0]

    assert draft["flagged_for_manual_review"] is True
    assert draft["manual_review_reason"] is not None
    assert "Insufficient" in draft["manual_review_reason"]
    # Check that contact name was not fabricated
    assert draft["recipient_name"] == "Quantum Holdings Team"


def test_never_invents_contact_name_or_unverified_email(client):
    """Ensures that missing contact names default safely to company team and never fabricate names."""
    _seed_discovered_leads()

    res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-unverified-3"],
    })
    assert res.status_code == 200
    draft = res.json()["drafts"][0]

    assert draft["recipient_name"] == "LogiRoute Logistics Team"
    assert "Hi LogiRoute Logistics Team," in draft["body"]
    assert draft["has_verified_email"] is False
    assert draft["recipient_email"] == "(No public email listed)"


def test_missing_ai_provider_configuration_error(client):
    """Tests that configuring an invalid AI provider or missing cloud API key returns HTTP 400."""
    _seed_discovered_leads()

    res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1"],
        "ai_config": {
            "provider_type": "openai",
            "model_name": "gpt-4o-mini",
            "api_key": "",  # Missing key
        }
    })
    assert res.status_code == 400
    assert "AI Provider configuration error" in res.json()["detail"]


# ==============================================================================
# 3. Human Approval & Sending Safety Gates
# ==============================================================================

def test_draft_creation_never_sends_email(client):
    """Strictly validates that creating/transferring a draft never dispatches an email."""
    _seed_discovered_leads()

    res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1"],
    })
    assert res.status_code == 200
    draft_id = res.json()["drafts"][0]["id"]

    # 1. Draft status must be 'drafted', never 'sent'
    draft_res = client.get(f"/api/outreach/drafts/{draft_id}")
    assert draft_res.status_code == 200
    assert draft_res.json()["status"] == "drafted"

    # 2. Idempotency tracker must not mark it as dispatched
    assert not global_dispatch_tracker.is_dispatched(draft_id)

    # 3. Outreach history should record 'drafted', not 'sent' or 'simulated'
    hist_res = client.get("/api/outreach/history")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["total"] == 1
    assert hist_data["items"][0]["status"] == "drafted"


def test_sending_blocked_without_explicit_approval(client):
    """Validates that outreach transmission is blocked unless approved is explicitly True."""
    _seed_discovered_leads()

    t_res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1"],
    })
    draft = t_res.json()["drafts"][0]

    # Attempt send with approved: False
    send_res = client.post("/api/outreach/send", json={
        "draft_id": draft["id"],
        "approved": False,
        "recipient_email": draft["recipient_email"],
        "subject": draft["subject"],
        "body": draft["body"],
    })
    assert send_res.status_code == 400
    assert "explicit operator approval" in send_res.json()["detail"].lower()


def test_approval_endpoint_and_safety_checks(client):
    """Tests the explicit draft approval endpoint, and verifies unverified emails cannot be approved."""
    _seed_discovered_leads()

    t_res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1", "lead-unverified-3"],
    })
    drafts = {d["lead_id"]: d for d in t_res.json()["drafts"]}
    verified_draft = drafts["disc-lead-rich-1"]
    unverified_draft = drafts["disc-lead-unverified-3"]

    # 1. Unverified draft approval must be rejected with 422
    unverified_appr = client.post(f"/api/outreach/drafts/{unverified_draft['id']}/approve")
    assert unverified_appr.status_code == 422
    assert "verified public" in unverified_appr.json()["detail"].lower()

    # 2. Verified draft approval succeeds
    verified_appr = client.post(f"/api/outreach/drafts/{verified_draft['id']}/approve")
    assert verified_appr.status_code == 200
    assert verified_appr.json()["status"] == "approved"

    # 3. Verified draft can be unapproved
    unappr_res = client.post(f"/api/outreach/drafts/{verified_draft['id']}/unapprove")
    assert unappr_res.status_code == 200
    assert unappr_res.json()["status"] == "drafted"


def test_edit_save_draft_persistence(client):
    """Tests editing a draft's subject and body, and verifies persistent storage in SQLite."""
    _seed_discovered_leads()

    t_res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1"],
    })
    draft_id = t_res.json()["drafts"][0]["id"]

    new_subject = "Custom Software Architecture for Acme Health Platforms"
    new_body = "Hi Acme Team,\n\nWe would love to discuss custom API development for your clinical platform.\n\nBest,\nAgentDesk Team"

    # Edit and save draft via PUT
    edit_res = client.put(f"/api/outreach/drafts/{draft_id}", json={
        "subject": new_subject,
        "body": new_body,
        "recipient_name": "Acme Clinical Leadership",
    })
    assert edit_res.status_code == 200
    updated = edit_res.json()
    assert updated["subject"] == new_subject
    assert updated["body"] == new_body
    assert updated["recipient_name"] == "Acme Clinical Leadership"

    # Verify persistence via GET
    get_res = client.get(f"/api/outreach/drafts/{draft_id}")
    assert get_res.status_code == 200
    assert get_res.json()["subject"] == new_subject
    assert get_res.json()["body"] == new_body


def test_discard_draft_action(client):
    """Tests discarding a draft and verifying its rejected status in history."""
    _seed_discovered_leads()

    t_res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1"],
    })
    draft_id = t_res.json()["drafts"][0]["id"]

    discard_res = client.post(f"/api/outreach/drafts/{draft_id}/discard", json={
        "reason": "Not a current fit for our Q4 engineering roadmap"
    })
    assert discard_res.status_code == 200
    assert discard_res.json()["status"] == "rejected"

    # Verify history reflects rejected status
    hist_res = client.get("/api/outreach/history?status=rejected")
    assert hist_res.status_code == 200
    assert hist_res.json()["total"] >= 1


def test_successful_send_flow_marks_sent_only_on_provider_success(client):
    """Tests that sending an approved draft with verified email succeeds in simulation and marks sent."""
    _seed_discovered_leads()

    t_res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-test-workflow",
        "lead_ids": ["lead-rich-1"],
    })
    draft = t_res.json()["drafts"][0]

    # Explicit approval
    appr_res = client.post(f"/api/outreach/drafts/{draft['id']}/approve")
    assert appr_res.status_code == 200

    # Dispatch in simulation mode
    send_res = client.post("/api/outreach/send", json={
        "draft_id": draft["id"],
        "approved": True,
        "recipient_email": draft["recipient_email"],
        "subject": draft["subject"],
        "body": draft["body"],
    })
    assert send_res.status_code == 200
    send_data = send_res.json()
    assert send_data["status"] in ("sent", "simulated")
    assert send_data["recipient_email"] == "contact@acmehealth.example.com"

    # Verify draft status is now 'sent'
    d_res = client.get(f"/api/outreach/drafts/{draft['id']}")
    assert d_res.json()["status"] == "sent"

    # Verify accidental duplicate send is blocked
    dup_res = client.post("/api/outreach/send", json={
        "draft_id": draft["id"],
        "approved": True,
        "recipient_email": draft["recipient_email"],
        "subject": draft["subject"],
        "body": draft["body"],
    })
    assert dup_res.status_code == 409
    assert "duplicate" in dup_res.json()["detail"].lower()
