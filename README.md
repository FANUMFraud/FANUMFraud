# FANUMFraud

## Our team

### Patryk Jurak
### Maksymilian Wójcik
### Grzegorz Makowski
### Tomasz Zając
### Michał Karwacki

---

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
  - article analysis (LLM extraction + deterministic scoring + heuristic fallback),
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
- Online data:
  - company registry is synchronized from public online records (GLEIF),
  - watchlist companies are always bootstrapped (including InPost, ORLEN, zondacrypto, Żabka, Nestle and others),
  - RSS crawler collects live publications from business/news sources,
  - startup bootstrap can run ingest + processing immediately,
  - scheduler keeps both company registry and articles refreshed.

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

## Article scoring model (v2.1)

- LLM is used only for structured extraction (`events`, `certainty`, `companies`, `evidence`, `keywords`).
- Final `risk_score` is computed in backend by a deterministic formula (no direct trust in model-provided score).
- Scoring uses calibrated weighted components: category severity, event certainty ladder, company role context, sentiment and text modifiers.
- If LLM extraction is incomplete, lexical backstop logic from article text prevents obvious risk underestimation.
- API response includes `score_breakdown` and `algorithm_version` for auditability.
- Regression calibration cases are covered in `backend/tests/test_scoring_calibration.py` and `backend/tests/fixtures/article_calibration_cases.json`.

## Quick start (Docker)

### 1) Optional env file

Docker Compose has safe local defaults, so `.env` is optional for online mode.

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

COMPANY_SYNC_ON_STARTUP=true
COMPANY_SYNC_LIMIT=300
COMPANY_SYNC_INTERVAL_HOURS=24
COMPANY_REGISTRY_COUNTRY=PL
COMPANY_REGISTRY_CATEGORY=GENERAL
WATCHLIST_BOOTSTRAP_ON_STARTUP=true
WATCHLIST_FEEDS_ENABLED=true
PIPELINE_BOOTSTRAP_ON_STARTUP=true
INGEST_INTERVAL_MINUTES=15
PROCESS_INTERVAL_MINUTES=5
```

Notes:
- `OPENROUTER_API_KEY` is optional. Without it, analyzer uses heuristic fallback.
- Do not commit `.env`.

### 2) Run stack with online data bootstrap

```bash
docker compose up --build
```

On startup the API:
- syncs companies from an online registry,
- ingests fresh RSS articles,
- processes pending risk-related articles.

You can tune limits and intervals using `.env` variables from `.env.example`.

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

## Useful manual pipeline commands

From `backend/`:

```bash
python -c "from pipeline.company_registry import sync_companies_from_registry; print(sync_companies_from_registry(limit=300))"
python -c "from pipeline.watchlist import ensure_watchlist_companies; print(ensure_watchlist_companies())"
python -c "from pipeline.ingest import run_ingest; print(run_ingest())"
python -c "from pipeline.processor import process_pending_articles; print(process_pending_articles())"
```

## API overview

Core endpoints:

- `GET /` - health
- `GET /companies` - list companies (worst first)
- `GET /companies/search?q=...` - fuzzy company search
- `POST /companies` - create company
- `POST /companies/sync/online` - sync registry from online source
- `POST /companies/watchlist/bootstrap` - force watchlist bootstrap
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
python -m pytest tests/test_scorer.py tests/test_anomaly_detector.py tests/test_analyzer_parser.py tests/test_scoring_calibration.py
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
- online registry synchronization + live RSS pipeline,
- article analysis,
- scoring history,
- company-linked article view,
- frontend/backend risk semantics alignment,
- category normalization for consistent dashboard reporting.

Planned next iterations:
- optional auth / role model
- stronger observability and data quality dashboards
- richer market-data integrations (eg stock movement context)
