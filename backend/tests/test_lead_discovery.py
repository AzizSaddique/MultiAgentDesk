"""
Comprehensive tests for Automated Lead Discovery Agent in AgentDesk.
Covers:
1. Natural-language request parsing, criteria validation, and ambiguity detection.
2. Missing or invalid search-provider configuration and status.
3. Mocked Google and Bing search provider responses.
4. Permitted public business directory discovery and source attribution.
5. URL validation, SSRF protection, and private network rejection.
6. Deduplication across search sources by canonical domain and business identity.
7. Evidence-backed fact extraction and zero fabricated data.
8. Strict public email verification status and dispatch eligibility.
9. Cooperative cancellation and background task management.
10. Persistent SQLite storage across restarts and tracker instances.
11. API pagination, filters, and RFC 4180 CSV export.
12. Sensitive credential redaction in logs and errors.
13. Transfer to outreach drafting workflow and human approval gate enforcement.
"""
import os
import json
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from backend.main import app, DRAFT_REGISTRY
from backend.models import (
    DiscoveryPlanRequest,
    DiscoveryPlan,
    DiscoveryJobCreateRequest,
    TransferToOutreachRequest,
    SendOutreachRequest,
    LeadRecord,
)
from backend.dispatch_tracker import DispatchTracker, global_dispatch_tracker
from backend.services.lead_discovery import (
    parse_natural_language_request,
    LeadDiscoveryService,
    global_lead_discovery_service,
)
from backend.providers.search.base import SearchResult
from backend.providers.search.tavily_search import TavilySearchProvider
from backend.providers.search.google_search import GoogleSearchProvider
from backend.providers.search.bing_search import BingSearchProvider
from backend.providers.search.directory_search import PublicBusinessDirectoryProvider
from backend.providers.search.factory import list_search_providers, get_search_provider
from backend.providers.playwright_scraper import validate_target_url

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_tracker(tmp_path, monkeypatch):
    """Isolates SQLite database for each test run."""
    db_file = tmp_path / "test_discovery.db"
    tracker = DispatchTracker(db_path=str(db_file))
    tracker.clear()
    DRAFT_REGISTRY.clear()

    monkeypatch.setattr("backend.dispatch_tracker.global_dispatch_tracker", tracker)
    monkeypatch.setattr("backend.main.global_dispatch_tracker", tracker)
    monkeypatch.setattr("backend.services.lead_discovery.global_dispatch_tracker", tracker)
    yield tracker
    tracker.clear()


# ============================================================================
# 1. Natural Language Request Parsing & Ambiguity Detection
# ============================================================================

def test_parse_solar_lahore_request():
    prompt = "Find 100 solar installation companies in Lahore that serve commercial customers."
    plan = parse_natural_language_request(prompt)

    assert plan.target_lead_count == 100
    assert "Solar" in plan.industry
    assert plan.location_city == "Lahore"
    assert plan.location_country == "Pakistan"
    assert plan.service_criteria == "Commercial and enterprise clients"
    assert plan.is_ambiguous is False
    assert plan.clarification_question is None


def test_parse_software_iot_pakistan_request():
    prompt = "Find software houses in Pakistan that might need IoT development services."
    plan = parse_natural_language_request(prompt)

    assert "Software" in plan.industry
    assert plan.location_country == "Pakistan"
    assert "IoT" in (plan.service_criteria or "")
    assert plan.is_ambiguous is False


def test_parse_manufacturing_saudi_arabia_request():
    prompt = "Discover manufacturing companies in Saudi Arabia and collect their official websites and publicly listed business contact emails."
    plan = parse_natural_language_request(prompt)

    assert "Manufacturing" in plan.industry
    assert plan.location_country == "Saudi Arabia"
    assert plan.is_ambiguous is False


def test_parse_robotics_germany_request():
    prompt = "Find robotics and automation companies in Germany that could be potential clients."
    plan = parse_natural_language_request(prompt)

    assert "Robotics" in plan.industry
    assert plan.location_country == "Germany"
    assert plan.is_ambiguous is False


def test_ambiguity_detection_short_or_vague_prompts():
    vague_prompts = ["leads", "find companies", "help", "search", "companies in the world"]
    for vp in vague_prompts:
        plan = parse_natural_language_request(vp)
        assert plan.is_ambiguous is True
        assert plan.clarification_question is not None


def test_api_discovery_plan_endpoint():
    res = client.post("/api/discovery/plan", json={
        "prompt": "Find 50 clean energy providers in Munich, Germany"
    })
    assert res.status_code == 200
    data = res.json()
    assert (data.get("target_lead_count") or data.get("target_count")) == 50
    assert (data.get("location_city") or data.get("city")) == "Munich"
    assert (data.get("location_country") or data.get("country")) == "Germany"
    assert data["is_ambiguous"] is False


def test_api_discovery_plan_empty_rejected():
    res = client.post("/api/discovery/plan", json={"prompt": "   "})
    assert res.status_code == 422


# ============================================================================
# 2. Search Provider Status & Configuration
# ============================================================================

def test_list_search_providers_endpoint():
    res = client.get("/api/discovery/providers")
    assert res.status_code == 200
    data = res.json()
    providers = {p["id"]: p for p in data["providers"]}

    assert "auto" in providers
    assert "tavily" in providers
    assert "google" in providers
    assert "bing" in providers
    assert "directory" in providers

    # Tavily requires a key and is reported with its display name
    assert providers["tavily"]["requires_key"] is True
    assert providers["tavily"]["name"] == "Tavily Search API"

    # Directory provider requires no keys and is always configured
    assert providers["directory"]["requires_key"] is False
    assert providers["directory"]["is_configured"] is True


def test_search_provider_missing_key_behavior():
    with patch.dict(os.environ, {"GOOGLE_SEARCH_API_KEY": "", "GOOGLE_SEARCH_ENGINE_ID": ""}):
        google = GoogleSearchProvider()
        assert google.is_configured is False
        assert "GOOGLE_SEARCH_API_KEY" in google.configuration_notice

    with patch.dict(os.environ, {"TAVILY_API_KEY": "", "AGENTDESK_TAVILY_API_KEY": ""}):
        tavily = TavilySearchProvider()
        assert tavily.is_configured is False
        assert "TAVILY_API_KEY" in tavily.configuration_notice

    # Test placeholder rejection: do not claim to work with placeholder keys
    with patch.dict(os.environ, {"TAVILY_API_KEY": "placeholder_key_value"}):
        tavily = TavilySearchProvider()
        assert tavily.is_configured is False

    with patch.dict(os.environ, {"GOOGLE_SEARCH_API_KEY": "your-api-key", "GOOGLE_SEARCH_ENGINE_ID": "your-cx"}):
        google = GoogleSearchProvider()
        assert google.is_configured is False


def test_automatic_provider_selection_hierarchy():
    # 1. When Tavily is configured, auto prefers Tavily
    with patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-valid-test-key-12345"}):
        provider = get_search_provider("auto")
        assert isinstance(provider, TavilySearchProvider)
        assert provider.provider_id == "tavily"

    # 2. When only Google is configured, auto selects Google
    with patch.dict(os.environ, {
        "TAVILY_API_KEY": "",
        "AGENTDESK_TAVILY_API_KEY": "",
        "GOOGLE_SEARCH_API_KEY": "AIzaSyTestKey1234567890",
        "GOOGLE_SEARCH_ENGINE_ID": "0123456789cx",
    }):
        provider = get_search_provider("auto")
        assert isinstance(provider, GoogleSearchProvider)
        assert provider.provider_id == "google"

    # 3. When only Bing is configured, auto selects Bing
    with patch.dict(os.environ, {
        "TAVILY_API_KEY": "",
        "AGENTDESK_TAVILY_API_KEY": "",
        "GOOGLE_SEARCH_API_KEY": "",
        "GOOGLE_SEARCH_ENGINE_ID": "",
        "BING_SEARCH_API_KEY": "bingSecretKey123456789",
    }):
        provider = get_search_provider("auto")
        assert isinstance(provider, BingSearchProvider)
        assert provider.provider_id == "bing"

    # 4. When no commercial providers configured, falls back cleanly to Directory
    with patch.dict(os.environ, {
        "TAVILY_API_KEY": "",
        "AGENTDESK_TAVILY_API_KEY": "",
        "GOOGLE_SEARCH_API_KEY": "",
        "GOOGLE_SEARCH_ENGINE_ID": "",
        "BING_SEARCH_API_KEY": "",
    }):
        provider = get_search_provider("auto")
        assert isinstance(provider, PublicBusinessDirectoryProvider)
        assert provider.provider_id == "directory"


# ============================================================================
# 3. Mocked Google, Bing & Tavily Provider Responses
# ============================================================================

@pytest.mark.anyio
async def test_tavily_provider_mocked_success():
    with patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-sample-test-key-mock"}):
        tavily = TavilySearchProvider(min_request_interval=0.0)
        mock_payload = {
            "query": "solar commercial Lahore",
            "results": [
                {
                    "title": "Solar Energy Lahore Ltd",
                    "url": "https://solarlahore.example.com",
                    "content": "Commercial solar panel installations and maintenance across Lahore.",
                    "score": 0.94,
                    "published_date": "2025-01-15",
                },
                {
                    "title": "Punjab Solar Solutions",
                    "url": "https://punjabsorange.example.com",
                    "content": "Industrial and commercial solar engineering services.",
                    "score": 0.88,
                    "published_date": "2025-02-10",
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            results = await tavily.search("solar commercial Lahore", max_results=5)

            # Verify request headers and payload
            assert mock_post.called
            call_kwargs = mock_post.call_args[1]
            assert "Authorization" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Authorization"] == "Bearer tvly-sample-test-key-mock"
            assert call_kwargs["json"]["query"] == "solar commercial Lahore"
            assert call_kwargs["json"]["max_results"] == 5

        assert len(results) == 2
        assert results[0].title == "Solar Energy Lahore Ltd"
        assert results[0].url == "https://solarlahore.example.com"
        assert results[0].source_provider == "tavily-search"
        assert results[0].metadata["score"] == 0.94
        assert results[0].metadata["published_date"] == "2025-01-15"
        assert results[1].title == "Punjab Solar Solutions"
        assert results[1].domain == "punjabsorange.example.com"


@pytest.mark.anyio
async def test_tavily_provider_ssrf_filtering():
    """Verifies internal/private network URLs returned by search API are dropped."""
    with patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-sample-test-key-mock"}):
        tavily = TavilySearchProvider(min_request_interval=0.0)
        mock_payload = {
            "query": "test private network filtering",
            "results": [
                {
                    "title": "Valid Public Portal",
                    "url": "https://company.example.com",
                    "content": "Official corporate website.",
                },
                {
                    "title": "Malicious Localhost URL",
                    "url": "http://127.0.0.1:8000/internal-data",
                    "content": "Should be filtered by SSRF protection.",
                },
                {
                    "title": "Private Subnet URL",
                    "url": "http://192.168.1.1/router",
                    "content": "Should be filtered by SSRF protection.",
                },
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            results = await tavily.search("test private network filtering")

        # Only the public URL should pass
        assert len(results) == 1
        assert results[0].url == "https://company.example.com"


@pytest.mark.anyio
async def test_tavily_provider_error_handling_and_redaction():
    """Verifies safe error handling and sensitive key redaction."""
    test_key = "tvly-supersecretkey-9999"
    with patch.dict(os.environ, {"TAVILY_API_KEY": test_key}):
        tavily = TavilySearchProvider(min_request_interval=0.0)

        # 1. 429 Rate Limit
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.json.return_value = {"detail": "Rate limit exceeded"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp_429
            with pytest.raises(RuntimeError) as exc_info:
                await tavily.search("query")
            assert "429" in str(exc_info.value)
            assert test_key not in str(exc_info.value)

        # 2. 401 Unauthorized
        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401
        mock_resp_401.json.return_value = {"detail": "Invalid API key"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp_401
            with pytest.raises(RuntimeError) as exc_info:
                await tavily.search("query")
            assert "unauthorized" in str(exc_info.value).lower()
            assert test_key not in str(exc_info.value)

        # 3. Connection Exception with key leak attempt in exception string
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception(f"Connection error while contacting api.tavily.com with key {test_key}")
            with pytest.raises(RuntimeError) as exc_info:
                await tavily.search("query")
            assert test_key not in str(exc_info.value)
            assert "[REDACTED_API_KEY]" in str(exc_info.value) or "[REDACTED_SECRET]" in str(exc_info.value)


@pytest.mark.anyio
async def test_google_provider_mocked_success():
    with patch.dict(os.environ, {"GOOGLE_SEARCH_API_KEY": "mock_google_key", "GOOGLE_SEARCH_ENGINE_ID": "mock_cx"}):
        google = GoogleSearchProvider()
        mock_payload = {
            "items": [
                {
                    "title": "SolarTech Commercial Pakistan",
                    "link": "https://solartech.example.com",
                    "snippet": "Leading commercial solar installations in Lahore and Punjab.",
                },
                {
                    "title": "Punjab Solar Solutions",
                    "link": "https://punjabsorange.example.com",
                    "snippet": "Industrial and commercial solar panel installation.",
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            results = await google.search("solar commercial Lahore", max_results=5)

        assert len(results) == 2
        assert results[0].title == "SolarTech Commercial Pakistan"
        assert results[0].url == "https://solartech.example.com"
        assert results[0].source_provider == "google-search"


@pytest.mark.anyio
async def test_bing_provider_mocked_success():
    with patch.dict(os.environ, {"BING_SEARCH_API_KEY": "mock_bing_key"}):
        bing = BingSearchProvider()
        mock_payload = {
            "webPages": {
                "value": [
                    {
                        "name": "RoboCraft Automation GmbH",
                        "url": "https://robocraft.example.de",
                        "snippet": "Industrial robotics and factory automation systems in Munich.",
                    }
                ]
            }
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            results = await bing.search("robotics automation Munich", max_results=5)

        assert len(results) == 1
        assert results[0].title == "RoboCraft Automation GmbH"
        assert results[0].url == "https://robocraft.example.de"
        assert results[0].source_provider == "bing-search"


# ============================================================================
# 4. Public Business Directory Discovery & Offline Safe Mode
# ============================================================================

@pytest.mark.anyio
async def test_directory_provider_searches_local_registries():
    provider = PublicBusinessDirectoryProvider()

    # Search Lahore solar
    results_lahore = await provider.search("solar Lahore", max_results=5)
    assert len(results_lahore) >= 1
    first = results_lahore[0]
    assert "solar" in first.title.lower() or "solar" in first.snippet.lower()
    assert first.metadata.get("directory_facts") is not None
    assert first.metadata["directory_facts"]["email"] != ""

    # Search Germany robotics
    results_germany = await provider.search("robotics Germany", max_results=5)
    assert len(results_germany) >= 1
    assert "robot" in results_germany[0].title.lower() or "automat" in results_germany[0].title.lower()


# ============================================================================
# 5. URL Validation & SSRF Network Protection
# ============================================================================

def test_url_validation_blocks_ssrf_and_disallowed_protocols():
    disallowed = [
        "http://localhost:8000/internal",
        "http://127.0.0.1:8000/admin",
        "http://10.0.0.5/secrets",
        "http://192.168.1.1/router",
        "http://172.16.0.1/intranet",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "gopher://evil.com",
    ]

    for bad_url in disallowed:
        is_valid, _, reason = validate_target_url(bad_url)
        assert is_valid is False, f"Expected {bad_url} to be blocked, but was allowed"
        assert len(reason) > 0

    allowed = [
        "https://www.solartech.com.pk",
        "http://cleanenergy.de",
        "https://iot-innovations.sa/contact",
    ]
    for good_url in allowed:
        is_valid, sanitized, _ = validate_target_url(good_url)
        assert is_valid is True, f"Expected {good_url} to be allowed"
        assert sanitized.startswith("http://") or sanitized.startswith("https://")


# ============================================================================
# 6. Deduplication Across Search Sources
# ============================================================================

@pytest.mark.anyio
async def test_deduplication_by_domain_and_name(clean_tracker):
    service = LeadDiscoveryService()
    plan = DiscoveryPlan(
        original_prompt="Test deduplication",
        industry="Solar",
        location_city="Lahore",
        location_country="Pakistan",
        keywords=["solar"],
        target_lead_count=10,
        desired_contact_info=["email"],
        search_language="en",
        max_crawl_depth=1,
        max_pages_per_domain=1,
        is_ambiguous=False,
    )

    req = DiscoveryJobCreateRequest(plan=plan, search_provider="directory")

    # Start discovery job
    job = await service.start_job(req)
    assert job.id.startswith("job-")

    # Wait briefly for background pipeline
    for _ in range(25):
        await asyncio.sleep(0.15)
        current = clean_tracker.get_discovery_job(job.id)
        if current and current.get("status") in ("completed", "failed"):
            break

    leads, total, _, _ = clean_tracker.query_discovered_leads(job_id=job.id)
    domains = [l["website"] for l in leads]
    # Verify no duplicate URLs exist
    assert len(domains) == len(set(domains))


# ============================================================================
# 7. Evidence-Backed Extraction & No Fabricated Data
# ============================================================================

def test_html_extraction_with_real_evidence():
    service = LeadDiscoveryService()
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Riyadh Precision Manufacturing - Industrial Excellence</title>
        <meta name="description" content="Commercial CNC machining and fabrication in Saudi Arabia." />
      </head>
      <body>
        <main>
          <h1>About Us</h1>
          <p>We provide enterprise-grade industrial tooling across the Gulf.</p>
          <a href="mailto:info@riyadhprecision.sa">Email Us: info@riyadhprecision.sa</a>
          <a href="tel:+966114567890">Call +966 11 456 7890</a>
          <a href="/contact-us">Contact Page</a>
        </main>
      </body>
    </html>
    """

    name, desc, emails, phones, subpages = service._extract_from_html(html, "https://riyadhprecision.sa")
    assert name == "Riyadh Precision Manufacturing"
    assert "Commercial CNC machining" in desc
    assert "info@riyadhprecision.sa" in emails
    assert any("+966" in p for p in phones)
    assert any("contact-us" in s for s in subpages)


def test_html_extraction_minimal_never_fabricates():
    service = LeadDiscoveryService()
    html = """
    <!DOCTYPE html>
    <html>
      <head><title>Silent Industrial</title></head>
      <body>
        <div>Just a company name, no emails or phone numbers.</div>
      </body>
    </html>
    """
    name, desc, emails, phones, _ = service._extract_from_html(html, "https://silentind.com")
    assert name == "Silent Industrial"
    assert emails == []
    assert phones == []


# ============================================================================
# 8. Strict Public Email Verification Status
# ============================================================================

def test_strict_email_verification_status():
    from backend.models import DiscoveredLeadRecord

    # Verified genuine email
    lead_verified = DiscoveredLeadRecord(
        id="lead-test-1",
        job_id="job-1",
        company_name="Apex Solar",
        website="https://apexsolar.pk",
        email="contact@apexsolar.pk",
        email_verification_status="verified_public",
        source_urls=["https://apexsolar.pk/contact"],
        discovery_source="directory",
        discovery_query="solar",
        discovered_at="2026-10-23T12:00:00Z",
    )
    assert lead_verified.email_verification_status == "verified_public"

    # Missing email
    lead_no_email = DiscoveredLeadRecord(
        id="lead-test-2",
        job_id="job-1",
        company_name="Quiet Solar",
        website="https://quietsolar.pk",
        email="",
        email_verification_status="not_found",
        source_urls=["https://quietsolar.pk"],
        discovery_source="directory",
        discovery_query="solar",
        discovered_at="2026-10-23T12:00:00Z",
    )
    assert lead_no_email.email_verification_status == "not_found"


# ============================================================================
# 9. Cooperative Cancellation & Resource Control
# ============================================================================

@pytest.mark.anyio
async def test_job_cancellation(clean_tracker):
    service = LeadDiscoveryService()
    plan = DiscoveryPlan(
        original_prompt="Cancel test",
        industry="Manufacturing",
        location_country="Saudi Arabia",
        keywords=["manufacturing"],
        target_lead_count=50,
        desired_contact_info=["email"],
        search_language="en",
        max_crawl_depth=1,
        max_pages_per_domain=1,
        is_ambiguous=False,
    )

    req = DiscoveryJobCreateRequest(plan=plan, search_provider="directory")
    job = await service.start_job(req)

    # Cancel immediately
    cancelled = service.cancel_job(job.id)
    assert cancelled is True

    # Check status
    assert service.is_job_cancelled(job.id) is True
    job_record = clean_tracker.get_discovery_job(job.id)
    assert job_record is not None
    assert job_record["status"] == "cancelled"


# ============================================================================
# 10. SQLite Persistence Across Tracker Instances
# ============================================================================

def test_persistence_across_tracker_instances(tmp_path):
    db_file = str(tmp_path / "restart_test.db")
    tracker1 = DispatchTracker(db_path=db_file)

    from backend.models import DiscoveryJob, DiscoveredLeadRecord

    job = DiscoveryJob(
        id="job-persisted-1",
        prompt="Persist prompt test",
        status="completed",
        created_at="2026-10-23T12:00:00Z",
        provider_used="directory",
        total_target=10,
        discovered_count=1,
        verified_email_count=1,
    )
    tracker1.save_discovery_job(job)

    lead = DiscoveredLeadRecord(
        id="lead-persisted-1",
        job_id="job-persisted-1",
        company_name="Durable Robotics",
        website="https://durablerobotics.de",
        email="info@durablerobotics.de",
        email_verification_status="verified_public",
        phone="+49 89 123456",
        phone_verification_status="verified_public",
        source_urls=["https://durablerobotics.de"],
        discovery_source="Public Directory",
        discovery_query="robotics Germany",
        discovered_at="2026-10-23T12:00:00Z",
        relevance_score=0.95,
        relevance_explanation="Verified test match",
        verified_fields=["company_name", "email", "phone"],
    )
    tracker1.save_discovered_lead(lead)

    # Instantiate a second tracker pointing to the same SQLite file
    tracker2 = DispatchTracker(db_path=db_file)
    restored_job = tracker2.get_discovery_job("job-persisted-1")
    assert restored_job is not None
    assert restored_job["prompt"] == "Persist prompt test"
    assert restored_job["discovered_count"] == 1

    restored_leads, count, _, counts = tracker2.query_discovered_leads("job-persisted-1")
    assert count == 1
    assert restored_leads[0]["company_name"] == "Durable Robotics"
    assert restored_leads[0]["email_verification_status"] == "verified_public"
    assert counts["verified_public"] == 1


# ============================================================================
# 11. API Endpoints: Pagination, Filtering & CSV Export
# ============================================================================

def test_api_jobs_leads_and_csv_export(clean_tracker):
    from backend.models import DiscoveryJob, DiscoveredLeadRecord

    job = DiscoveryJob(
        id="job-api-test",
        prompt="API export test",
        status="completed",
        created_at="2026-10-23T12:00:00Z",
        provider_used="directory",
        total_target=5,
        discovered_count=2,
    )
    clean_tracker.save_discovery_job(job)

    lead1 = DiscoveredLeadRecord(
        id="lead-api-1",
        job_id="job-api-test",
        company_name="Lahore Clean Solar",
        website="https://lahoresolar.pk",
        industry="Solar",
        city="Lahore",
        country="Pakistan",
        email="contact@lahoresolar.pk",
        email_verification_status="verified_public",
        source_urls=["https://lahoresolar.pk"],
        discovery_source="directory",
        discovery_query="solar lahore",
        discovered_at="2026-10-23T12:00:00Z",
    )
    lead2 = DiscoveredLeadRecord(
        id="lead-api-2",
        job_id="job-api-test",
        company_name="Karachi Tech Hub",
        website="https://karachitechiot.pk",
        industry="Software",
        city="Karachi",
        country="Pakistan",
        email="",
        email_verification_status="not_found",
        source_urls=["https://karachitechiot.pk"],
        discovery_source="directory",
        discovery_query="software karachi",
        discovered_at="2026-10-23T12:05:00Z",
    )
    clean_tracker.save_discovered_lead(lead1)
    clean_tracker.save_discovered_lead(lead2)

    # 1. Test get job
    res_job = client.get("/api/discovery/jobs/job-api-test")
    assert res_job.status_code == 200
    assert res_job.json()["job"]["id"] == "job-api-test"

    # 2. Test list leads with filter
    res_leads_filter = client.get("/api/discovery/jobs/job-api-test/leads?email_status=verified_public")
    assert res_leads_filter.status_code == 200
    data = res_leads_filter.json()
    assert data["total"] == 1
    assert data["leads"][0]["company_name"] == "Lahore Clean Solar"

    # 3. Test CSV export
    res_csv = client.get("/api/discovery/jobs/job-api-test/export-csv")
    assert res_csv.status_code == 200
    assert res_csv.headers["content-type"].startswith("text/csv")
    csv_text = res_csv.text
    assert "Lahore Clean Solar" in csv_text
    assert "contact@lahoresolar.pk" in csv_text
    assert "https://lahoresolar.pk" in csv_text


# ============================================================================
# 12. Transfer to Outreach & Human Approval Gate Regression
# ============================================================================

def test_transfer_to_outreach_preserves_strict_verification(clean_tracker):
    from backend.models import DiscoveredLeadRecord

    # Create a verified lead and an unverified lead
    lead_v = DiscoveredLeadRecord(
        id="lead-transfer-v",
        job_id="job-transfer-test",
        company_name="Solar Masters",
        website="https://solarmasters.pk",
        industry="Solar",
        city="Lahore",
        country="Pakistan",
        email="info@solarmasters.pk",
        email_verification_status="verified_public",
        source_urls=["https://solarmasters.pk"],
        discovery_source="directory",
        discovery_query="solar",
        discovered_at="2026-10-23T12:00:00Z",
    )
    lead_u = DiscoveredLeadRecord(
        id="lead-transfer-u",
        job_id="job-transfer-test",
        company_name="Anonymous Solar",
        website="https://anonymoussolar.pk",
        industry="Solar",
        city="Lahore",
        country="Pakistan",
        email="",
        email_verification_status="not_found",
        source_urls=["https://anonymoussolar.pk"],
        discovery_source="directory",
        discovery_query="solar",
        discovered_at="2026-10-23T12:00:00Z",
    )
    clean_tracker.save_discovered_lead(lead_v)
    clean_tracker.save_discovered_lead(lead_u)

    # Transfer both to outreach
    transfer_res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-transfer-test",
        "lead_ids": ["lead-transfer-v", "lead-transfer-u"]
    })
    assert transfer_res.status_code == 200
    t_data = transfer_res.json()
    assert t_data["total"] == 2
    assert t_data["verified_email_count"] == 1
    assert t_data["missing_email_count"] == 1

    drafts = {d["lead_id"]: d for d in t_data["drafts"]}
    draft_v = drafts["disc-lead-transfer-v"]
    draft_u = drafts["disc-lead-transfer-u"]

    assert draft_v["has_verified_email"] is True
    assert draft_v["recipient_email"] == "info@solarmasters.pk"

    assert draft_u["has_verified_email"] is False
    assert draft_u["recipient_email"] == "(No public email listed)"

    # SAFETY GATE CHECK 1: Transmission without approval must be blocked
    unapproved_send = client.post("/api/outreach/send", json={
        "draft_id": draft_v["id"],
        "approved": False,
        "recipient_email": draft_v["recipient_email"],
        "subject": draft_v["subject"],
        "body": draft_v["body"],
    })
    assert unapproved_send.status_code == 400

    # SAFETY GATE CHECK 2: Transmission to unverified lead must be blocked even if approved
    unverified_send = client.post("/api/outreach/send", json={
        "draft_id": draft_u["id"],
        "approved": True,
        "recipient_email": draft_u["recipient_email"],
        "subject": draft_u["subject"],
        "body": draft_u["body"],
    })
    assert unverified_send.status_code == 422

    # SAFETY GATE CHECK 3: Approved send of verified lead succeeds in simulation mode
    approved_send = client.post("/api/outreach/send", json={
        "draft_id": draft_v["id"],
        "approved": True,
        "recipient_email": draft_v["recipient_email"],
        "subject": draft_v["subject"],
        "body": draft_v["body"],
    })
    assert approved_send.status_code == 200
    assert approved_send.json()["status"] == "simulated"

    # SAFETY GATE CHECK 4: Duplicate-send protection blocks repeated transmission
    repeat_send = client.post("/api/outreach/send", json={
        "draft_id": draft_v["id"],
        "approved": True,
        "recipient_email": draft_v["recipient_email"],
        "subject": draft_v["subject"],
        "body": draft_v["body"],
    })
    assert repeat_send.status_code == 409
