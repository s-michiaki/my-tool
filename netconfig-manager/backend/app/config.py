from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # JWT
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Fernet (device credential encryption)
    app_secret_key: str = ""

    # DB
    database_url: str = "postgresql+asyncpg://netconfig:netconfig@db:5432/netconfig"

    # CORS
    cors_origins: str = "http://localhost,https://localhost"

    # Scheduler
    collect_interval_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def cors_origin_list(self) -> List[str]:
        return [s.strip() for s in self.cors_origins.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
