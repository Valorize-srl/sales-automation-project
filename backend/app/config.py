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

    # Smartlead — sole outreach provider. Auth via `?api_key=…` query
    # string on every Smartlead request. Webhook secret is the shared token
    # embedded in the webhook URL registered on Smartlead (Smartlead doesn't
    # sign payloads with HMAC, so we authenticate by token instead).
    smartlead_api_key: str = ""
    smartlead_webhook_secret: str = ""

    # Apollo
    apollo_api_key: str = ""


    # Findymail (email enrichment from LinkedIn URL or name+domain)
    findymail_api_key: str = ""

    # Webhooks
    webhook_base_url: str = ""

    # MCP server
    # Master key used only to create/revoke API keys via /api/admin/api-keys.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    mcp_master_key: str = ""
    mcp_enabled: bool = True

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
