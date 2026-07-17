# Deploy

Deployment artifacts for building and running the backend in production.

## Files

| File | Responsibility |
|------|---------------|
| `Dockerfile` | Multi-stage build: installs dependencies, copies application code, runs with gunicorn + uvicorn workers |
| `nginx/` | (reserved for future nginx-sidecar configuration) |

## Dockerfile Details

- Base: `python:3.11-slim`
- Server: `gunicorn` with 4 `uvicorn.workers.UvicornWorker` processes
- Health check: HTTP GET `/health` every 30s
- Exposed port: 80
