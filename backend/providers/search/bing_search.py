"""
Authorized Microsoft Bing Web Search API Provider.
Strictly uses official Azure Cognitive Services Bing Web Search REST endpoints.
Never scrapes Bing search results pages.
"""
import os
import httpx
from typing import List, Optional
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
        def sanitize_log_message(msg: str) -> str:
            return msg or ""


class BingSearchProvider(SearchProvider):
    """
    Integrates with official Microsoft Bing Web Search v7.0 API.
    Requires:
      - BING_SEARCH_API_KEY (or AGENTDESK_BING_API_KEY)
    Docs: https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/overview
    """
    API_URL = "https://api.bing.microsoft.com/v7.0/search"

    @property
    def provider_id(self) -> str:
        return "bing"

    @property
    def display_name(self) -> str:
        return "Bing Web Search API"

    @property
    def requires_key(self) -> bool:
        return True

    def _get_api_key(self) -> Optional[str]:
        val = (
            os.environ.get("BING_SEARCH_API_KEY")
            or os.environ.get("AGENTDESK_BING_API_KEY")
            or ""
        ).strip()
        if not val:
            try:
                load_root_env(override=False)
                val = (
                    os.environ.get("BING_SEARCH_API_KEY")
                    or os.environ.get("AGENTDESK_BING_API_KEY")
                    or ""
                ).strip()
            except Exception:
                pass
        return val

    @property
    def is_configured(self) -> bool:
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
            return "Microsoft Bing Web Search API is configured and ready."
        return (
            "Requires BING_SEARCH_API_KEY in root .env. "
            "Get an authorized key on Azure Portal (Cognitive Services / Bing Search)."
        )

    async def search(
        self,
        query: str,
        count: int = 10,
        country: Optional[str] = None,
        language: Optional[str] = "en",
        max_results: Optional[int] = None,
        **kwargs,
    ) -> List[SearchResult]:
        if not self.is_configured:
            return []

        effective_count = max_results if max_results is not None else count
        api_key = self._get_api_key()
        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "User-Agent": "AgentDesk-Bot/1.0",
        }
        params = {
            "q": query,
            "count": min(max(1, effective_count), 50),
            "responseFilter": "Webpages",
        }
        if country and len(country) == 2:
            params["cc"] = country.upper()
        if language:
            params["setLang"] = language

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.API_URL, headers=headers, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    web_pages = data.get("webPages", {}).get("value", [])
                    results: List[SearchResult] = []
                    for item in web_pages:
                        url = item.get("url", "")
                        if not url:
                            continue
                        results.append(
                            SearchResult(
                                title=item.get("name", ""),
                                url=url,
                                snippet=item.get("snippet", ""),
                                source="bing-search",
                                source_provider="bing-search",
                                query=query,
                            )
                        )
                    return results
                else:
                    err_msg = f"Bing Search API returned HTTP {resp.status_code}"
                    try:
                        err_json = resp.json()
                        if "error" in err_json and "message" in err_json["error"]:
                            err_msg += f": {err_json['error']['message']}"
                    except Exception:
                        pass
                    safe_msg = sanitize_log_message(err_msg, custom_secrets=[api_key])
                    raise RuntimeError(safe_msg)
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            safe_err = sanitize_log_message(str(e), custom_secrets=[api_key])
            raise RuntimeError(f"Bing Search request failed: {safe_err}")
