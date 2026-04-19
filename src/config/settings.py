from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    enable_docs: bool = True
    cors_origins: list[str] = []
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    log_level: str = "INFO"
    repository_backend: Literal["inmemory", "sqlite", "postgresql"] = "postgresql"
    sqlite_path: str = ".data/kanban.db"
    postgresql_dsn: str = "postgresql+psycopg://postgres:postgres@localhost:5432/kanban"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
