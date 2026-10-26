"""
Data models for AgentDesk Research and Lead Management.
Supports both Mock / Demo mode and Live Playwright Public-Web extraction.
"""
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Any

class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=100, description="Target search topic or niche keyword")
    industry: str = Field(..., min_length=2, max_length=100, description="Target industry sector")
    location: str = Field(..., min_length=2, max_length=100, description="Target geographic market or city")
    max_results: Optional[int] = Field(default=5, ge=1, le=25, description="Maximum number of lead records to generate")
    mode: Optional[str] = Field(default="demo", description="Research mode: 'demo' (simulated records) or 'live' (Playwright public web)")
    urls: Optional[List[str]] = Field(default=None, description="User-supplied public website URLs for live research (HTTP/HTTPS only)")
    follow_links: Optional[bool] = Field(default=True, description="Whether to follow on-domain links like /about or /contact")
    max_pages_per_domain: Optional[int] = Field(default=2, ge=1, le=5, description="Maximum pages to inspect per target domain")

class LeadRecord(BaseModel):
    id: str
    company_name: str
    contact_name: Optional[str] = Field(default="")
    contact_role: Optional[str] = Field(default="")
    email: Optional[str] = Field(default="")
    website: Optional[str] = Field(default="")
    industry: Optional[str] = Field(default="")
    location: Optional[str] = Field(default="")
    source_note: Optional[str] = Field(default="")
    created_at: Optional[str] = Field(default="")
    source_url: Optional[str] = Field(default="", description="The specific public page URL from which data was retrieved")
    description: Optional[str] = Field(default="", description="Public business description extracted from meta/page text")
    verified_fields: Optional[List[str]] = Field(default_factory=list, description="List of fields confirmed present on the public page")
    is_live: Optional[bool] = Field(default=False, description="True if extracted from live public web via Playwright")

class CrawlDiagnostic(BaseModel):
    url: str
    status: str
    reason: str

class ResearchResponse(BaseModel):
    topic: str
    industry: str
    location: str
    provider: str
    is_demo: bool
    disclaimer: str
    total_results: int
    leads: List[LeadRecord]
    pages_crawled: Optional[int] = 0
    diagnostics: Optional[List[CrawlDiagnostic]] = Field(default_factory=list)

class CSVExportRequest(BaseModel):
    leads: List[LeadRecord]

class AIProviderConfig(BaseModel):
    provider_type: str = Field(default="template", description="AI Provider: 'template' (built-in grounded), 'ollama' (local offline), 'openai' (cloud compatible)")
    model_name: Optional[str] = Field(default=None, description="Model identifier (e.g. llama3, mistral, gpt-4o-mini)")
    api_base: Optional[str] = Field(default=None, description="API base URL (e.g. http://localhost:11434 or https://api.openai.com/v1)")
    api_key: Optional[str] = Field(default=None, description="API key for cloud AI provider (never persisted or exposed)")

class OutreachDraftRequest(BaseModel):
    leads: List[LeadRecord] = Field(..., min_length=1, description="List of target lead records to draft outreach for")
    service_offering: str = Field(..., min_length=2, max_length=200, description="Your service offering or value proposition")
    tone: Optional[str] = Field(default="professional", description="Desired outreach tone: 'professional', 'consultative', 'concise'")
    sender_name: Optional[str] = Field(default="AgentDesk Operator", description="Sender contact name")
    sender_company: Optional[str] = Field(default="AgentDesk", description="Sender company name")
    ai_config: Optional[AIProviderConfig] = Field(default_factory=AIProviderConfig, description="Selected AI generation provider configuration")

class OutreachDraft(BaseModel):
    id: str
    lead_id: str
    company_name: str
    recipient_name: Optional[str] = ""
    recipient_role: Optional[str] = ""
    recipient_email: str
    has_verified_email: bool = False
    subject: str
    body: str
    status: str = Field(default="drafted", description="Draft review status: 'drafted', 'approved', 'rejected', 'sent'")
    created_at: str
    updated_at: Optional[str] = None
    source_url: Optional[str] = ""
    grounding_notes: Optional[str] = ""
    verified_facts_used: List[str] = Field(default_factory=list)
    discovery_source: Optional[str] = ""
    discovery_query: Optional[str] = ""
    relevance_explanation: Optional[str] = ""
    flagged_for_manual_review: bool = False
    manual_review_reason: Optional[str] = None


class OutreachDraftResponse(BaseModel):
    drafts: List[OutreachDraft]
    total: int
    verified_email_count: int
    missing_email_count: int
    provider_used: str

class SendOutreachRequest(BaseModel):
    draft_id: str
    approved: bool = Field(..., description="Operator approval flag. Transmission is blocked unless true.")
    recipient_email: str
    subject: str
    body: str
    has_verified_email: Optional[bool] = Field(default=None, description="Explicit verification status of the recipient email")
    confirmation_token: Optional[str] = Field(default=None, description="Operator confirmation token")

class SendOutreachResponse(BaseModel):
    draft_id: str
    status: str
    recipient_email: str
    message: str
    dispatched_at: str
    is_simulated: Optional[bool] = False
    provider: Optional[str] = "simulation"

class OutreachHistoryItem(BaseModel):
    id: str
    draft_id: str
    recipient_email: str
    recipient_name: Optional[str] = ""
    company_name: Optional[str] = ""
    subject: str
    body_preview: Optional[str] = ""
    body_snippet: Optional[str] = ""
    source_url: Optional[str] = ""
    status: str = Field(..., description="Dispatch status: 'simulated', 'sent', 'failed', 'drafted'")
    provider: str = Field(default="simulation", description="Provider mode (e.g. simulation, smtp, resend)")
    provider_mode: Optional[str] = Field(default=None, description="Alias for provider mode")
    is_simulated: bool = Field(default=False, description="True if safe offline simulation mode was used")
    dispatched_at: str = Field(..., description="UTC ISO 8601 timestamp of dispatch or draft")
    error_message: Optional[str] = Field(default=None, description="Sanitized failure diagnostic message")

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any):
        if isinstance(data, dict):
            # Sync provider and provider_mode
            if "provider" in data and not data.get("provider_mode"):
                data["provider_mode"] = data["provider"]
            elif "provider_mode" in data and not data.get("provider"):
                data["provider"] = data["provider_mode"]
            # Sync body_preview and body_snippet
            if "body_preview" in data and not data.get("body_snippet"):
                data["body_snippet"] = data["body_preview"]
            elif "body_snippet" in data and not data.get("body_preview"):
                data["body_preview"] = data["body_snippet"]
        return data

class OutreachHistoryResponse(BaseModel):
    items: List[OutreachHistoryItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    status_counts: dict = Field(default_factory=dict)
    counts_by_status: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def sync_counts(cls, data: Any):
        if isinstance(data, dict):
            counts = data.get("status_counts") or data.get("counts_by_status") or {}
            data["status_counts"] = counts
            data["counts_by_status"] = counts
        return data


# ==============================================================================
# Automated Lead Discovery Agent Models
# ==============================================================================

class DiscoveryPlanRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=1000, description="Natural language request for lead discovery")
    ai_config: Optional[AIProviderConfig] = Field(default=None, description="Optional AI configuration for request parsing")

class DiscoveryPlan(BaseModel):
    prompt: str = Field(default="", description="Target request prompt")
    industry: str = Field(default="", description="Target industry or business domain")
    location: str = Field(default="", description="Target geographic market (city/region/country)")
    city: Optional[str] = Field(default="", description="Target city if specified")
    country: Optional[str] = Field(default="", description="Target country if specified")
    keywords: List[str] = Field(default_factory=list, description="Target business activity keywords")
    target_count: int = Field(default=25, ge=1, le=100, description="Target number of leads to discover")
    search_queries: List[str] = Field(default_factory=list, description="Synthesized search engine & directory queries")
    company_criteria: Optional[str] = Field(default="", description="Optional company size or customer focus criteria")
    desired_contacts: List[str] = Field(default_factory=lambda: ["email", "website", "phone"], description="Requested contact modalities")
    search_language: str = Field(default="en", description="Search language code")
    max_crawl_depth: int = Field(default=1, ge=0, le=2, description="Maximum subpage crawl depth")
    max_pages_per_domain: int = Field(default=2, ge=1, le=5, description="Maximum pages to inspect per domain")
    is_ambiguous: bool = Field(default=False, description="True if prompt lacks clear location or business domain")
    clarification_question: Optional[str] = Field(default=None, description="Clarification question if prompt is ambiguous")

    @model_validator(mode="before")
    @classmethod
    def _remap_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "original_prompt" in d and not d.get("prompt"):
                d["prompt"] = d["original_prompt"]
            if "target_lead_count" in d and not d.get("target_count"):
                d["target_count"] = d["target_lead_count"]
            if "location_city" in d and not d.get("city"):
                d["city"] = d["location_city"]
            if "location_country" in d and not d.get("country"):
                d["country"] = d["location_country"]
            if "service_criteria" in d and not d.get("company_criteria"):
                d["company_criteria"] = d["service_criteria"]
            if "desired_contact_info" in d and not d.get("desired_contacts"):
                d["desired_contacts"] = d["desired_contact_info"]
            if not d.get("location"):
                loc_parts = [d.get("city"), d.get("country")]
                d["location"] = ", ".join([p for p in loc_parts if p]) or "Global"
            return d
        return data

    @property
    def original_prompt(self) -> str:
        return self.prompt

    @property
    def target_lead_count(self) -> int:
        return self.target_count

    @property
    def location_city(self) -> Optional[str]:
        return self.city

    @property
    def location_country(self) -> Optional[str]:
        return self.country

    @property
    def service_criteria(self) -> Optional[str]:
        return self.company_criteria

    @property
    def desired_contact_info(self) -> List[str]:
        return self.desired_contacts

class DiscoveryJobCreateRequest(BaseModel):
    plan: DiscoveryPlan
    search_provider: Optional[str] = Field(default="auto", description="Search source: 'auto', 'tavily', 'google', 'bing', or 'directory'")
    ai_config: Optional[AIProviderConfig] = None

class DiscoveredLeadRecord(BaseModel):
    id: str
    job_id: str
    company_name: str
    website: str
    industry: Optional[str] = ""
    city: Optional[str] = ""
    country: Optional[str] = ""
    services_description: Optional[str] = ""
    email: Optional[str] = ""
    email_verification_status: str = Field(
        default="not_found",
        description="Verification state: 'verified_public', 'found_unverified', 'not_found', or 'invalid'"
    )
    phone: Optional[str] = ""
    phone_verification_status: str = Field(
        default="not_found",
        description="Phone verification: 'verified_public', 'unverified', or 'not_found'"
    )
    source_urls: List[str] = Field(default_factory=list, description="All public source URLs confirming these facts")
    discovery_source: str = Field(default="google-search", description="Provider that first found this company")
    discovery_query: str = Field(default="", description="Search query that surfaced this lead")
    discovered_at: str = Field(..., description="UTC ISO timestamp of discovery")
    relevance_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Relevance score between 0.0 and 1.0")
    relevance_explanation: str = Field(default="", description="Short evidence-backed explanation of match")
    research_status: str = Field(default="completed", description="'completed', 'skipped', or 'failed'")
    failure_reason: Optional[str] = None
    verified_fields: List[str] = Field(default_factory=list)
    is_live: bool = Field(default=True)

class DiscoveryJob(BaseModel):
    id: str
    prompt: str
    status: str = Field(default="pending", description="'pending', 'running', 'completed', 'cancelled', 'failed'")
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    provider_used: str = "auto"
    total_target: int = 25
    discovered_count: int = 0
    verified_email_count: int = 0
    duplicate_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    progress_percent: int = 0
    current_stage: Optional[str] = "Queued"
    plan_json: Optional[str] = None
    error_message: Optional[str] = None

class DiscoveryJobResponse(BaseModel):
    job: DiscoveryJob
    leads: List[DiscoveredLeadRecord] = Field(default_factory=list)

class DiscoveredLeadsResponse(BaseModel):
    leads: List[DiscoveredLeadRecord]
    total: int
    page: int
    page_size: int
    total_pages: int
    verification_counts: dict = Field(default_factory=dict)

class SearchProviderInfo(BaseModel):
    id: str
    name: str
    description: str
    is_configured: bool
    requires_key: bool
    notice: str

class SearchProvidersResponse(BaseModel):
    providers: List[SearchProviderInfo]

class TransferToOutreachRequest(BaseModel):
    job_id: str
    lead_ids: List[str] = Field(default_factory=list, description="IDs of discovered leads to transfer to outreach")
    service_offering: Optional[str] = Field(default="Custom software development, IoT systems, and cloud architecture", description="Service offering or value proposition")
    tone: Optional[str] = Field(default="professional", description="Outreach tone")
    sender_name: Optional[str] = Field(default="AgentDesk Operator", description="Sender name")
    sender_company: Optional[str] = Field(default="AgentDesk", description="Sender organization")
    ai_config: Optional[AIProviderConfig] = Field(default=None, description="AI provider configuration")
    prevent_duplicates: bool = Field(default=True, description="Skip generating duplicate drafts for leads already drafted")

class LeadTransferResponse(OutreachDraftResponse):
    created_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    messages: List[str] = Field(default_factory=list)

class UpdateDraftRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    recipient_name: Optional[str] = None

class DiscardDraftRequest(BaseModel):
    reason: Optional[str] = None

class OutreachDraftsListResponse(BaseModel):
    drafts: List[OutreachDraft]
    total: int
    page: int
    page_size: int
    total_pages: int
    counts_by_status: dict = Field(default_factory=dict)
