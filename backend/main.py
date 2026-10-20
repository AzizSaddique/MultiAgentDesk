import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List

try:
    from .models import ResearchRequest, ResearchResponse, CSVExportRequest
    from .providers.mock import MockResearchProvider
    from .exporter import generate_leads_csv
except (ImportError, ValueError):
    from models import ResearchRequest, ResearchResponse, CSVExportRequest
    from providers.mock import MockResearchProvider
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

# Active research provider (currently Mock/Demo provider)
research_provider = MockResearchProvider()

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "AgentDesk API",
        "version": "0.1.0",
        "provider": research_provider.provider_name,
        "demo_mode": research_provider.is_demo,
    }

@app.post("/api/research/leads", response_model=ResearchResponse)
async def research_leads(request: ResearchRequest):
    """
    Execute lead research for a target topic, industry, and location.
    Currently delegates to the configured modular provider (Mock / Demo provider).
    """
    topic_clean = request.topic.strip()
    industry_clean = request.industry.strip()
    location_clean = request.location.strip()

    if len(topic_clean) < 2 or len(industry_clean) < 2 or len(location_clean) < 2:
        raise HTTPException(
            status_code=422,
            detail="Topic, industry, and location must each contain at least 2 non-whitespace characters."
        )

    leads = await research_provider.search(request)

    return ResearchResponse(
        topic=topic_clean,
        industry=industry_clean,
        location=location_clean,
        provider=research_provider.provider_name,
        is_demo=research_provider.is_demo,
        disclaimer="These records are simulated demo samples for workflow validation and pipeline testing. No live web scraping was performed.",
        total_results=len(leads),
        leads=leads,
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
    uvicorn.run(app, host="127.0.0.1", port=8000)
