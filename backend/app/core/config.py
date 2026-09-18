"""Configuració de l'aplicació Sevalor Suite."""

from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paràmetres globals de configuració del servei."""

    PROJECT_NAME: str = "Sevalor Suite API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Base de Dades PostgreSQL (Asyncpg)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "sevalor"
    DATABASE_URL: str | None = None

    # Redis Cache & Broker
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6380
    REDIS_URL: str | None = None

    # Servei d'Intel·ligència Artificial Local Whisper (CPU-only INT8 Hetzner CPX21)
    WHISPER_URL: str = "http://localhost:8008"

    # LM Studio / LLM Local (API compatible OpenAI)
    LM_STUDIO_URL: str = "http://localhost:1234/v1"
    LMSTUDIO_URL: str | None = None
    LM_STUDIO_MODEL: str = "default"
    LM_STUDIO_API_KEY: str = "lm-studio"

    # Criptografia i Tokens
    SECRET_KEY: str = "sevalor-dev-secret-key-32-chars-long-abc"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:4000", "http://127.0.0.1:4000", "http://localhost:8000", "https://sevalor-sevalor-pwa.80opze.easypanel.host"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Bot de Telegram
    TELEGRAM_BOT_TOKEN: str | None = None

    # Domini de desplegament (nginx + PWA)
    DOMAIN: str = "sevalor.app"

    # Entorn
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )

    def get_database_url(self) -> str:
        """Retorna la URL asíncrona de connexió a PostgreSQL."""
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()

import secrets

if not settings.SECRET_KEY:
    settings.SECRET_KEY = "sevalor-dev-secret-key-32-chars-long-abc"