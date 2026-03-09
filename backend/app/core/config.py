from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BXB_ENVIRONMENT: Literal["local", "staging", "production"] = "production"
    BXB_APP_NAME: str = "BoxBilling"
    BXB_DOMAIN: str = "example.com"
    BXB_DATA_PATH: str = "/var/lib/bxb"
    BXB_DATABASE_DSN: str = "postgresql://user:pass@host:5432/database"
    BXB_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    BXB_WEBHOOK_SECRET: str = "whsec_default_secret"                            # Webhook signing
    BXB_PORTAL_JWT_SECRET: str = "portal-secret-change-me"                      # Portal JWT secret
    BXB_RATE_LIMIT_EVENTS_PER_MINUTE: int = 1000                                # Rate limiting
    BXB_ADMIN_SECRET: str = ""  # For org management, at least 32 chars

    REDIS_URL: str = "redis://localhost:6379"
    OPENROUTER_API_KEY: str = ""
    SENTRY_DSN: str = ""

    # Payment providers
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    manual_webhook_secret: str = ""

    # UCP (Universal Commerce Protocol) settings
    ucp_base_url: str = ""  # Business's UCP base URL
    ucp_api_key: str = ""  # API key for UCP provider
    ucp_webhook_secret: str = ""  # Secret for verifying UCP webhooks
    ucp_merchant_id: str = ""  # Merchant ID for UCP

    # GoCardless settings
    gocardless_access_token: str = ""
    gocardless_webhook_secret: str = ""
    gocardless_environment: str = "sandbox"  # "sandbox" or "live"

    # Adyen settings
    adyen_api_key: str = ""
    adyen_merchant_account: str = ""
    adyen_webhook_hmac_key: str = ""
    adyen_environment: str = "test"  # "test" or "live"
    adyen_live_url_prefix: str = ""

    # SMTP email settings
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "billing@example.com"
    SMTP_FROM_NAME: str = "Billing"
    SMTP_USE_TLS: bool = True

    # ClickHouse settings
    CLICKHOUSE_URL: str = ""  # e.g. clickhouse://user:pass@host:port/database

    @property
    def version(self) -> str:
        for parent in Path(__file__).resolve().parents:
            version_file = parent / "VERSION"
            if version_file.is_file():
                return version_file.read_text().strip()
        return "0.0.0"

    @property
    def clickhouse_enabled(self) -> bool:
        return bool(self.CLICKHOUSE_URL)


settings = Settings()
