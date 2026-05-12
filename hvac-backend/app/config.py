"""Application configuration via Pydantic BaseSettings.

All values are read from environment variables (or .env file).
No secrets are hardcoded here.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV: str = Field(default="development")
    APP_DEBUG: bool = Field(default=False)
    APP_SECRET_KEY: str = Field(default="changeme-in-production")
    LOG_LEVEL: str = Field(default="INFO")
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:3000")

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://hvac:hvac_secret@localhost:5432/hvac_complaints"
    )
    DATABASE_SYNC_URL: str = Field(
        default="postgresql+psycopg2://hvac:hvac_secret@localhost:5432/hvac_complaints"
    )
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=10)

    # ── Redis / Celery ────────────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1")

    # ── LLM Provider (deepseek | qwen | gemini) ───────────────────────────
    LLM_PROVIDER: str = Field(default="deepseek")

    # DeepSeek — https://platform.deepseek.com/
    DEEPSEEK_API_KEY: str = Field(default="")
    DEEPSEEK_MODEL: str = Field(default="deepseek-chat")
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com")

    # Qwen / Alibaba DashScope — https://dashscope-intl.aliyuncs.com/
    QWEN_API_KEY: str = Field(default="")
    QWEN_MODEL: str = Field(default="qwen-plus")
    QWEN_BASE_URL: str = Field(default="https://dashscope-intl.aliyuncs.com/compatible-mode/v1")

    # Google Gemini (backward compat aliases) — https://aistudio.google.com/
    GOOGLE_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash-lite")
    GEMINI_BASE_URL: str = Field(default="https://generativelanguage.googleapis.com/v1beta/openai/")

    # ── Encryption ────────────────────────────────────────────────────────────
    RAW_TEXT_ENCRYPTION_KEY: str = Field(default="")
    PII_ENCRYPTION_KEY: str = Field(default="")
    RAW_TEXT_RETENTION_DAYS: int = Field(default=90)

    # ── ML Model ──────────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = Field(default="paraphrase-multilingual-MiniLM-L12-v2")
    EMBEDDING_MODEL_VERSION: str = Field(default="v1.0")
    EMBEDDING_DIM: int = Field(default=384)
    EMBEDDING_CACHE_TTL_SECONDS: int = Field(default=86400)

    # ── UMAP / Clustering ─────────────────────────────────────────────────────
    UMAP_RANDOM_STATE: int = Field(default=42)
    UMAP_N_COMPONENTS_CLUSTER: int = Field(default=50)
    UMAP_N_COMPONENTS_VIZ: int = Field(default=2)
    HDBSCAN_MIN_CLUSTER_SIZE: int = Field(default=15)
    CLUSTER_FINGERPRINT_THRESHOLD: float = Field(default=0.2)

    # ── Sentiment Thresholds (VADER compound score boundaries) ───────────────
    SENTIMENT_HIGH_THRESHOLD: float = Field(default=-0.5)
    SENTIMENT_CRITICAL_THRESHOLD: float = Field(default=-0.8)

    # ── Alert Thresholds ──────────────────────────────────────────────────────
    EMERGING_CLUSTER_GROWTH_THRESHOLD: float = Field(default=0.5)
    CRITICAL_SENTIMENT_THRESHOLD: float = Field(default=-0.6)
    MIN_COMPLAINTS_FOR_ALERT: int = Field(default=10)

    # ── Celery Beat ───────────────────────────────────────────────────────────
    CLUSTER_JOB_CRON: str = Field(default="0 2 * * *")

    @field_validator("LLM_PROVIDER", mode="before")
    @classmethod
    def validate_llm_provider(cls, v: Any) -> str:
        lowered = str(v).lower().strip()
        allowed = {"deepseek", "qwen", "gemini"}
        if lowered not in allowed:
            raise ValueError(
                f"LLM_PROVIDER must be one of {sorted(allowed)}, got {v!r}"
            )
        return lowered

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> Any:
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
