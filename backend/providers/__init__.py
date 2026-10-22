"""
Research Providers package for AgentDesk.
Supports both Mock / Demo and Playwright Live Web extraction.
"""
from .base import BaseResearchProvider
from .mock import MockResearchProvider
from .playwright_scraper import PlaywrightResearchProvider
from .llm import BaseLLMProvider, TemplateLLMProvider, OllamaLLMProvider, CloudOpenAICompatibleProvider, get_llm_provider
from .email_dispatcher import (
    dispatch_outreach_email,
    get_dispatch_status_info,
    DispatchError,
    DispatchConfigurationError,
    DispatchDeliveryError,
    DispatchResult,
)

__all__ = [
    "BaseResearchProvider",
    "MockResearchProvider",
    "PlaywrightResearchProvider",
    "BaseLLMProvider",
    "TemplateLLMProvider",
    "OllamaLLMProvider",
    "CloudOpenAICompatibleProvider",
    "get_llm_provider",
    "dispatch_outreach_email",
    "get_dispatch_status_info",
    "DispatchError",
    "DispatchConfigurationError",
    "DispatchDeliveryError",
    "DispatchResult",
]


