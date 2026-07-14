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

RUN mkdir -p /app/data

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import requests; r=requests.get('http://localhost:80/health'); r.raise_for_status()" || exit 1

CMD ["gunicorn", "api.api:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:80"]
