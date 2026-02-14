from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DEBUG: bool = False
    APP_DOMAIN: str = "example.com"
    APP_DATA_PATH: str = "/tmp"
    APP_DATABASE_DSN: str = "sqlite:////tmp/database.db"
    REDIS_URL: str = "redis://localhost:6379"
    OPENROUTER_API_KEY: str = ""

    # Payment providers
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    manual_webhook_secret: str = ""

    # Webhook signing
    webhook_secret: str = "whsec_default_secret"

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

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Rate limiting
    RATE_LIMIT_EVENTS_PER_MINUTE: int = 1000

    # ClickHouse settings
    CLICKHOUSE_URL: str = ""  # e.g. clickhouse://user:pass@host:port/database

    @property
    def clickhouse_enabled(self) -> bool:
        return bool(self.CLICKHOUSE_URL)


settings = Settings()
