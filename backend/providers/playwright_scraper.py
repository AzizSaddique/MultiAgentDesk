"""
Playwright-based Live Public-Website Research Provider for AgentDesk.
Complies with robots.txt, respects access limitations, never fabricates records,
and records source page URLs and verified fields.
"""
import asyncio
import re
import json
import urllib.robotparser
import urllib.request
from urllib.parse import urlparse, urljoin
from typing import List, Tuple, Optional, Set, Dict, Any
from datetime import datetime, timezone
from bs4 import BeautifulSoup

try:
    from .base import BaseResearchProvider
    from ..models import ResearchRequest, LeadRecord, CrawlDiagnostic
except (ImportError, ValueError):
    from providers.base import BaseResearchProvider
    from models import ResearchRequest, LeadRecord, CrawlDiagnostic

USER_AGENT = "AgentDesk-Bot/1.0 (+https://agentdesk.local/bot; ethical-public-researcher)"

def _sanitize_slug(text: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9]+', '', text.lower())
    return cleaned[:16] if cleaned else "web"

def validate_target_url(raw_url: str) -> Tuple[bool, str, str]:
    """
    Validates user-supplied URL. Only HTTP and HTTPS are permitted.
    Internal and loopback addresses are blocked.
    Returns (is_valid, sanitized_url, error_reason).
    """
    if not raw_url or not raw_url.strip():
        return False, "", "URL is empty"
    
    cleaned = raw_url.strip()
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', cleaned):
            cleaned = "https://" + cleaned
        else:
            return False, raw_url, "URL must use HTTP or HTTPS protocol."
            
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        return False, cleaned, f"Protocol '{parsed.scheme}' not allowed. Only HTTP and HTTPS are permitted."
        
    hostname = parsed.hostname
    if not hostname:
        return False, cleaned, "URL lacks a valid hostname."

    # Guard against SSRF / local network access
    if (
        hostname in ("localhost", "127.0.0.1", "0.0.0.0")
        or hostname.startswith("192.168.")
        or hostname.startswith("10.")
        or hostname.startswith("172.16.")
    ):
        return False, cleaned, "Internal / private network URLs are restricted."

    return True, cleaned, ""

def is_allowed_by_robots(target_url: str, user_agent: str = USER_AGENT, timeout: float = 3.0) -> Tuple[bool, str]:
    """
    Checks robots.txt for the domain of the target URL.
    Returns (is_allowed, reason).
    """
    try:
        parsed = urlparse(target_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        
        req = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                content = response.read().decode('utf-8', errors='ignore')
                rp.parse(content.splitlines())
                allowed = rp.can_fetch(user_agent, target_url) or rp.can_fetch("*", target_url)
                if not allowed:
                    return False, f"Disallowed by website robots.txt rules at {robots_url}"
                return True, "Permitted by robots.txt"
    except Exception:
        # Standard convention: If robots.txt is missing or unreachable, crawling is permitted
        return True, "robots.txt not found or unrestricted"
    return True, "Permitted"

def _clean_extracted_emails(emails: Set[str], domain: str) -> List[str]:
    """
    Filters out file artifacts, common image extensions, and placeholder domains.
    """
    valid = []
    excluded_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js', '.ico')
    excluded_domains = ('example.com', 'domain.com', 'sentry.io', 'wixpress.com', 'schema.org')
    
    for email in emails:
        e = email.lower().strip()
        if any(e.endswith(ext) for ext in excluded_extensions):
            continue
        if any(ex_d in e for ex_d in excluded_domains):
            continue
        if len(e) < 6 or '@' not in e or '.' not in e.split('@')[1]:
            continue
        valid.append(email.strip())
    return list(dict.fromkeys(valid))

def extract_lead_from_html(
    html: str,
    page_url: str,
    industry: str = "",
    location: str = "",
    topic: str = "",
) -> Tuple[Optional[LeadRecord], List[str]]:
    """
    Extracts structured company metadata and contact details strictly from visible HTML elements.
    Never fabricates names, roles, emails, or company titles.
    Returns (LeadRecord or None, subpage_links).
    """
    soup = BeautifulSoup(html, "html.parser")
    parsed_url = urlparse(page_url)
    domain = parsed_url.netloc

    # Detect anti-bot challenges / CAPTCHA pages
    text_lower = soup.get_text().lower()
    challenge_tokens = [
        "enable javascript and cookies to continue",
        "just a moment...",
        "security check to access",
        "cloudflare ray id",
        "please verify you are a human",
        "access denied |",
    ]
    if any(token in text_lower for token in challenge_tokens):
        return None, []

    verified_fields: List[str] = []

    # 1. Company Name Extraction
    company_name = ""
    # Try JSON-LD Schema
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw_text = script.string or ""
            data = json.loads(raw_text)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("@graph", [data])
            else:
                items = []

            for item in items:
                if isinstance(item, dict) and item.get("@type") in ("Organization", "Corporation", "LocalBusiness"):
                    if item.get("name"):
                        company_name = str(item["name"]).strip()
                        verified_fields.append("company_name (json-ld)")
                        break
            if company_name:
                break
        except Exception:
            continue

    if not company_name:
        # Try OpenGraph site_name
        og_site = soup.find("meta", property="og:site_name") or soup.find("meta", attrs={"name": "og:site_name"})
        if og_site and og_site.get("content"):
            company_name = str(og_site["content"]).strip()
            verified_fields.append("company_name (og:site_name)")

    if not company_name:
        # Try meta application-name
        app_name = soup.find("meta", attrs={"name": "application-name"})
        if app_name and app_name.get("content"):
            company_name = str(app_name["content"]).strip()
            verified_fields.append("company_name (application-name)")

    if not company_name and soup.title and soup.title.string:
        # Clean title: "Company | Tagline" -> "Company"
        title_text = soup.title.string.strip()
        for sep in (" | ", " - ", " – ", " — ", " :: "):
            if sep in title_text:
                title_text = title_text.split(sep)[0].strip()
                break
        if title_text:
            company_name = title_text[:70]
            verified_fields.append("company_name (title)")

    if not company_name:
        company_name = domain.replace("www.", "").capitalize()

    # 2. Public Business Description
    description = ""
    desc_meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
    if desc_meta and desc_meta.get("content"):
        description = str(desc_meta["content"]).strip()
        verified_fields.append("description (meta)")
    else:
        # Look for first meaningful visible paragraph
        for p in soup.find_all("p"):
            p_text = p.get_text().strip()
            if 30 <= len(p_text) <= 300:
                description = p_text
                verified_fields.append("description (body)")
                break

    # 3. Public Business Contact Email (Extract only visible mailto or text emails)
    found_emails: Set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("mailto:"):
            email_part = href.replace("mailto:", "").split("?")[0].strip()
            if email_part:
                found_emails.add(email_part)

    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    for match in re.findall(email_regex, soup.get_text()):
        found_emails.add(match)

    cleaned_emails = _clean_extracted_emails(found_emails, domain)
    contact_email = ""
    if cleaned_emails:
        contact_email = cleaned_emails[0]
        verified_fields.append("email")

    # 4. Contact Name / Role (Leave unverified/empty if not explicitly on page)
    contact_name = ""
    contact_role = ""

    # Discover relevant on-domain subpage links (e.g., /contact, /about, /team)
    subpage_links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("tel:"):
            continue
        full_url = urljoin(page_url, href)
        parsed_sub = urlparse(full_url)
        if parsed_sub.netloc == domain and parsed_sub.scheme in ("http", "https"):
            path_lower = parsed_sub.path.lower()
            if any(k in path_lower for k in ("contact", "about", "team", "company")):
                if full_url not in subpage_links and full_url != page_url:
                    subpage_links.append(full_url)

    now_iso = datetime.now(timezone.utc).isoformat()
    record = LeadRecord(
        id=f"live-lead-{_sanitize_slug(domain)}",
        company_name=company_name,
        contact_name=contact_name if contact_name else "(Not published on page)",
        contact_role=contact_role if contact_role else "(Not published on page)",
        email=contact_email if contact_email else "(No public email listed)",
        website=f"{parsed_url.scheme}://{domain}",
        industry=industry or "Identified via Web",
        location=location or "Public Web",
        source_note=f"[VERIFIED PUBLIC WEB] Extracted from {page_url}. Verified fields: {', '.join(verified_fields)}",
        created_at=now_iso,
        source_url=page_url,
        description=description,
        verified_fields=verified_fields,
        is_live=True,
    )

    return record, subpage_links

class PlaywrightResearchProvider(BaseResearchProvider):
    """
    Modular Playwright public-web research provider.
    Scrapes user-provided URLs in headless mode, checks robots.txt, respects rate limits,
    and extracts only visibly published public business data.
    """
    def __init__(self):
        self._diagnostics: List[CrawlDiagnostic] = []
        self._pages_crawled_count: int = 0

    @property
    def provider_name(self) -> str:
        return "playwright-live-provider"

    @property
    def is_demo(self) -> bool:
        return False

    @property
    def last_diagnostics(self) -> List[CrawlDiagnostic]:
        return self._diagnostics

    @property
    def pages_crawled_count(self) -> int:
        return self._pages_crawled_count

    async def search(self, request: ResearchRequest) -> List[LeadRecord]:
        """
        Executes live public-web extraction across user-provided target URLs.
        """
        self._diagnostics = []
        self._pages_crawled_count = 0
        results: List[LeadRecord] = []
        visited_domains: Set[str] = set()

        # Validate URLs list
        raw_urls = request.urls or []
        if not raw_urls:
            self._diagnostics.append(
                CrawlDiagnostic(
                    url="N/A",
                    status="missing_urls",
                    reason="Live research mode requires at least one target website URL (e.g. https://example.com)."
                )
            )
            return []

        # Validate each URL format
        valid_targets: List[str] = []
        for raw_url in raw_urls:
            is_valid, sanitized, reason = validate_target_url(raw_url)
            if not is_valid:
                self._diagnostics.append(
                    CrawlDiagnostic(
                        url=raw_url,
                        status="invalid_url",
                        reason=reason
                    )
                )
            else:
                valid_targets.append(sanitized)

        if not valid_targets:
            return []

        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"]
                )
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                    java_script_enabled=True,
                )

                for target_url in valid_targets:
                    if len(results) >= (request.max_results or 5):
                        break

                    parsed_target = urlparse(target_url)
                    domain = parsed_target.netloc

                    if domain in visited_domains:
                        continue
                    visited_domains.add(domain)

                    # 1. Check robots.txt
                    allowed, robots_reason = is_allowed_by_robots(target_url)
                    if not allowed:
                        self._diagnostics.append(
                            CrawlDiagnostic(
                                url=target_url,
                                status="disallowed_by_robots",
                                reason=robots_reason
                            )
                        )
                        continue

                    # 2. Navigate to Target URL via Playwright
                    page = await context.new_page()
                    primary_lead: Optional[LeadRecord] = None
                    subpage_links: List[str] = []

                    try:
                        response = await page.goto(target_url, timeout=12000, wait_until="domcontentloaded")
                        self._pages_crawled_count += 1

                        if response and response.status in (401, 403):
                            self._diagnostics.append(
                                CrawlDiagnostic(
                                    url=target_url,
                                    status="access_restricted",
                                    reason=f"HTTP {response.status}: Access restricted by server."
                                )
                            )
                            continue

                        # Extract visible page content
                        html_content = await page.content()
                        lead, discovered_links = extract_lead_from_html(
                            html_content,
                            page.url,
                            industry=request.industry,
                            location=request.location,
                            topic=request.topic
                        )

                        if lead is None:
                            self._diagnostics.append(
                                CrawlDiagnostic(
                                    url=target_url,
                                    status="challenge_detected",
                                    reason="Bot challenge or CAPTCHA screen detected; skipped without attempting bypass."
                                )
                            )
                            continue

                        primary_lead = lead
                        subpage_links = discovered_links

                        self._diagnostics.append(
                            CrawlDiagnostic(
                                url=target_url,
                                status="success",
                                reason=f"Extracted {len(lead.verified_fields)} verified public fields."
                            )
                        )

                    except Exception as exc:
                        self._diagnostics.append(
                            CrawlDiagnostic(
                                url=target_url,
                                status="fetch_error",
                                reason=f"Page navigation failed: {str(exc)[:120]}"
                            )
                        )
                    finally:
                        await page.close()

                    # 3. Follow On-Domain Links (if contact info like email is missing and follow_links is True)
                    if primary_lead and request.follow_links and primary_lead.email == "(No public email listed)":
                        max_subpages = min(request.max_pages_per_domain or 2, len(subpage_links), 2)
                        for sub_url in subpage_links[:max_subpages]:
                            # Check robots.txt for subpage
                            sub_allowed, _ = is_allowed_by_robots(sub_url)
                            if not sub_allowed:
                                continue

                            sub_page = await context.new_page()
                            try:
                                # Polite crawl rate limit delay
                                await asyncio.sleep(0.4)
                                await sub_page.goto(sub_url, timeout=9000, wait_until="domcontentloaded")
                                self._pages_crawled_count += 1
                                sub_html = await sub_page.content()
                                sub_lead, _ = extract_lead_from_html(sub_html, sub_page.url)

                                if sub_lead and sub_lead.email != "(No public email listed)":
                                    primary_lead.email = sub_lead.email
                                    primary_lead.source_url = sub_url
                                    if "email" not in primary_lead.verified_fields:
                                        primary_lead.verified_fields.append("email (subpage)")
                                    primary_lead.source_note += f" | Email verified on {sub_url}"
                                    break
                            except Exception:
                                pass
                            finally:
                                await sub_page.close()

                    if primary_lead:
                        results.append(primary_lead)

                await browser.close()

        except Exception as global_exc:
            self._diagnostics.append(
                CrawlDiagnostic(
                    url="playwright_subsystem",
                    status="browser_init_failed",
                    reason=f"Playwright browser error: {str(global_exc)[:140]}"
                )
            )

        return results
