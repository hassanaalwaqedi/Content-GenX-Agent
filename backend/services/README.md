# Services

Higher-level orchestration services that coordinate across connectors and analytics engines.

## Files

| File | Responsibility |
|------|---------------|
| `query_intelligence.py` | `QueryIntelligenceEngine`: expands raw keywords into platform-optimized search variants, synonyms, and hashtag variants for TikTok and Instagram |

## Design

- Pure computation — no external API calls
- Embedded synonym dictionary for cross-platform keyword expansion
- Consumed by TikTok and Instagram connectors during keyword-based searches
