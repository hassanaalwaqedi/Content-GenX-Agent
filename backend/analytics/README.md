# Analytics

Platform-agnostic scoring and analysis engines that operate on `NormalizedContent`.

## Files

| File | Responsibility |
|------|---------------|
| `trend_velocity.py` | `TrendVelocityEngine`: engagement rate, velocity, virality, growth scoring |
| `hooks.py` | `HookAnalyzer`: extracts opening hook text, categorizes by type (curiosity, authority, fear, story, etc.) |
| `relevance_engine.py` | `ContentRelevanceEngine`: scores content against a query context (10 positive + 3 negative factors) |

## Usage

These engines are consumed by the connectors layer during ingestion (e.g., Instagram connector uses `ContentRelevanceEngine` to filter relevant content). They are also available as standalone tools for manual analysis.
