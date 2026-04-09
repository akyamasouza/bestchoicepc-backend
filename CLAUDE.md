# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI backend for a PC component comparison platform. It exposes catalog and ranking APIs for hardware components, syncs daily offers from Telegram into MongoDB, and generates CPU+GPU match recommendations from benchmark and price data.

## Commands

```bash
# Install dependencies
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

# Run the API locally
uvicorn app.main:app --reload

# Run the full test suite
pytest

# Run one test file
pytest tests/test_matches.py

# Run one test
pytest tests/test_matches.py::test_list_matches_returns_ranked_pairs

# Seed catalog collections
python -m app.scripts.seed_cpus
python -m app.scripts.seed_gpus
python -m app.scripts.seed_ssds
python -m app.scripts.seed_rams
python -m app.scripts.seed_motherboards
python -m app.scripts.seed_psus

# Build derived catalog data
python -m app.scripts.build_ssds
python -m app.scripts.build_rams
python -m app.scripts.build_motherboards
python -m app.scripts.build_psus

# Recalculate benchmark-based rankings
python -m app.scripts.recalculate_rankings --entity-type all
python -m app.scripts.recalculate_rankings --entity-type cpu
python -m app.scripts.recalculate_rankings --entity-type gpu

# Telegram auth, search, and offer sync
python -m app.scripts.telegram_login
python -m app.scripts.telegram_search "Ryzen 7 9800X3D"
python -m app.scripts.sync_daily_offers --entity-type cpu --limit 1

# Audit recent daily offer coverage for matches
python -m app.scripts.audit_daily_offers_matches
```

Python 3.12+. No linter, formatter, or type-check command is configured.

## Architecture

**Stack**: FastAPI + PyMongo + Pydantic v2 + Telethon.

**Entry point**: `app/main.py` creates the app, configures structured logging, registers global error handlers, wires CORS, and mounts routers.

### Request and data flow

- **Routes (`app/routes/`)** keep FastAPI concerns thin. They use `Depends()` to assemble repositories and services, validate request-specific conditions, and translate domain results into response schemas.
- **Repositories (`app/repositories/`)** are the MongoDB access layer. The component repositories are built by composing small strategy objects (`PagedQueryStrategy`, `RankingQueryStrategy`, `CandidateQueryStrategy`) instead of embedding query logic directly in each endpoint.
- **Services (`app/services/`)** hold business rules in framework-independent code. Core examples:
  - `MatchService` evaluates CPU+GPU pairs using `MatchScoringPolicy` and `MatchReasonBuilder`.
  - `DailyOfferSyncService` runs the Telegram ingestion pipeline: catalog lookup -> Telegram search -> offer parsing -> entity validation -> Mongo upsert.
  - Ranking services calculate derived ranking fields from raw benchmark inputs.
- **Schemas (`app/schemas/`)** are transport models only. Service-layer objects are usually frozen dataclasses instead of Pydantic models.

### Important patterns

- **Protocol-based Mongo abstractions**: repositories depend on `CollectionProtocol` / `CursorProtocol`, so tests can use simple fakes instead of a live database.
- **Dependency override testing**: route tests usually instantiate fake repositories/services and inject them with `app.dependency_overrides`; service tests call the service classes directly.
- **Derived data pipeline**: component documents store raw benchmark fields, ranking scripts/services derive `ranking.*`, and the match flow combines those rankings with recent `daily_offers` snapshots.
- **Offer ingestion is entity-aware**: Telegram syncing does not persist raw search results blindly; it parses the message, validates the matched entity name/SKU, and upserts into `daily_offers`.
- **Cross-cutting infrastructure**: `app/core/errors.py` standardizes API errors and `app/core/logging.py` adds JSON request/response logging with request IDs.

## Data and configuration

- MongoDB collections are accessed through `app/core/database.py`, which keeps a cached singleton `MongoClient` and exposes collection-specific dependency helpers.
- Settings live in `app/core/config.py` and read from `.env`. The code accepts both legacy and current env names for Mongo config (`DB_URI`/`MONGO_URI`, `MONGODB_DATABASE`/`MONGO_DATABASE`).
- Telegram workflows require `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and usually `TELEGRAM_DEFAULT_CHANNEL`; session data is stored at `TELEGRAM_SESSION_PATH`.
- `daily_offers` uses a unique compound index on business date + entity + store, so sync jobs are designed around idempotent upserts.

## Testing

- Tests are synchronous `pytest` tests under `tests/`.
- API tests use `fastapi.testclient.TestClient` with dependency overrides.
- Most unit tests run against fakes or pure services; a real MongoDB instance is typically not required for the suite.