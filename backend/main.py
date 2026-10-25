import sys
import os
import json
import sqlite3
import asyncio
from datetime import datetime, timezone
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict

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
        OutreachHistoryItem, OutreachHistoryResponse,
        DiscoveryPlanRequest, DiscoveryPlan, DiscoveryJobCreateRequest,
        DiscoveredLeadRecord, DiscoveryJob, DiscoveryJobResponse,
        DiscoveredLeadsResponse, SearchProviderInfo, SearchProvidersResponse,
        TransferToOutreachRequest, LeadRecord,
    )
    from .providers.mock import MockResearchProvider
    from .providers.playwright_scraper import PlaywrightResearchProvider
    from .providers.llm import get_llm_provider
    from .providers.email_dispatcher import (
        dispatch_outreach_email, get_dispatch_status_info, get_dispatch_config,
        DispatchConfigurationError, DispatchDeliveryError, sanitize_log_message,
    )
    from .providers.search.factory import list_search_providers, get_search_provider
    from .services.lead_discovery import parse_natural_language_request, global_lead_discovery_service
    from .exporter import generate_leads_csv
    from .env_loader import load_root_env
    from .dispatch_tracker import global_dispatch_tracker
except (ImportError, ValueError):
    from models import (
        ResearchRequest, ResearchResponse, CSVExportRequest,
        OutreachDraftRequest, OutreachDraftResponse,
        SendOutreachRequest, SendOutreachResponse, AIProviderConfig,
        OutreachHistoryItem, OutreachHistoryResponse,
        DiscoveryPlanRequest, DiscoveryPlan, DiscoveryJobCreateRequest,
        DiscoveredLeadRecord, DiscoveryJob, DiscoveryJobResponse,
        DiscoveredLeadsResponse, SearchProviderInfo, SearchProvidersResponse,
        TransferToOutreachRequest, LeadRecord,
    )
    from providers.mock import MockResearchProvider
    from providers.playwright_scraper import PlaywrightResearchProvider
    from providers.llm import get_llm_provider
    from providers.email_dispatcher import (
        dispatch_outreach_email, get_dispatch_status_info, get_dispatch_config,
        DispatchConfigurationError, DispatchDeliveryError, sanitize_log_message,
    )
    from providers.search.factory import list_search_providers, get_search_provider
    from services.lead_discovery import parse_natural_language_request, global_lead_discovery_service
    from exporter import generate_leads_csv
    from env_loader import load_root_env
    from dispatch_tracker import global_dispatch_tracker

# Load root .env into environment if present
load_root_env(override=False)

# In-memory registry of active generated drafts for strict verification tracking
DRAFT_REGISTRY = {}

def _init_draft_storage():
    """Restores previously drafted records and their verification statuses across restarts."""
    try:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        storage_dir = os.path.normpath(os.path.join(backend_dir, "..", "storage"))
        if not os.path.isdir(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)
        db_path = os.path.join(storage_dir, "dispatches.db")
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS draft_records (
                    id TEXT PRIMARY KEY,
                    raw_json TEXT NOT NULL
                )
            """)
            conn.commit()
            cur = conn.execute("SELECT id, raw_json FROM draft_records")
            for row in cur.fetchall():
                try:
                    d_data = json.loads(row[1])
                    try:
                        from .models import OutreachDraft
                    except (ImportError, ValueError):
                        from models import OutreachDraft
                    DRAFT_REGISTRY[row[0]] = OutreachDraft.model_validate(d_data)
                except Exception:
                    pass
    except Exception:
        pass

def _persist_draft(draft):
    """Persists an OutreachDraft to SQLite for verification status durability across restarts."""
    try:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        storage_dir = os.path.normpath(os.path.join(backend_dir, "..", "storage"))
        db_path = os.path.join(storage_dir, "dispatches.db")
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO draft_records (id, raw_json) VALUES (?, ?)",
                (draft.id, draft.model_dump_json())
            )
            conn.commit()
    except Exception:
        pass

# Initialize draft storage on startup
_init_draft_storage()


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
            _persist_draft(draft)

            # Record draft creation in history
            global_dispatch_tracker.record_history_entry(
                draft_id=draft.id,
                recipient_email=draft.recipient_email,
                subject=draft.subject,
                status="drafted",
                provider=provider.display_name,
                is_simulated=False,
                recipient_name=draft.recipient_name,
                company_name=draft.company_name,
                body_preview=draft.body,
                source_url=draft.source_url,
                dispatched_at=draft.created_at,
            )

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

    # 1. Duplicate-send protection & concurrent in-flight claim
    allowed, reason, duplicate = global_dispatch_tracker.claim_dispatch(
        draft_id=request.draft_id,
        recipient_email=recipient,
        subject=subject_clean,
        body=body_clean,
    )
    if not allowed:
        if reason == "in_flight":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Duplicate Send Blocked: Outreach draft '{request.draft_id}' is currently in-flight. "
                    "A transmission request is already being processed for this message."
                )
            )
        else:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Duplicate Send Blocked: Outreach draft '{request.draft_id}' has already been dispatched "
                    f"to {duplicate.recipient_email} at {duplicate.dispatched_at} (Provider: {duplicate.provider}). "
                    "Repeated transmission is restricted to prevent duplicate emails."
                )
            )

    try:
        # 2. Strict public email verification check
        if not recipient or recipient == "(No public email listed)" or "@" not in recipient or "." not in recipient.split("@")[-1]:
            raise HTTPException(
                status_code=422,
                detail="Dispatch Blocked: Target lead lacks a verified public email address. Transmission to unverified leads is restricted."
            )

        reg_draft = DRAFT_REGISTRY.get(request.draft_id)
        # If the draft was recorded in DRAFT_REGISTRY, its verified status is authoritative:
        if reg_draft:
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

        current_cfg = get_dispatch_config()
        current_mode = current_cfg.get("mode", "simulation")

        try:
            result = dispatch_outreach_email(
                recipient_email=recipient,
                subject=subject_clean,
                body=body_clean,
                draft_id=request.draft_id,
            )
        except DispatchConfigurationError as exc:
            now_err_iso = datetime.now(timezone.utc).isoformat()
            clean_err = sanitize_log_message(str(exc))
            global_dispatch_tracker.record_history_entry(
                draft_id=request.draft_id,
                recipient_email=recipient,
                subject=subject_clean,
                status="failed",
                provider=current_mode,
                is_simulated=False,
                recipient_name=reg_draft.recipient_name if reg_draft else "",
                company_name=reg_draft.company_name if reg_draft else "",
                body_preview=body_clean,
                source_url=reg_draft.source_url if reg_draft else "",
                error_message=clean_err,
                dispatched_at=now_err_iso,
            )
            raise HTTPException(status_code=500, detail=clean_err)
        except DispatchDeliveryError as exc:
            now_err_iso = datetime.now(timezone.utc).isoformat()
            clean_err = sanitize_log_message(str(exc))
            global_dispatch_tracker.record_history_entry(
                draft_id=request.draft_id,
                recipient_email=recipient,
                subject=subject_clean,
                status="failed",
                provider=current_mode,
                is_simulated=False,
                recipient_name=reg_draft.recipient_name if reg_draft else "",
                company_name=reg_draft.company_name if reg_draft else "",
                body_preview=body_clean,
                source_url=reg_draft.source_url if reg_draft else "",
                error_message=clean_err,
                dispatched_at=now_err_iso,
            )
            raise HTTPException(status_code=502, detail=clean_err)
        except Exception as exc:
            now_err_iso = datetime.now(timezone.utc).isoformat()
            clean_err = sanitize_log_message(str(exc))
            global_dispatch_tracker.record_history_entry(
                draft_id=request.draft_id,
                recipient_email=recipient,
                subject=subject_clean,
                status="failed",
                provider=current_mode,
                is_simulated=False,
                recipient_name=reg_draft.recipient_name if reg_draft else "",
                company_name=reg_draft.company_name if reg_draft else "",
                body_preview=body_clean,
                source_url=reg_draft.source_url if reg_draft else "",
                error_message=f"Unexpected dispatch error: {clean_err}",
                dispatched_at=now_err_iso,
            )
            raise HTTPException(status_code=500, detail=f"Unexpected dispatch error: {clean_err}")

        if not getattr(result, "success", True):
            now_err_iso = datetime.now(timezone.utc).isoformat()
            fail_msg = getattr(result, "message", "Dispatch provider rejected transmission.")
            clean_err = sanitize_log_message(fail_msg)
            global_dispatch_tracker.record_history_entry(
                draft_id=request.draft_id,
                recipient_email=recipient,
                subject=subject_clean,
                status="failed",
                provider=getattr(result, "provider", current_mode),
                is_simulated=False,
                recipient_name=reg_draft.recipient_name if reg_draft else "",
                company_name=reg_draft.company_name if reg_draft else "",
                body_preview=body_clean,
                source_url=reg_draft.source_url if reg_draft else "",
                error_message=clean_err,
                dispatched_at=now_err_iso,
            )
            raise HTTPException(
                status_code=502,
                detail=clean_err,
            )

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

        # Update draft in registry and persistence
        if reg_draft:
            reg_draft.status = "sent"
            _persist_draft(reg_draft)

        # Record successful / simulated dispatch in outreach history
        global_dispatch_tracker.record_history_entry(
            draft_id=request.draft_id,
            recipient_email=recipient,
            subject=subject_clean,
            status=result.status,
            provider=result.provider,
            is_simulated=bool(result.is_simulated),
            recipient_name=reg_draft.recipient_name if reg_draft else "",
            company_name=reg_draft.company_name if reg_draft else "",
            body_preview=body_clean,
            source_url=reg_draft.source_url if reg_draft else "",
            dispatched_at=now_iso,
        )
    except Exception:
        # On failure or validation exception, release the in-flight claim so retry is possible
        global_dispatch_tracker.release_claim(
            draft_id=request.draft_id,
            recipient_email=recipient,
            subject=subject_clean,
            body=body_clean,
        )
        raise

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

@app.get("/api/outreach/history", response_model=OutreachHistoryResponse)
def get_outreach_history(
    status: Optional[str] = None,
    search: Optional[str] = None,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
):
    """
    Returns paginated, searchable, and filtered outreach history records.
    Distinguishes simulated, sent, failed, and drafted events.
    """
    effective_search = search if search is not None else query
    items, total, total_pages, counts = global_dispatch_tracker.query_history(
        status=status,
        search=effective_search,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return OutreachHistoryResponse(
        items=[OutreachHistoryItem(**it) for it in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        counts_by_status=counts,
    )

@app.get("/api/outreach/history/export-csv")
def export_outreach_history_csv(
    status: Optional[str] = None,
    search: Optional[str] = None,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Exports filtered outreach history records to an RFC 4180 CSV file stream.
    All secrets and credentials are sanitized and excluded.
    """
    effective_search = search if search is not None else query
    csv_content = global_dispatch_tracker.export_history_csv(
        status=status,
        search=effective_search,
        start_date=start_date,
        end_date=end_date,
    )
    filename = f"agentdesk_outreach_history_{int(datetime.now(timezone.utc).timestamp())}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# -------------------------------------------------------------------------
# Automated Lead Discovery Endpoints
# -------------------------------------------------------------------------

@app.post("/api/discovery/plan", response_model=DiscoveryPlan)
def generate_discovery_plan(request: DiscoveryPlanRequest):
    """
    Parses a natural-language lead generation request into a structured, editable DiscoveryPlan.
    Detects ambiguity and prompts for clarification if key business domain or location criteria are missing.
    """
    prompt_clean = (request.prompt or "").strip()
    if not prompt_clean:
        raise HTTPException(status_code=422, detail="Prompt must not be empty.")

    plan = parse_natural_language_request(prompt_clean, request.ai_config)
    return plan


@app.get("/api/discovery/providers", response_model=SearchProvidersResponse)
def get_discovery_providers():
    """
    Returns the configuration status and description of all supported search sources:
    Tavily Search API, Google Custom Search, Bing Web Search, and Public Business Directory.
    """
    providers = list_search_providers()
    return SearchProvidersResponse(providers=providers)


@app.post("/api/discovery/jobs", response_model=DiscoveryJob)
async def create_discovery_job(request: DiscoveryJobCreateRequest):
    """
    Creates and initiates a background automated lead discovery job.
    """
    if not request.plan.industry and not request.plan.keywords:
        raise HTTPException(status_code=422, detail="Plan must specify an industry or business keywords.")

    job = await global_lead_discovery_service.start_job(request)
    return job


@app.get("/api/discovery/jobs/{job_id}", response_model=DiscoveryJobResponse)
def get_discovery_job(job_id: str):
    """
    Retrieves discovery job status, telemetry metrics, and the latest discovered leads.
    """
    job_dict = global_dispatch_tracker.get_discovery_job(job_id)
    if not job_dict:
        raise HTTPException(status_code=404, detail=f"Discovery job '{job_id}' not found.")

    leads_list, _, _, _ = global_dispatch_tracker.query_discovered_leads(
        job_id=job_id,
        page=1,
        page_size=100,
    )

    job = DiscoveryJob(**job_dict)
    leads = [DiscoveredLeadRecord(**item) for item in leads_list]
    return DiscoveryJobResponse(job=job, leads=leads)


@app.post("/api/discovery/jobs/{job_id}/cancel", response_model=DiscoveryJob)
def cancel_discovery_job(job_id: str):
    """
    Cooperatively stops the background discovery pipeline for the specified job.
    """
    cancelled = global_lead_discovery_service.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail=f"Discovery job '{job_id}' not found.")

    job_dict = global_dispatch_tracker.get_discovery_job(job_id)
    if not job_dict:
        raise HTTPException(status_code=404, detail=f"Discovery job '{job_id}' not found.")
    return DiscoveryJob(**job_dict)


@app.get("/api/discovery/jobs/{job_id}/leads", response_model=DiscoveredLeadsResponse)
def list_discovered_leads(
    job_id: str,
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    category: Optional[str] = None,
    email_status: Optional[str] = None,
    sort_by: Optional[str] = "discovered_at",
    sort_order: Optional[str] = "desc",
):
    """
    Returns paginated, searchable, and filtered leads discovered by a job,
    including verification breakdown counts.
    """
    job_dict = global_dispatch_tracker.get_discovery_job(job_id)
    if not job_dict:
        raise HTTPException(status_code=404, detail=f"Discovery job '{job_id}' not found.")

    leads_list, total_count, total_pages, counts = global_dispatch_tracker.query_discovered_leads(
        job_id=job_id,
        search=search,
        country=country,
        city=city,
        category=category,
        email_status=email_status,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    return DiscoveredLeadsResponse(
        leads=[DiscoveredLeadRecord(**item) for item in leads_list],
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        verification_counts=counts,
    )


@app.get("/api/discovery/jobs/{job_id}/export-csv")
def export_discovered_leads_csv(
    job_id: str,
    search: Optional[str] = None,
    email_status: Optional[str] = None,
):
    """
    Exports discovered leads for a job to an RFC 4180 CSV file stream.
    """
    job_dict = global_dispatch_tracker.get_discovery_job(job_id)
    if not job_dict:
        raise HTTPException(status_code=404, detail=f"Discovery job '{job_id}' not found.")

    csv_content = global_dispatch_tracker.export_discovered_leads_csv(
        job_id=job_id,
        search=search,
        email_status=email_status,
    )
    filename = f"agentdesk_discovered_leads_{job_id}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@app.post("/api/discovery/transfer-outreach", response_model=OutreachDraftResponse)
async def transfer_leads_to_outreach(request: TransferToOutreachRequest):
    """
    Converts selected discovered leads into Outreach drafts and registers them in the
    outreach drafting workflow. Preserves strict public email verification rules.
    """
    if not request.lead_ids:
        raise HTTPException(status_code=422, detail="No lead IDs provided for outreach transfer.")

    llm_provider = get_llm_provider(None)
    drafts = []
    verified_count = 0
    missing_count = 0

    for lead_id in request.lead_ids:
        lead_data = global_dispatch_tracker.get_discovered_lead(lead_id)
        if not lead_data:
            continue

        has_verified_email = (lead_data.get("email_verification_status") == "verified_public")
        public_email = lead_data.get("email") if has_verified_email else "(No public email listed)"

        lead_obj = LeadRecord(
            id=f"disc-{lead_data['id']}",
            company_name=lead_data["company_name"],
            contact_name="",
            contact_role="",
            email=public_email,
            website=lead_data["website"],
            industry=lead_data["industry"],
            location=f"{lead_data['city']}, {lead_data['country']}".strip(", "),
            source_url=lead_data["website"],
            description=lead_data.get("services_description", ""),
            verified_fields=lead_data.get("verified_fields", []),
            is_live=True,
        )

        draft = await llm_provider.draft_lead_outreach(
            lead=lead_obj,
            service_offering=lead_data.get("services_description") or "Commercial Partnership",
        )

        DRAFT_REGISTRY[draft.id] = draft
        _persist_draft(draft)
        drafts.append(draft)

        if draft.has_verified_email:
            verified_count += 1
        else:
            missing_count += 1

    return OutreachDraftResponse(
        drafts=drafts,
        total=len(drafts),
        verified_email_count=verified_count,
        missing_email_count=missing_count,
        provider_used=llm_provider.display_name,
    )


if __name__ == "__main__":
    uvicorn.run("backend.main:app" if __package__ else "main:app", host="127.0.0.1", port=8000, loop="none")
