"""Tests for audit log API endpoints and audit trail integration."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.customer import generate_uuid
from app.repositories.audit_log_repository import AuditLogRepository
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Create a database session for direct repository testing."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def repo(db_session):
    """Create an AuditLogRepository instance."""
    return AuditLogRepository(db_session)


@pytest.fixture
def seed_audit_logs(repo):
    """Seed several audit log entries for testing."""
    resource_id_1 = uuid4()
    resource_id_2 = uuid4()

    repo.create(
        organization_id=DEFAULT_ORG_ID,
        resource_type="invoice",
        resource_id=resource_id_1,
        action="created",
        changes={"total": "100.00"},
        actor_type="api_key",
        actor_id="key_1",
    )
    repo.create(
        organization_id=DEFAULT_ORG_ID,
        resource_type="invoice",
        resource_id=resource_id_1,
        action="status_changed",
        changes={"status": {"old": "draft", "new": "finalized"}},
        actor_type="api_key",
    )
    repo.create(
        organization_id=DEFAULT_ORG_ID,
        resource_type="payment",
        resource_id=resource_id_2,
        action="created",
        changes={"amount": "50.00"},
        actor_type="system",
    )

    return resource_id_1, resource_id_2


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestAuditLogAPI:
    """Tests for audit log API endpoints."""

    def test_list_audit_logs(self, client, seed_audit_logs):
        """Test GET /v1/audit_logs/ returns all audit logs."""
        response = client.get("/v1/audit_logs/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_list_audit_logs_empty(self, client):
        """Test GET /v1/audit_logs/ returns empty list when no logs."""
        response = client.get("/v1/audit_logs/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_audit_logs_filter_by_resource_type(self, client, seed_audit_logs):
        """Test GET /v1/audit_logs/ with resource_type filter."""
        response = client.get("/v1/audit_logs/", params={"resource_type": "invoice"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(log["resource_type"] == "invoice" for log in data)

    def test_list_audit_logs_filter_by_action(self, client, seed_audit_logs):
        """Test GET /v1/audit_logs/ with action filter."""
        response = client.get("/v1/audit_logs/", params={"action": "created"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(log["action"] == "created" for log in data)

    def test_list_audit_logs_filter_by_resource_type_and_resource_id(
        self, client, seed_audit_logs
    ):
        """Test GET /v1/audit_logs/ with resource_type and resource_id filters."""
        resource_id_1, _ = seed_audit_logs
        response = client.get(
            "/v1/audit_logs/",
            params={"resource_type": "invoice", "resource_id": str(resource_id_1)},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(log["resource_id"] == str(resource_id_1) for log in data)

    def test_list_audit_logs_pagination(self, client, seed_audit_logs):
        """Test GET /v1/audit_logs/ with pagination."""
        response = client.get("/v1/audit_logs/", params={"skip": 0, "limit": 2})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        response2 = client.get("/v1/audit_logs/", params={"skip": 2, "limit": 2})
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2) == 1

    def test_get_resource_audit_trail(self, client, seed_audit_logs):
        """Test GET /v1/audit_logs/{resource_type}/{resource_id} returns trail."""
        resource_id_1, _ = seed_audit_logs
        response = client.get(f"/v1/audit_logs/invoice/{resource_id_1}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(log["resource_type"] == "invoice" for log in data)
        assert all(log["resource_id"] == str(resource_id_1) for log in data)

    def test_get_resource_audit_trail_empty(self, client):
        """Test GET /v1/audit_logs/{resource_type}/{resource_id} returns empty for unknown."""
        response = client.get(f"/v1/audit_logs/invoice/{uuid4()}")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_resource_audit_trail_pagination(self, client, repo):
        """Test GET /v1/audit_logs/{resource_type}/{resource_id} with pagination."""
        resource_id = uuid4()
        for _ in range(5):
            repo.create(
                organization_id=DEFAULT_ORG_ID,
                resource_type="subscription",
                resource_id=resource_id,
                action="updated",
                changes={},
                actor_type="system",
            )
        response = client.get(
            f"/v1/audit_logs/subscription/{resource_id}",
            params={"skip": 2, "limit": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_audit_log_response_format(self, client, seed_audit_logs):
        """Test that audit log response contains all expected fields."""
        response = client.get("/v1/audit_logs/")
        assert response.status_code == 200
        data = response.json()
        log = data[0]
        assert "id" in log
        assert "organization_id" in log
        assert "resource_type" in log
        assert "resource_id" in log
        assert "action" in log
        assert "changes" in log
        assert "actor_type" in log
        assert "actor_id" in log
        assert "metadata_" in log
        assert "created_at" in log


# ---------------------------------------------------------------------------
# Date range filter tests
# ---------------------------------------------------------------------------


def _create_audit_log_with_timestamp(
    db_session, *, created_at: datetime, action: str = "created"
) -> AuditLog:
    """Insert an audit log with a specific created_at timestamp."""
    log = AuditLog(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        resource_type="invoice",
        resource_id=generate_uuid(),
        action=action,
        changes={"field": "value"},
        actor_type="system",
        created_at=created_at,
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    return log


class TestAuditLogDateRangeFilter:
    """Tests for date range filtering on audit logs."""

    def test_filter_start_date_only(self, client, db_session):
        """Logs before start_date are excluded."""
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 1, 10, tzinfo=UTC)
        )
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 6, 15, tzinfo=UTC)
        )

        response = client.get(
            "/v1/audit_logs/",
            params={"start_date": "2024-03-01T00:00:00Z"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_filter_end_date_only(self, client, db_session):
        """Logs after end_date are excluded."""
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 1, 10, tzinfo=UTC)
        )
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 6, 15, tzinfo=UTC)
        )

        response = client.get(
            "/v1/audit_logs/",
            params={"end_date": "2024-03-01T00:00:00Z"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_filter_start_and_end_date(self, client, db_session):
        """Only logs within the date range are returned."""
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 1, 5, tzinfo=UTC)
        )
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 3, 15, tzinfo=UTC)
        )
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 8, 20, tzinfo=UTC)
        )

        response = client.get(
            "/v1/audit_logs/",
            params={
                "start_date": "2024-02-01T00:00:00Z",
                "end_date": "2024-06-01T00:00:00Z",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_filter_date_range_returns_empty(self, client, db_session):
        """A narrow range that excludes all logs returns empty."""
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 1, 10, tzinfo=UTC)
        )

        response = client.get(
            "/v1/audit_logs/",
            params={
                "start_date": "2024-06-01T00:00:00Z",
                "end_date": "2024-07-01T00:00:00Z",
            },
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_filter_date_range_combined_with_other_filters(self, client, db_session):
        """Date range works together with resource_type and action filters."""
        _create_audit_log_with_timestamp(
            db_session,
            created_at=datetime(2024, 3, 15, tzinfo=UTC),
            action="created",
        )
        _create_audit_log_with_timestamp(
            db_session,
            created_at=datetime(2024, 3, 20, tzinfo=UTC),
            action="updated",
        )
        # Outside date range
        _create_audit_log_with_timestamp(
            db_session,
            created_at=datetime(2024, 1, 5, tzinfo=UTC),
            action="created",
        )

        response = client.get(
            "/v1/audit_logs/",
            params={
                "start_date": "2024-02-01T00:00:00Z",
                "end_date": "2024-04-01T00:00:00Z",
                "action": "created",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["action"] == "created"

    def test_repository_date_range_filters(self, db_session):
        """Test repository-level date filtering directly."""
        repo = AuditLogRepository(db_session)
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 1, 10, tzinfo=UTC)
        )
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 6, 15, tzinfo=UTC)
        )
        _create_audit_log_with_timestamp(
            db_session, created_at=datetime(2024, 12, 1, tzinfo=UTC)
        )

        # start_date only
        results = repo.get_all(
            organization_id=DEFAULT_ORG_ID,
            start_date=datetime(2024, 5, 1, tzinfo=UTC),
        )
        assert len(results) == 2

        # end_date only
        results = repo.get_all(
            organization_id=DEFAULT_ORG_ID,
            end_date=datetime(2024, 5, 1, tzinfo=UTC),
        )
        assert len(results) == 1

        # both
        results = repo.get_all(
            organization_id=DEFAULT_ORG_ID,
            start_date=datetime(2024, 5, 1, tzinfo=UTC),
            end_date=datetime(2024, 9, 1, tzinfo=UTC),
        )
        assert len(results) == 1
