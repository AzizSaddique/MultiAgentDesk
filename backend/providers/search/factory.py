"""
Search Provider Factory and registry for AgentDesk Lead Discovery.
"""
import os
from typing import List, Optional
from .base import SearchProvider
from .tavily_search import TavilySearchProvider
from .google_search import GoogleSearchProvider
from .bing_search import BingSearchProvider
from .duckduckgo_search import DuckDuckGoLiveSearchProvider
from .directory_search import PublicBusinessDirectoryProvider

try:
    from ...models import SearchProviderInfo
except (ImportError, ValueError):
    try:
        from models import SearchProviderInfo
    except ImportError:
        from pydantic import BaseModel
        class SearchProviderInfo(BaseModel):
            id: str
            name: str
            description: str
            is_configured: bool
            requires_key: bool
            notice: str


def get_search_provider(provider_id: Optional[str] = "auto") -> SearchProvider:
    """
    Returns an instantiated SearchProvider by ID.
    If 'auto' is selected, prefers configured commercial API providers (Tavily, Google, Bing),
    and defaults to DuckDuckGo Live Search for authentic unauthenticated web discovery,
    or Public Business Directory if explicitly requested.
    """
    clean_id = (provider_id or "auto").strip().lower()

    if clean_id == "tavily":
        return TavilySearchProvider()
    elif clean_id == "google":
        return GoogleSearchProvider()
    elif clean_id == "bing":
        return BingSearchProvider()
    elif clean_id in ("duckduckgo", "ddg", "live"):
        return DuckDuckGoLiveSearchProvider()
    elif clean_id == "directory":
        return PublicBusinessDirectoryProvider()
    elif clean_id == "auto":
        tavily = TavilySearchProvider()
        if tavily.is_configured:
            return tavily
        google = GoogleSearchProvider()
        if google.is_configured:
            return google
        bing = BingSearchProvider()
        if bing.is_configured:
            return bing
        if os.environ.get("ENABLE_DDG_AUTO_FALLBACK", "").lower() in ("true", "1", "yes"):
            return DuckDuckGoLiveSearchProvider()
        return PublicBusinessDirectoryProvider()
    else:
        return PublicBusinessDirectoryProvider()


def list_search_providers() -> List[SearchProviderInfo]:
    """
    Returns the availability and configuration status of all supported search sources:
    DuckDuckGo Live Search, Tavily Search API, Google Custom Search, Bing Web Search,
    and Public Business Directory.
    """
    tavily = TavilySearchProvider()
    google = GoogleSearchProvider()
    bing = BingSearchProvider()
    ddg = DuckDuckGoLiveSearchProvider()
    directory = PublicBusinessDirectoryProvider()

    auto_configured = True
    active_auto_source = (
        "Tavily Search API" if tavily.is_configured
        else "Google Custom Search" if google.is_configured
        else "Bing Web Search" if bing.is_configured
        else "DuckDuckGo Live Search"
    )

    return [
        SearchProviderInfo(
            id="auto",
            name="Auto-Select Best Available",
            description=f"Automatically routes to highest priority configured provider (Current: {active_auto_source}).",
            is_configured=auto_configured,
            requires_key=False,
            notice=f"Active route: {active_auto_source}",
        ),
        SearchProviderInfo(
            id=ddg.provider_id,
            name=ddg.display_name,
            description="Real-time web search without external API key requirements. Discovers live company websites directly.",
            is_configured=ddg.is_configured,
            requires_key=ddg.requires_key,
            notice=ddg.configuration_notice,
        ),
        SearchProviderInfo(
            id=tavily.provider_id,
            name=tavily.display_name,
            description="Official Tavily AI Search API optimized for agent discovery, clean web extracts, and factual company sources.",
            is_configured=tavily.is_configured,
            requires_key=tavily.requires_key,
            notice=tavily.configuration_notice,
        ),
        SearchProviderInfo(
            id=google.provider_id,
            name=google.display_name,
            description="Official Google Custom Search JSON API for high-precision company website discovery.",
            is_configured=google.is_configured,
            requires_key=google.requires_key,
            notice=google.configuration_notice,
        ),
        SearchProviderInfo(
            id=bing.provider_id,
            name=bing.display_name,
            description="Official Azure Cognitive Services Bing Web Search v7.0 API for web business discovery.",
            is_configured=bing.is_configured,
            requires_key=bing.requires_key,
            notice=bing.configuration_notice,
        ),
        SearchProviderInfo(
            id=directory.provider_id,
            name=directory.display_name,
            description="Built-in public trade registries, verified corporate databases, and offline testing directory.",
            is_configured=directory.is_configured,
            requires_key=directory.requires_key,
            notice=directory.configuration_notice,
        ),
    ]
