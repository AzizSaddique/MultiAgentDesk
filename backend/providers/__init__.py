"""
Research Providers package for AgentDesk.
"""
from .base import BaseResearchProvider
from .mock import MockResearchProvider

__all__ = ["BaseResearchProvider", "MockResearchProvider"]
