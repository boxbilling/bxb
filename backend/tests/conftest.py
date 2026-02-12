"""Shared test fixtures for all test modules."""

import contextlib

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import database as db_module
from app.core.database import Base

# Create an in-memory SQLite engine with StaticPool so all connections
# share the same database state and there are no file-locking issues.
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test and truncate all data after.

    Patches the module-level engine and SessionLocal so all application code
    uses the in-memory test database. Clears data after each test.
    """
    # Patch module-level engine and session factory
    original_engine = db_module.engine
    original_session = db_module.SessionLocal
    db_module.engine = _test_engine
    db_module.SessionLocal = _TestSessionLocal

    Base.metadata.create_all(bind=_test_engine)
    yield
    with _test_engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            with contextlib.suppress(OperationalError):
                conn.execute(table.delete())
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.commit()

    # Restore originals
    db_module.engine = original_engine
    db_module.SessionLocal = original_session
