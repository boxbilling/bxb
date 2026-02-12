"""Shared test fixtures for all test modules."""

import contextlib

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.database import Base, engine


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test and truncate all data after.

    Creates tables idempotently (checkfirst) and clears data after each test
    by deleting from all tables. This avoids SQLite locking issues that occur
    with drop_all/create_all when pooled connections are active.
    """
    Base.metadata.create_all(bind=engine)
    yield
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            with contextlib.suppress(OperationalError):
                conn.execute(table.delete())
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.commit()
