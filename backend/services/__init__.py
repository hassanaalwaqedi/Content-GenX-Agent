"""
Services layer for the Content Intelligence Platform.

Provides higher-level intelligence services that orchestrate
across connectors and analytics engines:
    - QueryIntelligenceEngine: Keyword expansion and platform-aware search variants
"""

from services.query_intelligence import QueryIntelligenceEngine, QueryContext

__all__ = ["QueryIntelligenceEngine", "QueryContext"]
