.PHONY: install dev down migrate migration seed cluster test test-unit test-integ \
        lint format worker-embed worker-sent flower logs shell check-pii \
        clean help

# ── Colours ───────────────────────────────────────────────────────────────────
CYAN  := \033[36m
RESET := \033[0m

# ── Default target ────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "$(CYAN)HVAC Backend — available make targets$(RESET)"
	@echo "──────────────────────────────────────────────────────"
	@echo "  $(CYAN)install$(RESET)       Install all deps + pre-commit hooks"
	@echo "  $(CYAN)dev$(RESET)           docker compose up --build (full stack)"
	@echo "  $(CYAN)down$(RESET)          docker compose down -v (destroy volumes)"
	@echo "  $(CYAN)migrate$(RESET)       Run alembic upgrade head"
	@echo "  $(CYAN)seed$(RESET)          Seed DB with synthetic complaints"
	@echo "  $(CYAN)cluster$(RESET)       Trigger nightly batch cluster job"
	@echo "  $(CYAN)migration m=...$(RESET) Generate migration: make migration m='add index'"
	@echo "  $(CYAN)test$(RESET)          Run all tests with coverage"
	@echo "  $(CYAN)test-unit$(RESET)     Run unit tests only"
	@echo "  $(CYAN)test-integ$(RESET)    Run integration tests only"
	@echo "  $(CYAN)lint$(RESET)          ruff check + mypy"
	@echo "  $(CYAN)format$(RESET)        ruff format ."
	@echo "  $(CYAN)worker-embed$(RESET)  Start embedding Celery worker (local)"
	@echo "  $(CYAN)worker-sent$(RESET)   Start sentiment Celery worker (local)"
	@echo "  $(CYAN)flower$(RESET)        Start Flower monitoring UI"
	@echo "  $(CYAN)logs$(RESET)          Tail backend container logs"
	@echo "  $(CYAN)shell$(RESET)         Open Python shell inside backend container"
	@echo "  $(CYAN)check-pii$(RESET)     Run PII audit script"
	@echo "  $(CYAN)clean$(RESET)         Remove all build/cache artefacts"
	@echo ""

# ── Installation ──────────────────────────────────────────────────────────────
install:
	@echo "$(CYAN)Installing dependencies...$(RESET)"
	pip install uv --quiet
	uv pip install -e ".[dev]"
	@echo "$(CYAN)Installing pre-commit hooks...$(RESET)"
	pre-commit install
	pre-commit install --hook-type commit-msg
	@echo "$(CYAN)Done. Run 'make dev' to start the stack.$(RESET)"

# ── Docker ────────────────────────────────────────────────────────────────────
dev:
	@echo "$(CYAN)Starting full stack...$(RESET)"
	docker compose up --build

dev-bg:
	docker compose up --build -d
	@echo "$(CYAN)Stack running in background. Run 'make logs' to follow.$(RESET)"

down:
	@echo "$(CYAN)Stopping and removing containers + volumes...$(RESET)"
	docker compose down -v --remove-orphans

# ── Database migrations ───────────────────────────────────────────────────────
migrate:
	@echo "$(CYAN)Running alembic upgrade head...$(RESET)"
	alembic upgrade head

migration:
	@if [ -z "$(m)" ]; then \
		echo "Usage: make migration m='describe the change'"; \
		exit 1; \
	fi
	@echo "$(CYAN)Generating migration: $(m)$(RESET)"
	alembic revision --autogenerate -m "$(m)"

# ── Seed / manual pipeline trigger ───────────────────────────────────────────
seed:
	@echo "$(CYAN)Seeding database with synthetic complaints...$(RESET)"
	python scripts/seed_db.py

cluster:
	@echo "$(CYAN)Triggering nightly batch cluster job...$(RESET)"
	python -c "\
from app.workers.celery_app import celery_app; \
result = celery_app.send_task('app.workers.cluster_job.run_nightly_batch'); \
print('Task queued:', result.id)"

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	@echo "$(CYAN)Running all tests...$(RESET)"
	pytest tests/ -v

test-unit:
	@echo "$(CYAN)Running unit tests...$(RESET)"
	pytest tests/unit/ -v --no-cov

test-integ:
	@echo "$(CYAN)Running integration tests...$(RESET)"
	pytest tests/integration/ -v

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	@echo "$(CYAN)Running ruff check...$(RESET)"
	ruff check .
	@echo "$(CYAN)Running mypy...$(RESET)"
	mypy app/

format:
	@echo "$(CYAN)Formatting with ruff...$(RESET)"
	ruff format .
	ruff check --fix .

check-pii:
	@echo "$(CYAN)Running PII strip audit...$(RESET)"
	python scripts/check_pii_coverage.py

# ── Celery workers (local, no Docker) ────────────────────────────────────────
worker-embed:
	@echo "$(CYAN)Starting embedding worker...$(RESET)"
	celery -A app.workers.celery_app.celery_app worker \
		--queues=embeddings \
		--concurrency=4 \
		--loglevel=info \
		--hostname=embed@%h

worker-sent:
	@echo "$(CYAN)Starting sentiment worker...$(RESET)"
	celery -A app.workers.celery_app.celery_app worker \
		--queues=sentiment \
		--concurrency=8 \
		--loglevel=info \
		--hostname=sentiment@%h

# ── Monitoring ────────────────────────────────────────────────────────────────
flower:
	@echo "$(CYAN)Starting Flower on :5555...$(RESET)"
	docker compose --profile monitoring up flower

# ── Container utilities ───────────────────────────────────────────────────────
logs:
	docker compose logs -f backend

shell:
	docker compose exec backend python -c "\
import asyncio; \
from app.db.session import get_session_factory; \
print('Session factory:', get_session_factory()); \
print('Type help() for Python help, or import your modules directly.')"

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "$(CYAN)Clean.$(RESET)"
