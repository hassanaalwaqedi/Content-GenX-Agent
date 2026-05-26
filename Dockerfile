FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py .
COPY .env.example .env.example

# Copy connector and analytics packages
COPY connectors/ ./connectors/
COPY analytics/ ./analytics/
COPY services/ ./services/

# Create data directory
RUN mkdir -p /app/data

# Expose port (EB expects 80)
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import requests; r=requests.get('http://localhost:80/health'); r.raise_for_status()" || exit 1

# Run with uvicorn on port 80
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "80"]
