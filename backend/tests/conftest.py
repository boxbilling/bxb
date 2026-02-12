"""Shared test fixtures for all test modules."""

import contextlib
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import database as db_module
from app.core.database import Base
from app.models.organization import Organization

# Create an in-memory SQLite engine with StaticPool so all connections
# share the same database state and there are no file-locking issues.
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

# Well-known default organization ID used across all tests
DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _seed_default_organization(session: Session) -> None:
    """Insert a default organization used by all tests."""
    org = session.query(Organization).filter(Organization.id == DEFAULT_ORG_ID).first()
    if org is None:
        org = Organization(
            id=DEFAULT_ORG_ID,
            name="Default Test Organization",
        )
        session.add(org)
        session.commit()


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

    # Seed default organization so all tests can reference it
    session = _TestSessionLocal()
    try:
        _seed_default_organization(session)
    finally:
        session.close()

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


@pytest.fixture
def default_org_id():
    """Return the default organization ID for tests."""
    return DEFAULT_ORG_ID
