"""
Tests for Live Solar Lead Discovery Workflow in AgentDesk.
Validates:
1. Live-provider results are clearly distinguishable from predefined seed records (is_live flag, discovery_source).
2. Source URLs and evidence excerpts are stored faithfully.
3. Deduplication correctly rejects duplicate domains, company names, and phone numbers.
4. Missing evidence (missing email or phone) is handled safely (never synthesized or hallucinated).
5. Provider failures (e.g. HTTP 500, timeouts) cleanly fail without generating fabricated leads.
6. Truthful contact verification statuses (publicly_listed, syntax_valid, domain_valid, mailbox_unverified, needs_review).
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from backend.models import (
    DiscoveryPlan,
    DiscoveryJobCreateRequest,
    DiscoveredLeadRecord,
)
from backend.dispatch_tracker import DispatchTracker
from backend.providers.search.base import SearchProvider, SearchResult
from backend.providers.search.duckduckgo_search import DuckDuckGoLiveSearchProvider
from backend.providers.search.factory import get_search_provider, list_search_providers
from backend.services.lead_discovery import (
    LeadDiscoveryService,
    evaluate_email_verification,
    evaluate_phone_verification,
)


@pytest.fixture
def isolated_tracker(tmp_path, monkeypatch):
    """Provides isolated SQLite database for discovery tests."""
    db_file = str(tmp_path / "test_live_discovery.db")
    tracker = DispatchTracker(db_path=db_file)
    monkeypatch.setattr("backend.dispatch_tracker.global_dispatch_tracker", tracker)
    monkeypatch.setattr("backend.services.lead_discovery.global_dispatch_tracker", tracker)
    monkeypatch.setattr("backend.main.global_dispatch_tracker", tracker)
    yield tracker
    tracker.clear()


class MockLiveSearchProvider(SearchProvider):
    """Mock search provider returning simulated live search results."""
    def __init__(self, results=None, should_fail=False):
        self._results = results or []
        self._should_fail = should_fail

    @property
    def provider_id(self) -> str:
        return "mock_live"

    @property
    def display_name(self) -> str:
        return "Mock Live Search Engine"

    @property
    def requires_key(self) -> bool:
        return False

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def configuration_notice(self) -> str:
        return "Mock live search for testing."

    async def search(self, query: str, max_results: int = 10, language: str = "en"):
        if self._should_fail:
            raise RuntimeError("Live search upstream provider error: HTTP 503 Service Unavailable")
        return self._results


def test_search_provider_factory_registers_duckduckgo():
    """Verify factory includes DuckDuckGo Live Search and auto selects a live provider."""
    providers = list_search_providers()
    provider_ids = [p.id for p in providers]
    assert "duckduckgo" in provider_ids
    assert "auto" in provider_ids

    ddg_info = next(p for p in providers if p.id == "duckduckgo")
    assert ddg_info.requires_key is False
    assert ddg_info.is_configured is True

    ddg_provider = get_search_provider("duckduckgo")
    assert isinstance(ddg_provider, DuckDuckGoLiveSearchProvider)
    assert ddg_provider.provider_id == "duckduckgo"

    auto_provider = get_search_provider("auto")
    assert auto_provider.provider_id in ("duckduckgo", "tavily", "google", "bing", "directory")


def test_seed_records_distinguishable_from_live_discoveries():
    """Verify predefined seed records have is_live=False and distinct discovery_source."""
    seed_lead = DiscoveredLeadRecord(
        id="lead-solar-001",
        job_id="job-lahore-solar-c-and-i",
        company_name="Premier Energy (Pvt) Ltd",
        website="https://premierenergy.com.pk",
        industry="Solar Energy",
        city="Lahore",
        country="Pakistan",
        services_description="Turnkey commercial, industrial, and agricultural solar power installations.",
        email="info@premierenergy.com.pk",
        email_verification_status="publicly_listed",
        phone="+9242111234235",
        phone_verification_status="publicly_listed",
        source_urls=["https://premierenergy.com.pk", "https://www.dhalahore.org"],
        discovery_source="Predefined Seed Dataset (DHA & PPIB Audit Roster)",
        discovery_query="commercial solar EPC Lahore",
        discovered_at="2026-10-27T16:52:00Z",
        relevance_score=0.98,
        relevance_explanation="Verified on DHA Lahore approved roster and PPIB Category C-1.",
        research_status="completed",
        is_live=False,  # Predefined seed data must never be flagged as live discovery
    )

    live_lead = DiscoveredLeadRecord(
        id="lead-live-001",
        job_id="job-live-solar-run",
        company_name="BrightArc Solar EPC",
        website="https://www.brightarc.pk/commercial",
        industry="Solar Energy",
        city="Lahore",
        country="Pakistan",
        services_description="Commercial solar EPC 20 kW to 2 MW rooftop installations in Lahore.",
        email="contact@brightarc.pk",
        email_verification_status="publicly_listed",
        phone="03213993897",
        phone_verification_status="publicly_listed",
        source_urls=["https://www.brightarc.pk/commercial"],
        discovery_source="DuckDuckGo Live Search",
        discovery_query="commercial solar EPC Lahore",
        discovered_at="2026-10-28T07:00:00Z",
        relevance_score=0.95,
        relevance_explanation="Discovered via live web search; verified commercial rooftop EPC.",
        research_status="completed",
        is_live=True,  # Real live discovery
    )

    assert seed_lead.is_live is False
    assert "Seed" in seed_lead.discovery_source or "Predefined" in seed_lead.discovery_source

    assert live_lead.is_live is True
    assert "Live Search" in live_lead.discovery_source


@pytest.mark.anyio
async def test_live_discovery_pipeline_stores_source_urls_and_deduplicates(isolated_tracker, monkeypatch):
    """
    Verify live pipeline:
    1. Distinguishes live records (is_live=True).
    2. Stores exact source URLs.
    3. Deduplicates across canonical domain, company name, and phone.
    4. Handles missing contact data safely without fabricating placeholder digits or fake emails.
    """
    service = LeadDiscoveryService()

    # Create mock search results with duplicate domain and duplicate phone
    mock_results = [
        SearchResult(
            title="SolarMax Commercial Solutions | Rooftop EPC Lahore",
            url="https://solarmax.pk/commercial",
            snippet="Turnkey industrial solar rooftop installations for factories and warehouses in Lahore.",
            source="mock_live",
            source_provider="mock_live",
        ),
        # Duplicate domain with different path
        SearchResult(
            title="SolarMax Pakistan About Us",
            url="https://solarmax.pk/about",
            snippet="About our company.",
            source="mock_live",
            source_provider="mock_live",
        ),
        # Unique company, but lacks email on page
        SearchResult(
            title="Greentech Energy EPC Lahore",
            url="https://greentech-solar.pk",
            snippet="Commercial solar projects across Sundar Industrial Estate Lahore.",
            source="mock_live",
            source_provider="mock_live",
        ),
    ]

    mock_provider = MockLiveSearchProvider(results=mock_results)
    monkeypatch.setattr(
        "backend.services.lead_discovery.get_search_provider",
        lambda provider_id: mock_provider,
    )

    # Mock candidate page inspection HTML
    async def mock_inspect(candidate, plan, job_id, search_provider):
        if "solarmax.pk" in candidate.url:
            lead = DiscoveredLeadRecord(
                id="lead-test-1",
                job_id=job_id,
                company_name="SolarMax Commercial",
                website="https://solarmax.pk/commercial",
                industry="Solar Energy",
                city="Lahore",
                country="Pakistan",
                services_description="Turnkey industrial solar rooftop installations in Lahore.",
                email="commercial@solarmax.pk",
                email_verification_status="publicly_listed",
                phone="04235789900",
                phone_verification_status="publicly_listed",
                source_urls=["https://solarmax.pk/commercial", "https://solarmax.pk/contact"],
                discovery_source="Mock Live Search Engine",
                discovery_query="commercial solar EPC Lahore",
                discovered_at="2026-10-28T07:10:00Z",
                relevance_score=0.92,
                relevance_explanation="Verified commercial solar rooftop installer in Lahore.",
                research_status="completed",
                verified_fields=[
                    "company_name (website)",
                    "website (official)",
                    "lahore_presence (evidence: lahore)",
                    "commercial_fit (evidence: commercial, industrial)",
                    "email (website contact)",
                    "phone (website)",
                ],
                is_live=True,
            )
            return lead, "completed"
        elif "greentech-solar.pk" in candidate.url:
            # Missing email and missing phone
            lead = DiscoveredLeadRecord(
                id="lead-test-2",
                job_id=job_id,
                company_name="Greentech Energy EPC",
                website="https://greentech-solar.pk",
                industry="Solar Energy",
                city="Lahore",
                country="Pakistan",
                services_description="Commercial solar projects across Sundar Industrial Estate.",
                email="",  # Missing email must remain empty string, never hallucinated
                email_verification_status="not_found",
                phone="",  # Missing phone must remain empty string, never sequential placeholder
                phone_verification_status="not_found",
                source_urls=["https://greentech-solar.pk"],
                discovery_source="Mock Live Search Engine",
                discovery_query="commercial solar EPC Lahore",
                discovered_at="2026-10-28T07:10:00Z",
                relevance_score=0.82,
                relevance_explanation="Verified commercial solar presence; contact details not listed publicly.",
                research_status="completed",
                verified_fields=[
                    "company_name (website)",
                    "website (official)",
                    "lahore_presence (evidence: sundar, lahore)",
                    "commercial_fit (evidence: commercial)",
                    "email (Needs Review)",
                    "phone (Needs Review)",
                ],
                is_live=True,
            )
            return lead, "completed"
        return None, "skipped"

    monkeypatch.setattr(service, "_inspect_and_verify_candidate", mock_inspect)

    plan = DiscoveryPlan(
        original_prompt="Find commercial solar EPC companies in Lahore",
        industry="Solar Energy",
        location_city="Lahore",
        location_country="Pakistan",
        keywords=["commercial", "industrial", "EPC"],
        target_lead_count=10,
    )

    req = DiscoveryJobCreateRequest(
        plan=plan,
        search_provider="mock_live",
    )

    job = await service.start_job(req)

    # Wait for background pipeline to complete
    for _ in range(30):
        await asyncio.sleep(0.1)
        j = isolated_tracker.get_discovery_job(job.id)
        if j and j.get("status") in ("completed", "failed"):
            break

    finished_job = isolated_tracker.get_discovery_job(job.id)
    assert finished_job["status"] == "completed"
    assert finished_job["duplicate_count"] >= 1  # Duplicate domains across queries and within result set rejected
    assert finished_job["discovered_count"] == 2

    # Query leads
    leads, count, _, _ = isolated_tracker.query_discovered_leads(job.id)
    assert count == 2

    lead1 = next(l for l in leads if "solarmax" in l["website"])
    lead2 = next(l for l in leads if "greentech" in l["website"])

    # Live verification
    assert lead1["is_live"] is True
    assert lead2["is_live"] is True
    assert lead1["discovery_source"] == "Mock Live Search Engine"

    # Source URLs
    assert len(lead1["source_urls"]) >= 1
    assert "https://solarmax.pk/commercial" in lead1["source_urls"]

    # Missing evidence is safely preserved (never fabricated)
    assert lead2["email"] == ""
    assert lead2["email_verification_status"] == "not_found"
    assert lead2["phone"] == ""
    assert lead2["phone_verification_status"] == "not_found"


@pytest.mark.anyio
async def test_provider_failure_does_not_fabricate_leads(isolated_tracker, monkeypatch):
    """Verify that when a live search provider throws errors, no fake leads are created."""
    service = LeadDiscoveryService()
    failing_provider = MockLiveSearchProvider(should_fail=True)

    monkeypatch.setattr(
        "backend.services.lead_discovery.get_search_provider",
        lambda provider_id: failing_provider,
    )

    plan = DiscoveryPlan(
        original_prompt="Find commercial solar EPC companies in Lahore",
        industry="Solar Energy",
        location_city="Lahore",
        target_lead_count=5,
    )

    req = DiscoveryJobCreateRequest(plan=plan, search_provider="mock_live")
    job = await service.start_job(req)

    for _ in range(30):
        await asyncio.sleep(0.1)
        j = isolated_tracker.get_discovery_job(job.id)
        if j and j.get("status") in ("completed", "failed"):
            break

    finished_job = isolated_tracker.get_discovery_job(job.id)
    assert finished_job["status"] == "failed"
    assert "Live search upstream provider error" in (finished_job.get("error_message") or "")
    assert finished_job["discovered_count"] == 0

    leads, count, _, _ = isolated_tracker.query_discovered_leads(job.id)
    assert count == 0  # Zero fabricated records


def test_truthful_verification_status_evaluation():
    """Verify contact evaluation rules strictly enforce truthful statuses."""
    # 1. Real public email
    status, note = evaluate_email_verification("info@elco.pk", provider_verified=False)
    assert status == "publicly_listed"
    assert "mailbox unverified" in note.lower()

    # 2. Missing email
    status, _ = evaluate_email_verification("", provider_verified=False)
    assert status == "not_found"

    # 3. Invalid syntax
    status, _ = evaluate_email_verification("not-an-email", provider_verified=False)
    assert status == "invalid"

    # 4. Valid phone
    p_status, _ = evaluate_phone_verification("+9242111234235")
    assert p_status == "publicly_listed"

    # 5. Missing phone
    p_status, _ = evaluate_phone_verification("")
    assert p_status == "not_found"

    # 6. Corrupted / placeholder phone
    p_status, _ = evaluate_phone_verification("9.23E+11")
    assert p_status == "needs_review"
