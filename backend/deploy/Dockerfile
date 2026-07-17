FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY core/ ./core/
COPY pipeline/ ./pipeline/
COPY enrichment/ ./enrichment/
COPY connectors/ ./connectors/
COPY analytics/ ./analytics/
COPY services/ ./services/
COPY .env.example .

RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/data \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import requests; r=requests.get('http://localhost:8000/health'); r.raise_for_status()" || exit 1

# SQLite supports concurrent reads but a single API process avoids competing
# schema initialization and write locks at container startup.
CMD ["gunicorn", "api.api:app", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
