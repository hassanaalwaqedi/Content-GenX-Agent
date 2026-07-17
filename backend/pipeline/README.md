# Pipeline

ETL orchestration — the heart of the platform. Ingests content from all platforms, processes/scored it, enriches with AI, and stores results.

## Files

| File | Responsibility |
|------|---------------|
| `runner.py` | Main orchestrator: calls each stage in sequence, manages pipeline lock |
| `scheduler.py` | Daily cron-like scheduler using the `schedule` library |
| `ingestion.py` | YouTube Data API v3 client (mostPopular + keyword search) |
| ~~`reddit_ingestion.py`~~ | _Deprecated — replaced by `connectors/reddit_connector.py` (Apify)_ |
| `processing.py` | Scoring engine: engagement rate, recency decay, weighted composite score |
| `trends.py` | Trend discovery and opportunity detection (topic clustering + LLM) |
| `transcripts.py` | YouTube transcript fetcher (manual + auto-generated captions) |
| `migrate.py` | One-shot schema migration script (legacy, migrations now auto-applied) |
| `backfill_transcripts.py` | Batch transcript backfill for existing database records |

## Pipeline Flow

```
runner.py
  │
  ├── 0. init_db()
  ├── 1. Preflight checks (API keys)
  ├── 2. Ingest
  │     ├── pipeline/ingestion.py (YouTube)
  │     ├── pipeline/reddit_ingestion.py (Reddit)
  │     └── connectors/* (TikTok, Instagram via ConnectorRegistry)
  ├── 3. process_videos() — score + filter
  ├── 4. enrich_videos() — Groq AI analysis
  ├── 5. Transcript extraction (YouTube only)
  └── 6. insert_videos() — database upsert
```
