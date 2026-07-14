# Backend

Python backend for the Content Intelligence Platform. Built with FastAPI, SQLite, and Groq AI.

## Architecture

```
api/           HTTP endpoints, auth, request validation
core/          Shared infrastructure (config, database, queries)
pipeline/      ETL: ingest → process → enrich → store
enrichment/    AI layer (Groq LLM client + analysis)
connectors/    Platform adapters (YouTube, Reddit, TikTok, Instagram)
analytics/     Scoring engines (trend velocity, hooks, relevance)
services/      Cross-cutting orchestration (query intelligence)
deploy/        Dockerfile, nginx config
```

## Dependency Flow

```
core  (no deps on other packages)
  ↑
pipeline  →  enrichment
  ↑
api  (consumes all above)
connectors  →  core, pipeline, services, analytics
analytics   →  connectors (models), core
services    →  (standalone)
```

## Running

```bash
# Inside Docker (recommended)
docker compose up -d --build

# Directly
cd backend && pip install -r requirements.txt && uvicorn api.api:app --reload
```
