"""Tests for idempotency model, repository, and core dependency."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.idempotency import (
    IdempotencyResult,
    check_idempotency,
    record_idempotency_response,
)
from app.models.idempotency_record import IdempotencyRecord
from app.repositories.idempotency_repository import IdempotencyRepository
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def db_session():
    """Create a database session for direct testing."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def repo(db_session: Session) -> IdempotencyRepository:
    return IdempotencyRepository(db_session)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestIdempotencyRecordModel:
    def test_create_record(self, db_session: Session) -> None:
        record = IdempotencyRecord(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="key-1",
            request_method="POST",
            request_path="/v1/customers",
        )
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)

        assert record.id is not None
        assert record.organization_id == DEFAULT_ORG_ID
        assert record.idempotency_key == "key-1"
        assert record.request_method == "POST"
        assert record.request_path == "/v1/customers"
        assert record.response_status is None
        assert record.response_body is None
        assert record.created_at is not None

    def test_unique_constraint(self, db_session: Session) -> None:
        record1 = IdempotencyRecord(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="dup-key",
            request_method="POST",
            request_path="/v1/customers",
        )
        db_session.add(record1)
        db_session.commit()

        record2 = IdempotencyRecord(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="dup-key",
            request_method="POST",
            request_path="/v1/customers",
        )
        db_session.add(record2)
        with pytest.raises(Exception):  # noqa: B017
            db_session.commit()
        db_session.rollback()


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestIdempotencyRepository:
    def test_create_and_get_by_key(self, repo: IdempotencyRepository) -> None:
        record = repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="repo-key-1",
            request_method="POST",
            request_path="/v1/subscriptions",
        )
        assert record.id is not None
        assert record.idempotency_key == "repo-key-1"

        fetched = repo.get_by_key(DEFAULT_ORG_ID, "repo-key-1")
        assert fetched is not None
        assert fetched.id == record.id

    def test_get_by_key_not_found(self, repo: IdempotencyRepository) -> None:
        result = repo.get_by_key(DEFAULT_ORG_ID, "nonexistent")
        assert result is None

    def test_different_orgs_dont_collide(self, repo: IdempotencyRepository) -> None:
        org_a = DEFAULT_ORG_ID
        org_b = uuid4()

        # Seed org_b in the organizations table
        from app.models.organization import Organization

        org = Organization(id=org_b, name="Org B")
        repo.db.add(org)
        repo.db.commit()

        repo.create(
            organization_id=org_a,
            idempotency_key="shared-key",
            request_method="POST",
            request_path="/v1/customers",
            response_status=201,
            response_body={"id": "aaa"},
        )
        repo.create(
            organization_id=org_b,
            idempotency_key="shared-key",
            request_method="POST",
            request_path="/v1/customers",
            response_status=201,
            response_body={"id": "bbb"},
        )

        record_a = repo.get_by_key(org_a, "shared-key")
        record_b = repo.get_by_key(org_b, "shared-key")
        assert record_a is not None
        assert record_b is not None
        assert record_a.response_body == {"id": "aaa"}
        assert record_b.response_body == {"id": "bbb"}

    def test_update_response(self, repo: IdempotencyRepository) -> None:
        record = repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="update-key",
            request_method="POST",
            request_path="/v1/invoices",
        )
        assert record.response_status is None

        repo.update_response(record, 201, {"id": "inv-1"})

        fetched = repo.get_by_key(DEFAULT_ORG_ID, "update-key")
        assert fetched is not None
        assert fetched.response_status == 201
        assert fetched.response_body == {"id": "inv-1"}

    def test_delete_expired(self, db_session: Session, repo: IdempotencyRepository) -> None:
        # Create a record and backdate it
        record = repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="old-key",
            request_method="POST",
            request_path="/v1/events",
            response_status=200,
            response_body={},
        )
        old_time = datetime.now(UTC) - timedelta(hours=25)
        record.created_at = old_time  # type: ignore[assignment]
        db_session.commit()

        # Create a fresh record
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="new-key",
            request_method="POST",
            request_path="/v1/events",
            response_status=200,
            response_body={},
        )

        deleted = repo.delete_expired(max_age_hours=24)
        assert deleted == 1

        assert repo.get_by_key(DEFAULT_ORG_ID, "old-key") is None
        assert repo.get_by_key(DEFAULT_ORG_ID, "new-key") is not None

    def test_delete_expired_none(self, repo: IdempotencyRepository) -> None:
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="fresh-key",
            request_method="POST",
            request_path="/v1/customers",
            response_status=201,
            response_body={},
        )
        deleted = repo.delete_expired(max_age_hours=24)
        assert deleted == 0


# ---------------------------------------------------------------------------
# Core dependency tests
# ---------------------------------------------------------------------------


def _make_request(headers: dict[str, str] | None = None, method: str = "POST", path: str = "/v1/customers") -> Request:
    """Build a minimal ASGI Request for testing."""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    request = Request(scope)
    return request


class TestCheckIdempotency:
    def test_no_header_returns_none(self, db_session: Session) -> None:
        request = _make_request()
        result = check_idempotency(request, db_session, DEFAULT_ORG_ID)
        assert result is None

    def test_new_key_returns_idempotency_result(self, db_session: Session) -> None:
        request = _make_request(headers={"Idempotency-Key": "new-dep-key"})
        result = check_idempotency(request, db_session, DEFAULT_ORG_ID)

        assert isinstance(result, IdempotencyResult)
        assert result.key == "new-dep-key"
        assert result.method == "POST"
        assert result.path == "/v1/customers"

        # Verify a record was created in the database
        repo = IdempotencyRepository(db_session)
        record = repo.get_by_key(DEFAULT_ORG_ID, "new-dep-key")
        assert record is not None
        assert record.response_status is None

    def test_existing_completed_key_returns_cached_response(
        self, db_session: Session, repo: IdempotencyRepository
    ) -> None:
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="cached-key",
            request_method="POST",
            request_path="/v1/customers",
            response_status=201,
            response_body={"id": "cust-123", "name": "Test"},
        )

        request = _make_request(headers={"Idempotency-Key": "cached-key"})
        result = check_idempotency(request, db_session, DEFAULT_ORG_ID)

        from fastapi.responses import JSONResponse

        assert isinstance(result, JSONResponse)
        assert result.status_code == 201
        assert result.headers.get("Idempotency-Replayed") == "true"

    def test_existing_pending_key_returns_idempotency_result(
        self, db_session: Session, repo: IdempotencyRepository
    ) -> None:
        # Record exists but response not yet stored (concurrent request)
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="pending-key",
            request_method="POST",
            request_path="/v1/customers",
        )

        request = _make_request(headers={"Idempotency-Key": "pending-key"})
        result = check_idempotency(request, db_session, DEFAULT_ORG_ID)

        assert isinstance(result, IdempotencyResult)
        assert result.key == "pending-key"


class TestRecordIdempotencyResponse:
    def test_records_response(self, db_session: Session, repo: IdempotencyRepository) -> None:
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="record-key",
            request_method="POST",
            request_path="/v1/customers",
        )

        record_idempotency_response(
            db_session, DEFAULT_ORG_ID, "record-key", 201, {"id": "cust-456"}
        )

        record = repo.get_by_key(DEFAULT_ORG_ID, "record-key")
        assert record is not None
        assert record.response_status == 201
        assert record.response_body == {"id": "cust-456"}

    def test_no_record_does_nothing(self, db_session: Session) -> None:
        # Should not raise even if no record exists
        record_idempotency_response(
            db_session, DEFAULT_ORG_ID, "missing-key", 201, {"id": "x"}
        )
