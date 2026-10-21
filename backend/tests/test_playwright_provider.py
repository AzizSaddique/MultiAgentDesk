"""
Tests for Playwright Live Web Research Provider and HTML Extraction Engine.
All tests use local HTML fixtures and mocked network/page components;
they do not depend on external live websites or internet access.
"""
import sys
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app, live_provider
from backend.models import ResearchRequest, CrawlDiagnostic
from backend.providers.playwright_scraper import (
    validate_target_url,
    is_allowed_by_robots,
    _clean_extracted_emails,
    extract_lead_from_html,
    _is_selector_loop,
    PlaywrightResearchProvider,
)

client = TestClient(app)

SAMPLE_FIXTURE_RICH_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Apex Energy Labs | Sustainable Storage Solutions</title>
    <meta name="description" content="Pioneering commercial clean energy storage solutions and grid stabilization.">
    <meta property="og:site_name" content="Apex Energy Labs">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Apex Energy Labs Inc.",
        "url": "https://www.apexenergylabs.test",
        "email": "contact@apexenergylabs.test"
    }
    </script>
</head>
<body>
    <header>
        <h1>Apex Energy Labs</h1>
        <nav>
            <a href="/about-us">About Us</a>
            <a href="/contact">Contact</a>
            <a href="https://otherdomain.test/external">External</a>
        </nav>
    </header>
    <main>
        <p>Apex Energy Labs provides next-generation grid battery systems for municipal utilities.</p>
        <p>Inquiries: <a href="mailto:info@apexenergylabs.test">info@apexenergylabs.test</a></p>
    </main>
</body>
</html>
"""

SAMPLE_FIXTURE_MINIMAL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Minimal Software Works - Home</title>
</head>
<body>
    <h1>Minimal Software Works</h1>
    <p>A boutique development firm crafting robust APIs and cloud architectures for early-stage startups.</p>
</body>
</html>
"""

SAMPLE_FIXTURE_BOT_CHALLENGE = """
<!DOCTYPE html>
<html>
<head><title>Access Denied</title></head>
<body>
    <h1>Security Check to Access</h1>
    <p>Please verify you are a human. Cloudflare Ray ID: 87654321</p>
</body>
</html>
"""

def test_url_validation_permitted_and_restricted():
    # Valid HTTP / HTTPS
    valid, url, _ = validate_target_url("https://company.org/contact")
    assert valid is True
    assert url == "https://company.org/contact"

    valid, url, _ = validate_target_url("http://sub.domain.co.uk")
    assert valid is True

    # Prepending https://
    valid, url, _ = validate_target_url("mycompany.io")
    assert valid is True
    assert url == "https://mycompany.io"

    # Restricted protocols
    valid, _, reason = validate_target_url("ftp://files.example.com")
    assert valid is False
    assert "HTTP or HTTPS" in reason

    valid, _, reason = validate_target_url("javascript:alert(1)")
    assert valid is False

    valid, _, reason = validate_target_url("file:///etc/passwd")
    assert valid is False

    # Blocked local/loopback
    valid, _, reason = validate_target_url("http://localhost:8080")
    assert valid is False
    assert "Internal / private" in reason

    valid, _, reason = validate_target_url("https://127.0.0.1/dashboard")
    assert valid is False

    valid, _, reason = validate_target_url("https://192.168.1.1/admin")
    assert valid is False

def test_email_cleaning_and_filtering():
    raw_emails = {
        "hello@company.com",
        "icon@2x.png",
        "bg_image@1x.jpg",
        "test@example.com",
        "support@company.com",
        "bad@sentry.io",
    }
    cleaned = _clean_extracted_emails(raw_emails, "company.com")
    assert "hello@company.com" in cleaned
    assert "support@company.com" in cleaned
    assert not any(e.endswith(".png") for e in cleaned)
    assert not any("example.com" in e for e in cleaned)
    assert not any("sentry.io" in e for e in cleaned)

def test_html_extraction_rich_fixture():
    lead, sublinks = extract_lead_from_html(
        SAMPLE_FIXTURE_RICH_HTML,
        "https://www.apexenergylabs.test",
        industry="CleanTech",
        location="Denver, CO",
        topic="Battery Storage"
    )
    assert lead is not None
    # JSON-LD takes precedence
    assert lead.company_name == "Apex Energy Labs Inc."
    assert "company_name (json-ld)" in lead.verified_fields
    assert "description (meta)" in lead.verified_fields
    assert "clean energy storage" in lead.description.lower()
    assert lead.email == "info@apexenergylabs.test"
    assert "email" in lead.verified_fields
    assert lead.is_live is True
    assert lead.source_url == "https://www.apexenergylabs.test"
    assert lead.website == "https://www.apexenergylabs.test"

    # Verify discovered on-domain subpages (ignoring external)
    assert "https://www.apexenergylabs.test/about-us" in sublinks
    assert "https://www.apexenergylabs.test/contact" in sublinks
    assert not any("otherdomain.test" in link for link in sublinks)

def test_html_extraction_minimal_no_fabricated_data():
    lead, sublinks = extract_lead_from_html(
        SAMPLE_FIXTURE_MINIMAL_HTML,
        "https://minimal.test/home",
        industry="Software",
        location="Remote"
    )
    assert lead is not None
    assert lead.company_name == "Minimal Software Works"
    # Never fabricate missing contact or email!
    assert lead.email == "(No public email listed)"
    assert "email" not in lead.verified_fields
    assert lead.contact_name == "(Not published on page)"
    assert lead.contact_role == "(Not published on page)"
    assert lead.is_live is True
    assert "description (body)" in lead.verified_fields

def test_html_extraction_skips_challenge_screens():
    lead, sublinks = extract_lead_from_html(
        SAMPLE_FIXTURE_BOT_CHALLENGE,
        "https://protected.test/login"
    )
    assert lead is None
    assert sublinks == []

def test_robots_txt_disallowed_fixture():
    # Mock urllib response with restrictive robots.txt
    mock_robots_content = b"User-agent: *\nDisallow: /private/\nDisallow: /admin/\n"
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = mock_robots_content
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        # Allowed path
        allowed, _ = is_allowed_by_robots("https://company.test/public/page")
        assert allowed is True

        # Disallowed path
        allowed_blocked, reason = is_allowed_by_robots("https://company.test/private/data")
        assert allowed_blocked is False
        assert "Disallowed by website robots.txt" in reason

def test_live_research_endpoint_missing_urls_diagnostic():
    payload = {
        "topic": "CleanTech",
        "industry": "Energy",
        "location": "Austin",
        "mode": "live",
        "urls": []
    }
    response = client.post("/api/research/leads", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "playwright-live-provider"
    assert data["is_demo"] is False
    assert data["total_results"] == 0
    assert len(data["diagnostics"]) > 0
    assert data["diagnostics"][0]["status"] == "missing_urls"

def test_live_research_endpoint_invalid_url_diagnostic():
    payload = {
        "topic": "CleanTech",
        "industry": "Energy",
        "location": "Austin",
        "mode": "live",
        "urls": ["ftp://restricted.server.net/pub"]
    }
    response = client.post("/api/research/leads", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "playwright-live-provider"
    assert data["is_demo"] is False
    assert data["total_results"] == 0
    assert any(diag["status"] == "invalid_url" for diag in data["diagnostics"])

def test_is_selector_loop_detection():
    """Verify _is_selector_loop correctly flags Windows SelectorEventLoop and allows ProactorEventLoop."""
    if sys.platform == "win32":
        selector_loop = asyncio.SelectorEventLoop()
        try:
            assert _is_selector_loop(selector_loop) is True
        finally:
            selector_loop.close()

        proactor_loop = asyncio.ProactorEventLoop()
        try:
            assert _is_selector_loop(proactor_loop) is False
        finally:
            proactor_loop.close()

def test_playwright_not_implemented_error_diagnostic():
    """Verify that when browser launch fails with NotImplementedError, clear diagnostic is recorded."""
    provider = PlaywrightResearchProvider()
    req = ResearchRequest(
        topic="CleanTech",
        industry="Energy",
        location="Austin",
        mode="live",
        urls=["https://example.com"]
    )

    with patch("playwright.async_api.async_playwright") as mock_ap:
        mock_p = AsyncMock()
        mock_ap.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.side_effect = NotImplementedError()

        results = asyncio.run(provider._execute_search(req))
        assert results == []
        assert len(provider.last_diagnostics) == 1
        diag = provider.last_diagnostics[0]
        assert diag.status == "browser_init_failed"
        assert diag.url == "playwright_subsystem"
        if sys.platform == "win32":
            assert "ProactorEventLoop" in diag.reason

def test_playwright_provider_closes_browser_and_context_on_exception():
    """Verify browser and context resources are properly closed even after navigation exceptions."""
    provider = PlaywrightResearchProvider()
    req = ResearchRequest(
        topic="CleanTech",
        industry="Energy",
        location="Austin",
        mode="live",
        urls=["https://example.com"]
    )

    with patch("playwright.async_api.async_playwright") as mock_ap:
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_ap.return_value.__aenter__.return_value = mock_p
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.goto.side_effect = RuntimeError("Fatal page crash")

        results = asyncio.run(provider._execute_search(req))
        assert results == []
        # Ensure cleanup occurred
        assert mock_context.close.called
        assert mock_browser.close.called

def test_live_research_endpoint_browser_init_failure_reports_clear_disclaimer():
    """Verify that when browser initialization fails, API reports failure disclaimer rather than success."""
    with patch.object(live_provider, "search") as mock_search:
        async def fake_search(req):
            live_provider._diagnostics = [
                CrawlDiagnostic(
                    url="playwright_subsystem",
                    status="browser_init_failed",
                    reason="Playwright requires a Windows ProactorEventLoop to launch browser subprocesses."
                )
            ]
            live_provider._pages_crawled_count = 0
            return []
        mock_search.side_effect = fake_search

        payload = {
            "topic": "CleanTech",
            "industry": "Energy",
            "location": "Austin",
            "mode": "live",
            "urls": ["https://example.com"]
        }
        response = client.post("/api/research/leads", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "playwright-live-provider"
        assert data["is_demo"] is False
        assert data["total_results"] == 0
        assert data["leads"] == []
        assert "browser subsystem failed to launch" in data["disclaimer"].lower()
        assert any(d["status"] == "browser_init_failed" for d in data["diagnostics"])

