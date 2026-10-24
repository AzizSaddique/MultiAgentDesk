"""
Search Provider Abstraction for AgentDesk Automated Lead Discovery.
Defines interfaces for compliant web search and business directory integrations.
Zero scraping of unauthorized SERP pages.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    query: str = ""
    domain: str = ""
    source_provider: str = ""
    source_query: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.source_query and self.query:
            self.source_query = self.query
        elif not self.query and self.source_query:
            self.query = self.source_query
        if not self.domain and self.url:
            try:
                from urllib.parse import urlparse
                self.domain = urlparse(self.url).netloc.lower().replace("www.", "")
            except Exception:
                self.domain = ""
        if not self.source_provider and self.source:
            self.source_provider = self.source



class SearchProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @property
    @abstractmethod
    def requires_key(self) -> bool:
        pass

    @property
    @abstractmethod
    def configuration_notice(self) -> str:
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        count: int = 10,
        country: Optional[str] = None,
        language: Optional[str] = "en",
    ) -> List[SearchResult]:
        """
        Executes a query against the authorized search API or directory.
        Returns a list of structured SearchResult objects.
        """
        pass
