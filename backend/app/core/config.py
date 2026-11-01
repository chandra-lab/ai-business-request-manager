"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the AIBRM API and workers."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AIBRM"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    jwt_secret: str = Field(
        default="change-me-to-a-long-random-secret-at-least-32-chars",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    postgres_user: str = "aibrm"
    postgres_password: str = "aibrm_dev_password"
    postgres_db: str = "aibrm"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str | None = None

    rabbitmq_user: str = "aibrm"
    rabbitmq_password: str = "aibrm_dev_password"
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    celery_broker_url: str | None = None
    celery_result_backend: str = "rpc://"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    ai_provider: str = "mock"
    anthropic_api_key: str = ""
    # Official Claude Haiku 5.5 — set via ANTHROPIC_MODEL (or legacy ANTHROPIC_MODEL_ID)
    anthropic_model_id: str = Field(
        default="claude-haiku-5-5",
        validation_alias=AliasChoices("ANTHROPIC_MODEL", "ANTHROPIC_MODEL_ID", "anthropic_model_id"),
    )
    anthropic_max_tokens: int = 512
    # Groq OpenAI-compatible API — https://console.groq.com/docs/models
    groq_api_key: str = ""
    groq_model: str = Field(
        default="openai/gpt-oss-20b",
        validation_alias=AliasChoices("GROQ_MODEL", "groq_model"),
    )
    groq_max_tokens: int = Field(
        default=512,
        validation_alias=AliasChoices("GROQ_MAX_TOKENS", "groq_max_tokens"),
    )
    # Simulate provider outage (forces AI failure → manual review) for scenario testing
    ai_force_failure: bool = False

    # Confidence routing thresholds (Phase 4)
    routing_auto_assign_min: float = 0.85
    routing_review_min: float = 0.60
    outbox_max_attempts: int = 5

    seed_demo_password: str = "DemoPass123!"

    upload_dir: str = "uploads"
    upload_max_bytes: int = 10 * 1024 * 1024  # 10 MiB
    upload_allowed_content_types: str = (
        "application/pdf,"
        "image/png,image/jpeg,image/webp,"
        "text/plain,"
        "application/msword,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_be_long(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def broker_url(self) -> str:
        if self.celery_broker_url:
            return self.celery_broker_url
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}//"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_upload_content_types(self) -> set[str]:
        return {t.strip() for t in self.upload_allowed_content_types.split(",") if t.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
