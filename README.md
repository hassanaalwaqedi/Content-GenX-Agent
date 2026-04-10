# Content Intelligence Platform

> Production-grade data pipeline and REST API for discovering high-performing AI content on YouTube.

Built as a modular, extensible backend system that **ingests**, **scores**, **enriches with AI**, and **serves insights** — designed to run daily on autopilot.

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌────────────┐
│  YouTube    │────▶│  Processing  │────▶│ AI Enrichment  │────▶│  Database  │
│  Data API   │     │  & Scoring   │     │  (Groq LLM)    │     │  (SQLite)  │
└─────────────┘     └──────────────┘     └────────────────┘     └──────┬─────┘
                                                                       │
  ┌─────────────┐                        ┌────────────────┐           │
  │  Scheduler  │──── daily @ 06:00 ────▶│   Pipeline     │───────────┘
  │  (cron)     │                        │   Runner       │
  └─────────────┘                        └────────────────┘
                                                                       │
                                         ┌────────────────┐           │
                                         │   FastAPI      │◀──────────┘
                                         │   REST API     │
                                         └────────────────┘
                                           /health
                                           /videos/top
                                           /videos/trending
                                           /videos/{video_id}
                                           /creators/top
                                           /pipeline/run
                                           /pipeline/history
                                           /stats
```

### Data Flow

1. **Ingestion** (`ingestion.py`) — Queries YouTube Data API v3 with pagination, retry, and backoff
2. **Processing** (`processing.py`) — Computes engagement rate, applies exponential-decay recency scoring, min-max normalizes, and filters by configurable thresholds
3. **AI Enrichment** (`ai_enrichment.py`) — Sends titles/descriptions to Groq LLM for topic extraction, audience analysis, content format classification, and competitive insights. Falls back to rule-based extraction on failure
4. **Storage** (`database.py`) — Upserts into SQLite with WAL mode, idempotent `ON CONFLICT` logic, and indexed schema
5. **API** (`api.py`) — FastAPI with typed Pydantic response models, Swagger docs, and background pipeline triggering

---

## Quick Start

```bash
# 1. Clone and enter the project
cd content-intelligence-agent

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
.\venv\Scripts\activate          # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys:
#   YOUTUBE_API_KEY=your_key_here
#   GROQ_API_KEY=your_key_here

# 5. Run the pipeline
python main.py

# 6. Start the API
uvicorn api:app --reload
# Open http://localhost:8000/docs for Swagger UI
```

---

## Project Structure

```
content-intelligence-agent/
├── main.py              # Pipeline orchestrator (CLI entry point)
├── api.py               # FastAPI REST application
├── config.py            # Pydantic Settings with .env loading
├── ingestion.py         # YouTube Data API v3 client
├── processing.py        # Scoring engine (log-views + engagement + recency)
├── ai_enrichment.py     # Groq LLM integration with rate-limit handling
├── database.py          # SQLite persistence + pipeline audit table
├── queries.py           # Analytical query layer
├── scheduler.py         # Daily automation with graceful shutdown
├── requirements.txt     # Pinned dependencies
├── tests/
│   └── test_processing.py   # Unit tests for scoring logic
├── .env.example         # Environment variable template
└── .gitignore
```

---

## API Documentation

Once running, interactive docs are available at:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System health check with DB status |
| `GET` | `/videos/top?niche=...&days=30` | Top-scoring videos per niche |
| `GET` | `/videos/trending?days=7` | Fastest-growing content |
| `GET` | `/videos/{video_id}` | Full detail for a single video |
| `GET` | `/creators/top?min_videos=2` | Top creators by aggregate score |
| `GET` | `/stats` | Database-wide aggregate statistics |
| `POST` | `/pipeline/run` | Trigger pipeline (background, mutex-locked) |
| `GET` | `/pipeline/history` | Pipeline run audit log |

---

## Scoring Formula

Videos are scored using a weighted composite of three normalized signals:

```
score = 0.40 × norm(log(1 + views))
      + 0.35 × norm(engagement_rate)
      + 0.25 × recency_factor
```

Where:
- **`engagement_rate`** = `(likes + comments) / views`
- **`recency_factor`** = exponential decay with 30-day half-life (`e^(-ln2 × age/30)`)
- **`norm()`** = min-max normalization across the current batch

Weights and filter thresholds are fully configurable via environment variables.

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **SQLite** over PostgreSQL | Zero-config deployment, WAL mode handles concurrent reads. Schema is PostgreSQL-compatible for easy migration |
| **Groq** over OpenAI | 10x faster inference (< 500ms per call), free tier sufficient for daily batches |
| **Exponential decay** for recency | Mathematically smooth degradation vs. hard time windows. Half-life is configurable |
| **Rule-based fallback** | Ensures 100% enrichment coverage even when LLM rate limits are hit |
| **Pipeline audit table** | Every run is recorded with status, counts, and elapsed time for operational observability |
| **Pydantic models** at boundaries | Type safety at config, processing, and API layers catches issues before they reach storage |

---

## Configuration

All settings are managed via `.env` with Pydantic validation:

| Variable | Default | Description |
|----------|---------|-------------|
| `YOUTUBE_API_KEY` | *(required)* | YouTube Data API v3 key |
| `GROQ_API_KEY` | *(optional)* | Groq API key for LLM enrichment |
| `SCORE_WEIGHT_VIEWS` | `0.4` | Weight for log(views) in scoring |
| `SCORE_WEIGHT_ENGAGEMENT` | `0.35` | Weight for engagement rate |
| `SCORE_WEIGHT_RECENCY` | `0.25` | Weight for recency factor |
| `FILTER_MIN_VIEWS` | `1000` | Minimum views to include a video |
| `FILTER_MIN_ENGAGEMENT_RATE` | `0.02` | Minimum engagement rate |
| `PIPELINE_SCHEDULE_TIME` | `06:00` | Daily pipeline execution time (UTC) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Testing

```bash
# Run unit tests
python -m pytest tests/ -v

# Run integration test against live API
python test_api.py
```

---

## Tech Stack

- **Python 3.11+**
- **FastAPI** — async REST framework with auto-generated OpenAPI docs
- **Pydantic v2** — data validation, settings management, response models
- **SQLite** — embedded database with WAL mode and indexed schema
- **Groq API** — fast LLM inference (llama-3.3-70b-versatile)
- **requests** — HTTP client with retry/backoff via urllib3
- **schedule** — lightweight cron-style task scheduling

---

## License

MIT
