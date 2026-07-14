# Connectors

Plugin-based connector architecture for ingesting content from multiple platforms through a unified interface.

## Files

| File | Responsibility |
|------|---------------|
| `base.py` | Abstract `BaseConnector` class — contract all connectors must implement |
| `models.py` | `NormalizedContent` — canonical platform-agnostic content schema with `to_raw_video()` bridge to legacy pipeline |
| `registry.py` | `ConnectorRegistry` singleton — auto-discovers available connectors based on configured credentials |
| `rate_limiter.py` | Per-platform daily scan limiter with JSON persistence |
| `youtube_connector.py` | Wraps `pipeline.ingestion.YouTubeClient` into `BaseConnector` |
| `reddit_connector.py` | Reddit via Apify Reddit Scraper (ApifyMixin-based) |
| `tiktok_connector.py` | TikTok via Apify `clockworks/tiktok-scraper` actor |
| `instagram_connector.py` | Instagram via Apify Instagram Scraper actor |

## How It Works

1. `ConnectorRegistry` scans `.env` credentials at first access
2. Each enabled platform is registered with its connector instance
3. `pipeline/runner.py` iterates all registered connectors (skipping YouTube/Reddit which use the legacy path)
4. Each connector returns `List[NormalizedContent]`
5. `NormalizedContent.to_raw_video()` bridges into the legacy processing pipeline

## Adding a New Platform

```python
# 1. Create connectors/myplatform.py with BaseConnector subclass
# 2. Add to ConnectorRegistry._discover()
# 3. Add platform settings to core/config.py
# 4. Done — pipeline auto-picks it up
```
