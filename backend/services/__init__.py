"""
AgentDesk Services package.
"""
from .lead_discovery import (
    parse_natural_language_request,
    LeadDiscoveryService,
    global_lead_discovery_service,
)

__all__ = [
    "parse_natural_language_request",
    "LeadDiscoveryService",
    "global_lead_discovery_service",
]
