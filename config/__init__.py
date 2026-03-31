"""
MCRcore Growth Engine - Configuration Package
Phase 0: Foundation configuration for multi-agent B2B lead generation system.
"""

from config.settings import settings
from config.icp_rules import ICP_RULES
from config.service_catalog import SERVICE_CATALOG
from config.differentiators import DIFFERENTIATORS
from config.source_policy import SOURCE_POLICY
from config.geo_routing import GEO_ROUTING

__all__ = [
    "settings",
    "ICP_RULES",
    "SERVICE_CATALOG",
    "DIFFERENTIATORS",
    "SOURCE_POLICY",
    "GEO_ROUTING",
]
