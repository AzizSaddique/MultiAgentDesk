"""
Tests for AgentDesk Lead Research API and CSV Exporter.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import LeadRecord, ResearchRequest
from backend.exporter import generate_leads_csv, CSV_HEADERS
from backend.providers.mock import MockResearchProvider

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "AgentDesk API"
    assert data["provider"] == "mock-demo-provider"
    assert data["demo_mode"] is True

def test_research_leads_valid_payload():
    payload = {
        "topic": "AI Automation Agency",
        "industry": "Software & AI",
        "location": "Austin, TX",
        "max_results": 5
    }
    response = client.post("/api/research/leads", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert data["topic"] == "AI Automation Agency"
    assert data["industry"] == "Software & AI"
    assert data["location"] == "Austin, TX"
    assert data["provider"] == "mock-demo-provider"
    assert data["is_demo"] is True
    assert "simulated demo samples" in data["disclaimer"].lower()
    assert data["total_results"] == 5
    assert len(data["leads"]) == 5

    first_lead = data["leads"][0]
    assert first_lead["id"] == "demo-lead-1"
    assert first_lead["company_name"] != ""
    assert first_lead["contact_name"] != ""
    assert first_lead["contact_role"] != ""
    assert "@" in first_lead["email"]
    assert first_lead["website"].startswith("https://")
    assert first_lead["industry"] == "Software & AI"
    assert first_lead["location"] == "Austin, TX"
    assert "[DEMO RECORD]" in first_lead["source_note"]
    assert first_lead["created_at"] != ""

def test_research_leads_respects_max_results():
    payload = {
        "topic": "Renewable Energy",
        "industry": "CleanTech",
        "location": "Denver, CO",
        "max_results": 2
    }
    response = client.post("/api/research/leads", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["leads"]) == 2
    assert data["total_results"] == 2

def test_research_leads_validation_empty_and_whitespace():
    # Blank whitespace fields
    payload = {
        "topic": "   ",
        "industry": "CleanTech",
        "location": "Denver, CO"
    }
    response = client.post("/api/research/leads", json=payload)
    assert response.status_code == 422

    # Too short (< 2 characters)
    payload_short = {
        "topic": "A",
        "industry": "CleanTech",
        "location": "Denver, CO"
    }
    response_short = client.post("/api/research/leads", json=payload_short)
    assert response_short.status_code == 422

def test_research_leads_missing_required_fields():
    response = client.post("/api/research/leads", json={"topic": "B2B SaaS"})
    assert response.status_code == 422

def test_generate_leads_csv_unit():
    sample_leads = [
        LeadRecord(
            id="demo-lead-1",
            company_name="Acme Solutions (Austin)",
            contact_name="Elena Rostova",
            contact_role="Chief Executive Officer",
            email="elena.rostova@demo.example.com",
            website="https://www.demo.example.com",
            industry="Software & IT",
            location="Austin, TX",
            source_note="[DEMO RECORD] Sample note",
            created_at="2026-10-20T12:00:00Z"
        )
    ]
    csv_text = generate_leads_csv(sample_leads)
    lines = csv_text.strip().split("\r\n")
    assert len(lines) == 2
    assert lines[0] == ",".join(CSV_HEADERS)
    assert "demo-lead-1" in lines[1]
    assert "Elena Rostova" in lines[1]
    assert "elena.rostova@demo.example.com" in lines[1]

def test_export_csv_endpoint():
    payload = {
        "leads": [
            {
                "id": "demo-lead-1",
                "company_name=" : "Acme Corp",
                "company_name": "Acme Corp",
                "contact_name": "Jane Doe",
                "contact_role": "CTO",
                "email": "jane@example.com",
                "website": "https://example.com",
                "industry": "Cloud",
                "location": "Seattle, WA",
                "source_note": "[DEMO RECORD] Sample",
                "created_at": "2026-10-20T12:00:00Z"
            }
        ]
    }
    response = client.post("/api/research/export-csv", json=payload)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "agentdesk_leads.csv" in response.headers["content-disposition"]
    assert "Jane Doe" in response.text
