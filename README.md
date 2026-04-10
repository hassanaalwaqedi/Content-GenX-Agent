# Content Intelligence Platform — Backend API

> **GenX Leadership Academy** — Production-grade AI-powered content intelligence engine that identifies high-performing content across YouTube and Reddit, extracts transcripts, and enriches videos with strategic LLM insights.

## 📋 Project Scope

**The backend API is the core deliverable.** It is a fully self-contained, production-ready service that can be consumed by _any_ frontend, mobile app, or data pipeline.

A **React dashboard** is included as a _bonus visualization layer_ to demonstrate the backend capabilities in action. The company can:

- ✅ **Use the backend only** — integrate the REST API into your own frontend, BI tool, or data workflow
- ✅ **Use both** — the included React dashboard is fully functional and production-hosted
- ✅ **Replace the frontend** — the API is self-documented (`/docs`) and works with any HTTP client

### Getting Started (2 API Keys Only)

The entire platform runs with just **two API keys**:

| Key | Required | Free Tier | Get It |
|-----|----------|-----------|--------|
| `YOUTUBE_API_KEY` | ✅ Yes | 10,000 units/day | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |
| `GROQ_API_KEY` | 🔶 Recommended | 14,400 req/day | [Groq Console](https://console.groq.com/keys) |

> Reddit API credentials are optional and only needed if you want Reddit content alongside YouTube.

---

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐
│  YouTube    │     │   Reddit    │
│  Data API   │     │  OAuth API  │
└──────┬──────┘     └──────┬──────┘
       │                   │
       ▼                   ▼
┌──────────────────────────────────┐
│        Data Ingestion            │  ← Step 1: Collect raw content
│  ingestion.py + reddit_ingestion │
└──────────────┬───────────────────┘
               ▼
┌──────────────────────────────────┐
│     Processing & Scoring         │  ← Step 2: Clean, score, filter
│        processing.py             │
│  engagement_rate + recency +     │
│  log(views) → composite score    │
└──────────────┬───────────────────┘
               ▼
┌──────────────────────────────────┐
│       AI Enrichment              │  ← Step 3: LLM-powered analysis
│      ai_enrichment.py            │
│  Target audience · Strategic     │
│  advice · Content gaps · Topics  │
└──────────────┬───────────────────┘
               ▼
┌──────────────────────────────────┐
│    Transcript Extraction         │  ← Step 4: YouTube captions
│       transcripts.py             │
│  Multi-language · Auto-generated │
└──────────────┬───────────────────┘
               ▼
┌──────────────────────────────────┐
│      SQLite Database             │  ← Step 5: Persist & index
│        database.py               │
│  WAL mode · Upsert · Migrations  │
└──────────────┬───────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐   ┌──────────────┐
│  FastAPI     │   │  React 19    │
│  REST API    │   │  Dashboard   │
│  (Backend)   │   │  (Bonus)     │
└─────────────┘   └──────────────┘
```

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/hassanaalwaqedi/Content-GenX-Agent.git
cd Content-GenX-Agent

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
.\venv\Scripts\activate          # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — only two keys needed:
#   YOUTUBE_API_KEY=your_key_here      (required)
#   GROQ_API_KEY=your_key_here         (recommended)

# 5. Run the pipeline (ingests, scores, enriches, extracts transcripts)
python main.py

# 6. Start the backend API
uvicorn api:app --reload
# Swagger docs → http://localhost:8000/docs
```

### (Optional) Start the Dashboard

```bash
cd frontend
npm install
npm run dev
# Dashboard → http://localhost:5173
```

---

## Live Demo

| Component | URL | Status |
|-----------|-----|--------|
| **Backend API** | `https://d3tcfetguww88w.cloudfront.net` | ✅ Live |
| **Swagger Docs** | `https://d3tcfetguww88w.cloudfront.net/docs` | ✅ Live |
| **Dashboard** (bonus) | `https://genxagent-f420f.web.app` | ✅ Live |

> **Infrastructure**: Backend hosted on AWS (Elastic Beanstalk + CloudFront HTTPS). Dashboard on Firebase Hosting.

---

## API Documentation

Interactive docs available at `/docs` (Swagger) or `/redoc` (ReDoc).

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System health check with DB status |
| `GET` | `/videos/top?niche=...&days=30` | Top-scoring videos per niche |
| `GET` | `/videos/trending?days=7` | Fastest-growing content |
| `GET` | `/videos/{video_id}` | Full detail with transcript + AI insights |
| `GET` | `/creators/top?min_videos=2` | Top creators by aggregate score |
| `GET` | `/stats` | Database-wide statistics + platform breakdown |
| `GET` | `/stats/transcripts` | Transcript coverage metrics |
| `POST` | `/pipeline/run` | Trigger pipeline (background, mutex-locked) |
| `GET` | `/pipeline/history` | Pipeline run audit log |

### Example Queries

```bash
# Top 10 AI videos from the last 7 days
curl "https://d3tcfetguww88w.cloudfront.net/videos/top?niche=AI+for+business&days=7&limit=10"

# Fastest-growing content
curl "https://d3tcfetguww88w.cloudfront.net/videos/trending?days=7&limit=20"

# Top creators
curl "https://d3tcfetguww88w.cloudfront.net/creators/top?limit=20&min_videos=2"
```

---

## Key Design Decisions

| Decision | Rationale | Tradeoffs |
|----------|-----------|-----------|
| **YouTube API** over scraping | Reliable, structured data. Google's ToS explicitly allow API usage | Limited to 10,000 units/day. Sufficient for daily batches of 150+ videos per niche |
| **Reddit API** as second platform | Free, rich text content. Subreddits map directly to our "niche" concept | Requires OAuth2 app registration; approval may take 1-2 days |
| **SQLite** over PostgreSQL | Zero-config deployment, WAL mode handles concurrent reads. Schema is PostgreSQL-compatible for easy migration | Single-writer limitation. Mitigated with pipeline mutex lock |
| **Groq API** (Llama 3.3 70B) over OpenAI | 10x faster inference (<500ms per call), generous free tier | Smaller context window. Mitigated by enriching only top N videos per niche |
| **Exponential decay** for recency | Smooth degradation vs. hard time windows. 2-day-old video scores ~0.95, 30-day-old scores ~0.5 | Configurable half-life parameter |
| **Circuit breaker** pattern | Prevents cascading failures when Groq API is down or rate-limited | Falls back to rule-based topic extraction (~80% accuracy vs ~95% with LLM) |
| **youtube-transcript-api** for transcripts | No API key needed, supports auto-generated + manual captions in 6 languages | YouTube rate-limits aggressive usage. Mitigated with throttled requests |

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
- **Filtering**: Videos with < 1,000 views or < 2% engagement rate are excluded

All weights and thresholds are configurable via environment variables.

---

## Project Structure

```
content-intelligence-agent/
├── api.py                   # FastAPI REST application (core deliverable)
├── main.py                  # Pipeline orchestrator (5-step ETL)
├── config.py                # Pydantic Settings with .env loading
├── ingestion.py             # YouTube Data API v3 client
├── reddit_ingestion.py      # Reddit OAuth2 API client
├── processing.py            # Scoring engine (views + engagement + recency)
├── ai_enrichment.py         # Groq LLM integration with circuit breaker
├── transcripts.py           # YouTube transcript extraction (multi-language)
├── database.py              # SQLite persistence + auto-migration
├── queries.py               # Analytical query layer
├── scheduler.py             # Daily automation with graceful shutdown
├── requirements.txt         # Pinned dependencies
├── Dockerfile               # Production container image
├── Procfile                 # Process definition for PaaS platforms
├── .github/workflows/ci.yml # GitHub Actions CI (tests on push/PR)
├── tests/                   # 106 automated tests
│   ├── test_processing.py       # 17 tests — scoring, normalization, recency
│   ├── test_database.py         # 16 tests — schema, upserts, locking
│   ├── test_enrichment.py       # 11 tests — circuit breaker, rate limits
│   ├── test_api.py              # 15 tests — endpoint contracts
│   ├── test_api_endpoints.py    # 32 tests — full API integration
│   ├── test_config.py           #  8 tests — settings validation
│   └── test_reddit_ingestion.py #  7 tests — Reddit integration
├── frontend/                # (Bonus) React 19 + Vite dashboard
│   ├── src/pages/               # Dashboard, TopVideos, Trending, etc.
│   ├── src/api/client.js        # API wrapper
│   └── src/api/export.js        # PDF report generation
├── .env.example             # Environment variable template
└── .gitignore
```

---

## Testing

```bash
# Run the full test suite (106 tests)
python -m pytest tests/ -v

# Run specific module
python -m pytest tests/test_processing.py -v

# CI: Tests run automatically on every push/PR via GitHub Actions
```

**Test coverage**: 106 tests across 7 modules covering scoring logic, database operations, AI enrichment (circuit breaker, rate limits), API endpoint contracts, configuration validation, and Reddit integration.

---

## Database Schema

```sql
CREATE TABLE videos (
    video_id         TEXT PRIMARY KEY,
    platform         TEXT NOT NULL DEFAULT 'youtube',
    niche            TEXT NOT NULL,
    title            TEXT NOT NULL,
    description      TEXT DEFAULT '',
    channel          TEXT DEFAULT '',
    thumbnail_url    TEXT DEFAULT '',
    published_at     TEXT DEFAULT '',
    views            INTEGER DEFAULT 0,
    likes            INTEGER DEFAULT 0,
    comments         INTEGER DEFAULT 0,
    engagement_rate  REAL DEFAULT 0.0,
    score            REAL DEFAULT 0.0,
    target_audience  TEXT DEFAULT 'Analysis pending',
    strategic_advice TEXT DEFAULT 'Analysis pending',
    content_gap      TEXT DEFAULT 'Analysis pending',
    transcript       TEXT DEFAULT '',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE pipeline_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    status           TEXT DEFAULT 'running',
    videos_ingested  INTEGER DEFAULT 0,
    videos_processed INTEGER DEFAULT 0,
    videos_enriched  INTEGER DEFAULT 0,
    videos_stored    INTEGER DEFAULT 0,
    elapsed_seconds  REAL,
    error_message    TEXT,
    triggered_by     TEXT DEFAULT 'scheduler'
);
```

---

## Configuration

All settings managed via `.env` with Pydantic validation:

| Variable | Default | Description |
|----------|---------|-------------|
| `YOUTUBE_API_KEY` | *(required)* | YouTube Data API v3 key |
| `GROQ_API_KEY` | *(optional)* | Groq API key for LLM enrichment |
| `REDDIT_CLIENT_ID` | *(optional)* | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | *(optional)* | Reddit app client secret |
| `SCORE_WEIGHT_VIEWS` | `0.4` | Weight for log(views) in scoring |
| `SCORE_WEIGHT_ENGAGEMENT` | `0.35` | Weight for engagement rate |
| `SCORE_WEIGHT_RECENCY` | `0.25` | Weight for recency factor |
| `FILTER_MIN_VIEWS` | `1000` | Minimum views to include a video |
| `FILTER_MIN_ENGAGEMENT_RATE` | `0.02` | Minimum engagement rate |
| `PIPELINE_SCHEDULE_TIME` | `06:00` | Daily pipeline execution time (UTC) |

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.11+, FastAPI | REST API with auto-generated OpenAPI docs |
| **Database** | SQLite (WAL mode) | Embedded, indexed, migration-safe storage |
| **AI** | Groq API (Llama 3.3 70B) | Content analysis and strategic insights |
| **Data Sources** | YouTube Data API v3, Reddit OAuth2 | Video/post metadata and search |
| **Transcripts** | youtube-transcript-api | Caption extraction (no API key needed) |
| **Testing** | pytest (106 tests) | Automated test suite with CI |
| **CI/CD** | GitHub Actions | Tests on push/PR across Python 3.11-3.13 |
| **Deployment** | Docker, AWS Elastic Beanstalk | Production backend hosting |
| **Frontend** *(bonus)* | React 19, Vite | Interactive dashboard with dark/light theme |

---

## Limitations and Assumptions

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| YouTube API quota (10K units/day) | ~100 searches/day | Pipeline batches efficiently, results cached in DB |
| YouTube transcript rate limiting | Aggressive fetching gets blocked | Throttled requests (1-2s delay), backfill recovery script |
| Reddit API pending approval | Reddit ingestion ready but may be inactive | System gracefully skips Reddit when credentials absent |
| SQLite single-writer | Only one pipeline can run at a time | Database-level mutex lock prevents concurrent runs |
| Groq rate limits | May fail on large batches | Circuit breaker pattern, selective enrichment (top N only) |

---

## License

MIT
