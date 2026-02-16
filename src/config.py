"""ForensicValue AI — Configuration"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- LLM Providers ---
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    antigravity_proxy_url: str = Field(
        default="http://localhost:3000", alias="ANTIGRAVITY_PROXY_URL"
    )
    antigravity_enabled: bool = Field(default=False, alias="ANTIGRAVITY_ENABLED")
    openrouter_api_key: Optional[str] = Field(
        default=None, alias="OPENROUTER_API_KEY"
    )
    default_llm_provider: str = Field(
        default="gemini", alias="DEFAULT_LLM_PROVIDER"
    )

    # --- Databases ---
    postgres_user: str = Field(default="forensic", alias="POSTGRES_USER")
    postgres_password: str = Field(
        default="forensicvalue2026", alias="POSTGRES_PASSWORD"
    )
    postgres_db: str = Field(default="forensic_value", alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5433, alias="POSTGRES_PORT")

    redis_url: str = Field(default="redis://localhost:6380", alias="REDIS_URL")
    qdrant_url: str = Field(
        default="http://localhost:6333", alias="QDRANT_URL"
    )

    # --- Application ---
    secret_key: str = Field(
        default="change-this-to-random-string", alias="SECRET_KEY"
    )
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Data Sources ---
    screener_api_key: Optional[str] = Field(
        default=None, alias="SCREENER_API_KEY"
    )

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
