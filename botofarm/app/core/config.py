"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables or .env file.

    Attributes:
        database_url: Async-compatible SQLAlchemy database URL.
        secret_key: Secret key used to sign JWT tokens.
        algorithm: JWT signing algorithm.
        access_token_expire_minutes: Token lifetime in minutes.
        lock_ttl_seconds: How long a user lock remains valid before it expires.
        metrics_token: Static bearer token required to access ``/metrics``.
            When empty, the endpoint is blocked entirely from non-localhost
            callers.
        cors_origins: Comma-separated list of allowed CORS origins.
    """

    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    lock_ttl_seconds: int = 300
    metrics_token: str = ""
    cors_origins: list[str] = ["http://localhost"]


settings = Settings()  # type: ignore[call-arg]
