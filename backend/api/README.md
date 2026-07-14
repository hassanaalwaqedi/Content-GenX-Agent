# API Layer

FastAPI REST endpoints that expose the platform's intelligence to the frontend and external tools.

## Files

| File | Responsibility |
|------|---------------|
| `api.py` | All HTTP routes: health, videos, creators, trends, pipeline config CRUD, AI content generation |
| `auth.py` | JWT-based single-operator authentication with rate-limited login |

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | System health + database status |
| GET | `/videos/top` | Top-scoring videos per niche |
| GET | `/videos/trending` | Fastest-growing videos |
| GET | `/creators/top` | Top creators by aggregate score |
| POST | `/pipeline/run` | Trigger a data refresh |
| GET | `/pipeline/history` | Recent pipeline run audit log |
| POST | `/pipeline/config` | Save a custom pipeline configuration |

## Design

- Routes are thin — business logic lives in `pipeline/` and `core/`
- Pipeline runs execute in a background thread (non-blocking)
- Auth uses HttpOnly cookies for the dashboard and X-API-Key for programmatic access
