# Intelligent-Trends

Intelligent-Trends is a content intelligence platform for discovering high-performing and emerging video content across YouTube, TikTok, Instagram, and Reddit.

It combines platform connectors, trend scoring, transcript processing, AI enrichment, and a React dashboard for exploring videos, creators, trends, and pipeline results.

## Project documentation

- [Last Phase Master Change Document](docs/LAST_PHASE_CHANGE_MASTER.md) — completed work, architecture, operations, verification, and remaining constraints.

## Features

- YouTube ingestion through the YouTube Data API
- TikTok, Instagram, and Reddit ingestion through Apify actors
- Pipeline runs with dataset/workspace scoping
- Trend discovery and opportunity detection
- Transcript extraction and content analysis
- Creator intelligence and top-content rankings
- Connector health monitoring
- JWT-based single-operator login
- SQLite storage by default

## Project structure

```text
backend/
  api/          FastAPI routes, auth, request protection, and platform routers
  core/         Configuration, database, and queries
  connectors/   YouTube, TikTok, Instagram, and Reddit adapters
  pipeline/     Ingestion, processing, enrichment, and scheduling
  analytics/    Scoring and relevance analysis
  enrichment/   Groq-based AI enrichment

frontend/
  src/api/      API client and Vite proxy integration
  src/pages/    Dashboard, content, trends, creators, and pipeline views
  src/components/ Reusable dashboard components
```

## Requirements

- Python 3.11+
- Node.js 18+
- npm

## Configuration

Create `backend/.env` and add the required credentials:

```env
GENX_ADMIN_USERNAME=admin
GENX_ADMIN_PASSWORD=use-a-unique-password
# At least 32 random characters; do not reuse the admin password.
GENX_AUTH_SECRET=use-a-long-random-secret-at-least-32-characters

YOUTUBE_API_KEY=your-youtube-api-key
GROQ_API_KEY=your-groq-api-key
APIFY_API_TOKEN=your-apify-token

TIKTOK_ENABLED=true
APIFY_TIKTOK_ACTOR_ID=clockworks~tiktok-scraper
INSTAGRAM_ENABLED=true
APIFY_INSTAGRAM_ACTOR_ID=shu8hvrXbJbY3Eb9W
REDDIT_ENABLED=true
APIFY_REDDIT_ACTOR_ID=automation-lab~reddit-scraper
```

Never commit `.env` files or expose API keys publicly. Rotate keys that have been shared in chat, screenshots, or source control.

The backend permits browser requests only from the local Vite origins by
default. Add the exact HTTPS production origin to `CORS_ALLOWED_ORIGINS`
before deployment. Scans require an authenticated operator; set
`PIPELINE_API_KEY` only when a trusted automation client also needs to start
them. `API_RATE_LIMIT_REQUESTS` and `API_RATE_LIMIT_WINDOW_SECONDS` configure
the local rolling request limit.

## Run locally

Start the backend:

```powershell
cd backend
python -m pip install -r requirements.txt
$env:PYTHONPATH=(Get-Location).Path
python -m uvicorn api.api:app --host 127.0.0.1 --port 8000 --reload
```

Start the frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173) and log in with the credentials configured in `backend/.env`.

The backend health endpoint is available at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

## Operations

The API adds an `X-Request-ID` header to every response and emits JSON logs by
default. Set `LOG_JSON=false` when working locally if you prefer readable
plain-text logs.

All existing endpoints remain available without a prefix. The same endpoints
are also available under `/v1` for forward-compatible integrations, for
example `GET /v1/health` and `GET /v1/videos/top`.

Create a consistent SQLite snapshot with the built-in backup command:

```powershell
cd backend
$env:PYTHONPATH=(Get-Location).Path
python -m core.backup
```

Backups are written beside the database in `backups/` by default. Configure
`DATABASE_BACKUP_DIR` and `DATABASE_BACKUP_RETENTION_DAYS` for a different
location or retention period. Schedule this command through your platform's
task scheduler for production deployments.

## Run with Docker

```bash
docker compose up -d --build
```

The Docker deployment exposes the frontend on port `3000` and the backend on port `8000`.
It deliberately runs one API worker because the default SQLite database has a
single-writer model. Move to a server database such as PostgreSQL before
scaling the API across multiple workers or replicas.

## Pipeline workflow

1. Configure target markets, keywords, content type, and source platforms.
2. Launch an intelligence scan from the Pipeline page.
3. The backend ingests and normalizes platform data.
4. Videos are scored, enriched, and stored in a pipeline dataset.
5. The active dataset is displayed on the Dashboard, Trending, and Top Content pages.

If a run reports zero results, check the Connector Health panel, verify the selected Apify actor IDs and enabled flags, and inspect the pipeline run history.

## Useful API endpoints

```text
GET  /health
GET  /connectors/health
GET  /videos/top
GET  /videos/trending
GET  /creators/intelligence
GET  /pipeline/history
POST /pipeline/run

# Versioned aliases
GET  /v1/health
GET  /v1/videos/top
```

## Development

Frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

Backend tests:

```powershell
$env:PYTHONPATH=(Join-Path (Get-Location) 'backend')
python -m pytest backend/tests -q
```

The default database is `backend/content_intelligence.db`. Keep local database files out of version control when they contain private or production data.

## Architecture notes

The API is organized by domain: `api/videos.py`, `api/creators.py`,
`api/datasets.py`, `api/reddit.py`, and `api/system.py` own their respective
routes, while the legacy module retains pipeline, trend, and AI-generation
routes. The scan runner uses connector adapters for Reddit, TikTok, and
Instagram; YouTube remains on its established ingestion path. Query
Intelligence produces bounded platform-specific terms for YouTube and Reddit,
while TikTok and Instagram expand terms within their own connectors.

Performance scoring and query relevance are intentionally separate signals:
the processing pipeline calculates a cross-platform performance score, and
`analytics/relevance_engine.py` measures how well a result matches the scan
intent. This keeps rankings interpretable instead of mixing popularity and
relevance into one opaque number.
