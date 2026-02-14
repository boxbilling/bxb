"""ClickHouse client module for event storage and aggregation."""

import logging
from urllib.parse import urlparse

import clickhouse_connect
from clickhouse_connect.driver import Client

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None
_initialized: bool = False

EVENTS_RAW_TABLE = "events_raw"

CREATE_EVENTS_RAW_TABLE = f"""
CREATE TABLE IF NOT EXISTS {EVENTS_RAW_TABLE} (
    organization_id String,
    transaction_id String,
    external_customer_id String,
    code String,
    timestamp DateTime64(3),
    properties String,
    value Nullable(String),
    decimal_value Nullable(Decimal(38, 26)),
    created_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(created_at)
PRIMARY KEY (organization_id, code, external_customer_id, toDate(timestamp))
ORDER BY (
    organization_id, code, external_customer_id,
    toDate(timestamp), timestamp, transaction_id
)
SETTINGS index_granularity = 8192
"""


def _parse_clickhouse_url(url: str) -> dict[str, object]:
    """Parse a ClickHouse URL into connection parameters."""
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 8123,
        "username": parsed.username or "default",
        "password": parsed.password or "",
        "database": (parsed.path or "/default").lstrip("/") or "default",
    }


def get_clickhouse_client() -> Client | None:
    """Get or create a ClickHouse client singleton.

    Returns None when CLICKHOUSE_URL is not configured.
    """
    global _client, _initialized

    if not settings.clickhouse_enabled:
        return None

    if _client is not None:
        return _client

    params = _parse_clickhouse_url(settings.CLICKHOUSE_URL)
    _client = clickhouse_connect.get_client(**params)  # type: ignore[arg-type]

    if not _initialized:
        _client.command(CREATE_EVENTS_RAW_TABLE)
        _initialized = True
        logger.info("ClickHouse events_raw table ensured")

    return _client


def reset_client() -> None:
    """Reset the cached client. Used for testing."""
    global _client, _initialized
    _client = None
    _initialized = False
