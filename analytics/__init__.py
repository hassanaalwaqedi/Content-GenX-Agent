"""
Analytics engines for the Content Intelligence Platform.

Provides platform-agnostic analytics that operate on NormalizedContent:
    - TrendVelocityEngine: Engagement, velocity, virality, growth scoring
    - HookAnalyzer: Hook extraction and categorization
    - ContentRelevanceEngine: Query-aware relevance scoring
"""

from analytics.trend_velocity import TrendVelocityEngine
from analytics.hooks import HookAnalyzer
from analytics.relevance_engine import ContentRelevanceEngine

__all__ = ["TrendVelocityEngine", "HookAnalyzer", "ContentRelevanceEngine"]
