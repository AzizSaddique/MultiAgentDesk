"""
Research Providers package for AgentDesk.
Supports both Mock / Demo and Playwright Live Web extraction.
"""
from .base import BaseResearchProvider
from .mock import MockResearchProvider
from .playwright_scraper import PlaywrightResearchProvider

__all__ = ["BaseResearchProvider", "MockResearchProvider", "PlaywrightResearchProvider"]
