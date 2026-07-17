"""
Connector Architecture for Content Intelligence Platform.

Provides a unified, plugin-based system for ingesting content from
multiple platforms (YouTube, Reddit, TikTok, Instagram, etc.) through
a single abstract interface.

Public API:
    - BaseConnector: Abstract base class for all platform connectors
    - NormalizedContent: Unified content model across all platforms
    - ConnectorRegistry: Auto-discovers and manages available connectors
    - ConnectorHealth: Health status model for connector diagnostics
    - ConnectorMetrics: Request/failure tracking per connector
"""

from connectors.models import (
    NormalizedContent,
    ConnectorHealth,
    ConnectorMetrics,
)
from connectors.base import BaseConnector
from connectors.registry import ConnectorRegistry

__all__ = [
    "BaseConnector",
    "NormalizedContent",
    "ConnectorHealth",
    "ConnectorMetrics",
    "ConnectorRegistry",
]
