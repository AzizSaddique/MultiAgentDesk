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
    contact_name: str
    contact_role: str
    email: str
    website: str
    industry: str
    location: str
    source_note: str
    created_at: str
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
