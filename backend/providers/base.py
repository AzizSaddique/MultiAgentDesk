"""
Base interface for research providers.
Allows swapping Mock provider with Playwright public-web scraper in subsequent milestones.
"""
from abc import ABC, abstractmethod
from typing import List
from ..models import ResearchRequest, LeadRecord

class BaseResearchProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider implementation."""
        pass

    @property
    @abstractmethod
    def is_demo(self) -> bool:
        """Whether this provider yields simulated demo records."""
        pass

    @abstractmethod
    async def search(self, request: ResearchRequest) -> List[LeadRecord]:
        """
        Execute research for the given topic, industry, and location.
        Returns a structured list of LeadRecord items.
        """
        pass
