"""
Data models for AgentDesk Research and Lead Management.
"""
from pydantic import BaseModel, Field
from typing import List, Optional

class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=100, description="Target search topic or niche keyword")
    industry: str = Field(..., min_length=2, max_length=100, description="Target industry sector")
    location: str = Field(..., min_length=2, max_length=100, description="Target geographic market or city")
    max_results: Optional[int] = Field(default=5, ge=1, le=25, description="Maximum number of lead records to generate")

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

class ResearchResponse(BaseModel):
    topic: str
    industry: str
    location: str
    provider: str
    is_demo: bool
    disclaimer: str
    total_results: int
    leads: List[LeadRecord]

class CSVExportRequest(BaseModel):
    leads: List[LeadRecord]
