# HVAC Complaint Intelligence System

[![GitHub repo](https://img.shields.io/badge/GitHub-Auxilus08%2FHVAC--Customer--Complaint--Intelligence--System-blue?logo=github)](https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

An end-to-end platform that ingests HVAC service complaints (English + Hinglish),
clusters them by semantic similarity, detects emerging fault patterns, and
generates LLM-authored advisories for service-quality leadership.

Compresses the typical **6–8 week manual pattern-detection cycle into under 24
hours**.

---

## Repository layout

```
HVAC/
├── hvac-backend/    FastAPI + Celery + Postgres/pgvector + Redis
├── hvac-ml/         Embeddings, UMAP, HDBSCAN, trend detection, advisory prompts
├── hvac-frontend/   React 18 + Vite + Tailwind dashboard
└── presentation/    Pitch deck (PptxGenJS) + judge Q&A
```

| Component | Stack |
|-----------|-------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0 async, Alembic, Celery, Redis |
| ML | sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`), UMAP, HDBSCAN, VADER |
| LLM | Google Gemini (`gemini-2.5-flash-lite`) for cluster labels + advisories |
| Database | PostgreSQL 16 + `pgvector` extension |
| Frontend | React 18, Vite, TailwindCSS, react-query, Plotly, Recharts |

---

## Prerequisites

You need the following installed on the host machine.

| Tool | Version | Linux | Windows |
|------|---------|-------|---------|
| Python | 3.11+ | distro package or pyenv | [python.org installer](https://www.python.org/downloads/) — tick "Add to PATH" |
| Node.js | 18+ | distro package or `nvm` | [nodejs.org installer](https://nodejs.org/) |
| Docker + Compose v2 | latest | Docker Engine + compose plugin | Docker Desktop (WSL2 backend) |
| Git | any recent | distro package | Git for Windows |
| `make` (optional) | — | distro package | Git Bash ships with `make`, or use WSL |

The fastest path on **Windows is to run everything inside WSL2 (Ubuntu)** —
the Linux instructions below apply unchanged once you are inside the WSL
shell. The "Windows native" sections only matter if you are deliberately
avoiding WSL.

---

## 1. Get the code

```bash
git clone https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System.git HVAC
cd HVAC
```

---

## 2. Backend setup

### Option A — Docker Compose (recommended, identical on Linux & Windows)

This brings up Postgres, Redis, the FastAPI server, and all Celery workers.

**Linux / macOS / WSL:**
```bash
cd hvac-backend
cp .env.example .env
# edit .env — set GOOGLE_API_KEY (Gemini), SECRET_KEY, RAW_TEXT_ENCRYPTION_KEY
docker compose up --build
```

**Windows (PowerShell, native Docker Desktop):**
```powershell
cd hvac-backend
Copy-Item .env.example .env
notepad .env   # fill in keys
docker compose up --build
```

Generate the two required keys (paste the output into `.env`):

Linux / WSL:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Windows PowerShell:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Once the stack is up:
- API: <http://localhost:8000>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

### Option B — Local Python (no Docker)

You still need Postgres 16 with `pgvector` and Redis 7 running locally.
Install them via your package manager (Linux) or use a managed dev
container / WSL (Windows).

**Linux:**
```bash
cd hvac-backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip uv
uv pip install -e ".[dev]"

cp .env.example .env   # edit DATABASE_URL to point at your local Postgres

alembic upgrade head
python scripts/seed_db.py        # optional: synthetic complaints
uvicorn app.main:app --reload --port 8000
```

In separate terminals (same venv):
```bash
celery -A app.workers.celery_app.celery_app worker -Q embeddings -c 4
celery -A app.workers.celery_app.celery_app worker -Q sentiment  -c 8
celery -A app.workers.celery_app.celery_app worker -Q batch      -c 2
```

**Windows (PowerShell):**
```powershell
cd hvac-backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip uv
uv pip install -e ".[dev]"

Copy-Item .env.example .env   # edit DATABASE_URL

alembic upgrade head
python scripts\seed_db.py
uvicorn app.main:app --reload --port 8000
```

If PowerShell blocks the activation script, run once as admin:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Celery on Windows native does not support the default `prefork` pool — use
the `solo` pool or run workers inside WSL/Docker:
```powershell
celery -A app.workers.celery_app.celery_app worker -Q embeddings --pool=solo
```

### Common backend tasks (Linux/WSL via `make`)

```bash
make dev           # docker compose up --build
make migrate       # alembic upgrade head
make seed          # synthetic complaint seed
make test          # full test suite
make lint          # ruff + mypy
make down          # stop + drop volumes
```

On Windows native without `make`, run the equivalent command from the
Makefile directly (e.g. `docker compose up --build`).

---

## 3. ML package setup

`hvac-ml` is imported by the backend. In the Docker workflow it's already
installed inside the backend container. For local Python development:

**Linux / WSL:**
```bash
cd hvac-ml
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip uv
uv pip install -e ".[dev]"
pytest -m "not slow"           # fast tests
pytest -m slow                  # ML quality gates (silhouette, Jaccard)
```

**Windows PowerShell:**
```powershell
cd hvac-ml
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip uv
uv pip install -e ".[dev]"
pytest -m "not slow"
```

> **Note** — `umap-learn` requires `scikit-learn<1.7` because of the
> `force_all_finite` rename. The pyproject pins `scikit-learn==1.6.1`.

---

## 4. Frontend setup

**Linux / macOS / WSL:**
```bash
cd hvac-frontend
npm install
npm run dev      # http://localhost:5173
```

**Windows PowerShell:**
```powershell
cd hvac-frontend
npm install
npm run dev
```

The dev server proxies `/api/*` to `http://localhost:8000` (the backend).
Override via `VITE_API_BASE_URL` in `hvac-frontend/.env.local`:
```
VITE_API_BASE_URL=http://localhost:8000
```

Production build:
```bash
npm run build && npm run preview
```

---

## 5. Putting it together — first-run checklist

1. Backend up (`docker compose up --build` in `hvac-backend/`).
2. Migrations applied (`make migrate` or `alembic upgrade head`).
3. Seed data loaded (`make seed` or `python scripts/seed_db.py`).
4. Trigger the nightly batch once to populate clusters:
   ```bash
   make cluster
   # or
   python -c "from app.workers.celery_app import celery_app; \
              celery_app.send_task('app.workers.cluster_job.run_nightly_batch')"
   ```
5. Frontend up (`npm run dev` in `hvac-frontend/`).
6. Open <http://localhost:5173> — you should see clusters, alerts, and the
   trend dashboard.

Verify everything with:
```bash
cd hvac-backend
python scripts/verify_demo_data.py
```

---

## 6. Environment variables you must set

Edit `hvac-backend/.env` after copying from `.env.example`. The required keys:

| Variable | Purpose | How to get it |
|----------|---------|---------------|
| `GOOGLE_API_KEY` | Gemini cluster labels & advisories | <https://aistudio.google.com/app/apikey> |
| `SECRET_KEY` | App-level signing key (32+ chars) | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `RAW_TEXT_ENCRYPTION_KEY` | AES-256-GCM key for PII vault | `python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"` |
| `POSTGRES_*` | DB credentials | Set to whatever you want for local dev |

Everything else has sensible defaults.

---

## 7. Testing

```bash
# Backend
cd hvac-backend
make test                # full suite with coverage
make test-unit           # fast unit tests
pytest tests/compliance  # PII compliance (22 tests)

# ML quality gates (slow)
cd ../hvac-ml
pytest -m slow

# Frontend lint
cd ../hvac-frontend
npm run lint
```

---

## 8. Troubleshooting

**Docker on Windows says "WSL 2 not installed"** — install WSL2 from an
admin PowerShell:
```powershell
wsl --install
```
Then enable WSL2 backend in Docker Desktop settings.

**`pgvector` extension not found** — you must use the `pgvector/pgvector:pg16`
image (already configured in `docker-compose.yml`). If running Postgres
locally, install the extension via your package manager and run
`CREATE EXTENSION vector;` once.

**Celery worker exits immediately on Windows** — use `--pool=solo` or run
workers inside WSL/Docker.

**`ANTHROPIC_API_KEY` referenced in code** — this project migrated to
Gemini. Ignore Anthropic env vars; only `GOOGLE_API_KEY` is needed.

**Frontend shows "Network Error"** — confirm `VITE_API_BASE_URL` points
to a reachable backend and that CORS in `.env` includes your dev origin
(default `http://localhost:5173`).

**`umap-learn` install fails** — make sure `scikit-learn==1.6.1` is
installed before `umap-learn` (the pyproject already pins this).

**Apple Silicon / ARM** — sentence-transformers may need to download a
PyTorch wheel; this is handled automatically on first run (~400 MB).

---

## 9. Useful URLs (default ports)

| Service | URL |
|---------|-----|
| Backend API | <http://localhost:8000> |
| Swagger docs | <http://localhost:8000/docs> |
| Health check | <http://localhost:8000/health> |
| Frontend dashboard | <http://localhost:5173> |
| Postgres | `localhost:5432` |
| Redis | `localhost:6379` |
| Flower (Celery monitor) | <http://localhost:5555> *(if started via `make flower`)* |

---

## 10. Project documentation

- [`hvac-backend/README.md`](https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System/blob/main/hvac-backend/README.md) — backend architecture & API reference
- [`hvac-backend/DEMO_SCRIPT.md`](https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System/blob/main/hvac-backend/DEMO_SCRIPT.md) — 5-minute spoken demo
- [`hvac-backend/BRANCHING_STRATEGY.md`](https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System/blob/main/hvac-backend/BRANCHING_STRATEGY.md) — git workflow
- [`hvac-ml/README.md`](https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System/blob/main/hvac-ml/README.md) — ML pipeline internals
- [`hvac-frontend/README.md`](https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System/blob/main/hvac-frontend/README.md) — frontend structure
- [`presentation/hvac_judge_qa.md`](https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System/blob/main/presentation/hvac_judge_qa.md) — hackathon Q&A preparation

---

## License

Internal hackathon project. All rights reserved by the authors.

---

<p align="center">
  <a href="https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System">⭐ Star this repo</a> · 
  <a href="https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System/issues">Report a Bug</a> · 
  <a href="https://github.com/Auxilus08/HVAC-Customer-Complaint-Intelligence-System/pulls">Contribute</a>
</p>
