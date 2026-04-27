# FANUMFraud

Prototype system for monitoring company reputation based on media publications, focused on AML risk support.

This project was built for the Transparent Data hackathon challenge:
- collect and process media signals,
- detect risky context in articles,
- map risk to companies,
- keep score history in time,
- present results in a web dashboard.

## What is implemented

- Backend API in FastAPI with:
  - company registry,
  - article ingestion + scraping,
  - article analysis (LLM + heuristic fallback),
  - reputation scoring and anomaly detection endpoints,
  - scheduled pipeline jobs.
- Frontend dashboard in Next.js with:
  - company list + search,
  - company detail view,
  - score history chart,
  - category breakdown,
  - anomaly alert.
- Data layer:
  - PostgreSQL for core data,
  - Elasticsearch for fuzzy company search (with SQL fallback).
- Demo data:
  - Docker Compose runs `seed-demo` automatically,
  - seed creates 12 fictional companies, 1800 demo articles and score history points,
  - default seed is deterministic and safe to run multiple times,
  - optional random seed mode can generate a fresh demo variant.

## Architecture

- `frontend/` - Next.js app (React 19)
- `backend/` - FastAPI app + pipeline + scoring logic
- `docker-compose.yml` - local stack (api + postgres + redis + elasticsearch)

Main backend flow:
1. RSS crawler collects candidate URLs.
2. Scraper extracts article text.
3. Risk keyword pre-filter marks records as pending for analysis.
4. Processor analyzes pending articles and matches them to companies.
5. Score history is saved and `companies.current_score` is updated.

## Score semantics (important)

- `current_score` is a reputation score in range `0..100`.
- Higher score = better reputation (lower risk).
- UI risk buckets are aligned with backend logic:
  - `high risk`: score `< 45`
  - `medium risk`: score `< 75`
  - `low risk`: score `>= 75`

## Quick start (Docker)

### 1) Optional env file

Docker Compose has safe local defaults, so `.env` is optional for demo mode.

If you want to override settings or add an LLM key, create `.env` in project root based on `.env.example`:

```env
POSTGRES_USER=fanumfraud
POSTGRES_PASSWORD=fanumfraud
POSTGRES_DB=fanumfraud
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0
ELASTICSEARCH_URL=http://elasticsearch:9200

OPENROUTER_API_KEY=
```

Notes:
- `OPENROUTER_API_KEY` is optional. Without it, analyzer uses heuristic fallback.
- Do not commit `.env`.

### 2) Run stack with demo data

```bash
docker compose up --build
```

The `seed-demo` service runs automatically and populates PostgreSQL with fictional demo data.

Expected default seed size:
- 12 companies,
- 1800 articles,
- score history for demo signals and trend points.

### 3) Open apps

- API docs: `http://localhost:8000/docs`
- Frontend (if run separately): `http://localhost:3000`

## Local development (without Docker)

## Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend expects backend at `http://localhost:8000` by default (`NEXT_PUBLIC_API_URL`).

## Rerun demo seed manually

Stable default dataset:

```bash
docker compose run --rm seed-demo
```

Fresh random demo variant:

```bash
docker compose build seed-demo
docker compose run --rm seed-demo python scripts/seed_demo.py --seed random
```

If the database stack is fully stopped, start dependencies first:

```bash
docker compose up -d postgres elasticsearch
docker compose run --rm seed-demo python scripts/seed_demo.py --seed random
```

Reproducible custom variant:

```bash
docker compose run --rm seed-demo python scripts/seed_demo.py --seed 12345
```

Larger random dataset:

```bash
docker compose run --rm seed-demo python scripts/seed_demo.py --seed random --per-company 500
```

The seed is idempotent for generated demo articles: it removes previous generated demo articles/history and inserts a dataset for the selected seed.

## Useful manual pipeline commands

From `backend/`:

```bash
python -c "from pipeline.ingest import run_ingest; print(run_ingest())"
python -c "from pipeline.processor import process_pending_articles; print(process_pending_articles())"
```

## API overview

Core endpoints:

- `GET /` - health
- `GET /companies` - list companies (worst first)
- `GET /companies/search?q=...` - fuzzy company search
- `POST /companies` - create company
- `GET /companies/{company_id}` - company detail
- `GET /companies/{company_id}/score` - score timeline
- `GET /companies/{company_id}/articles` - articles linked to company via score history
- `GET /articles` - list articles with filters
- `GET /articles/{article_id}` - article detail
- `POST /articles/analyze` - analyze URL or raw content for one company context

Algorithm endpoints:

- `POST /algorithm/analyze`
- `POST /algorithm/score`
- `POST /algorithm/anomaly`

## Testing

Backend tests:

```bash
cd backend
python -m pytest tests/test_scorer.py tests/test_anomaly_detector.py tests/test_analyzer_parser.py
```

Frontend quality checks:

```bash
cd frontend
npm run lint
npm run build
```

## Current status

Implemented and integrated:
- company registry,
- media ingestion,
- large deterministic demo dataset,
- article analysis,
- scoring history,
- company-linked article view,
- frontend/backend risk semantics alignment,
- category normalization for consistent dashboard reporting.

Planned next iterations:
- optional auth / role model
- stronger observability and data quality dashboards
- richer market-data integrations (eg stock movement context)
