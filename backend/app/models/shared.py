"""Shared model utilities used across all models."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import String, TypeDecorator
from sqlalchemy.engine import Dialect


class UUIDType(TypeDecorator[uuid.UUID]):
    """Platform-independent UUID type.

    Uses String(36) for SQLite, native UUID for PostgreSQL.
    """

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(value))

    def process_result_value(self, value: Any, dialect: Dialect) -> uuid.UUID | None:
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


DEFAULT_ORGANIZATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(UTC)
