"""
Tests for Persistent Outreach History, SQLite Audit Trail, Search/Filter, Pagination, and CSV Export.
Verifies all safety, persistence across restarts, and credential redaction requirements.
"""
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import (
    LeadRecord,
    OutreachDraftRequest,
    SendOutreachRequest,
)
from backend.dispatch_tracker import DispatchTracker, global_dispatch_tracker

client = TestClient(app)

SAMPLE_LEAD_1 = LeadRecord(
    id="lead-history-1",
    company_name="Apex Robotics Corp",
    contact_name="Marcus Vance",
    contact_role="CTO",
    email="marcus@apexrobotics.test",
    website="https://apexrobotics.test",
    industry="Automation & Robotics",
    location="Austin, TX",
    source_note="[VERIFIED PUBLIC WEB] Extracted from https://apexrobotics.test/about",
    created_at="2026-10-21T12:00:00Z",
    source_url="https://apexrobotics.test/about",
    description="Building intelligent autonomous warehouse sorting systems.",
    verified_fields=["company_name", "email"],
    is_live=True,
)

SAMPLE_LEAD_2 = LeadRecord(
    id="lead-history-2",
    company_name="Helios Clean Energy",
    contact_name="Sarah Connor",
    contact_role="Director of Operations",
    email="sarah@heliosenergy.test",
    website="https://heliosenergy.test",
    industry="CleanTech",
    location="Denver, CO",
    source_note="[VERIFIED PUBLIC WEB] Extracted from https://heliosenergy.test/contact",
    created_at="2026-10-21T12:00:00Z",
    source_url="https://heliosenergy.test/contact",
    description="Solar micro-grids and battery storage deployments.",
    verified_fields=["company_name", "email"],
    is_live=True,
)


@pytest.fixture(autouse=True)
def clean_tracker(tmp_path, monkeypatch):
    """Use an isolated SQLite test database for each test."""
    db_file = tmp_path / "test_history.db"
    tracker = DispatchTracker(db_path=str(db_file))
    tracker.clear()

    # Monkeypatch the singleton in backend.dispatch_tracker and backend.main
    monkeypatch.setattr("backend.dispatch_tracker.global_dispatch_tracker", tracker)
    monkeypatch.setattr("backend.main.global_dispatch_tracker", tracker)
    yield tracker
    tracker.clear()


# ============================================================================
# 1. History Persistence Across Backend Restarts / Tracker Instances
# ============================================================================

def test_history_persistence_across_tracker_instances(tmp_path):
    """Verify records written by one tracker instance remain accessible to a brand new instance."""
    db_path = str(tmp_path / "persist_test.db")
    tracker1 = DispatchTracker(db_path=db_path)

    # Record entries in tracker1
    tracker1.record_history_entry(
        draft_id="draft-restart-1",
        recipient_email="founder@startup.test",
        subject="Partnership Discussion",
        status="sent",
        provider="smtp",
        is_simulated=False,
        recipient_name="Alex River",
        company_name="Startup Dynamics",
        body_preview="Hello Alex, noticed your company is scaling...",
        source_url="https://startup.test/about",
    )
    tracker1.record_history_entry(
        draft_id="draft-restart-2",
        recipient_email="cto@tech.test",
        subject="AI Architecture",
        status="simulated",
        provider="simulation",
        is_simulated=True,
        recipient_name="Jordan Cole",
        company_name="Tech Lab",
        body_preview="Hello Jordan...",
        source_url="https://tech.test",
    )

    # Simulate backend restart by creating a completely new tracker instance pointing to same DB
    tracker2 = DispatchTracker(db_path=db_path)
    items, total, total_pages, status_counts = tracker2.query_history()

    assert total == 2
    assert len(items) == 2
    assert status_counts.get("sent") == 1
    assert status_counts.get("simulated") == 1

    # Verify field integrity
    items_by_email = {item["recipient_email"]: item for item in items}
    assert "founder@startup.test" in items_by_email
    assert items_by_email["founder@startup.test"]["status"] == "sent"
    assert items_by_email["founder@startup.test"]["is_simulated"] == 0 or items_by_email["founder@startup.test"]["is_simulated"] is False
    assert items_by_email["founder@startup.test"]["provider"] == "smtp"

    assert "cto@tech.test" in items_by_email
    assert items_by_email["cto@tech.test"]["status"] == "simulated"
    assert items_by_email["cto@tech.test"]["is_simulated"] == 1 or items_by_email["cto@tech.test"]["is_simulated"] is True


# ============================================================================
# 2. Correct Simulated, Sent, and Failed Statuses
# ============================================================================

def test_simulated_dispatch_recorded_as_simulated_never_sent(monkeypatch):
    """Ensure simulation dispatches are recorded with status 'simulated' and never 'sent'."""
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "simulation")

    # Draft an outreach
    draft_res = client.post(
        "/api/outreach/draft",
        json={"leads": [SAMPLE_LEAD_1.model_dump()], "service_offering": "Cloud Ops"},
    )
    assert draft_res.status_code == 200
    draft_id = draft_res.json()["drafts"][0]["id"]

    # Send in simulation mode
    send_res = client.post(
        "/api/outreach/send",
        json={
            "draft_id": draft_id,
            "approved": True,
            "recipient_email": SAMPLE_LEAD_1.email,
            "subject": "Proposal for Apex",
            "body": "Body text",
            "has_verified_email": True,
        },
    )
    assert send_res.status_code == 200
    assert send_res.json()["is_simulated"] is True

    # Query history
    history_res = client.get("/api/outreach/history")
    assert history_res.status_code == 200
    data = history_res.json()

    # Must contain drafted and simulated entries
    sim_items = [i for i in data["items"] if i["status"] == "simulated"]
    sent_items = [i for i in data["items"] if i["status"] == "sent"]

    assert len(sim_items) == 1
    assert len(sent_items) == 0
    assert sim_items[0]["is_simulated"] is True
    assert sim_items[0]["provider_mode"] == "simulation" or sim_items[0]["provider"] == "simulation"


def test_failed_dispatch_recorded_as_failed_never_sent(monkeypatch):
    """Ensure failed dispatches are recorded with status 'failed', sanitized error, and never 'sent'."""
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "smtp")
    monkeypatch.setenv("AGENTDESK_SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("AGENTDESK_SMTP_USER", "operator")
    monkeypatch.setenv("AGENTDESK_SMTP_PASSWORD", "SuperSecretP@ssword99!")
    monkeypatch.setenv("AGENTDESK_SMTP_FROM_EMAIL", "sender@test.com")

    # Draft
    draft_res = client.post(
        "/api/outreach/draft",
        json={"leads": [SAMPLE_LEAD_2.model_dump()], "service_offering": "Grid Ops"},
    )
    draft_id = draft_res.json()["drafts"][0]["id"]

    # Mock dispatch_outreach_email to raise a delivery exception
    with patch("backend.main.dispatch_outreach_email") as mock_dispatch:
        from backend.providers.email_dispatcher import DispatchDeliveryError
        mock_dispatch.side_effect = DispatchDeliveryError(
            "SMTP Authentication failed for operator with password=SuperSecretP@ssword99! at smtp.test.com"
        )

        send_res = client.post(
            "/api/outreach/send",
            json={
                "draft_id": draft_id,
                "approved": True,
                "recipient_email": SAMPLE_LEAD_2.email,
                "subject": "Proposal for Helios",
                "body": "Body text",
                "has_verified_email": True,
            },
        )
        assert send_res.status_code == 502

    # Query history
    history_res = client.get("/api/outreach/history")
    data = history_res.json()

    failed_items = [i for i in data["items"] if i["status"] == "failed"]
    sent_items = [i for i in data["items"] if i["status"] == "sent"]

    assert len(failed_items) == 1
    assert len(sent_items) == 0
    assert failed_items[0]["status"] == "failed"
    assert "SuperSecretP@ssword99!" not in (failed_items[0]["error_message"] or "")
    assert "[REDACTED]" in (failed_items[0]["error_message"] or "")


def test_successful_live_dispatch_recorded_as_sent(monkeypatch):
    """Ensure successful live dispatch is recorded as sent with is_simulated=False."""
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "smtp")
    monkeypatch.setenv("AGENTDESK_SMTP_HOST", "smtp.live.test")
    monkeypatch.setenv("AGENTDESK_SMTP_FROM_EMAIL", "agent@live.test")

    draft_res = client.post(
        "/api/outreach/draft",
        json={"leads": [SAMPLE_LEAD_1.model_dump()], "service_offering": "DevOps"},
    )
    draft_id = draft_res.json()["drafts"][0]["id"]

    with patch("backend.main.dispatch_outreach_email") as mock_dispatch:
        from backend.providers.email_dispatcher import DispatchResult
        mock_dispatch.return_value = DispatchResult(
            success=True,
            status="sent",
            is_simulated=False,
            provider="smtp",
            message="Message delivered successfully to apex robotics",
        )

        send_res = client.post(
            "/api/outreach/send",
            json={
                "draft_id": draft_id,
                "approved": True,
                "recipient_email": SAMPLE_LEAD_1.email,
                "subject": "Proposal for Apex",
                "body": "Body text",
                "has_verified_email": True,
            },
        )
        assert send_res.status_code == 200

    history_res = client.get("/api/outreach/history?status=sent")
    data = history_res.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "sent"
    assert data["items"][0]["is_simulated"] is False
    assert data["items"][0]["provider"] == "smtp"


# ============================================================================
# 3. Search, Filter, and Pagination Behavior
# ============================================================================

def test_history_search_and_filter_behavior(clean_tracker):
    """Verify query filtering by status, search term, and date range."""
    clean_tracker.record_history_entry(
        draft_id="d-1",
        recipient_email="alpha@domain1.test",
        subject="Security Architecture",
        status="sent",
        provider="smtp",
        recipient_name="Alice",
        company_name="Acme Alpha",
        body_preview="Snippet 1",
        dispatched_at="2026-10-01T10:00:00Z",
    )
    clean_tracker.record_history_entry(
        draft_id="d-2",
        recipient_email="beta@domain2.test",
        subject="Marketing Cloud Optimization",
        status="simulated",
        provider="simulation",
        is_simulated=True,
        recipient_name="Bob",
        company_name="Beta Corp",
        body_preview="Snippet 2",
        dispatched_at="2026-10-10T12:00:00Z",
    )
    clean_tracker.record_history_entry(
        draft_id="d-3",
        recipient_email="gamma@domain3.test",
        subject="Database Resilience",
        status="failed",
        provider="resend",
        recipient_name="Charlie",
        company_name="Gamma Global",
        body_preview="Snippet 3",
        error_message="Rate limit exceeded",
        dispatched_at="2026-10-20T15:30:00Z",
    )

    # 1. Filter by status: simulated
    res = client.get("/api/outreach/history?status=simulated")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["recipient_email"] == "beta@domain2.test"

    # 2. Filter by search query on company
    res = client.get("/api/outreach/history?query=Gamma")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["company_name"] == "Gamma Global"

    # 3. Filter by search query on subject
    res = client.get("/api/outreach/history?query=Security")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["subject"] == "Security Architecture"

    # 4. Filter by date range (only include Oct 05 to Oct 15)
    res = client.get("/api/outreach/history?start_date=2026-10-05&end_date=2026-10-15")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["recipient_email"] == "beta@domain2.test"


def test_history_pagination(clean_tracker):
    """Verify pagination mechanics: page size, page navigation, total pages calculation."""
    for i in range(12):
        clean_tracker.record_history_entry(
            draft_id=f"page-draft-{i}",
            recipient_email=f"user{i}@test.com",
            subject=f"Subject {i}",
            status="simulated",
            provider="simulation",
            is_simulated=True,
            dispatched_at=f"2026-10-22T10:{i:02d}:00Z",
        )

    # Page 1, page_size 5 -> items 0 to 4
    res = client.get("/api/outreach/history?page=1&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 12
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total_pages"] == 3
    assert len(data["items"]) == 5

    # Page 3, page_size 5 -> remaining 2 items
    res3 = client.get("/api/outreach/history?page=3&page_size=5")
    assert res3.status_code == 200
    data3 = res3.json()
    assert len(data3["items"]) == 2


# ============================================================================
# 4. CSV Export and Secret Redaction
# ============================================================================

def test_csv_export_and_secret_redaction(clean_tracker):
    """Verify that CSV export conforms to RFC 4180 and redacts sensitive credentials."""
    secret_key = "re_live_secret1234567890abcdef"
    secret_pass = "P@ssw0rd987!"

    clean_tracker.record_history_entry(
        draft_id="csv-draft-1",
        recipient_email="export.target@corp.test",
        subject="Important Integration, Proposal",
        status="failed",
        provider="resend",
        recipient_name="Executive Contact",
        company_name="Target Enterprise Inc.",
        body_preview="Hello, we noticed your API...",
        source_url="https://corp.test",
        error_message=f"Resend rejected key: {secret_key} with password={secret_pass}",
    )

    res = client.get("/api/outreach/history/export-csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    csv_text = res.text

    # Verify RFC 4180 headers
    assert "Recipient Email" in csv_text
    assert "Company Name" in csv_text
    assert "Status" in csv_text
    assert "export.target@corp.test" in csv_text
    assert "Target Enterprise Inc." in csv_text

    # Verify secrets are redacted from CSV export
    assert secret_key not in csv_text
    assert secret_pass not in csv_text
    assert "[REDACTED" in csv_text


# ============================================================================
# 5. Empty History and Database Safety
# ============================================================================

def test_empty_history_handling(clean_tracker):
    """Ensure querying and exporting empty history returns clean responses without errors."""
    res = client.get("/api/outreach/history")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_pages"] == 0
    assert data["status_counts"]["sent"] == 0
    assert data["status_counts"]["simulated"] == 0
    assert data["status_counts"]["failed"] == 0

    csv_res = client.get("/api/outreach/history/export-csv")
    assert csv_res.status_code == 200
    lines = csv_res.text.strip().split("\r\n")
    # Only header row present
    assert len(lines) == 1
    assert "Recipient Email" in lines[0]


def test_database_creation_and_migration(tmp_path):
    """Ensure tracker automatically initializes tables on fresh or existing databases safely."""
    new_db = str(tmp_path / "fresh_auto_init.db")
    tracker = DispatchTracker(db_path=new_db)

    # Tables must exist and support operations immediately
    tracker.record_history_entry(
        draft_id="draft-fresh-1",
        recipient_email="fresh@test.com",
        subject="Hello Fresh",
        status="sent",
        provider="smtp",
    )
    items, total, total_pages, status_counts = tracker.query_history()
    assert total == 1
    assert items[0]["recipient_email"] == "fresh@test.com"


# ============================================================================
# 6. Regression: Approval Checks, Verified Emails, Duplicate Protection
# ============================================================================

def test_regression_human_approval_gate_enforced(clean_tracker):
    """Attempting dispatch with approved=False must be rejected and never recorded as sent."""
    res = client.post(
        "/api/outreach/send",
        json={
            "draft_id": "draft-unapproved",
            "approved": False,
            "recipient_email": "test@domain.com",
            "subject": "Subject",
            "body": "Body",
            "has_verified_email": True,
        },
    )
    assert res.status_code == 400
    assert "Safety Gate: Outreach transmission requires explicit operator approval" in res.json()["detail"]

    items, total, _, _ = clean_tracker.query_history()
    assert total == 0


def test_regression_unverified_email_rejected(clean_tracker):
    """Attempting dispatch to unverified email must be rejected and never recorded as sent."""
    res = client.post(
        "/api/outreach/send",
        json={
            "draft_id": "draft-unverified",
            "approved": True,
            "recipient_email": "(No public email listed)",
            "subject": "Subject",
            "body": "Body",
            "has_verified_email": False,
        },
    )
    assert res.status_code == 422
    assert "verified public email" in res.json()["detail"]

    items, total, _, _ = clean_tracker.query_history()
    assert total == 0


def test_regression_duplicate_send_prevention(monkeypatch, clean_tracker):
    """Submitting the same draft_id twice must be blocked by duplicate protection."""
    monkeypatch.setenv("AGENTDESK_OUTREACH_DISPATCH_MODE", "simulation")

    # Initial dispatch
    res1 = client.post(
        "/api/outreach/send",
        json={
            "draft_id": "draft-dup-test",
            "approved": True,
            "recipient_email": SAMPLE_LEAD_1.email,
            "subject": "Subject 1",
            "body": "Body 1",
            "has_verified_email": True,
        },
    )
    assert res1.status_code == 200

    # Repeated dispatch with exact same draft_id
    res2 = client.post(
        "/api/outreach/send",
        json={
            "draft_id": "draft-dup-test",
            "approved": True,
            "recipient_email": SAMPLE_LEAD_1.email,
            "subject": "Subject 2",
            "body": "Body 2",
            "has_verified_email": True,
        },
    )
    assert res2.status_code == 409
    assert "Duplicate Send Blocked" in res2.json()["detail"]
