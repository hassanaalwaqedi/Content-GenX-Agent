# Intelligent-Trends — Last Phase Master Change Document

**Date:** 17 July 2026
**Status:** Completed and verified locally
**Scope:** Product UI redesign, multi-platform intelligence, backend hardening, architecture cleanup, and operational readiness.

This document is the authoritative record of the most recent delivery phase.
It describes the implemented behavior, operational expectations, and remaining
constraints. It deliberately excludes passwords, tokens, and API keys.

## 1. Executive summary

The project was upgraded from a primarily YouTube-oriented trend dashboard into
a multi-platform content-intelligence application supporting YouTube, TikTok,
Instagram, and Reddit.

The work also addressed the main audit findings:

- authenticated and rate-limited sensitive operations;
- safer SQLite pipeline locking and container execution;
- a meaningful testing foundation;
- a smaller, domain-oriented API structure;
- structured logs, request IDs, versioned API aliases, backups, CI, and setup
  documentation.

The active backend is compatible with the existing frontend API paths. Existing
endpoints continue to work, and equivalent `/v1/...` aliases are now available.

## 2. Delivered user experience

### Dashboard and navigation

- Rebuilt the main Intelligence Center dashboard into the GenX dark analytics
  design system.
- Added a shared application layout, workspace switcher, platform navigation,
  authentication state, and dataset context.
- Dashboard metrics, live trends, opportunity cards, distribution charts, and
  insight signals now consume the active dataset instead of static mock data.
- A live-trend card opens the exact trend-member content through
  `GET /trends/videos`; it no longer redirects users to unrelated content.

### Top Content, Trending, and Creators

- Redesigned the Top Content page with filtering, featured content, ranked
  content cards, platform distribution, signal summaries, and export actions.
- Redesigned Trending as an analytical page with filters, trend momentum, chart
  and list views, keyword signals, and platform distribution.
- Redesigned Creator Intelligence with creator ranking, growth, engagement,
  opportunity-fit, platform leadership, and distribution views.
- Added specific rendering support for TikTok and Reddit records. TikTok
  thumbnail extraction now uses the normalized connector data when available;
  a visual placeholder remains only when an upstream platform does not return
  an image.

### Pipeline and Reddit Intelligence

- Redesigned the Intelligence Pipeline configuration and run-history screens.
- Added connector health status, selected platform/market summaries, dataset
  activation, and protected scan controls.
- Added a dedicated Reddit Intelligence page and sidebar entry with overview,
  trending subreddits, emerging discussions, pain points, sentiment,
  contributors, clusters, connector health, and opportunities.
- Platform selection in content views is respected end-to-end: selecting a
  platform requests and displays only content from that platform.

## 3. Platform ingestion and data behavior

### Connector model

- Introduced/extended a canonical `NormalizedContent` connector model so
  platform data has a common identity, author, content, engagement, source URL,
  thumbnail, and metadata shape before it reaches the legacy processing path.
- Retained a compatibility bridge to the existing `RawVideo` processing flow,
  avoiding a database or frontend-breaking migration.

### Query Intelligence

- Query expansion now creates platform-specific variants for YouTube, TikTok,
  Instagram, and Reddit.
- YouTube receives bounded plain-language search phrases.
- Reddit receives bounded plain-language variants and searches up to four
  variants, deduplicating returned posts rather than using just the first term.
- TikTok and Instagram retain their connector-level expansion and hashtag
  behavior, preventing duplicate expansion in the pipeline runner.

### Data quality and scoring

- The processing pipeline continues to generate the cross-platform performance
  score from views, engagement, and recency.
- Query relevance remains a separate, explainable signal: it measures whether
  content matches the scan intent. It is not combined invisibly with performance
  ranking.
- Reddit records are not discarded merely because an actor returns zero video
  views. The processing filter handles Reddit posts as a platform-specific case.
- Platform filters, active dataset scoping, source URLs, and metadata are
  carried through to content pages and Reddit analysis endpoints.

## 4. Backend architecture changes

### Route separation

`backend/api/api.py` was reduced from approximately 1,300 lines to 777 lines.
The following route domains are now independently owned:

| Module | Responsibility |
| --- | --- |
| `api/videos.py` | top content, trending videos, detail, transcript retrieval |
| `api/creators.py` | creator rankings, intelligence, rising creators, trend matching |
| `api/datasets.py` | dataset listing, active workspace, dataset activation |
| `api/reddit.py` | Reddit Intelligence read APIs |
| `api/system.py` | health, connector health, aggregate stats, transcript coverage |
| `api/schemas.py` | shared route response models |
| `api/api.py` | application setup plus pipeline, trends, and AI-generation legacy routes |

This was intentionally incremental: client URLs and payload shapes were kept
stable while route ownership was moved.

### API compatibility and versioning

- Existing unversioned endpoints remain supported, such as `/health` and
  `/videos/top`.
- The `V1PathPrefixMiddleware` maps `/v1/...` to the same stable routes, such
  as `/v1/health` and `/v1/videos/top`.
- API responses include an `X-Request-ID` value so a frontend error can be
  matched to its server log entry.

## 5. Security and stability improvements

### Authentication and access control

- JWT-based operator authentication protects sensitive write and costly
  endpoints, including pipeline scans, dataset activation, pipeline-config
  updates/deletions, transcript fetching, and AI content generation.
- Pipeline scans can alternatively use `X-API-Key` only when the optional
  server-to-server key is configured.
- Login attempts have local lockout protection.
- The admin credentials and JWT secret are environment-only configuration;
  `.env` files and local databases are excluded from version control.

### HTTP and configuration safety

- Browser CORS origins must be explicit; wildcard origins are rejected.
- A rolling per-client request limiter is active in the API middleware.
- Invalid log levels, wildcard CORS, an undersized JWT secret, or admin
  credentials without a persistent signing secret are rejected at configuration
  validation time.
- Runtime credentials are not recorded in this document or committed to Git.

### Pipeline/database safety

- Pipeline locks are acquired atomically with SQLite `BEGIN IMMEDIATE` to
  prevent two scans being accepted at the same time.
- A scan is reserved before its background worker starts and is recorded in
  pipeline history even if preflight fails.
- Stale running locks are cleaned during database initialization.
- Index-creation failures are logged and surfaced instead of being silently
  ignored.

## 6. Operations and deployment

### Logging and observability

- JSON logging is enabled by default through `LOG_JSON=true`.
- Request logs include request ID, method, route, status code, duration, and
  event name.
- Set `LOG_JSON=false` for readable local logs.

### Backups

- Added `python -m core.backup` to create a consistent SQLite snapshot using
  SQLite's online backup API.
- Backups default to `backend/backups/`, are ignored by Git, and are pruned
  according to `DATABASE_BACKUP_RETENTION_DAYS` (default: 14 days).
- `DATABASE_BACKUP_DIR` can point to a persistent mounted volume or other
  storage location. Schedule this command externally for production backups.

### Containers and CI

- Docker images avoid local environment files, SQLite databases, caches, and
  frontend dependencies through Docker ignore rules.
- The backend container runs as a non-root user and uses one worker because
  SQLite has a single-writer model.
- Docker Compose persists database data and points the frontend proxy at the
  backend service.
- CI runs backend compilation/tests and frontend lint/build checks.

## 7. Configuration additions

Add or review the following in `backend/.env` when deploying:

```env
# Observability
LOG_LEVEL=INFO
LOG_JSON=true

# Backup retention
DATABASE_BACKUP_DIR=backups
DATABASE_BACKUP_RETENTION_DAYS=14

# API protection
CORS_ALLOWED_ORIGINS=["https://your-production-domain.example"]
API_RATE_LIMIT_REQUESTS=180
API_RATE_LIMIT_WINDOW_SECONDS=60
```

Use real values only in the local or deployment environment. Do not place
tokens, passwords, or private URLs in source files, screenshots, or tickets.

## 8. Verification performed

The following checks passed after the last phase:

| Check | Result |
| --- | --- |
| Backend test suite | 21 passed |
| Backend compilation | passed |
| Authentication integration | passed |
| Pipeline preflight/lock integration | passed |
| Connector normalization and Reddit multi-query behavior | passed |
| JSON logging, API versioning, and backup behavior | passed |
| Frontend ESLint | passed |
| Frontend production build | passed |
| Docker Compose configuration | valid |
| Live `GET /health` | HTTP 200 |
| Live `GET /v1/videos/top` | HTTP 200 |

The frontend build reports a bundle-size advisory for its main production
bundle. It does not fail the build; code splitting is a future performance
optimization.

## 9. How to operate the updated system

### Start locally

```powershell
# Terminal 1
cd backend
python -m pip install -r requirements.txt
$env:PYTHONPATH=(Get-Location).Path
python -m uvicorn api.api:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

### Verify service health

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:8000/v1/videos/top
```

### Run checks before release

```powershell
$env:PYTHONPATH=(Join-Path (Get-Location) 'backend')
python -m pytest backend/tests -q

cd frontend
npm run lint
npm run build
```

## 10. Remaining constraints and recommended next work

These are known product/engineering constraints, not release blockers:

1. **SQLite scaling:** use PostgreSQL before running multiple backend workers
   or replicas.
2. **Rate limiting:** the current rate limiter is process-local. Move it to a
   gateway or shared store (for example Redis) when scaling horizontally.
3. **Backup delivery:** the project creates local snapshots; production needs a
   scheduled job that copies encrypted backups to durable off-host storage.
4. **Remaining legacy API domains:** pipeline configuration, trends, and AI
   generation remain in `api/api.py`; extract them incrementally after their
   public contracts receive dedicated integration tests.
5. **Bundle size:** split large frontend routes/components with dynamic imports
   to reduce first-load JavaScript.
6. **Platform data limitations:** thumbnail, metrics, and result quality are
   limited by the upstream YouTube/Apify actor response. The UI provides safe
   fallbacks but cannot create data absent from the source platform.
7. **Secret hygiene:** rotate any credentials that were ever pasted into chat,
   screenshots, history, or source control.

## 11. Acceptance conclusion

The last phase is complete. The product is now materially safer to operate,
better structured for future development, compatible with the existing UI and
API consumers, and has a tested path for backups, observability, and
multi-platform content intelligence.
