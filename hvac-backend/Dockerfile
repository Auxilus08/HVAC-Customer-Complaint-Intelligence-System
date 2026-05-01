# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed to compile C extensions (psycopg2, hdbscan, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, deterministic dependency resolution
RUN pip install --no-cache-dir uv==0.2.18

# Copy dependency manifest only — maximise Docker layer cache
COPY pyproject.toml .

# Install all production + dev deps into an isolated venv
RUN uv venv /app/venv && \
    . /app/venv/bin/activate && \
    uv pip install --no-cache ".[dev]"

# Download spaCy model into the venv so it ships with the image
RUN . /app/venv/bin/activate && \
    python -m spacy download en_core_web_sm

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system libraries only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the fully built venv from the builder stage
COPY --from=builder /app/venv /app/venv

# Copy application source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY scripts/ ./scripts/

# Create non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appgroup /app

USER appuser

# Make the venv's binaries the default Python
ENV PATH="/app/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
