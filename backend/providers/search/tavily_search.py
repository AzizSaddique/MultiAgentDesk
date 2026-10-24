"""
Authorized Tavily Search API Provider for AgentDesk Automated Lead Discovery.
Strictly uses official Tavily REST API endpoints (https://api.tavily.com/search).
Zero scraping of unauthorized search engine result pages.
Docs: https://docs.tavily.com/
"""
import os
import time
import asyncio
import httpx
from typing import List, Optional, Dict, Any
from .base import SearchProvider, SearchResult

try:
    from ...env_loader import load_root_env
except (ImportError, ValueError):
    try:
        from env_loader import load_root_env
    except ImportError:
        def load_root_env(override: bool = False):
            return {}

try:
    from ..email_dispatcher import sanitize_log_message
except (ImportError, ValueError):
    try:
        from providers.email_dispatcher import sanitize_log_message
    except ImportError:
        def sanitize_log_message(msg: str, custom_secrets: Optional[list] = None) -> str:
            clean = msg or ""
            if custom_secrets:
                for s in custom_secrets:
                    if s:
                        clean = clean.replace(str(s), "[REDACTED_SECRET]")
            return clean

try:
    from ..playwright_scraper import validate_target_url
except (ImportError, ValueError):
    try:
        from providers.playwright_scraper import validate_target_url
    except ImportError:
        from urllib.parse import urlparse
        def validate_target_url(raw_url: str):
            if not raw_url or not raw_url.strip():
                return False, "", "URL is empty"
            cleaned = raw_url.strip()
            try:
                parsed = urlparse(cleaned)
                if parsed.scheme not in ("http", "https"):
                    return False, cleaned, "Only HTTP and HTTPS are permitted."
                hostname = parsed.hostname or ""
                if (
                    hostname in ("localhost", "127.0.0.1", "0.0.0.0")
                    or hostname.startswith("192.168.")
                    or hostname.startswith("10.")
                    or hostname.startswith("172.16.")
                ):
                    return False, cleaned, "Internal / private network URLs are restricted."
                return True, cleaned, ""
            except Exception:
                return False, cleaned, "Malformed URL"


class TavilySearchProvider(SearchProvider):
    """
    First-class Tavily Search API provider.
    Optimized for AI agent lead discovery and company website extraction.
    Requires:
      - TAVILY_API_KEY (or AGENTDESK_TAVILY_API_KEY) in root .env.
    Official Docs: https://docs.tavily.com/
    """
    API_URL = "https://api.tavily.com/search"

    def __init__(self, min_request_interval: float = 0.2):
        self._min_request_interval = min_request_interval
        self._last_request_time = 0.0
        self._lock: Optional[asyncio.Lock] = None

    @property
    def provider_id(self) -> str:
        return "tavily"

    @property
    def display_name(self) -> str:
        return "Tavily Search API"

    @property
    def requires_key(self) -> bool:
        return True

    def _get_api_key(self) -> str:
        """
        Reads TAVILY_API_KEY securely using the root .env loader pattern.
        """
        key = (
            os.environ.get("TAVILY_API_KEY")
            or os.environ.get("AGENTDESK_TAVILY_API_KEY")
            or ""
        ).strip()
        if not key:
            try:
                load_root_env(override=False)
                key = (
                    os.environ.get("TAVILY_API_KEY")
                    or os.environ.get("AGENTDESK_TAVILY_API_KEY")
                    or ""
                ).strip()
            except Exception:
                pass
        return key

    @property
    def is_configured(self) -> bool:
        """
        Verifies if Tavily has a valid, non-placeholder API key configured.
        """
        key = self._get_api_key()
        if not key:
            return False
        lower = key.lower()
        if any(p in lower for p in ["placeholder", "your-", "your_", "example", "<", "xxx"]):
            return False
        return len(key) >= 10

    @property
    def configuration_notice(self) -> str:
        if self.is_configured:
            return "Tavily Search API is configured and ready."
        return (
            "Requires TAVILY_API_KEY in root .env. "
            "Get an API key at https://app.tavily.com (1,000 free searches/month, no credit card required)."
        )

    async def _throttle(self) -> None:
        """
        Simple rate limit cooldown to prevent rapid bursting.
        """
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - elapsed)
            self._last_request_time = time.time()

    async def search(
        self,
        query: str,
        count: int = 10,
        country: Optional[str] = None,
        language: Optional[str] = "en",
        max_results: Optional[int] = None,
        **kwargs,
    ) -> List[SearchResult]:
        """
        Executes a real-time web search via Tavily's official POST /search endpoint.
        Returns a structured list of SearchResult items with SSRF guards applied.
        """
        if not self.is_configured:
            return []

        effective_count = max_results if max_results is not None else count
        # Tavily supports max_results between 1 and 20 per request
        num_results = min(max(1, effective_count), 20)
        api_key = self._get_api_key()

        # Enforce client-side rate limit spacing
        await self._throttle()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "AgentDesk-Bot/1.0",
        }

        payload: Dict[str, Any] = {
            "query": query,
            "max_results": num_results,
            "search_depth": "basic",
            "topic": "general",
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }

        if language:
            payload["language"] = language
        if country and isinstance(country, str) and country.strip():
            payload["country"] = country.strip().lower()

        # Bounded network timeout: 10s total, 5s connect
        timeout = httpx.Timeout(10.0, connect=5.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(self.API_URL, json=payload, headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("results", [])
                    results: List[SearchResult] = []
                    for item in items:
                        url = item.get("url", "")
                        if not url:
                            continue

                        # Apply strict SSRF and URL format validation
                        is_valid, safe_url, _ = validate_target_url(url)
                        if not is_valid:
                            continue

                        results.append(
                            SearchResult(
                                title=item.get("title", "") or "Untitled",
                                url=safe_url,
                                snippet=item.get("content", ""),
                                source="tavily-search",
                                source_provider="tavily-search",
                                query=query,
                                metadata={
                                    "score": item.get("score"),
                                    "published_date": item.get("published_date"),
                                },
                            )
                        )
                    return results

                elif resp.status_code == 429:
                    err_msg = "Tavily Search API rate limit exceeded (HTTP 429). Please retry after cooldown."
                    safe_msg = sanitize_log_message(err_msg, custom_secrets=[api_key])
                    raise RuntimeError(safe_msg)

                elif resp.status_code in (401, 403):
                    err_msg = f"Tavily Search API key unauthorized or invalid (HTTP {resp.status_code}). Please verify TAVILY_API_KEY in root .env."
                    safe_msg = sanitize_log_message(err_msg, custom_secrets=[api_key])
                    raise RuntimeError(safe_msg)

                else:
                    err_msg = f"Tavily Search API returned HTTP {resp.status_code}"
                    try:
                        err_json = resp.json()
                        if "detail" in err_json:
                            err_msg += f": {err_json['detail']}"
                        elif "error" in err_json:
                            err_msg += f": {err_json['error']}"
                    except Exception:
                        pass
                    safe_msg = sanitize_log_message(err_msg, custom_secrets=[api_key])
                    raise RuntimeError(safe_msg)

        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            safe_err = sanitize_log_message(str(e), custom_secrets=[api_key])
            raise RuntimeError(f"Tavily Search request failed: {safe_err}")
