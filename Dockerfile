# Multi-stage Dockerfile for the entire app
FROM python:3.12-slim AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS sync
CMD ["python", "-m", "app.scripts.sync_daily_offers"]

FROM base AS enrich
CMD ["python", "-m", "app.scripts.enrich_catalog_candidates"]

FROM base AS pipeline
CMD ["python", "-m", "app.scripts.run_catalog_candidate_pipeline"]

FROM base AS telegram-login
CMD ["python", "-m", "app.scripts.telegram_login"]

FROM base AS promotion
CMD ["python", "-m", "app.scripts.promote_catalog_candidate"]

FROM base AS listener
CMD ["python", "-m", "app.scripts.telegram_listener"]
