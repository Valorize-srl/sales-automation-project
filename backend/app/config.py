from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://sales_user:sales_password@localhost:5432/sales_automation"
    database_url_sync: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic
    anthropic_api_key: str = ""

    # Instantly
    instantly_api_key: str = ""

    # Webhooks
    webhook_base_url: str = ""

    # App
    app_env: str = "development"
    debug: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        """Railway provides postgresql://, convert to postgresql+asyncpg://"""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @model_validator(mode="after")
    def derive_sync_url(self) -> "Settings":
        """Derive sync URL from async URL for alembic migrations."""
        if not self.database_url_sync:
            self.database_url_sync = self.database_url.replace(
                "postgresql+asyncpg://", "postgresql://", 1
            )
        return self


settings = Settings()
