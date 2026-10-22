"""
Data models for AgentDesk Research and Lead Management.
Supports both Mock / Demo mode and Live Playwright Public-Web extraction.
"""
from pydantic import BaseModel, Field
from typing import List, Optional

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
    recipient_name: str
    recipient_role: str
    recipient_email: str
    has_verified_email: bool
    subject: str
    body: str
    status: str = Field(default="drafted", description="Draft review status: 'drafted', 'approved', 'rejected', 'sent'")
    created_at: str
    source_url: str
    grounding_notes: str
    verified_facts_used: List[str] = Field(default_factory=list)

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


