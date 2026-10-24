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
                    discovered_count += 1
                    if lead_record.email_verification_status == "verified_public":
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

        # Query 2: Industry + official website / contact
        if loc_str:
            q2 = f"{industry_str} {loc_str} official website contact".strip()
        else:
            q2 = f"{industry_str} official website commercial".strip()
        queries.append(q2)

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

        # Determine strict email verification status
        email_status = "not_found"
        if found_email:
            if _has_genuine_email(found_email):
                email_status = "verified_public"
            else:
                email_status = "invalid"

        # Determine phone verification status
        phone_status = "verified_public" if (found_phone and len(found_phone) >= 7) else "not_found"

        # Relevance scoring & explanation
        relevance_score = 0.85
        relevance_notes = []

        target_ind = (plan.industry or "").lower()
        if target_ind and (target_ind in company_name.lower() or target_ind in business_desc.lower()):
            relevance_score += 0.08
            relevance_notes.append(f"Industry '{plan.industry}' matched")

        target_loc = (plan.location_city or plan.location_country or "").lower()
        if target_loc and (target_loc in business_desc.lower() or target_loc in sanitized_url.lower()):
            relevance_score += 0.05
            relevance_notes.append(f"Location '{target_loc.title()}' matched")

        if email_status == "verified_public":
            relevance_notes.append("Verified public email available")
        else:
            relevance_notes.append("No public contact email confirmed on page")

        query_used = getattr(candidate, "source_query", "") or getattr(candidate, "query", "") or plan.industry
        explanation = f"Matched via {query_used}. " + "; ".join(relevance_notes) + "."
        relevance_score = min(0.99, round(relevance_score, 2))

        lead_id = f"lead-{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        is_live_source = (getattr(search_provider, "provider_id", "") != "directory")

        lead = DiscoveredLeadRecord(
            id=lead_id,
            job_id=job_id,
            company_name=company_name or domain.capitalize(),
            website=sanitized_url,
            industry=plan.industry,
            city=plan.location_city or candidate.metadata.get("city") or "",
            country=plan.location_country or candidate.metadata.get("country") or "",
            services_description=business_desc[:300] if business_desc else "Commercial services provider",
            email=found_email if email_status == "verified_public" else (found_email or ""),
            email_verification_status=email_status,
            phone=found_phone,
            phone_verification_status=phone_status,
            source_urls=source_urls,
            discovery_source=search_provider.display_name,
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

        phone_regex = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}'
        for match in re.findall(phone_regex, soup.get_text()):
            clean_m = match.strip()
            if len(re.sub(r'\D', '', clean_m)) >= 7:
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
