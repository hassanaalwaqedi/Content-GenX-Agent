# Enrichment

AI enrichment layer that adds strategic metadata to ingested content using Groq LLM.

## Files

| File | Responsibility |
|------|---------------|
| `ai.py` | Groq client: strategic analysis (target audience, advice, content gaps), topic extraction, circuit breaker for rate limits |

## Features

- **Strategic insights**: For each video, generates target audience, strategic advice, and content gap analysis
- **Topic extraction**: LLM-powered topics with rule-based fallback
- **Graceful degradation**: On API failure, fills fields with "Analysis pending" — never crashes the pipeline
- **Circuit breaker**: Opens after 3 consecutive failures, skips remaining videos to avoid wasting API quota
- **Top-N enrichment**: Only enriches the highest-scored videos per niche to control costs
