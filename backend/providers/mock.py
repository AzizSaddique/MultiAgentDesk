"""
Mock / Demo Research Provider for AgentDesk.
Explicitly labels all generated records as simulated demo data.
"""
from typing import List
from datetime import datetime, timezone
import re
try:
    from .base import BaseResearchProvider
    from ..models import ResearchRequest, LeadRecord
except (ImportError, ValueError):
    from providers.base import BaseResearchProvider
    from models import ResearchRequest, LeadRecord

SAMPLE_PERSONAS = [
    {"name": "Elena Rostova", "role": "Chief Executive Officer"},
    {"name": "Marcus Vance", "role": "Head of Operations & Procurement"},
    {"name": "Dr. Sarah Chen", "role": "VP of Technology & Partnerships"},
    {"name": "David Alverez", "role": "Director of Business Development"},
    {"name": "Amina Morales", "role": "Managing Director"},
    {"name": "Julian Hayes", "role": "Chief Operating Officer"},
    {"name": "Sophia Lindqvist", "role": "Head of Strategic Growth"},
    {"name": "Kenji Takahashi", "role": "VP of Infrastructure & Solutions"},
]

def _sanitize_slug(text: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9]+', '', text.lower())
    return cleaned[:14] if cleaned else "co"

class MockResearchProvider(BaseResearchProvider):
    @property
    def provider_name(self) -> str:
        return "mock-demo-provider"

    @property
    def is_demo(self) -> bool:
        return True

    async def search(self, request: ResearchRequest) -> List[LeadRecord]:
        """
        Generates simulated lead records explicitly tagged as demo samples.
        """
        results: List[LeadRecord] = []
        limit = min(request.max_results or 5, len(SAMPLE_PERSONAS))
        now_iso = datetime.now(timezone.utc).isoformat()

        clean_topic = request.topic.strip()
        clean_ind = request.industry.strip()
        clean_loc = request.location.strip()
        loc_slug = _sanitize_slug(clean_loc)
        ind_slug = _sanitize_slug(clean_ind)

        company_suffixes = ["Solutions", "Ventures", "Dynamics", "Enterprises", "Labs", "Partners", "Innovations", "Group"]

        for i in range(limit):
            persona = SAMPLE_PERSONAS[i]
            suffix = company_suffixes[i % len(company_suffixes)]
            
            # Contextual simulated company name
            company_base = f"{clean_ind.split()[0].title() if clean_ind else 'Nexus'} {suffix}"
            domain_slug = f"demo-{ind_slug}-{_sanitize_slug(suffix)}"
            
            first_name = persona["name"].split()[0].lower()
            last_name = persona["name"].split()[-1].lower()
            demo_email = f"{first_name}.{last_name}@{domain_slug}.example.com"
            demo_website = f"https://www.{domain_slug}.example.com"

            results.append(
                LeadRecord(
                    id=f"demo-lead-{i + 1}",
                    company_name=f"{company_base} ({clean_loc.split(',')[0].title()})",
                    contact_name=persona["name"],
                    contact_role=persona["role"],
                    email=demo_email,
                    website=demo_website,
                    industry=clean_ind,
                    location=clean_loc,
                    source_note=f"[DEMO RECORD] Simulated sample for query: '{clean_topic}' | Industry: {clean_ind} | Location: {clean_loc}",
                    created_at=now_iso,
                )
            )

        return results
