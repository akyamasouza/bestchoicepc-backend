# Multi-stage Dockerfile for the entire app
FROM python:3.12-slim AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS api
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker
COPY . .
CMD ["python", "-m", "app.workers.sync_worker"]  # Placeholder for worker entry

FROM base AS enricher
COPY . .
CMD ["python", "-m", "app.workers.enrich_worker"]  # Placeholder