# hvac-backend

FastAPI + Celery backend for the HVAC Complaint Intelligence System.

## Purpose

Ingests 500+ daily complaints across 6 channels, strips PII, queues async embedding and sentiment tasks, runs nightly HDBSCAN clustering, and exposes REST APIs for the dashboard.

## Architecture

```
POST /complaints/upload  →  PII strip  →  DB write  →  Redis queue
                                                              ↓
                                              embedding_worker (Celery)
                                              sentiment_worker (Celery)
                                                              ↓
                                              cluster_job (nightly, 02:00 UTC)
                                               label_job   (Gemini API, Jaccard-gated)
                                              trend_job   (WoW growth, cost exposure)
```

## Quick Start

```bash
cp .env.example .env
# Fill in GOOGLE_API_KEY, ANTHROPIC_API_KEY, and RAW_TEXT_ENCRYPTION_KEY

docker compose up --build
```

The API is available at `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/unit          # fast, no DB required
pytest tests/integration   # requires test DB (SQLite in-memory via conftest)
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://hvac:hvac_secret@localhost:5432/hvac_complaints` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `GOOGLE_API_KEY` | Google API key for Gemini cluster labeling | _(required)_ |
| `GEMINI_MODEL` | Gemini model ID for labeling | `gemini-2.5-flash` |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude advisory service | _(required for advisories)_ |
| `CLAUDE_MODEL` | Claude model ID for advisories | `claude-sonnet-4-20250514` |
| `RAW_TEXT_ENCRYPTION_KEY` | Base64-encoded 32-byte AES key | _(required)_ |
| `EMBEDDING_MODEL` | SentenceTransformer model name | `paraphrase-multilingual-MiniLM-L12-v2` |
| `HDBSCAN_MIN_CLUSTER_SIZE` | Minimum cluster size for HDBSCAN | `15` |
| `EMERGING_CLUSTER_GROWTH_THRESHOLD` | WoW growth fraction to mark emerging | `0.5` |
| `CRITICAL_SENTIMENT_THRESHOLD` | VADER compound score for CRITICAL label | `-0.6` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Migrations

```bash
alembic upgrade head        # apply all migrations
alembic revision --autogenerate -m "describe change"   # generate new migration
```

## Key Design Decisions

- **< 100 ms ingestion**: DB write is synchronous; embedding/sentiment are async Celery tasks.
- **Two UMAP fits**: 50D for clustering, 2D for visualisation — never mixed.
- **PII stripping in exactly 2 places**: before DB write (`complaint_service.py`) and before any Claude API call (`advisory_service.py`, `label_job.py`).
- **Embedding cache**: SHA-256 text hash in Embedder's built-in in-memory cache prevents recomputing identical texts.
- **Jaccard gate**: LLM relabeling only when cluster fingerprint distance > 0.2 (reduces nightly calls to 1–3).
