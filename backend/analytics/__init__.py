"""
Analytics engines for the Content Intelligence Platform.

Provides platform-agnostic analytics that operate on NormalizedContent:
    - ContentRelevanceEngine: Query-aware relevance scoring
"""

from analytics.relevance_engine import ContentRelevanceEngine

__all__ = ["ContentRelevanceEngine"]
