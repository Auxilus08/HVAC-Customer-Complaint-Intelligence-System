# HVAC Customer Complaint Intelligence System

End-to-end platform that ingests HVAC service complaints (English + Hinglish), clusters
them by semantic similarity, detects emerging fault patterns, and generates LLM-authored
advisories. Goal: compress 6–8 week manual pattern-detection cycles to under 24 hours.

## Repository layout

| Path | Purpose | Stack |
|------|---------|-------|
| [hvac-backend/](hvac-backend/) | API + workers + DB | Python 3.11, FastAPI, SQLAlchemy 2.0 async, Alembic, Celery, Redis, Postgres 16 + pgvector |
| [hvac-ml/](hvac-ml/) | ML pipeline (imported by backend) | sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`), UMAP, HDBSCAN, VADER |
| [hvac-frontend/](hvac-frontend/) | Dashboard | React 18, Vite, Tailwind, react-query, Plotly, Recharts |

**LLM provider is pluggable.** Set `LLM_PROVIDER` in `.env` to one of `deepseek`, `qwen`, or `gemini`. All three are accessed through the OpenAI Python SDK against each provider's compatible-mode endpoint, so the call sites are uniform. The factory lives at [hvac-backend/app/services/llm_client.py](hvac-backend/app/services/llm_client.py) — `get_llm_client() -> (OpenAI, model_name)`. Anthropic is no longer used; ignore any stale `ANTHROPIC_API_KEY` references.

| Provider | Default model | Base URL |
|----------|--------------|----------|
| `deepseek` | `deepseek-chat` | `https://api.deepseek.com` |
| `qwen` | `qwen3-vl-plus` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `gemini` | `gemini-2.5-flash-lite` | `https://generativelanguage.googleapis.com/v1beta/openai/` |

The legacy `google.generativeai` SDK path is preserved in [hvac-ml/pipeline/labeler.py](hvac-ml/pipeline/labeler.py) for backward compatibility — when the labeler is constructed without an injected `client`/`base_url` it falls back to that path. New call sites should always inject the client from `get_llm_client()`.

## Backend internals

- Entry: [hvac-backend/app/main.py](hvac-backend/app/main.py)
- HTTP routes: [hvac-backend/app/api/](hvac-backend/app/api/)
- ORM models: [hvac-backend/app/models/](hvac-backend/app/models/)
- Pydantic schemas: [hvac-backend/app/schemas/](hvac-backend/app/schemas/)
- Business logic: [hvac-backend/app/services/](hvac-backend/app/services/)
- Celery workers: [hvac-backend/app/workers/](hvac-backend/app/workers/) — queues: `embeddings`, `sentiment`, `batch`
- Migrations: [hvac-backend/alembic/](hvac-backend/alembic/)

## ML pipeline

Stage modules in [hvac-ml/pipeline/](hvac-ml/pipeline/): `embedder.py` → `clusterer.py` → `labeler.py` → `sentiment.py` → `trend_detector.py`.

`umap-learn` requires `scikit-learn<1.7` (the `force_all_finite` rename); pyproject pins `scikit-learn==1.6.1` — don't bump it.

## Frontend internals

- Entry: [hvac-frontend/src/main.jsx](hvac-frontend/src/main.jsx), [hvac-frontend/src/App.jsx](hvac-frontend/src/App.jsx)
- API client: [hvac-frontend/src/api/](hvac-frontend/src/api/)
- Components: [hvac-frontend/src/components/](hvac-frontend/src/components/)
- Dev server proxies `/api/*` → `http://localhost:8000`. Override via `VITE_API_BASE_URL` in `hvac-frontend/.env.local`.

## Common commands

Run from each subproject root.

### Backend ([hvac-backend/Makefile](hvac-backend/Makefile))

```bash
make dev              # docker compose up --build (full stack: api + workers + pg + redis)
make down             # stop stack and drop volumes
make migrate          # alembic upgrade head
make migration m='...' # autogenerate migration
make seed             # synthetic complaints
make cluster          # trigger nightly batch cluster job
make test             # fast tests (excludes slow + performance)
make test-unit        # unit only
make test-integ       # integration only
make test-compliance  # PII compliance suite (22 tests)
make test-slow        # ML quality gates (silhouette, Jaccard)
make lint             # ruff check + mypy
make format           # ruff format + --fix
make check-pii        # PII strip audit
make demo-check       # verify_demo_data.py
make flower           # Celery monitor at :5555
```

### ML

```bash
cd hvac-ml
pytest -m "not slow"  # fast
pytest -m slow        # quality gates
```

### Frontend

```bash
cd hvac-frontend
npm install
npm run dev           # :5173
npm run build && npm run preview
npm run lint
```

## Required environment

Edit `hvac-backend/.env` (copy from `.env.example`):

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | `deepseek`, `qwen`, or `gemini` — picks which key/model/base-URL trio gets used |
| `DEEPSEEK_API_KEY` / `QWEN_API_KEY` / `GOOGLE_API_KEY` | At least the active provider's key must be set |
| `SECRET_KEY` | App signing key (32+ chars) — `python -c "import secrets; print(secrets.token_hex(32))"` |
| `RAW_TEXT_ENCRYPTION_KEY`, `PII_ENCRYPTION_KEY` | AES-256-GCM keys (base64 32-byte) — `python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"` |
| `POSTGRES_*` | DB credentials |

## Default ports

| Service | URL |
|---------|-----|
| API | http://localhost:8000 (docs at `/docs`, health at `/health`) |
| Frontend | http://localhost:5173 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |
| Flower | http://localhost:5555 (when `make flower`) |

## Conventions and gotchas

- Repo root on this machine is owned by `root`; writing files at the top level needs sudo. The `.claude/` directory is owned by `anas` so Claude Code can write to it freely.
- Async SQLAlchemy 2.0 throughout the backend — use `AsyncSession`, not the sync API.
- Celery on Windows native needs `--pool=solo`; prefer Docker or WSL.
- pgvector requires the `pgvector/pgvector:pg16` image (already wired into compose). Bare Postgres needs `CREATE EXTENSION vector;`.
- PII handling is non-optional — there's a dedicated compliance test suite (`make test-compliance`) and a `check-pii` audit. Don't log raw complaint text outside the encrypted vault.
- Pre-commit hooks are installed via `make install`; don't bypass with `--no-verify`.

## More docs

- [hvac-backend/README.md](hvac-backend/README.md) — backend architecture & API reference
- [hvac-backend/DEMO_SCRIPT.md](hvac-backend/DEMO_SCRIPT.md) — 5-minute spoken demo
- [hvac-backend/BRANCHING_STRATEGY.md](hvac-backend/BRANCHING_STRATEGY.md) — git workflow
- [hvac-ml/README.md](hvac-ml/README.md) — ML pipeline internals
- [hvac-frontend/README.md](hvac-frontend/README.md) — frontend structure
- [README.md](README.md) — full setup walkthrough (Linux + Windows)
