import sys
import os
import asyncio
from datetime import datetime, timezone
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
    from .models import (
        ResearchRequest, ResearchResponse, CSVExportRequest,
        OutreachDraftRequest, OutreachDraftResponse,
        SendOutreachRequest, SendOutreachResponse, AIProviderConfig,
    )
    from .providers.mock import MockResearchProvider
    from .providers.playwright_scraper import PlaywrightResearchProvider
    from .providers.llm import get_llm_provider
    from .providers.email_dispatcher import (
        dispatch_outreach_email, get_dispatch_status_info,
        DispatchConfigurationError, DispatchDeliveryError
    )
    from .exporter import generate_leads_csv
    from .env_loader import load_root_env
    from .dispatch_tracker import global_dispatch_tracker
except (ImportError, ValueError):
    from models import (
        ResearchRequest, ResearchResponse, CSVExportRequest,
        OutreachDraftRequest, OutreachDraftResponse,
        SendOutreachRequest, SendOutreachResponse, AIProviderConfig,
    )
    from providers.mock import MockResearchProvider
    from providers.playwright_scraper import PlaywrightResearchProvider
    from providers.llm import get_llm_provider
    from providers.email_dispatcher import (
        dispatch_outreach_email, get_dispatch_status_info,
        DispatchConfigurationError, DispatchDeliveryError
    )
    from exporter import generate_leads_csv
    from env_loader import load_root_env
    from dispatch_tracker import global_dispatch_tracker

# Load root .env into environment if present
load_root_env(override=False)

# In-memory registry of active generated drafts for strict verification tracking
DRAFT_REGISTRY = {}


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

@app.get("/api/outreach/providers")
def get_outreach_providers():
    """
    Returns available AI drafting providers and email dispatch status.
    """
    return {
        "providers": [
            {
                "id": "template",
                "name": "Built-in Grounded Drafter",
                "description": "Deterministic, zero-leakage drafter using strictly verified public metadata. Fast & offline-ready.",
                "requires_key": False,
                "is_available": True,
            },
            {
                "id": "ollama",
                "name": "Local Ollama (Offline LLM)",
                "description": "Connects to a local Ollama instance (default: http://localhost:11434, model: llama3). Private & local.",
                "requires_key": False,
                "is_available": True,
            },
            {
                "id": "openai",
                "name": "Cloud AI (OpenAI Compatible)",
                "description": "Connects to any OpenAI-compatible API endpoint (OpenAI, Groq, OpenRouter, Azure).",
                "requires_key": True,
                "is_available": bool(os.environ.get("AGENTDESK_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")),
            },
        ],
        "dispatch": get_dispatch_status_info(),
    }

@app.post("/api/outreach/draft", response_model=OutreachDraftResponse)
async def draft_outreach(request: OutreachDraftRequest):
    """
    Generates personalized outreach drafts for selected lead records.
    Strictly grounded in verified public metadata without fabricating names or unverified claims.
    """
    if not request.leads:
        raise HTTPException(status_code=422, detail="At least one lead record must be selected for outreach drafting.")
    if len(request.service_offering.strip()) < 2:
        raise HTTPException(status_code=422, detail="Service offering description must be at least 2 characters.")

    try:
        provider = get_llm_provider(request.ai_config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"AI Provider configuration error: {str(e)}")

    drafts = []
    verified_count = 0
    missing_count = 0

    for lead in request.leads:
        try:
            draft = await provider.draft_lead_outreach(
                lead=lead,
                service_offering=request.service_offering.strip(),
                tone=request.tone or "professional",
                sender_name=request.sender_name or "AgentDesk Operator",
                sender_company=request.sender_company or "AgentDesk",
            )
            drafts.append(draft)
            DRAFT_REGISTRY[draft.id] = draft
            if draft.has_verified_email:
                verified_count += 1
            else:
                missing_count += 1
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Outreach drafting error via {provider.display_name}: {str(exc)}"
            )

    return OutreachDraftResponse(
        drafts=drafts,
        total=len(drafts),
        verified_email_count=verified_count,
        missing_email_count=missing_count,
        provider_used=provider.display_name,
    )

@app.post("/api/outreach/send", response_model=SendOutreachResponse)
async def send_outreach(request: SendOutreachRequest):
    """
    Explicit Human Approval Gate for Outreach Dispatch.
    Transmission is strictly blocked unless the human operator explicitly approved the draft
    and the target lead has a verified public email address.
    Dispatches via configured SMTP / API provider or clearly identifies simulation mode.
    Enforces duplicate-send protection and strict public email verification.
    """
    if not request.approved:
        raise HTTPException(
            status_code=400,
            detail="Safety Gate: Outreach transmission requires explicit operator approval ('approved: true')."
        )

    recipient = (request.recipient_email or "").strip()
    subject_clean = request.subject.strip()
    body_clean = request.body.strip()

    if not subject_clean or not body_clean:
        raise HTTPException(
            status_code=422,
            detail="Subject and email body must not be empty."
        )

    # 1. Duplicate-send protection (Draft ID & Content idempotency)
    duplicate = global_dispatch_tracker.check_duplicate(
        draft_id=request.draft_id,
        recipient_email=recipient,
        subject=subject_clean,
        body=body_clean,
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Duplicate Send Blocked: Outreach draft '{request.draft_id}' has already been dispatched "
                f"to {duplicate.recipient_email} at {duplicate.dispatched_at} (Provider: {duplicate.provider}). "
                "Repeated transmission is restricted to prevent duplicate emails."
            )
        )

    # 2. Strict public email verification check
    if not recipient or recipient == "(No public email listed)" or "@" not in recipient or "." not in recipient.split("@")[-1]:
        raise HTTPException(
            status_code=422,
            detail="Dispatch Blocked: Target lead lacks a verified public email address. Transmission to unverified leads is restricted."
        )

    # If the draft was recorded in DRAFT_REGISTRY, its verified status is authoritative:
    if request.draft_id in DRAFT_REGISTRY:
        reg_draft = DRAFT_REGISTRY[request.draft_id]
        if not reg_draft.has_verified_email:
            raise HTTPException(
                status_code=422,
                detail="Dispatch Blocked: Target lead lacks a verified public email address. A syntactically valid email alone does not count as verified."
            )
        if reg_draft.recipient_email.lower() != recipient.lower():
            raise HTTPException(
                status_code=422,
                detail="Dispatch Blocked: Recipient address does not match the verified public email recorded for this draft."
            )
    elif request.has_verified_email is False:
        raise HTTPException(
            status_code=422,
            detail="Dispatch Blocked: Target lead lacks a verified public email address. A syntactically valid email alone does not count as verified."
        )

    try:
        result = dispatch_outreach_email(
            recipient_email=recipient,
            subject=subject_clean,
            body=body_clean,
            draft_id=request.draft_id,
        )
    except DispatchConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except DispatchDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected dispatch error: {str(exc)}")

    # Record dispatch in idempotency registry only on success
    global_dispatch_tracker.record_dispatch(
        draft_id=request.draft_id,
        recipient_email=recipient,
        subject=subject_clean,
        body=body_clean,
        status=result.status,
        provider=result.provider,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    return SendOutreachResponse(
        draft_id=request.draft_id,
        status=result.status,
        recipient_email=recipient,
        message=result.message,
        dispatched_at=now_iso,
        is_simulated=result.is_simulated,
        provider=result.provider,
    )

if __name__ == "__main__":
    uvicorn.run("backend.main:app" if __package__ else "main:app", host="127.0.0.1", port=8000, loop="none")


