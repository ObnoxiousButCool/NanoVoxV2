"""Typed application configuration.

Every tunable value in the system is read here, from the environment or a ``.env``
file, and validated once at import of the settings object. Nothing else in the
codebase reads ``os.environ``.

Configuration is validated eagerly so a bad value fails at startup with an
explicit message rather than surfacing as an obscure error on first use.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.errors import ConfigurationError
from infrastructure.config.paths import (
    BACKEND_ROOT,
    DEFAULT_LOG_DIR,
    DEFAULT_RUBRIC_PATH,
    DEFAULT_TAXONOMY_PATH,
    default_database_url,
)

AppEnv = Literal["local", "dev", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["json", "text"]


class Settings(BaseSettings):
    """All backend configuration, sourced from the environment and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    app_env: AppEnv = "local"
    app_name: str = "NanoVox"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # --- Database ----------------------------------------------------------
    database_url: str = Field(default_factory=default_database_url)
    db_echo: bool = False

    # --- Analysis configuration --------------------------------------------
    taxonomy_path: Path = DEFAULT_TAXONOMY_PATH
    rubric_path: Path = DEFAULT_RUBRIC_PATH

    # --- Model providers ---------------------------------------------------
    llm_provider: str = "ollama"
    llm_timeout_seconds: float = Field(default=120.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=10)
    llm_max_output_tokens: int = Field(default=4096, ge=256, le=128_000)

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"

    # --- Logging -----------------------------------------------------------
    log_enabled: bool = True
    log_level: LogLevel = "INFO"
    log_dir: Path = DEFAULT_LOG_DIR
    log_format: LogFormat = "json"
    log_retention_days: int = Field(default=14, ge=1, le=365)
    log_to_console: bool = True
    log_llm_prompts: bool = False

    @field_validator("api_prefix")
    @classmethod
    def _prefix_must_be_rooted(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("API_PREFIX must start with '/'")
        return value.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def _database_must_be_async_sqlite(cls, value: str) -> str:
        # The persistence layer is written against the async SQLAlchemy API. A
        # synchronous URL would fail later, inside a request; catch it here.
        if not value.startswith("sqlite+aiosqlite:"):
            raise ValueError(
                "DATABASE_URL must use the async SQLite driver, "
                "e.g. sqlite+aiosqlite:///C:/path/to/nanovox.db"
            )
        return value

    @field_validator("llm_provider")
    @classmethod
    def _provider_is_normalised(cls, value: str) -> str:
        normalised = value.strip().lower()
        if not normalised:
            raise ValueError("LLM_PROVIDER must not be empty")
        return normalised

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, parsed from the comma-separated setting."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_file(self) -> Path | None:
        """On-disk location of the SQLite database, or ``None`` for in-memory."""
        _, _, location = self.database_url.partition("///")
        if not location or ":memory:" in location:
            return None
        return Path(location)

    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache the settings, translating validation failure into a domain error.

    Cached because configuration is immutable for the lifetime of the process;
    tests clear the cache explicitly.
    """
    try:
        return Settings()
    except PydanticValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigurationError(
            "Invalid backend configuration — the application cannot start.",
            detail=problems,
        ) from exc
