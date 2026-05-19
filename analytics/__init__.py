"""
Analytics engines for the Content Intelligence Platform.

Provides platform-agnostic analytics that operate on NormalizedContent:
    - TrendVelocityEngine: Engagement, velocity, virality, growth scoring
    - HookAnalyzer: Hook extraction and categorization
"""

from analytics.trend_velocity import TrendVelocityEngine
from analytics.hooks import HookAnalyzer

__all__ = ["TrendVelocityEngine", "HookAnalyzer"]
