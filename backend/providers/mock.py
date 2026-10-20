"""
Mock / Demo Research Provider for AgentDesk.
Explicitly labels all generated records as simulated demo data.
Supports query-aware personas, sector tailoring, and deterministic simulation of empty/error results.
"""
from typing import List, Dict, Any
from datetime import datetime, timezone
import hashlib
import re

try:
    from .base import BaseResearchProvider
    from ..models import ResearchRequest, LeadRecord
except (ImportError, ValueError):
    from providers.base import BaseResearchProvider
    from models import ResearchRequest, LeadRecord

# Industry-specific persona & company pools for contextual demo generation
SECTOR_PROFILES: Dict[str, Dict[str, Any]] = {
    "software": {
        "stems": ["NeuralScale", "CognitiveCloud", "NexusAI", "SynapseByte", "CoreStack", "DataForge", "HyperLogic"],
        "roles": [
            ("Elena Rostova", "Chief Executive Officer"),
            ("Dr. Sarah Chen", "VP of Engineering & AI"),
            ("Marcus Vance", "Head of Product Infrastructure"),
            ("Kenji Takahashi", "Director of Cloud Architecture"),
            ("Amina Morales", "VP of Strategic Partnerships"),
        ],
    },
    "cleantech": {
        "stems": ["EcoVolt", "VerdePower", "SunGrid", "TerraWind", "CleanFlux", "PureCurrent", "AeroSustain"],
        "roles": [
            ("Julian Hayes", "Chief Sustainability Officer"),
            ("Sophia Lindqvist", "Director of Grid Solutions"),
            ("David Alvarez", "VP of Renewable Infrastructure"),
            ("Dr. Aris Thorne", "Head of Storage Technology"),
            ("Maya Patel", "Director of Environmental Compliance"),
        ],
    },
    "health": {
        "stems": ["MedPulse", "BioSynthetics", "CareVenture", "CuraWave", "HelixHealth", "OmniCare", "Vitalis"],
        "roles": [
            ("Dr. Evelyn Reed", "Chief Medical Officer"),
            ("Nathaniel Brooks", "Director of Clinical Informatics"),
            ("Clara Gomez", "VP of Digital Therapeutics"),
            ("Tariq Mansour", "Head of Regulatory & Quality"),
            ("Dr. Hannah Weiss", "Chief Scientific Officer"),
        ],
    },
    "fintech": {
        "stems": ["EquiVault", "ApexLedger", "Solventia", "VeritasCapital", "NovaPay", "BridgeFinancial", "PrimeSettlement"],
        "roles": [
            ("Victor Sterling", "Managing Director"),
            ("Helena Cruz", "Chief Risk & Compliance Officer"),
            ("Liam O'Connor", "Head of Quantitative Infrastructure"),
            ("Rachel Zhao", "VP of Global Payment Rails"),
            ("Oliver Vance", "Director of Institutional Accounts"),
        ],
    },
    "default": {
        "stems": ["Beacon", "Pinnacle", "Sterling", "Summit", "Horizon", "Ascend", "Vanguard"],
        "roles": [
            ("Alexander Wright", "Managing Partner"),
            ("Victoria Bell", "Chief Operating Officer"),
            ("Michael Chang", "Director of Business Development"),
            ("Sarah Jenkins", "Head of Strategic Growth"),
            ("Daniel Ramos", "VP of Commercial Operations"),
        ],
    },
}

COMPANY_SUFFIXES = ["Solutions", "Ventures", "Dynamics", "Enterprises", "Labs", "Partners", "Innovations", "Group"]

def _sanitize_slug(text: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9]+', '', text.lower())
    return cleaned[:14] if cleaned else "co"

def _resolve_sector_profile(industry: str) -> Dict[str, Any]:
    ind_lower = industry.lower()
    if any(k in ind_lower for k in ("clean", "solar", "wind", "energy", "sustain", "climate")):
        return SECTOR_PROFILES["cleantech"]
    if any(k in ind_lower for k in ("health", "bio", "med", "care", "pharma", "clinic")):
        return SECTOR_PROFILES["health"]
    if any(k in ind_lower for k in ("fin", "bank", "pay", "capital", "invest", "wealth", "insur")):
        return SECTOR_PROFILES["fintech"]
    if any(k in ind_lower for k in ("soft", "ai", "cloud", "saas", "cyber", "data", "tech", "it")):
        return SECTOR_PROFILES["software"]
    return SECTOR_PROFILES["default"]

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
        Dynamically reacts to query criteria:
        - If query matches empty keywords ('empty', 'zero', 'no-match', 'none'), yields [] (zero results state).
        - If query matches error keywords ('error', 'timeout', 'fail'), simulates a provider error.
        - Otherwise, generates contextual records tailored to topic, industry, and location.
        """
        clean_topic = request.topic.strip()
        clean_ind = request.industry.strip()
        clean_loc = request.location.strip()

        # Simulated provider failure for error state testing
        topic_lower = clean_topic.lower()
        if any(term in topic_lower for term in ("simulate-error", "force-fail", "err-test")):
            raise RuntimeError(f"Simulated provider failure triggered by query token '{clean_topic}'.")

        # Simulated zero-result scenarios for empty state testing
        if any(term in topic_lower for term in ("empty", "zero-leads", "no-match", "unmatched")):
            return []

        profile = _resolve_sector_profile(clean_ind)
        stems = profile["stems"]
        roles = profile["roles"]

        limit = min(request.max_results or 5, len(roles), 25)
        now_iso = datetime.now(timezone.utc).isoformat()

        loc_slug = _sanitize_slug(clean_loc)
        ind_slug = _sanitize_slug(clean_ind)
        city_display = clean_loc.split(',')[0].strip().title()

        # Seed pseudo-randomness deterministically based on input parameters
        hash_seed = int(hashlib.md5(f"{clean_topic}:{clean_ind}:{clean_loc}".encode()).hexdigest()[:8], 16)

        results: List[LeadRecord] = []
        for i in range(limit):
            stem = stems[(i + hash_seed) % len(stems)]
            suffix = COMPANY_SUFFIXES[(i + hash_seed * 3) % len(COMPANY_SUFFIXES)]
            persona_name, persona_role = roles[i % len(roles)]

            company_name = f"{stem} {suffix} ({city_display})"
            domain_slug = f"demo-{_sanitize_slug(stem)}-{_sanitize_slug(suffix)}"

            first_name = persona_name.split()[0].lower().replace("dr.", "").strip()
            last_name = persona_name.split()[-1].lower()
            demo_email = f"{first_name}.{last_name}@{domain_slug}.example.com"
            demo_website = f"https://www.{domain_slug}.example.com"

            results.append(
                LeadRecord(
                    id=f"demo-lead-{i + 1}",
                    company_name=company_name,
                    contact_name=persona_name,
                    contact_role=persona_role,
                    email=demo_email,
                    website=demo_website,
                    industry=clean_ind,
                    location=clean_loc,
                    source_note=f"[DEMO RECORD] Simulated sample for query: '{clean_topic}' | Sector: {clean_ind} | Market: {clean_loc}",
                    created_at=now_iso,
                    source_url="simulated://demo-sample",
                    description=f"Simulated {clean_ind} company profile for demonstration.",
                    verified_fields=["company_name", "simulated_persona"],
                    is_live=False,
                )
            )

        return results
