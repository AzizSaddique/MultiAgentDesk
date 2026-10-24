"""
Authorized Google Custom Search JSON API Provider.
Strictly uses official Google REST endpoints (https://www.googleapis.com/customsearch/v1).
Never scrapes Google search results pages.
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


class GoogleSearchProvider(SearchProvider):
    """
    Integrates with Google Custom Search JSON API.
    Requires:
      - GOOGLE_SEARCH_API_KEY (or AGENTDESK_GOOGLE_API_KEY)
      - GOOGLE_SEARCH_ENGINE_ID (or GOOGLE_SEARCH_CX or AGENTDESK_GOOGLE_CX)
    Docs: https://developers.google.com/custom-search/v1/overview
    """
    API_URL = "https://www.googleapis.com/customsearch/v1"

    @property
    def provider_id(self) -> str:
        return "google"

    @property
    def display_name(self) -> str:
        return "Google Custom Search API"

    @property
    def requires_key(self) -> bool:
        return True

    def _get_api_key(self) -> Optional[str]:
        val = (
            os.environ.get("GOOGLE_SEARCH_API_KEY")
            or os.environ.get("AGENTDESK_GOOGLE_API_KEY")
            or ""
        ).strip()
        if not val:
            try:
                load_root_env(override=False)
                val = (
                    os.environ.get("GOOGLE_SEARCH_API_KEY")
                    or os.environ.get("AGENTDESK_GOOGLE_API_KEY")
                    or ""
                ).strip()
            except Exception:
                pass
        return val

    def _get_cx(self) -> Optional[str]:
        val = (
            os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
            or os.environ.get("GOOGLE_SEARCH_CX")
            or os.environ.get("AGENTDESK_GOOGLE_CX")
            or ""
        ).strip()
        if not val:
            try:
                load_root_env(override=False)
                val = (
                    os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
                    or os.environ.get("GOOGLE_SEARCH_CX")
                    or os.environ.get("AGENTDESK_GOOGLE_CX")
                    or ""
                ).strip()
            except Exception:
                pass
        return val

    @property
    def is_configured(self) -> bool:
        key = self._get_api_key()
        cx = self._get_cx()
        if not key or not cx:
            return False
        for val in (key, cx):
            lower = val.lower()
            if any(p in lower for p in ["placeholder", "your-", "your_", "example", "<", "xxx"]):
                return False
        return len(key) >= 10 and len(cx) >= 5

    @property
    def configuration_notice(self) -> str:
        if self.is_configured:
            return "Google Custom Search JSON API is configured and ready."
        return (
            "Requires GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID in root .env. "
            "Get an authorized key at https://developers.google.com/custom-search/v1/overview."
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
        cx = self._get_cx()

        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": min(max(1, effective_count), 10),
        }
        if language:
            params["lr"] = f"lang_{language}"
        if country and len(country) == 2:
            params["gl"] = country.lower()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.API_URL, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    results: List[SearchResult] = []
                    for item in items:
                        url = item.get("link", "")
                        if not url:
                            continue
                        results.append(
                            SearchResult(
                                title=item.get("title", ""),
                                url=url,
                                snippet=item.get("snippet", ""),
                                source="google-search",
                                source_provider="google-search",
                                query=query,
                            )
                        )
                    return results
                else:
                    err_msg = f"Google Search API returned HTTP {resp.status_code}"
                    try:
                        err_json = resp.json()
                        if "error" in err_json and "message" in err_json["error"]:
                            err_msg += f": {err_json['error']['message']}"
                    except Exception:
                        pass
                    # Mask API key before raising or returning
                    safe_msg = sanitize_log_message(err_msg, custom_secrets=[api_key, cx])
                    raise RuntimeError(safe_msg)
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            safe_err = sanitize_log_message(str(e), custom_secrets=[api_key, cx])
            raise RuntimeError(f"Google Search request failed: {safe_err}")
