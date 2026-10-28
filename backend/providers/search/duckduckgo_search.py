"""
Authorized DuckDuckGo HTML Live Search Provider for AgentDesk.
Executes live, unauthenticated web search queries against DuckDuckGo.
Never scrapes unauthorized private pages.
Zero API keys required.
"""
import re
import asyncio
import urllib.parse
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
from .base import SearchProvider, SearchResult

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 AgentDesk/1.0"
)


class DuckDuckGoLiveSearchProvider(SearchProvider):
    """
    Live web search provider utilizing DuckDuckGo HTML search.
    Provides authentic, real-time web discovery without commercial API keys.
    """
    ENDPOINT = "https://html.duckduckgo.com/html/"

    def __init__(self, min_request_interval: float = 0.5):
        self._min_request_interval = min_request_interval
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()

    @property
    def provider_id(self) -> str:
        return "duckduckgo"

    @property
    def display_name(self) -> str:
        return "DuckDuckGo Live Search"

    @property
    def requires_key(self) -> bool:
        return False

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def configuration_notice(self) -> str:
        return "Live web search available out-of-the-box. Zero API keys required."

    async def search(
        self,
        query: str,
        max_results: int = 15,
        language: Optional[str] = "en",
    ) -> List[SearchResult]:
        """
        Executes a live search query and parses authentic web results.
        """
        clean_query = (query or "").strip()
        if not clean_query:
            return []

        async with self._lock:
            # Respect polite pacing
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_request_interval:
                await asyncio.sleep(self._min_request_interval - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        data = {"q": clean_query}

        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            try:
                resp = await client.post(self.ENDPOINT, data=data, headers=headers)
            except Exception as exc:
                raise RuntimeError(f"DuckDuckGo live search connection error: {exc}")

            if resp.status_code == 429:
                raise RuntimeError("DuckDuckGo rate limit encountered (HTTP 429). Please retry after a brief delay.")
            elif resp.status_code != 200:
                raise RuntimeError(f"DuckDuckGo returned HTTP {resp.status_code}")

        soup = BeautifulSoup(resp.text, "html.parser")
        results: List[SearchResult] = []
        seen_urls = set()

        for res_div in soup.find_all("div", class_="result"):
            if len(results) >= max_results:
                break

            title_elem = res_div.find("a", class_="result__a")
            snippet_elem = res_div.find("a", class_="result__snippet")
            link_elem = res_div.find("a", class_="result__url") or title_elem

            if not title_elem or not link_elem:
                continue

            raw_href = link_elem.get("href", "")
            # Unpack DuckDuckGo redirect uddg= parameter
            real_url = raw_href
            if "uddg=" in raw_href:
                try:
                    parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                    if "uddg" in parsed_q:
                        real_url = parsed_q["uddg"][0]
                except Exception:
                    real_url = raw_href

            real_url = real_url.strip()
            if not real_url.startswith("http://") and not real_url.startswith("https://"):
                continue

            # Ignore duckduckgo internal links and ads
            if "duckduckgo.com" in real_url:
                continue

            # Normalize for deduplication
            norm_url = real_url.lower().rstrip("/")
            if norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)

            title = title_elem.get_text(strip=True)
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

            # Clean tracking parameters
            try:
                p_url = urllib.parse.urlparse(real_url)
                clean_url = f"{p_url.scheme}://{p_url.netloc}{p_url.path}"
                if p_url.query:
                    # Keep safe search queries, strip utm_
                    q_params = [
                        qp for qp in p_url.query.split("&")
                        if not qp.startswith("utm_") and not qp.startswith("fbclid")
                    ]
                    if q_params:
                        clean_url += "?" + "&".join(q_params)
            except Exception:
                clean_url = real_url

            results.append(
                SearchResult(
                    title=title,
                    url=clean_url,
                    snippet=snippet,
                    source="duckduckgo",
                    source_provider="duckduckgo",
                    metadata={
                        "query": clean_query,
                        "search_method": "live_web_search",
                        "is_live": True,
                    },
                )
            )

        return results
