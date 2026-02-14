"""Tests for AuditLog model, AuditLogRepository, and AuditService."""

from uuid import uuid4

import pytest

from app.core.database import get_db
from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.audit_log import AuditLogResponse
from app.services.audit_service import AuditService
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
def repo(db_session):
    """Create an AuditLogRepository instance."""
    return AuditLogRepository(db_session)


@pytest.fixture
def service(db_session):
    """Create an AuditService instance."""
    return AuditService(db_session)


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestAuditLogRepository:
    def test_create(self, repo):
        resource_id = uuid4()
        log = repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="invoice",
            resource_id=resource_id,
            action="created",
            changes={"total": {"old": None, "new": "100.00"}},
            actor_type="system",
            actor_id=None,
            metadata={"source": "test"},
        )
        assert log.id is not None
        assert log.organization_id == DEFAULT_ORG_ID
        assert log.resource_type == "invoice"
        assert log.resource_id == resource_id
        assert log.action == "created"
        assert log.changes == {"total": {"old": None, "new": "100.00"}}
        assert log.actor_type == "system"
        assert log.actor_id is None
        assert log.metadata_ == {"source": "test"}
        assert log.created_at is not None

    def test_create_without_metadata(self, repo):
        log = repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="customer",
            resource_id=uuid4(),
            action="created",
            changes={},
            actor_type="api_key",
            actor_id="key_123",
        )
        assert log.metadata_ is None
        assert log.actor_id == "key_123"

    def test_get_by_resource(self, repo):
        resource_id = uuid4()
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="payment",
            resource_id=resource_id,
            action="created",
            changes={},
            actor_type="system",
        )
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="payment",
            resource_id=resource_id,
            action="status_changed",
            changes={"status": {"old": "pending", "new": "succeeded"}},
            actor_type="webhook",
        )
        # Different resource — should not appear
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="payment",
            resource_id=uuid4(),
            action="created",
            changes={},
            actor_type="system",
        )

        results = repo.get_by_resource("payment", resource_id)
        assert len(results) == 2

    def test_get_by_resource_pagination(self, repo):
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
        page = repo.get_by_resource("subscription", resource_id, skip=2, limit=2)
        assert len(page) == 2

    def test_get_all(self, repo):
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="invoice",
            resource_id=uuid4(),
            action="created",
            changes={},
            actor_type="system",
        )
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="payment",
            resource_id=uuid4(),
            action="status_changed",
            changes={},
            actor_type="webhook",
        )
        results = repo.get_all(DEFAULT_ORG_ID)
        assert len(results) == 2

    def test_get_all_filter_resource_type(self, repo):
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="invoice",
            resource_id=uuid4(),
            action="created",
            changes={},
            actor_type="system",
        )
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="payment",
            resource_id=uuid4(),
            action="created",
            changes={},
            actor_type="system",
        )
        results = repo.get_all(DEFAULT_ORG_ID, resource_type="invoice")
        assert len(results) == 1
        assert results[0].resource_type == "invoice"

    def test_get_all_filter_action(self, repo):
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="invoice",
            resource_id=uuid4(),
            action="created",
            changes={},
            actor_type="system",
        )
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="invoice",
            resource_id=uuid4(),
            action="status_changed",
            changes={},
            actor_type="system",
        )
        results = repo.get_all(DEFAULT_ORG_ID, action="status_changed")
        assert len(results) == 1
        assert results[0].action == "status_changed"

    def test_get_all_pagination(self, repo):
        for _ in range(5):
            repo.create(
                organization_id=DEFAULT_ORG_ID,
                resource_type="invoice",
                resource_id=uuid4(),
                action="created",
                changes={},
                actor_type="system",
            )
        page = repo.get_all(DEFAULT_ORG_ID, skip=3, limit=10)
        assert len(page) == 2


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestAuditService:
    def test_log_create(self, service, db_session):
        resource_id = uuid4()
        service.log_create(
            resource_type="invoice",
            resource_id=resource_id,
            organization_id=DEFAULT_ORG_ID,
            actor_type="api_key",
            actor_id="key_abc",
            data={"total": "250.00", "currency": "USD"},
        )
        repo = AuditLogRepository(db_session)
        logs = repo.get_by_resource("invoice", resource_id)
        assert len(logs) == 1
        log = logs[0]
        assert log.action == "created"
        assert log.changes == {"total": "250.00", "currency": "USD"}
        assert log.actor_type == "api_key"
        assert log.actor_id == "key_abc"

    def test_log_create_defaults(self, service, db_session):
        resource_id = uuid4()
        service.log_create(
            resource_type="customer",
            resource_id=resource_id,
            organization_id=DEFAULT_ORG_ID,
        )
        repo = AuditLogRepository(db_session)
        logs = repo.get_by_resource("customer", resource_id)
        assert len(logs) == 1
        assert logs[0].actor_type == "system"
        assert logs[0].actor_id is None
        assert logs[0].changes == {}

    def test_log_update_diffs_fields(self, service, db_session):
        resource_id = uuid4()
        service.log_update(
            resource_type="invoice",
            resource_id=resource_id,
            organization_id=DEFAULT_ORG_ID,
            old_data={"total": "100.00", "currency": "USD", "status": "draft"},
            new_data={"total": "200.00", "currency": "USD", "status": "finalized"},
        )
        repo = AuditLogRepository(db_session)
        logs = repo.get_by_resource("invoice", resource_id)
        assert len(logs) == 1
        changes = logs[0].changes
        assert "total" in changes
        assert changes["total"] == {"old": "100.00", "new": "200.00"}
        assert "status" in changes
        assert changes["status"] == {"old": "draft", "new": "finalized"}
        # currency unchanged — should not appear in diff
        assert "currency" not in changes

    def test_log_update_no_changes_skips(self, service, db_session):
        resource_id = uuid4()
        service.log_update(
            resource_type="customer",
            resource_id=resource_id,
            organization_id=DEFAULT_ORG_ID,
            old_data={"name": "Alice"},
            new_data={"name": "Alice"},
        )
        repo = AuditLogRepository(db_session)
        logs = repo.get_by_resource("customer", resource_id)
        assert len(logs) == 0

    def test_log_update_with_new_field(self, service, db_session):
        resource_id = uuid4()
        service.log_update(
            resource_type="invoice",
            resource_id=resource_id,
            organization_id=DEFAULT_ORG_ID,
            old_data={"total": "100.00"},
            new_data={"total": "100.00", "paid_at": "2026-01-01"},
        )
        repo = AuditLogRepository(db_session)
        logs = repo.get_by_resource("invoice", resource_id)
        assert len(logs) == 1
        assert logs[0].changes == {"paid_at": {"old": None, "new": "2026-01-01"}}

    def test_log_update_with_removed_field(self, service, db_session):
        resource_id = uuid4()
        service.log_update(
            resource_type="invoice",
            resource_id=resource_id,
            organization_id=DEFAULT_ORG_ID,
            old_data={"total": "100.00", "note": "test"},
            new_data={"total": "100.00"},
        )
        repo = AuditLogRepository(db_session)
        logs = repo.get_by_resource("invoice", resource_id)
        assert len(logs) == 1
        assert logs[0].changes == {"note": {"old": "test", "new": None}}

    def test_log_update_defaults(self, service, db_session):
        resource_id = uuid4()
        service.log_update(
            resource_type="customer",
            resource_id=resource_id,
            organization_id=DEFAULT_ORG_ID,
        )
        repo = AuditLogRepository(db_session)
        logs = repo.get_by_resource("customer", resource_id)
        # Both old and new are empty dicts — no changes
        assert len(logs) == 0

    def test_log_status_change(self, service, db_session):
        resource_id = uuid4()
        service.log_status_change(
            resource_type="invoice",
            resource_id=resource_id,
            organization_id=DEFAULT_ORG_ID,
            old_status="draft",
            new_status="finalized",
            actor_type="api_key",
            actor_id="key_xyz",
        )
        repo = AuditLogRepository(db_session)
        logs = repo.get_by_resource("invoice", resource_id)
        assert len(logs) == 1
        log = logs[0]
        assert log.action == "status_changed"
        assert log.changes == {"status": {"old": "draft", "new": "finalized"}}
        assert log.actor_type == "api_key"
        assert log.actor_id == "key_xyz"

    def test_log_status_change_defaults(self, service, db_session):
        resource_id = uuid4()
        service.log_status_change(
            resource_type="payment",
            resource_id=resource_id,
            organization_id=DEFAULT_ORG_ID,
            old_status="pending",
            new_status="succeeded",
        )
        repo = AuditLogRepository(db_session)
        logs = repo.get_by_resource("payment", resource_id)
        assert len(logs) == 1
        assert logs[0].actor_type == "system"
        assert logs[0].actor_id is None


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestAuditLogSchema:
    def test_response_from_model(self, repo):
        resource_id = uuid4()
        log = repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="invoice",
            resource_id=resource_id,
            action="created",
            changes={"total": "100.00"},
            actor_type="system",
            metadata={"ip": "127.0.0.1"},
        )
        response = AuditLogResponse.model_validate(log)
        assert response.id == log.id
        assert response.resource_type == "invoice"
        assert response.resource_id == resource_id
        assert response.action == "created"
        assert response.changes == {"total": "100.00"}
        assert response.actor_type == "system"
        assert response.metadata_ == {"ip": "127.0.0.1"}
        assert response.created_at is not None

    def test_response_with_null_metadata(self, repo):
        log = repo.create(
            organization_id=DEFAULT_ORG_ID,
            resource_type="customer",
            resource_id=uuid4(),
            action="updated",
            changes={},
            actor_type="api_key",
            actor_id="key_1",
        )
        response = AuditLogResponse.model_validate(log)
        assert response.metadata_ is None
        assert response.actor_id == "key_1"
