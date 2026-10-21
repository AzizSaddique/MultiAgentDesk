import sys
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List

# On Windows, configure default policy to ProactorEventLoop before loops are started
if sys.platform == "win32":
    try:
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

try:
    from .models import ResearchRequest, ResearchResponse, CSVExportRequest
    from .providers.mock import MockResearchProvider
    from .providers.playwright_scraper import PlaywrightResearchProvider
    from .exporter import generate_leads_csv
except (ImportError, ValueError):
    from models import ResearchRequest, ResearchResponse, CSVExportRequest
    from providers.mock import MockResearchProvider
    from providers.playwright_scraper import PlaywrightResearchProvider
    from exporter import generate_leads_csv

app = FastAPI(
    title="AgentDesk API",
    description="AgentDesk Desktop AI Agent Management Backend Service",
    version="0.1.0",
)

# Allow requests from Tauri shell and local development frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Providers
mock_provider = MockResearchProvider()
live_provider = PlaywrightResearchProvider()

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "AgentDesk API",
        "version": "0.1.0",
        "provider": mock_provider.provider_name,
        "available_providers": [mock_provider.provider_name, live_provider.provider_name],
        "demo_mode": mock_provider.is_demo,
    }

@app.post("/api/research/leads", response_model=ResearchResponse)
async def research_leads(request: ResearchRequest):
    """
    Execute lead research for a target topic, industry, and location.
    Delegates to either MockResearchProvider (Demo Mode) or PlaywrightResearchProvider (Live Web Mode).
    """
    topic_clean = request.topic.strip()
    industry_clean = request.industry.strip()
    location_clean = request.location.strip()

    if len(topic_clean) < 2 or len(industry_clean) < 2 or len(location_clean) < 2:
        raise HTTPException(
            status_code=422,
            detail="Topic, industry, and location must each contain at least 2 non-whitespace characters."
        )

    is_live = request.mode == "live"
    provider = live_provider if is_live else mock_provider

    try:
        leads = await provider.search(request)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Research provider execution error: {str(e)}"
        )

    if is_live:
        pages_crawled = getattr(provider, "pages_crawled_count", len(leads))
        diagnostics = getattr(provider, "last_diagnostics", [])
        has_init_failure = any(d.status == "browser_init_failed" for d in diagnostics)
        if has_init_failure:
            disclaimer = (
                "Live web research could not be performed: The Playwright browser subsystem failed to launch. "
                "Inspect the crawl diagnostics for specific failure details."
            )
        elif len(leads) == 0 and len(diagnostics) > 0 and all(d.status in ("missing_urls", "invalid_url") for d in diagnostics):
            disclaimer = (
                "Live web research skipped: No valid target website URLs were supplied. "
                "Provide at least one accessible HTTP/HTTPS URL."
            )
        else:
            disclaimer = (
                "Live web research conducted via Playwright. Extracted strictly from publicly accessible pages. "
                "Source URLs and verified fields recorded; missing fields are left blank. No data was fabricated."
            )
    else:
        disclaimer = (
            "These records are simulated demo samples for workflow validation and pipeline testing. "
            "No live web scraping was performed."
        )
        pages_crawled = 0
        diagnostics = []

    return ResearchResponse(
        topic=topic_clean,
        industry=industry_clean,
        location=location_clean,
        provider=provider.provider_name,
        is_demo=provider.is_demo,
        disclaimer=disclaimer,
        total_results=len(leads),
        leads=leads,
        pages_crawled=pages_crawled,
        diagnostics=diagnostics,
    )

@app.post("/api/research/export-csv")
def export_leads_csv(payload: CSVExportRequest):
    """
    Serializes lead records into an RFC 4180 CSV attachment stream.
    """
    csv_content = generate_leads_csv(payload.leads)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=agentdesk_leads.csv"
        }
    )

if __name__ == "__main__":
    uvicorn.run("backend.main:app" if __package__ else "main:app", host="127.0.0.1", port=8000, loop="none")

