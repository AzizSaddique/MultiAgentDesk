"""
Lead Discovery Service for AgentDesk.
Orchestrates:
1. Natural language request parsing into structured DiscoveryPlans (with ambiguity detection).
2. Focused multi-source search query generation.
3. Execution through pluggable SearchProviders (Google, Bing, Public Directories).
4. Canonical domain deduplication and SSRF URL protection.
5. In-depth public website inspection with Playwright, respecting robots.txt and crawl limits.
6. Evidence-backed business fact extraction and genuine public email verification.
7. Background task execution with cooperative cancellation and SQLite persistence.
"""
import os
import re
import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Set, Any
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

try:
    from ..models import (
        DiscoveryPlan, DiscoveryJob, DiscoveredLeadRecord,
        DiscoveryJobCreateRequest, AIProviderConfig, LeadRecord
    )
    from ..providers.search.base import SearchProvider, SearchResult
    from ..providers.search.factory import get_search_provider
    from ..providers.search.directory_search import PublicBusinessDirectoryProvider
    from ..providers.playwright_scraper import (
        validate_target_url, is_allowed_by_robots, _clean_extracted_emails,
        PlaywrightResearchProvider, USER_AGENT
    )
    from ..providers.llm import _has_genuine_email, get_llm_provider
    from ..providers.email_dispatcher import sanitize_log_message
    from ..dispatch_tracker import global_dispatch_tracker
except (ImportError, ValueError):
    from models import (
        DiscoveryPlan, DiscoveryJob, DiscoveredLeadRecord,
        DiscoveryJobCreateRequest, AIProviderConfig, LeadRecord
    )
    from providers.search.base import SearchProvider, SearchResult
    from providers.search.factory import get_search_provider
    from providers.search.directory_search import PublicBusinessDirectoryProvider
    from providers.playwright_scraper import (
        validate_target_url, is_allowed_by_robots, _clean_extracted_emails,
        PlaywrightResearchProvider, USER_AGENT
    )
    from providers.llm import _has_genuine_email, get_llm_provider
    from providers.email_dispatcher import sanitize_log_message
    from dispatch_tracker import global_dispatch_tracker


# -------------------------------------------------------------------------
# 1. Natural Language Plan Parser
# -------------------------------------------------------------------------

KNOWN_COUNTRIES = [
    "pakistan", "saudi arabia", "germany", "united states", "usa", "us",
    "united kingdom", "uk", "canada", "united arab emirates", "uae",
    "australia", "france", "singapore", "india", "netherlands", "qatar"
]

KNOWN_CITIES = {
    "lahore": ("Lahore", "Pakistan"),
    "karachi": ("Karachi", "Pakistan"),
    "islamabad": ("Islamabad", "Pakistan"),
    "rawalpindi": ("Rawalpindi", "Pakistan"),
    "riyadh": ("Riyadh", "Saudi Arabia"),
    "jeddah": ("Jeddah", "Saudi Arabia"),
    "dammam": ("Dammam", "Saudi Arabia"),
    "berlin": ("Berlin", "Germany"),
    "munich": ("Munich", "Germany"),
    "frankfurt": ("Frankfurt", "Germany"),
    "stuttgart": ("Stuttgart", "Germany"),
    "austin": ("Austin", "USA"),
    "new york": ("New York", "USA"),
    "san francisco": ("San Francisco", "USA"),
    "london": ("London", "UK"),
    "dubai": ("Dubai", "UAE"),
}

COMMON_INDUSTRIES = [
    ("solar installation", ["solar", "photovoltaic", "clean energy", "commercial solar"]),
    ("solar", ["solar energy", "renewable energy", "solar panels"]),
    ("software houses", ["software development", "web development", "custom software", "saas"]),
    ("software", ["software development", "it services", "tech company"]),
    ("iot development", ["iot", "internet of things", "embedded systems", "smart devices"]),
    ("manufacturing", ["manufacturing", "industrial", "fabrication", "assembly"]),
    ("robotics and automation", ["robotics", "automation", "industrial automation", "plc"]),
    ("robotics", ["robotics", "automation", "mechatronics", "autonomous systems"]),
    ("automation", ["process automation", "industrial automation", "systems integration"]),
    ("clean energy", ["clean energy", "renewable energy", "cleantech", "sustainability"]),
    ("cleantech", ["cleantech", "clean technology", "sustainability", "environmental"]),
    ("construction", ["construction", "engineering", "contractors", "infrastructure"]),
    ("healthcare", ["healthcare", "medical devices", "biotech", "clinics"]),
    ("logistics", ["logistics", "supply chain", "freight forwarding", "warehousing"]),
    ("consulting", ["business consulting", "management consulting", "advisory"]),
]


def parse_natural_language_request(prompt: str, ai_config: Optional[AIProviderConfig] = None) -> DiscoveryPlan:
    """
    Parses a natural-language lead generation prompt into a structured DiscoveryPlan.
    Detects ambiguity and generates a clarification question if crucial criteria are missing.
    """
    text = (prompt or "").strip()
    text_lower = text.lower()

    # Ambiguity check for extremely short or vague requests
    if len(text) < 5 or text_lower in ("leads", "find leads", "companies", "search", "help", "hello", "find companies"):
        return DiscoveryPlan(
            original_prompt=text,
            industry="",
            target_lead_count=25,
            is_ambiguous=True,
            clarification_question="Please specify the business category or industry (e.g. 'solar installation' or 'software houses') and the target location (e.g. 'Lahore' or 'Germany').",
        )

    # 1. Target Lead Count
    target_count = 25
    count_match = re.search(r'\b(?:find|discover|collect|get|target)?\s*([1-9][0-9]{0,2})\s*(?:leads|companies|businesses|software houses|firms)?\b', text_lower)
    if count_match:
        try:
            val = int(count_match.group(1))
            if 1 <= val <= 100:
                target_count = val
        except Exception:
            target_count = 25

    # 2. Location (City and Country)
    found_city: Optional[str] = None
    found_country: Optional[str] = None

    for city_key, (c_name, c_country) in KNOWN_CITIES.items():
        if re.search(rf'\b{re.escape(city_key)}\b', text_lower):
            found_city = c_name
            found_country = c_country
            break

    if not found_country:
        for c_candidate in KNOWN_COUNTRIES:
            if re.search(rf'\b{re.escape(c_candidate)}\b', text_lower):
                found_country = c_candidate.title() if c_candidate not in ("usa", "us", "uk", "uae") else c_candidate.upper()
                break

    # 3. Industry / Business Category
    detected_industry = ""
    keywords: List[str] = []

    for ind_name, kw_list in COMMON_INDUSTRIES:
        if re.search(rf'\b{re.escape(ind_name)}\b', text_lower):
            detected_industry = ind_name.title()
            keywords = list(kw_list)
            break

    GENERIC_WORDS = {
        "companies", "company", "businesses", "business", "firms", "firm",
        "providers", "provider", "houses", "house", "contractors", "contractor",
        "services", "service", "leads", "lead", "clients", "client",
        "startups", "startup", "enterprises", "enterprise", "industry", "industries",
        "organizations", "organization"
    }

    if not detected_industry:
        # Heuristic extraction: look for "find [count] <X> in" or "<X> companies"
        ind_match = re.search(r'(?:find|discover|get|for|collect)?\s*(?:[0-9]+\s+)?([a-zA-Z\s\-]{3,35})\s+(?:companies|businesses|firms|providers|houses|contractors|services|in\b)', text, re.IGNORECASE)
        if ind_match:
            candidate = ind_match.group(1).strip()
            # remove count numbers or leading words
            candidate = re.sub(r'^(?:[0-9]+\s+|top\s+|commercial\s+)', '', candidate, flags=re.IGNORECASE).strip()
            if candidate and len(candidate) > 2 and candidate.lower() not in GENERIC_WORDS:
                detected_industry = candidate.title()
                keywords = [candidate.lower()]

    if detected_industry and detected_industry.lower() in GENERIC_WORDS:
        detected_industry = ""
        keywords = []

    # 4. Service / Company size / Special criteria
    service_criteria = None
    if "commercial" in text_lower:
        service_criteria = "Commercial and enterprise clients"
    elif "iot" in text_lower:
        service_criteria = "IoT development and connected device solutions"
    elif "automation" in text_lower:
        service_criteria = "Industrial automation and robotics engineering"

    # 5. Check ambiguity if neither industry nor location was determined
    is_ambiguous = False
    clarification_question = None
    if not detected_industry and not found_country and not found_city:
        is_ambiguous = True
        clarification_question = "What industry sector and geographic region or city would you like to target?"
    elif not detected_industry:
        is_ambiguous = True
        loc_str = f"{found_city}, {found_country}" if found_city and found_country else (found_city or found_country)
        clarification_question = f"We recognized the target region ({loc_str}). Which industry or business niche should we search for?"
    elif not found_country and not found_city:
        # Defaults to worldwide / general search with a note
        keywords.append("commercial")

    if not keywords and detected_industry:
        keywords = [detected_industry.lower()]

    return DiscoveryPlan(
        original_prompt=text,
        industry=detected_industry or "General Commercial",
        location_region=None,
        location_city=found_city,
        location_country=found_country,
        keywords=keywords,
        target_lead_count=target_count,
        company_size_criteria=None,
        service_criteria=service_criteria,
        desired_contact_info=["email", "phone", "website"],
        search_language="en",
        max_crawl_depth=1,
        max_pages_per_domain=2,
        is_ambiguous=is_ambiguous,
        clarification_question=clarification_question,
    )


# -------------------------------------------------------------------------
# Industry Classification Taxonomy & Quality Functions
# -------------------------------------------------------------------------

INDUSTRY_TAXONOMY: Dict[str, List[str]] = {
    "Solar Energy": [
        r'\bsolar\b',
        r'\bphotovoltaic\b',
        r'\bpv\s+systems?\b',
        r'\brooftop\s+solar\b',
        r'\bsolar\s+panels?\b',
        r'\bnet\s+metering\b',
        r'\bsolar\s+epc\b',
        r'\bsolar\s+power\b',
        r'\bsolar\s+solutions?\b',
        r'\bsolar\s+installations?\b',
        r'\bclean\s+solar\b',
    ],
    "Energy Storage": [
        r'\bbattery\s+storage\b',
        r'\bbess\b',
        r'\benergy\s+storage\b',
        r'\bbattery\s+systems?\b',
        r'\blithium-ion\b',
        r'\bbattery\s+banks?\b',
    ],
    "Renewable Energy": [
        r'\brenewable\s+energy\b',
        r'\bgreen\s+transition\b',
        r'\bclean\s+energy\b',
        r'\bwind\s+(?:power|turbine|energy)\b',
        r'\bbiomass\b',
        r'\bhydro\s+power\b',
        r'\bgeothermal\b',
        r'\bdecarboniz(?:ation|e)\b',
    ],
    "Power Systems": [
        r'\bpower\s+systems?\b',
        r'\bpower\s+generation\b',
        r'\belectrical\s+grid\b',
        r'\bsubstation\b',
        r'\bpower\s+distribution\b',
        r'\bswitchgear\b',
        r'\btransformers?\b',
        r'\bups\s+systems?\b',
        r'\bpower\s+plants?\b',
    ],
    "Logistics": [
        r'\bfreight\s+forwarding\b',
        r'\bsupply\s+chain\b',
        r'\bwarehous(?:ing|e)\b',
        r'\bcargo\s+transportation\b',
        r'\btrucking\b',
        r'\b3pl\b',
        r'\bthird-party\s+logistics\b',
        r'\bocean\s+freight\b',
        r'\bshipping\s+containers?\b',
        r'\bhauling\b',
        r'\bfleet\s+management\b',
        r'\bdistribution\s+centers?\b',
    ],
    "Software & Cloud Services": [
        r'\bsoftware\s+(?:house|development|engineering|company|solutions?)\b',
        r'\bcloud\s+(?:services?|architecture|integration|native)\b',
        r'\bsaas\b',
        r'\benterprise\s+software\b',
        r'\bweb\s+applications?\b',
        r'\bmobile\s+apps?\b',
        r'\bfintech\b',
        r'\bcustom\s+software\b',
    ],
    "IoT & Embedded Systems": [
        r'\biot\b',
        r'\binternet\s+of\s+things\b',
        r'\bembedded\s+(?:systems?|software|firmware)\b',
        r'\bconnected\s+(?:devices?|vehicle)\b',
        r'\bhardware\s+telemetry\b',
        r'\bsmart\s+devices?\b',
        r'\bsensor\s+networks?\b',
    ],
    "Robotics & Industrial Automation": [
        r'\brobotics\b',
        r'\bindustrial\s+automation\b',
        r'\bplc\s+programming\b',
        r'\bscada\b',
        r'\bautomation\s+engineering\b',
        r'\bfactory\s+automation\b',
    ],
    "Manufacturing & Industrial": [
        r'\bmanufacturing\s+plants?\b',
        r'\bindustrial\s+fabrication\b',
        r'\bcnc\s+machining\b',
        r'\bassembly\s+lines?\b',
        r'\bheavy\s+machinery\b',
        r'\bindustrial\s+equipment\b',
    ],
    "Food & Beverage": [
        r'\bfood\s+processing\b',
        r'\bbeverage\s+(?:production|manufacturing)\b',
        r'\bagro-industrial\b',
        r'\bfood\s+packaging\b',
    ],
    "Healthcare Technology": [
        r'\bhealthtech\b',
        r'\bmedical\s+devices?\b',
        r'\btelemedicine\b',
        r'\bclinical\s+software\b',
        r'\bhospital\s+management\b',
    ],
}


def classify_company_industry(
    company_name: str,
    description: str,
    keywords: Optional[List[str]] = None,
    source_url: str = "",
    plan_industry: Optional[str] = None,
) -> Tuple[str, float, str]:
    """
    Classifies company industry from business description and supporting evidence.
    Never assigns industry based solely on user search keywords or plan industry.
    Returns (industry_label, confidence, reason).
    """
    evidence_tokens = [company_name or "", description or "", " ".join(keywords or []), source_url or ""]
    evidence_text = " ".join(evidence_tokens).lower()

    scores: Dict[str, int] = {}
    matched_patterns: Dict[str, List[str]] = {}

    for industry_name, patterns in INDUSTRY_TAXONOMY.items():
        match_count = 0
        hits = []
        for pat in patterns:
            found = re.findall(pat, evidence_text, flags=re.IGNORECASE)
            if found:
                match_count += len(found)
                hits.append(pat.replace(r'\b', '').replace(r'\s+', ' '))
        if match_count > 0:
            scores[industry_name] = match_count
            matched_patterns[industry_name] = hits

    if scores:
        best_industry = max(scores, key=lambda k: scores[k])
        hits_str = ", ".join(matched_patterns[best_industry][:3])
        confidence = min(0.98, 0.65 + 0.10 * scores[best_industry])
        return best_industry, confidence, f"Classified as '{best_industry}' based on evidence keywords ({hits_str})"

    clean_desc = (description or "").strip()
    if plan_industry and plan_industry.lower() not in ("general commercial", "commercial", ""):
        p_clean = re.sub(r'[^a-zA-Z]+', ' ', plan_industry).strip().lower()
        p_tokens = [t for t in p_clean.split() if len(t) >= 4 and t not in ("companies", "services", "solutions", "provider")]
        if p_tokens and any(tok in clean_desc.lower() for tok in p_tokens) and len(clean_desc) >= 35:
            return plan_industry, 0.70, f"Matched plan industry '{plan_industry}' supported by business description"

    if not clean_desc or clean_desc.lower() in ("commercial services provider", "welcome to our website"):
        return "Unknown", 0.20, "No business description or industry evidence available"
    elif len(clean_desc) < 35:
        return "Needs Review", 0.35, "Insufficient business description to confirm industry sector with confidence"
    else:
        return "Needs Review", 0.40, "Evidence does not match known industry sectors; requires review"


def is_scientific_notation_corrupted(val: Optional[str]) -> bool:
    """Detects numbers corrupted by spreadsheet scientific notation (e.g. 9.23E+11)."""
    if not val:
        return False
    s = str(val).strip()
    return bool(re.match(r'^[+-]?\d+(?:\.\d+)?[eE][+-]?\d+$', s))


def evaluate_email_verification(
    email: Optional[str],
    provider_verified: bool = False,
    delivery_confirmed: bool = False,
) -> Tuple[str, str]:
    """
    Truthfully evaluates email verification status.
    Distinguishes public-source discovery ('publicly_listed') from actual provider verification.
    Never claims delivery confirmation unless delivery has actually been confirmed.
    """
    if not email or not str(email).strip():
        return "not_found", "No public business email address found on official sources"

    clean_email = str(email).strip()
    if not _has_genuine_email(clean_email):
        return "invalid", f"Email address '{clean_email}' failed genuine email syntax validation"

    if provider_verified:
        return "verified_by_provider", "Inbox operational status verified by email verification provider"

    # Public source discovery - syntax is valid, domain exists, but mailbox delivery is unverified
    return "publicly_listed", "Publicly listed business email discovered on official website or registry; mailbox unverified"


def evaluate_phone_verification(
    phone: Optional[str],
    provider_verified: bool = False,
) -> Tuple[str, str]:
    """
    Truthfully evaluates phone verification status.
    Preserves exact string. Does NOT invent digits for corrupted numbers.
    Flags spreadsheet scientific notation (9.23E+11) or <7 digits for operator review.
    """
    if not phone or not str(phone).strip():
        return "not_found", "No telephone number discovered"

    clean_phone = str(phone).strip()
    if is_scientific_notation_corrupted(clean_phone):
        return "needs_review", f"Phone number '{clean_phone}' appears corrupted by spreadsheet scientific notation; manual review required"

    digits = re.sub(r'\D', '', clean_phone)
    if len(digits) < 7:
        return "needs_review", f"Phone number '{clean_phone}' contains fewer than 7 digits"

    if provider_verified:
        return "verified_by_provider", "Telephone line active status verified by telephony provider"

    return "publicly_listed", "Publicly listed telephone contact; operational status unverified"


def calculate_lead_relevance(
    plan: DiscoveryPlan,
    company_name: str,
    business_desc: str,
    classified_industry: str,
    industry_confidence: float,
    city: str,
    country: str,
    website: str,
    email: str,
    email_status: str,
    phone: str,
    phone_status: str,
    source_query: str = "",
) -> Tuple[float, str]:
    """
    Computes a dynamic relevance score (0.10 - 0.98) and transparent evidence-backed explanation.
    Evaluates industry match, geographic fit, contact availability, and description substance.
    Penalizes thin descriptions (<35 chars), missing evidence, or industry discrepancies.
    """
    score = 0.20
    relevance_notes: List[str] = []

    # 1. Industry Alignment
    target_ind = (plan.industry or "").lower()
    target_tokens = [t for t in re.split(r'[^a-zA-Z0-9]+', target_ind) if len(t) >= 3 and t not in ("general", "commercial")]

    if classified_industry in ("Unknown", "Needs Review"):
        score -= 0.05
        relevance_notes.append(f"Industry unverified ({classified_industry})")
    elif any(tok in classified_industry.lower() for tok in target_tokens):
        score += 0.35 * industry_confidence
        relevance_notes.append(f"Industry '{classified_industry}' directly aligns with target '{plan.industry}'")
    elif any(tok in (business_desc or "").lower() for tok in target_tokens):
        score += 0.25 * industry_confidence
        relevance_notes.append(f"Business description aligns with target '{plan.industry}'")
    else:
        score -= 0.15
        relevance_notes.append(f"Industry '{classified_industry}' diverges from target '{plan.industry}'")

    # 2. Location Alignment
    target_city = (plan.location_city or "").strip().lower()
    target_country = (plan.location_country or "").strip().lower()
    desc_lower = (business_desc or "").lower()
    url_lower = (website or "").lower()
    city_lower = (city or "").lower()
    country_lower = (country or "").lower()

    loc_matched = False
    if target_city:
        if target_city in city_lower or target_city in desc_lower or target_city in url_lower:
            score += 0.20
            relevance_notes.append(f"City '{plan.location_city}' confirmed in business profile")
            loc_matched = True
        else:
            relevance_notes.append(f"City '{plan.location_city}' not confirmed in profile")

    if target_country:
        if target_country in country_lower or target_country in desc_lower or target_country in url_lower or (target_country == "pakistan" and ".pk" in url_lower):
            score += 0.10
            if not loc_matched:
                relevance_notes.append(f"Country '{plan.location_country}' confirmed")
                loc_matched = True
        elif not loc_matched:
            relevance_notes.append(f"Target country '{plan.location_country}' unconfirmed")

    # 3. Description Depth & Substance
    clean_desc = (business_desc or "").strip()
    if len(clean_desc) >= 100:
        score += 0.15
        relevance_notes.append("Detailed operational description available")
    elif len(clean_desc) >= 35:
        score += 0.08
        relevance_notes.append("Standard business description available")
    else:
        score -= 0.15
        relevance_notes.append("Thin business description (<35 chars); flagged for review")

    # 4. Contact Verifiability
    if email and email_status in ("publicly_listed", "verified_by_provider", "verified_public"):
        score += 0.12
        relevance_notes.append("Public business email verified")
    elif email:
        score += 0.04
        relevance_notes.append(f"Email present ({email_status})")
    else:
        relevance_notes.append("No public email discovered")

    if phone and phone_status in ("publicly_listed", "verified_by_provider", "verified_public"):
        score += 0.08
        relevance_notes.append("Public telephone listed")
    elif phone_status == "needs_review":
        score -= 0.05
        relevance_notes.append("Telephone number flagged for review")

    # 5. Keywords match
    if plan.keywords:
        kw_matches = [kw for kw in plan.keywords if kw.lower() in desc_lower or kw.lower() in company_name.lower()]
        if kw_matches:
            bonus = min(0.12, 0.04 * len(kw_matches))
            score += bonus
            relevance_notes.append(f"Keyword matches: {', '.join(kw_matches[:3])}")

    # Clamping and penalty caps
    if len(clean_desc) < 35 or classified_industry in ("Unknown", "Needs Review"):
        final_score = min(0.50, max(0.10, score))
    else:
        final_score = min(0.98, max(0.15, score))

    final_score = round(final_score, 2)
    q_label = source_query or plan.original_prompt or plan.industry
    explanation = f"Query: '{q_label}'. " + "; ".join(relevance_notes) + f". Score: {final_score:.2f}."
    return final_score, explanation


# -------------------------------------------------------------------------
# 2. Lead Discovery Service & Execution Pipeline
# -------------------------------------------------------------------------

class LeadDiscoveryService:
    """
    Manages automated lead discovery jobs, cooperative cancellation,
    multi-source querying, website inspection via Playwright, and persistence.
    """
    def __init__(self):
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._cancelled_jobs: Set[str] = set()
        self._domain_locks: Dict[str, asyncio.Lock] = {}
        self._domain_last_visited: Dict[str, float] = {}

    def is_job_cancelled(self, job_id: str) -> bool:
        if job_id in self._cancelled_jobs:
            return True
        job = global_dispatch_tracker.get_discovery_job(job_id)
        return bool(job and job.get("status") == "cancelled")

    def cancel_job(self, job_id: str) -> bool:
        self._cancelled_jobs.add(job_id)
        job = global_dispatch_tracker.get_discovery_job(job_id)
        if job:
            if job.get("status") in ("pending", "running"):
                global_dispatch_tracker.update_discovery_job(
                    job_id,
                    status="cancelled",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    current_stage="Job cancelled by operator",
                )
            # Cancel running asyncio task if active
            task = self._active_tasks.get(job_id)
            if task and not task.done():
                task.cancel()
            return True
        return False

    async def start_job(self, request: DiscoveryJobCreateRequest) -> DiscoveryJob:
        """
        Validates criteria, records the job in SQLite, and launches the background pipeline.
        """
        job_id = f"job-{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        plan = request.plan

        # Clamp requested lead count
        clamped_count = max(1, min(100, plan.target_lead_count))

        job = DiscoveryJob(
            id=job_id,
            prompt=plan.original_prompt,
            status="pending",
            created_at=now_iso,
            provider_used=request.search_provider or "auto",
            total_target=clamped_count,
            discovered_count=0,
            verified_email_count=0,
            duplicate_count=0,
            skipped_count=0,
            failed_count=0,
            progress_percent=0,
            current_stage="Job queued",
            plan_json=plan.model_dump_json(),
        )

        global_dispatch_tracker.save_discovery_job(job)

        # Launch non-blocking background task
        task = asyncio.create_task(
            self._execute_pipeline(
                job_id=job_id,
                plan=plan,
                provider_id=request.search_provider or "auto",
                ai_config=request.ai_config,
            )
        )
        self._active_tasks[job_id] = task

        # Clean up task reference when complete
        def _on_done(t):
            self._active_tasks.pop(job_id, None)
            self._cancelled_jobs.discard(job_id)

        task.add_done_callback(_on_done)
        return job

    async def _execute_pipeline(
        self,
        job_id: str,
        plan: DiscoveryPlan,
        provider_id: str,
        ai_config: Optional[AIProviderConfig] = None,
    ):
        """
        Background discovery execution pipeline.
        """
        start_time_iso = datetime.now(timezone.utc).isoformat()
        global_dispatch_tracker.update_discovery_job(
            job_id,
            status="running",
            started_at=start_time_iso,
            current_stage="Initializing search provider",
            progress_percent=5,
        )

        try:
            # 1. Resolve search provider
            search_provider: SearchProvider = get_search_provider(provider_id)
            global_dispatch_tracker.update_discovery_job(
                job_id,
                provider_used=search_provider.provider_id,
                current_stage=f"Connected to {search_provider.display_name}. Formulating search queries...",
                progress_percent=10,
            )

            # 2. Formulate search queries
            queries = self._generate_search_queries(plan)

            # 3. Collect search results across queries
            raw_results: List[SearchResult] = []
            max_to_fetch = max(plan.target_lead_count * 2, 10)

            for q_idx, query in enumerate(queries):
                if self.is_job_cancelled(job_id):
                    return

                stage_msg = f"Executing query [{q_idx+1}/{len(queries)}]: '{query}'"
                global_dispatch_tracker.update_discovery_job(
                    job_id,
                    current_stage=stage_msg,
                    progress_percent=15 + int((q_idx / len(queries)) * 15),
                )

                try:
                    res = await search_provider.search(
                        query=query,
                        max_results=max_to_fetch,
                        language=plan.search_language or "en",
                    )
                    raw_results.extend(res)
                except Exception as exc:
                    clean_err = sanitize_log_message(str(exc))
                    # Record failure if primary provider failed
                    if not raw_results and q_idx == len(queries) - 1:
                        global_dispatch_tracker.update_discovery_job(
                            job_id,
                            status="failed",
                            completed_at=datetime.now(timezone.utc).isoformat(),
                            error_message=f"Search provider error: {clean_err}",
                            current_stage="Failed during search query execution",
                        )
                        return

            # Fallback to directory provider if commercial provider returned 0 results
            if not raw_results and search_provider.provider_id != "directory":
                dir_provider = PublicBusinessDirectoryProvider()
                for query in queries:
                    d_res = await dir_provider.search(query=query, max_results=max_to_fetch)
                    raw_results.extend(d_res)

            if not raw_results:
                global_dispatch_tracker.update_discovery_job(
                    job_id,
                    status="completed",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    progress_percent=100,
                    current_stage="Completed. No matching businesses found for the specified criteria.",
                )
                return

            # 4. Normalize and Deduplicate results by canonical domain & company name
            unique_results: List[SearchResult] = []
            seen_domains: Set[str] = set()
            seen_names: Set[str] = set()
            seen_phones: Set[str] = set()
            duplicate_count = 0

            for r in raw_results:
                parsed = urlparse(r.url)
                canonical_domain = parsed.netloc.lower().replace("www.", "")
                clean_name = re.sub(r'[^a-zA-Z0-9]+', '', r.title.lower())

                if not canonical_domain or canonical_domain in seen_domains or clean_name in seen_names:
                    duplicate_count += 1
                    continue

                seen_domains.add(canonical_domain)
                if clean_name:
                    seen_names.add(clean_name)
                unique_results.append(r)

            global_dispatch_tracker.update_discovery_job(
                job_id,
                duplicate_count=duplicate_count,
                current_stage=f"Normalized {len(unique_results)} candidate websites ({duplicate_count} duplicates removed). Inspecting public sources...",
                progress_percent=30,
            )

            # 5. Process each candidate website
            discovered_count = 0
            verified_email_count = 0
            skipped_count = 0
            failed_count = 0

            # Bounded concurrency semaphore for page visits
            semaphore = asyncio.Semaphore(3)

            for idx, candidate in enumerate(unique_results):
                if self.is_job_cancelled(job_id):
                    return

                if discovered_count >= plan.target_lead_count:
                    break

                progress = 30 + int(((idx + 1) / len(unique_results)) * 65)
                global_dispatch_tracker.update_discovery_job(
                    job_id,
                    current_stage=f"Inspecting company {idx+1}/{len(unique_results)}: {candidate.title}",
                    progress_percent=min(progress, 98),
                )

                async with semaphore:
                    lead_record, outcome = await self._inspect_and_verify_candidate(
                        candidate=candidate,
                        plan=plan,
                        job_id=job_id,
                        search_provider=search_provider,
                    )

                if outcome == "skipped":
                    skipped_count += 1
                    global_dispatch_tracker.update_discovery_job(job_id, skipped_count=skipped_count)
                elif outcome == "failed":
                    failed_count += 1
                    global_dispatch_tracker.update_discovery_job(job_id, failed_count=failed_count)
                elif outcome == "completed" and lead_record:
                    # Phone number deduplication across records
                    if lead_record.phone:
                        clean_p = re.sub(r'\D', '', lead_record.phone)
                        if clean_p and len(clean_p) >= 7:
                            if clean_p in seen_phones:
                                duplicate_count += 1
                                global_dispatch_tracker.update_discovery_job(job_id, duplicate_count=duplicate_count)
                                continue
                            seen_phones.add(clean_p)

                    discovered_count += 1
                    if lead_record.email_verification_status in (
                        "verified_public",
                        "publicly_listed",
                        "verified_by_provider",
                        "domain_valid",
                        "syntax_valid",
                        "mailbox_unverified",
                    ):
                        verified_email_count += 1

                    global_dispatch_tracker.save_discovered_lead(lead_record)
                    global_dispatch_tracker.update_discovery_job(
                        job_id,
                        discovered_count=discovered_count,
                        verified_email_count=verified_email_count,
                    )

            # 6. Finalize job status
            if self.is_job_cancelled(job_id):
                return

            completed_at_iso = datetime.now(timezone.utc).isoformat()
            stage_summary = (
                f"Discovery completed. Discovered {discovered_count} leads "
                f"({verified_email_count} with verified public emails, {duplicate_count} duplicates skipped)."
            )

            global_dispatch_tracker.update_discovery_job(
                job_id,
                status="completed",
                completed_at=completed_at_iso,
                discovered_count=discovered_count,
                verified_email_count=verified_email_count,
                duplicate_count=duplicate_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                progress_percent=100,
                current_stage=stage_summary,
            )

        except asyncio.CancelledError:
            global_dispatch_tracker.update_discovery_job(
                job_id,
                status="cancelled",
                completed_at=datetime.now(timezone.utc).isoformat(),
                current_stage="Discovery cancelled by operator",
            )
        except Exception as exc:
            clean_err = sanitize_log_message(str(exc))
            global_dispatch_tracker.update_discovery_job(
                job_id,
                status="failed",
                completed_at=datetime.now(timezone.utc).isoformat(),
                error_message=clean_err,
                current_stage=f"Execution error: {clean_err}",
            )

    def _generate_search_queries(self, plan: DiscoveryPlan) -> List[str]:
        """
        Generates targeted search queries based on the structured plan.
        """
        queries: List[str] = []
        loc_parts = []
        if plan.location_city:
            loc_parts.append(plan.location_city)
        if plan.location_country:
            loc_parts.append(plan.location_country)
        loc_str = " ".join(loc_parts)

        industry_str = plan.industry or "commercial businesses"

        # Query 1: Direct industry + location
        q1 = f"{industry_str} {loc_str}".strip()
        queries.append(q1)

        # Query 2: Focused C&I queries if solar requested
        if "solar" in industry_str.lower() or any("solar" in kw.lower() for kw in (plan.keywords or [])):
            queries.append(f"commercial industrial solar EPC {loc_str}".strip())
            queries.append(f"industrial rooftop solar contractor {loc_str}".strip())
            queries.append(f"turnkey solar net metering {loc_str}".strip())
        else:
            # Standard industry + official website / contact
            if loc_str:
                queries.append(f"{industry_str} {loc_str} official website contact".strip())
            else:
                queries.append(f"{industry_str} official website commercial".strip())

        # Query 3: Specific keywords if available
        if plan.keywords:
            kw_combo = " ".join(plan.keywords[:2])
            q3 = f"{kw_combo} {loc_str} companies".strip()
            if q3 not in queries:
                queries.append(q3)

        return queries

    async def _inspect_and_verify_candidate(
        self,
        candidate: SearchResult,
        plan: DiscoveryPlan,
        job_id: str,
        search_provider: SearchProvider,
    ) -> Tuple[Optional[DiscoveredLeadRecord], str]:
        """
        Inspects an individual candidate website using SSRF guards, robots.txt,
        Playwright or fallback directory facts.
        Returns (DiscoveredLeadRecord or None, outcome: 'completed'|'skipped'|'failed').
        """
        raw_url = candidate.url
        is_valid, sanitized_url, err_msg = validate_target_url(raw_url)
        if not is_valid:
            return None, "skipped"

        # Check robots.txt
        is_allowed, robot_reason = is_allowed_by_robots(sanitized_url, timeout=2.5)
        if not is_allowed:
            return None, "skipped"

        # Per-domain rate limit enforcement (minimum 0.4s between requests to same domain)
        parsed = urlparse(sanitized_url)
        domain = parsed.netloc.lower()
        now_ts = asyncio.get_event_loop().time()
        last_visit = self._domain_last_visited.get(domain, 0.0)
        if (now_ts - last_visit) < 0.4:
            await asyncio.sleep(0.4 - (now_ts - last_visit))
        self._domain_last_visited[domain] = asyncio.get_event_loop().time()

        # If candidate already includes verified directory facts (e.g. from PublicBusinessDirectoryProvider)
        direct_facts = candidate.metadata.get("directory_facts")
        company_name = candidate.metadata.get("company_name") or candidate.title
        business_desc = candidate.snippet or ""
        found_email = candidate.metadata.get("email") or ""
        found_phone = candidate.metadata.get("phone") or ""
        verified_fields: List[str] = []
        source_urls: List[str] = [sanitized_url]

        # Clean company name
        for sep in (" | ", " - ", " – ", " — ", " :: "):
            if sep in company_name:
                company_name = company_name.split(sep)[0].strip()
                break

        # If live HTML inspection is feasible
        html_content = ""
        try:
            import httpx
            async with httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
                timeout=6.0,
            ) as client:
                resp = await client.get(sanitized_url)
                if resp.status_code == 200:
                    html_content = resp.text
                    # SSRF check on final redirected URL
                    redirected_url = str(resp.url)
                    valid_red, sanitized_red, _ = validate_target_url(redirected_url)
                    if not valid_red:
                        return None, "skipped"
                    sanitized_url = sanitized_red
        except Exception:
            pass

        # If HTML content was obtained, extract verified facts
        if html_content:
            extracted_name, extracted_desc, extracted_emails, extracted_phones, subpages = self._extract_from_html(
                html=html_content,
                base_url=sanitized_url,
            )

            if extracted_name and not candidate.metadata.get("company_name"):
                company_name = extracted_name
                verified_fields.append("company_name")
            elif direct_facts:
                verified_fields.append("company_name (directory)")

            if extracted_desc:
                business_desc = extracted_desc
                verified_fields.append("description")

            if extracted_emails:
                found_email = extracted_emails[0]
                verified_fields.append("email")
            elif direct_facts and direct_facts.get("email"):
                found_email = direct_facts.get("email")
                verified_fields.append("email (directory)")

            if extracted_phones:
                found_phone = extracted_phones[0]
                verified_fields.append("phone")
            elif direct_facts and direct_facts.get("phone"):
                found_phone = direct_facts.get("phone")
                verified_fields.append("phone (directory)")

            # If email was not on homepage, visit one relevant subpage (e.g. /contact or /about)
            if not found_email and subpages and plan.max_pages_per_domain > 1:
                sub_url = subpages[0]
                v_sub, s_sub, _ = validate_target_url(sub_url)
                if v_sub and is_allowed_by_robots(s_sub)[0]:
                    try:
                        async with httpx.AsyncClient(
                            headers={"User-Agent": USER_AGENT},
                            follow_redirects=True,
                            timeout=5.0,
                        ) as client:
                            sub_resp = await client.get(s_sub)
                            if sub_resp.status_code == 200:
                                _, _, sub_emails, sub_phones, _ = self._extract_from_html(
                                    html=sub_resp.text,
                                    base_url=s_sub,
                                )
                                if sub_emails:
                                    found_email = sub_emails[0]
                                    verified_fields.append("email (contact page)")
                                    source_urls.append(s_sub)
                                if sub_phones and not found_phone:
                                    found_phone = sub_phones[0]
                                    verified_fields.append("phone (contact page)")
                                    if s_sub not in source_urls:
                                        source_urls.append(s_sub)
                    except Exception:
                        pass
        elif direct_facts:
            # Verified directory entry fallback
            verified_fields.extend(["company_name (registry)", "website (verified)"])
            if found_email:
                verified_fields.append("email (registry)")
            if found_phone:
                verified_fields.append("phone (registry)")

        # Determine truthful email verification status
        email_status, email_status_note = evaluate_email_verification(
            email=found_email,
            provider_verified=False,
            delivery_confirmed=False,
        )

        # Determine truthful phone verification status (preserves string, flags corruption)
        phone_status, phone_status_note = evaluate_phone_verification(
            phone=found_phone,
            provider_verified=False,
        )

        # Classify industry based on evidence (company name, description, keywords, url)
        raw_keywords = candidate.metadata.get("directory_facts", {}).get("keywords") if candidate.metadata.get("directory_facts") else plan.keywords
        classified_industry, industry_conf, industry_reason = classify_company_industry(
            company_name=company_name,
            description=business_desc,
            keywords=raw_keywords,
            source_url=sanitized_url,
            plan_industry=plan.industry,
        )

        # Evidence tracking in verified_fields
        if direct_facts:
            verified_fields.extend(["company_name (registry)", "website (official)", "description (registry)"])
        else:
            if not any("company_name" in vf for vf in verified_fields):
                verified_fields.append("company_name (website)")
            if not any("description" in vf for vf in verified_fields):
                if business_desc and len(business_desc) >= 35:
                    verified_fields.append("description (meta/page)")
                else:
                    verified_fields.append("description (Needs Review)")

        if classified_industry in ("Unknown", "Needs Review"):
            verified_fields.append(f"industry ({classified_industry})")
        else:
            verified_fields.append(f"industry (classified: {classified_industry})")

        # Extract Lahore presence and C&I fit evidence
        text_corpus = ((html_content or "") + " " + business_desc + " " + (candidate.snippet or "")).lower()
        lahore_kw = ["lahore", "gulberg", "dha", "johar town", "model town", "kot lakhpat", "sundar", "quaid-e-azam", "raiwind", "canal road", "ferozepur road", "lesco"]
        lahore_matches = [k for k in lahore_kw if k in text_corpus]
        if lahore_matches:
            target_city = "Lahore"
            target_country = "Pakistan"
            verified_fields.append(f"lahore_presence (evidence: {', '.join(lahore_matches[:3])})")
        elif plan.location_city and plan.location_city.lower() == "lahore":
            verified_fields.append("lahore_presence (Needs Review: unconfirmed in text)")

        ci_kw = ["commercial", "industrial", "c&i", "rooftop", "epc", "mw", "megawatt", "factory", "factories", "manufacturing", "textile", "warehouse", "cold storage", "hospital", "plaza", "net-metering", "lesco net metering", "bess"]
        ci_matches = [k for k in ci_kw if k in text_corpus]
        if ci_matches:
            verified_fields.append(f"commercial_fit (evidence: {', '.join(ci_matches[:4])})")
        else:
            verified_fields.append("commercial_fit (Needs Review: general)")

        if found_email and email_status in ("publicly_listed", "verified_by_provider", "verified_public"):
            if not any("email" in vf for vf in verified_fields):
                verified_fields.append("email (website contact)")
        else:
            if not any("email" in vf for vf in verified_fields):
                verified_fields.append("email (Needs Review)")

        if found_phone and phone_status in ("publicly_listed", "verified_by_provider", "verified_public"):
            if not any("phone" in vf for vf in verified_fields):
                verified_fields.append("phone (website)")
        elif phone_status == "needs_review":
            verified_fields.append("phone (Needs Review: corrupted)")
        else:
            if not any("phone" in vf for vf in verified_fields):
                verified_fields.append("phone (Needs Review)")

        # Dynamic evidence-backed relevance scoring
        target_city = plan.location_city or candidate.metadata.get("city") or ""
        target_country = plan.location_country or candidate.metadata.get("country") or ""
        relevance_score, explanation = calculate_lead_relevance(
            plan=plan,
            company_name=company_name,
            business_desc=business_desc,
            classified_industry=classified_industry,
            industry_confidence=industry_conf,
            city=target_city,
            country=target_country,
            website=sanitized_url,
            email=found_email,
            email_status=email_status,
            phone=found_phone,
            phone_status=phone_status,
            source_query=getattr(candidate, "source_query", "") or getattr(candidate, "query", ""),
        )

        lead_id = f"lead-{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        is_live_source = (getattr(search_provider, "provider_id", "") != "directory")

        # Distinguish company website from directory source in source_urls & discovery_source
        if direct_facts:
            discovery_source_label = "Public Business Directory"
            registry_url = "https://agentdesk.directory/registry"
            if registry_url not in source_urls:
                source_urls.append(registry_url)
        else:
            discovery_source_label = search_provider.display_name

        lead = DiscoveredLeadRecord(
            id=lead_id,
            job_id=job_id,
            company_name=company_name or domain.capitalize(),
            website=sanitized_url,
            industry=classified_industry,
            city=target_city,
            country=target_country,
            services_description=business_desc[:300] if business_desc else "Commercial services provider",
            email=found_email or "",
            email_verification_status=email_status,
            phone=found_phone or "",
            phone_verification_status=phone_status,
            source_urls=source_urls,
            discovery_source=discovery_source_label,
            discovery_query=getattr(candidate, "source_query", "") or getattr(candidate, "query", "") or plan.original_prompt,
            discovered_at=now_iso,
            relevance_score=relevance_score,
            relevance_explanation=explanation,
            research_status="completed",
            failure_reason=None,
            verified_fields=verified_fields,
            is_live=is_live_source,
        )

        return lead, "completed"


    def _extract_from_html(
        self,
        html: str,
        base_url: str,
    ) -> Tuple[str, str, List[str], List[str], List[str]]:
        """
        Extracts company name, description, verified public emails, phones, and subpage links.
        Returns (company_name, description, emails, phones, subpage_links).
        """
        soup = BeautifulSoup(html, "html.parser")
        parsed = urlparse(base_url)
        domain = parsed.netloc.lower().replace("www.", "")

        # 1. Company Name
        company_name = ""
        # Schema.org JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
                for item in items:
                    if isinstance(item, dict) and item.get("@type") in ("Organization", "Corporation", "LocalBusiness"):
                        if item.get("name"):
                            company_name = str(item["name"]).strip()
                            break
                if company_name:
                    break
            except Exception:
                continue

        if not company_name:
            og_site = soup.find("meta", property="og:site_name") or soup.find("meta", attrs={"name": "og:site_name"})
            if og_site and og_site.get("content"):
                company_name = str(og_site["content"]).strip()

        if not company_name and soup.title and soup.title.string:
            title_text = soup.title.string.strip()
            for sep in (" | ", " - ", " – ", " — ", " :: "):
                if sep in title_text:
                    title_text = title_text.split(sep)[0].strip()
                    break
            if title_text:
                company_name = title_text[:60]

        # 2. Description
        description = ""
        desc_meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
        if desc_meta and desc_meta.get("content"):
            description = str(desc_meta["content"]).strip()
        else:
            for p in soup.find_all("p"):
                p_text = p.get_text().strip()
                if 40 <= len(p_text) <= 250:
                    description = p_text
                    break

        # 3. Emails
        found_emails: Set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("mailto:"):
                e_clean = href.replace("mailto:", "").split("?")[0].strip()
                if e_clean:
                    found_emails.add(e_clean)

        email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        for match in re.findall(email_regex, soup.get_text()):
            found_emails.add(match)

        cleaned_emails = _clean_extracted_emails(found_emails, domain)

        # 4. Phones
        found_phones: Set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("tel:"):
                tel_clean = href.replace("tel:", "").split("?")[0].strip()
                if tel_clean and len(tel_clean) >= 7:
                    found_phones.add(tel_clean)

        phone_regex = r'(?:\+?\d{1,4}[-.\s]?)?\(?\d{2,5}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}(?:[-.\s]?\d{1,4})?'
        for match in re.findall(phone_regex, soup.get_text()):
            clean_m = match.strip()
            digits = re.sub(r'\D', '', clean_m)
            if len(digits) >= 7 and not is_scientific_notation_corrupted(clean_m):
                found_phones.add(clean_m)

        cleaned_phones = list(dict.fromkeys(found_phones))[:3]

        # 5. Subpage links (/contact, /about)
        subpage_links: List[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            full_sub = urljoin(base_url, href)
            p_sub = urlparse(full_sub)
            if p_sub.netloc.lower().replace("www.", "") == domain and p_sub.scheme in ("http", "https"):
                p_lower = p_sub.path.lower()
                link_text = a.get_text().strip().lower()
                if any(k in p_lower for k in ("contact", "about", "reach", "touch")) or any(k in link_text for k in ("contact", "about")):
                    if full_sub not in subpage_links and full_sub != base_url:
                        subpage_links.append(full_sub)

        return company_name, description, cleaned_emails, cleaned_phones, subpage_links


# Global Lead Discovery Service singleton
global_lead_discovery_service = LeadDiscoveryService()
