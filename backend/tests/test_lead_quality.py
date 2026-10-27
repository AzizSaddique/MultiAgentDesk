"""
Regression and Data-Quality Tests for Lead Discovery Agent in AgentDesk.
Validates:
1. Industry classification: solar/energy companies are never misclassified as 'Logistics';
   logistics is only assigned when genuine freight/warehousing evidence exists;
   insufficient evidence yields 'Unknown' or 'Needs Review'.
2. Truthful verification status: public discovery yields 'publicly_listed' (mailbox unverified),
   only actual verification provider yields 'verified_by_provider'.
3. Phone number preservation: string types, leading zeros ('03111111926'), country codes ('+924235789000'),
   corrupted numbers ('9.23E+11') flagged as 'needs_review' without hallucinated digits.
4. CSV export: formula encapsulation prevents Excel/Sheets scientific notation and zero stripping.
5. Dynamic relevance scoring: dynamic scores (not hardcoded 0.85), transparent reasons, thin description penalties.
6. Source evidence attribution: official websites distinguished from directory registries; unsupported fields marked 'Needs Review'.
"""
import io
import csv
import pytest
from fastapi.testclient import TestClient

from backend.main import app, DRAFT_REGISTRY
from backend.models import (
    DiscoveryPlan,
    DiscoveredLeadRecord,
    DiscoveryJob,
    DiscoveryJobCreateRequest,
)
from backend.dispatch_tracker import DispatchTracker
from backend.services.lead_discovery import (
    LeadDiscoveryService,
    classify_company_industry,
    evaluate_email_verification,
    evaluate_phone_verification,
    is_scientific_notation_corrupted,
    calculate_lead_relevance,
)
from backend.providers.search.base import SearchResult
from backend.providers.search.directory_search import PublicBusinessDirectoryProvider

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_tracker(tmp_path, monkeypatch):
    """Isolates SQLite database for each test run."""
    db_file = tmp_path / "test_quality.db"
    tracker = DispatchTracker(db_path=str(db_file))
    tracker.clear()
    DRAFT_REGISTRY.clear()

    monkeypatch.setattr("backend.dispatch_tracker.global_dispatch_tracker", tracker)
    monkeypatch.setattr("backend.main.global_dispatch_tracker", tracker)
    monkeypatch.setattr("backend.services.lead_discovery.global_dispatch_tracker", tracker)
    yield tracker
    tracker.clear()


# ============================================================================
# 1. Industry Classification Tests
# ============================================================================

def test_solar_companies_never_classified_as_logistics_even_if_search_was_logistics():
    """
    Solar and energy technology companies must be classified under Solar Energy,
    Energy Storage, or Renewable Energy based on evidence, NEVER Logistics.
    """
    solar_candidates = [
        (
            "Reon Energy Limited - Industrial Solar Solutions",
            "Leading industrial and commercial solar solutions provider in Pakistan, serving corporate and industrial clients in Lahore and Karachi with EPC and battery storage.",
            ["solar", "energy", "lahore", "pakistan", "commercial", "renewable", "installation"],
            "https://reonenergy.com",
        ),
        (
            "SkyElectric Pakistan - Smart Solar Systems",
            "AI-powered smart solar and battery energy systems for residential, commercial and industrial consumers across Lahore, Islamabad, and Karachi.",
            ["solar", "smart", "energy", "lahore", "pakistan", "commercial", "installation"],
            "https://www.skyelectric.com",
        ),
        (
            "Premier Energy Pakistan - Solar EPC Contractor",
            "Premier Energy is an authorized solar EPC contractor providing commercial, industrial and agricultural solar power installations based in Lahore, Pakistan.",
            ["solar", "premier", "energy", "lahore", "pakistan", "commercial", "installation"],
            "https://premierenergy.com.pk",
        ),
        (
            "Pantera Energy - Turnkey Solar Solutions",
            "Providing premium commercial and rooftop solar panel installations, net metering, and maintenance across Punjab and Lahore, Pakistan.",
            ["solar", "pantera", "energy", "lahore", "pakistan", "commercial", "installation"],
            "https://panteraenergy.pk",
        ),
        (
            "Zero Carbon Pakistan - Commercial Clean Energy",
            "Accelerating the green transition with high-efficiency commercial and industrial solar power plants in Lahore and Faisalabad.",
            ["solar", "zero carbon", "energy", "lahore", "pakistan", "commercial", "clean energy"],
            "https://zerocarbon.com.pk",
        ),
    ]

    # Even if the user requested "Logistics", the classifier must rely on business evidence
    for name, desc, kws, url in solar_candidates:
        industry, confidence, reason = classify_company_industry(
            company_name=name,
            description=desc,
            keywords=kws,
            source_url=url,
            plan_industry="Logistics",
        )
        assert industry != "Logistics", f"Company '{name}' was erroneously classified as 'Logistics'!"
        assert industry in ("Solar Energy", "Renewable Energy", "Energy Storage"), f"Unexpected industry '{industry}' for solar company '{name}'"
        assert confidence >= 0.70
        assert "evidence keywords" in reason


def test_logistics_only_assigned_with_genuine_freight_evidence():
    """Logistics category must only be assigned when genuine logistics evidence exists."""
    # Legitimate logistics company
    logistics_name = "Agility Logistics Pakistan"
    logistics_desc = "Providing international freight forwarding, customs clearance, bonded warehousing, and third-party logistics (3PL) across Karachi and Lahore."
    ind, conf, reason = classify_company_industry(
        company_name=logistics_name,
        description=logistics_desc,
        keywords=["freight", "logistics", "warehousing", "pakistan"],
        source_url="https://agility.com",
        plan_industry="Commercial Services",
    )
    assert ind == "Logistics"
    assert conf >= 0.85

    # Software company with zero logistics evidence must not be classified as Logistics
    sw_name = "Systems Limited"
    sw_desc = "Global enterprise software development, cloud computing architectures, and digital transformation consulting in Lahore, Pakistan."
    ind_sw, conf_sw, reason_sw = classify_company_industry(
        company_name=sw_name,
        description=sw_desc,
        keywords=["software", "cloud", "pakistan"],
        source_url="https://www.systemsltd.com",
        plan_industry="Logistics",  # User asked for logistics
    )
    assert ind_sw != "Logistics"
    assert ind_sw == "Software & Cloud Services"


def test_insufficient_or_ambiguous_evidence_yields_needs_review_or_unknown():
    """If evidence is empty, stub, or generic, classify as 'Unknown' or 'Needs Review'."""
    # Completely empty description
    ind_empty, conf_empty, _ = classify_company_industry(
        company_name="Anonymous Corp",
        description="",
        plan_industry="General Commercial",
    )
    assert ind_empty == "Unknown"
    assert conf_empty <= 0.30

    # Thin stub description (<35 chars) with no specific industry markers
    ind_stub, conf_stub, _ = classify_company_industry(
        company_name="ABC Enterprises",
        description="Serving Lahore since 2015.",
        plan_industry="Commercial",
    )
    assert ind_stub == "Needs Review"
    assert conf_stub <= 0.40


# ============================================================================
# 2. Truthful Verification Status Tests
# ============================================================================

def test_truthful_email_verification_status():
    """
    Public web discovery yields 'publicly_listed' (mailbox unverified).
    'verified_by_provider' is ONLY returned when provider confirmation is explicit.
    """
    # 1. Public discovery of valid email
    status_pub, reason_pub = evaluate_email_verification("info@reonenergy.com", provider_verified=False)
    assert status_pub == "publicly_listed"
    assert "mailbox unverified" in reason_pub.lower()

    # 2. Provider verified email
    status_prov, reason_prov = evaluate_email_verification("info@reonenergy.com", provider_verified=True)
    assert status_prov == "verified_by_provider"
    assert "provider" in reason_prov.lower()

    # 3. Missing email
    status_none, reason_none = evaluate_email_verification(None)
    assert status_none == "not_found"

    # 4. Invalid email format
    status_inv, reason_inv = evaluate_email_verification("user@not-a-valid-domain")
    assert status_inv == "invalid"


# ============================================================================
# 3. Phone Number Preservation Tests
# ============================================================================

def test_pakistani_phone_numbers_preserved_as_strings(clean_tracker):
    """
    Pakistani numbers like '03111111926' and '+924235789000' must preserve leading zeros,
    country codes, and plus signs across SQLite storage and retrieval.
    """
    # Pakistani mobile: 03111111926 (starts with leading zero)
    status_mob, _ = evaluate_phone_verification("03111111926")
    assert status_mob == "publicly_listed"

    # Pakistani landline: +924235789000 (starts with plus sign and country code)
    status_land, _ = evaluate_phone_verification("+924235789000")
    assert status_land == "publicly_listed"

    # Save to SQLite tracker
    lead = DiscoveredLeadRecord(
        id="lead-pk-phone-test",
        job_id="job-pk-phone",
        company_name="Pantera Energy",
        website="https://panteraenergy.pk",
        industry="Solar Energy",
        city="Lahore",
        country="Pakistan",
        email="info@panteraenergy.pk",
        email_verification_status="publicly_listed",
        phone="03111111926",
        phone_verification_status="publicly_listed",
        source_urls=["https://panteraenergy.pk"],
        discovery_source="directory",
        discovery_query="solar lahore",
        discovered_at="2026-10-27T12:00:00Z",
    )
    clean_tracker.save_discovered_lead(lead)

    # Retrieve from tracker
    restored, count, _, _ = clean_tracker.query_discovered_leads("job-pk-phone")
    assert count == 1
    stored_phone = restored[0]["phone"]
    assert isinstance(stored_phone, str)
    assert stored_phone == "03111111926"
    assert stored_phone.startswith("0311")
    assert len(stored_phone) == 11


def test_corrupted_phone_not_invented_and_flagged_for_review():
    """
    Phone numbers corrupted with scientific notation (e.g. 9.23E+11) must NOT be silently
    corrected or have digits hallucinated; they must be flagged as 'needs_review'.
    """
    corrupted_raw = "9.23E+11"
    assert is_scientific_notation_corrupted(corrupted_raw) is True

    status, reason = evaluate_phone_verification(corrupted_raw)
    assert status == "needs_review"
    assert "scientific notation" in reason.lower()
    # Ensure raw string is not altered
    assert corrupted_raw == "9.23E+11"

    # Test short number (<7 digits)
    status_short, reason_short = evaluate_phone_verification("12345")
    assert status_short == "needs_review"
    assert "fewer than 7 digits" in reason_short.lower()


def test_csv_export_prevents_spreadsheet_scientific_notation(clean_tracker):
    """
    CSV export must wrap phone numbers in spreadsheet text formula syntax (="<phone>")
    to prevent Excel and Google Sheets from converting '+924235789000' to '9.23E+11'
    or stripping the leading zero from '03111111926'.
    """
    job = DiscoveryJob(
        id="job-csv-phone-test",
        prompt="CSV phone test",
        status="completed",
        created_at="2026-10-27T12:00:00Z",
        provider_used="directory",
        total_target=2,
        discovered_count=2,
    )
    clean_tracker.save_discovery_job(job)

    lead1 = DiscoveredLeadRecord(
        id="lead-pk-1",
        job_id="job-csv-phone-test",
        company_name="Alpha Solar",
        website="https://alphasolar.pk",
        industry="Solar Energy",
        city="Lahore",
        country="Pakistan",
        email="contact@alphasolar.pk",
        email_verification_status="publicly_listed",
        phone="03111111926",
        phone_verification_status="publicly_listed",
        source_urls=["https://alphasolar.pk"],
        discovery_source="directory",
        discovery_query="solar lahore",
        discovered_at="2026-10-27T12:00:00Z",
    )
    lead2 = DiscoveredLeadRecord(
        id="lead-pk-2",
        job_id="job-csv-phone-test",
        company_name="Beta Power",
        website="https://betapower.pk",
        industry="Power Systems",
        city="Lahore",
        country="Pakistan",
        email="info@betapower.pk",
        email_verification_status="publicly_listed",
        phone="+924235789000",
        phone_verification_status="publicly_listed",
        source_urls=["https://betapower.pk"],
        discovery_source="directory",
        discovery_query="power lahore",
        discovered_at="2026-10-27T12:05:00Z",
    )
    clean_tracker.save_discovered_lead(lead1)
    clean_tracker.save_discovered_lead(lead2)

    csv_data = clean_tracker.export_discovered_leads_csv("job-csv-phone-test")

    # Parse with standard RFC 4180 CSV reader
    reader = csv.reader(io.StringIO(csv_data))
    rows = list(reader)
    headers = rows[0]
    phone_idx = headers.index("Phone")

    exported_phones = {rows[1][phone_idx], rows[2][phone_idx]}
    assert '="03111111926"' in exported_phones
    assert '="+924235789000"' in exported_phones

    # Verify that raw CSV string contains formula encapsulation
    assert '"=""03111111926"""' in csv_data
    assert '"=""+924235789000"""' in csv_data
    assert "9.23E+11" not in csv_data


# ============================================================================
# 4. Dynamic Relevance Scoring Tests
# ============================================================================

def test_dynamic_relevance_scoring_not_hardcoded():
    """
    Relevance score must NOT be a hardcoded 0.85; it must dynamically reflect
    industry match, geographic fit, description depth, and contact verifiability.
    """
    plan = DiscoveryPlan(
        original_prompt="Find commercial solar installation companies in Lahore.",
        industry="Solar Energy",
        location_city="Lahore",
        location_country="Pakistan",
        keywords=["solar", "commercial", "installation"],
        target_lead_count=10,
        desired_contact_info=["email", "phone"],
        search_language="en",
        max_crawl_depth=1,
        max_pages_per_domain=2,
        is_ambiguous=False,
    )

    # Lead A: High match (Solar in Lahore, email & phone verified, rich description)
    score_a, exp_a = calculate_lead_relevance(
        plan=plan,
        company_name="Reon Energy Limited",
        business_desc="Leading industrial and commercial solar solutions provider in Pakistan, serving corporate clients in Lahore with EPC and battery storage.",
        classified_industry="Solar Energy",
        industry_confidence=0.98,
        city="Lahore",
        country="Pakistan",
        website="https://reonenergy.com",
        email="info@reonenergy.com",
        email_status="publicly_listed",
        phone="+92 42 111 736 637",
        phone_status="publicly_listed",
        source_query="commercial solar installation lahore",
    )

    # Lead B: Thin description (<35 chars), missing email and phone
    score_b, exp_b = calculate_lead_relevance(
        plan=plan,
        company_name="Stub Solar",
        business_desc="Solar panels in Lahore.",
        classified_industry="Solar Energy",
        industry_confidence=0.70,
        city="Lahore",
        country="Pakistan",
        website="https://stubsolar.pk",
        email="",
        email_status="not_found",
        phone="",
        phone_status="not_found",
        source_query="commercial solar installation lahore",
    )

    # Lead C: Mismatched industry (Food & Beverage)
    score_c, exp_c = calculate_lead_relevance(
        plan=plan,
        company_name="Lahore Food Processing Ltd",
        business_desc="Industrial food processing, beverage bottling and agro-packaging operations based in Lahore.",
        classified_industry="Food & Beverage",
        industry_confidence=0.95,
        city="Lahore",
        country="Pakistan",
        website="https://lahorefood.pk",
        email="sales@lahorefood.pk",
        email_status="publicly_listed",
        phone="+92 42 358 123 45",
        phone_status="publicly_listed",
        source_query="commercial solar installation lahore",
    )

    # Assertions
    assert score_a > 0.85, f"Expected high match score > 0.85, got {score_a}"
    assert score_b <= 0.50, f"Expected penalized thin description <= 0.50, got {score_b}"
    assert score_c < score_a, f"Mismatched industry must score lower than matched industry"
    assert score_a != score_b != score_c, "Scores must not be identical hardcoded values!"

    # Explanations must transparently state the reasons
    assert "Solar Energy" in exp_a
    assert "Lahore" in exp_a
    assert "Thin business description (<35 chars); flagged for review" in exp_b
    assert "diverges from target" in exp_c


# ============================================================================
# 5. Source Evidence Attribution Tests
# ============================================================================

def test_source_evidence_distinguishes_website_and_directory(clean_tracker):
    """
    Candidate inspection preserves company website and distinguishes third-party directory source.
    Marks unsupported fields as 'Needs Review'.
    """
    service = LeadDiscoveryService()
    plan = DiscoveryPlan(
        original_prompt="Find solar installation companies in Lahore.",
        industry="Solar Energy",
        location_city="Lahore",
        location_country="Pakistan",
        keywords=["solar", "commercial"],
        target_lead_count=5,
        desired_contact_info=["email", "phone"],
        search_language="en",
        max_crawl_depth=1,
        max_pages_per_domain=1,
        is_ambiguous=False,
    )

    # Candidate from public business directory
    dir_entry = {
        "title": "Pantera Energy - Turnkey Solar Solutions",
        "url": "https://panteraenergy.pk",
        "snippet": "Providing premium commercial and rooftop solar panel installations, net metering, and maintenance across Punjab and Lahore, Pakistan.",
        "keywords": ["solar", "pantera", "energy", "lahore", "pakistan"],
        "country": "PK",
        "city": "Lahore",
        "email": "info@panteraenergy.pk",
        "phone": "+92 42 357 890 00",
    }
    candidate = SearchResult(
        title=dir_entry["title"],
        url=dir_entry["url"],
        snippet=dir_entry["snippet"],
        source="business-directory",
        source_provider="directory",
        query="solar lahore",
        metadata={"directory_facts": dir_entry, "city": "Lahore", "country": "PK", "email": dir_entry["email"], "phone": dir_entry["phone"]},
    )
    provider = PublicBusinessDirectoryProvider()

    import asyncio
    lead_record, outcome = asyncio.run(
        service._inspect_and_verify_candidate(
            candidate=candidate,
            plan=plan,
            job_id="job-evidence-test",
            search_provider=provider,
        )
    )

    assert outcome == "completed"
    assert lead_record is not None
    assert lead_record.company_name == "Pantera Energy"
    assert lead_record.industry == "Solar Energy"
    assert lead_record.discovery_source == "Public Business Directory"
    assert "https://panteraenergy.pk" in lead_record.source_urls
    assert "https://agentdesk.directory/registry" in lead_record.source_urls
    assert "website (official)" in lead_record.verified_fields
    assert "email (website contact)" in lead_record.verified_fields or "email (registry)" in lead_record.verified_fields


# ============================================================================
# 6. End-to-End Outreach Transfer Compatibility
# ============================================================================

def test_transfer_leads_with_truthful_statuses_to_outreach(clean_tracker):
    """
    Leads discovered with 'publicly_listed' status must transfer to outreach drafts
    with has_verified_email == True and recipient_email populated.
    """
    lead = DiscoveredLeadRecord(
        id="lead-truthful-transfer",
        job_id="job-truthful-test",
        company_name="Reon Energy Limited",
        website="https://reonenergy.com",
        industry="Solar Energy",
        city="Lahore",
        country="Pakistan",
        services_description="Industrial solar power and battery storage.",
        email="info@reonenergy.com",
        email_verification_status="publicly_listed",
        phone="+92 42 111 736 637",
        phone_verification_status="publicly_listed",
        source_urls=["https://reonenergy.com"],
        discovery_source="Public Business Directory",
        discovery_query="solar lahore",
        discovered_at="2026-10-27T12:00:00Z",
    )
    clean_tracker.save_discovered_lead(lead)

    res = client.post("/api/discovery/transfer-outreach", json={
        "job_id": "job-truthful-test",
        "lead_ids": ["lead-truthful-transfer"]
    })
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["verified_email_count"] == 1
    draft = data["drafts"][0]
    assert draft["has_verified_email"] is True
    assert draft["recipient_email"] == "info@reonenergy.com"
    assert "Reon Energy" in draft["subject"]
