"""Tests for notification API endpoints, repository, service, and schema."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationCountResponse, NotificationResponse
from app.services.notification_service import (
    CATEGORY_DUNNING,
    CATEGORY_INVOICE,
    CATEGORY_PAYMENT,
    CATEGORY_WALLET,
    CATEGORY_WEBHOOK,
    NotificationService,
)
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
    """Create a NotificationRepository instance."""
    return NotificationRepository(db_session)


@pytest.fixture
def service(db_session):
    """Create a NotificationService instance."""
    return NotificationService(db_session)


@pytest.fixture
def seed_notifications(repo):
    """Seed several notifications for testing."""
    n1 = repo.create(
        organization_id=DEFAULT_ORG_ID,
        category="webhook",
        title="Webhook failed",
        message="Delivery to https://example.com failed.",
    )
    n2 = repo.create(
        organization_id=DEFAULT_ORG_ID,
        category="dunning",
        title="Dunning alert",
        message="Payment request created for customer.",
        resource_type="payment_request",
        resource_id=uuid4(),
    )
    n3 = repo.create(
        organization_id=DEFAULT_ORG_ID,
        category="invoice",
        title="Invoice overdue",
        message="Invoice INV-001 is overdue.",
        resource_type="invoice",
        resource_id=uuid4(),
    )
    return n1, n2, n3


# ── Repository Tests ──────────────────────────────────────────────


class TestNotificationRepository:
    def test_create(self, repo):
        n = repo.create(
            organization_id=DEFAULT_ORG_ID,
            category="webhook",
            title="Test",
            message="Test message",
        )
        assert n.id is not None
        assert n.category == "webhook"
        assert n.title == "Test"
        assert n.is_read is False

    def test_create_with_resource(self, repo):
        rid = uuid4()
        n = repo.create(
            organization_id=DEFAULT_ORG_ID,
            category="invoice",
            title="Invoice overdue",
            message="Overdue",
            resource_type="invoice",
            resource_id=rid,
        )
        assert n.resource_type == "invoice"
        assert n.resource_id == rid

    def test_get_by_id(self, repo):
        n = repo.create(
            organization_id=DEFAULT_ORG_ID,
            category="wallet",
            title="Wallet expiring",
            message="Expiring soon.",
        )
        found = repo.get_by_id(n.id)
        assert found is not None
        assert found.id == n.id

    def test_get_by_id_not_found(self, repo):
        assert repo.get_by_id(uuid4()) is None

    def test_get_all(self, repo, seed_notifications):
        results = repo.get_all(DEFAULT_ORG_ID)
        assert len(results) == 3

    def test_get_all_filter_category(self, repo, seed_notifications):
        results = repo.get_all(DEFAULT_ORG_ID, category="webhook")
        assert len(results) == 1
        assert results[0].category == "webhook"

    def test_get_all_filter_is_read(self, repo, seed_notifications):
        n1, _, _ = seed_notifications
        repo.mark_as_read(n1.id)
        unread = repo.get_all(DEFAULT_ORG_ID, is_read=False)
        assert len(unread) == 2
        read = repo.get_all(DEFAULT_ORG_ID, is_read=True)
        assert len(read) == 1

    def test_get_all_pagination(self, repo, seed_notifications):
        results = repo.get_all(DEFAULT_ORG_ID, skip=0, limit=2)
        assert len(results) == 2
        results = repo.get_all(DEFAULT_ORG_ID, skip=2, limit=2)
        assert len(results) == 1

    def test_get_all_order_by(self, repo, seed_notifications):
        results = repo.get_all(DEFAULT_ORG_ID, order_by="category")
        categories = [r.category for r in results]
        assert categories == sorted(categories)

    def test_count_unread(self, repo, seed_notifications):
        assert repo.count_unread(DEFAULT_ORG_ID) == 3

    def test_count_unread_after_mark(self, repo, seed_notifications):
        n1, _, _ = seed_notifications
        repo.mark_as_read(n1.id)
        assert repo.count_unread(DEFAULT_ORG_ID) == 2

    def test_mark_as_read(self, repo, seed_notifications):
        n1, _, _ = seed_notifications
        assert n1.is_read is False
        updated = repo.mark_as_read(n1.id)
        assert updated is not None
        assert updated.is_read is True

    def test_mark_as_read_not_found(self, repo):
        assert repo.mark_as_read(uuid4()) is None

    def test_mark_all_as_read(self, repo, seed_notifications):
        count = repo.mark_all_as_read(DEFAULT_ORG_ID)
        assert count == 3
        assert repo.count_unread(DEFAULT_ORG_ID) == 0

    def test_mark_all_as_read_empty(self, repo):
        count = repo.mark_all_as_read(DEFAULT_ORG_ID)
        assert count == 0


# ── Service Tests ─────────────────────────────────────────────────


class TestNotificationService:
    def test_notify(self, service):
        n = service.notify(
            organization_id=DEFAULT_ORG_ID,
            category="webhook",
            title="Test",
            message="Message",
        )
        assert n.category == "webhook"
        assert n.title == "Test"

    def test_notify_webhook_failure(self, service):
        wid = uuid4()
        n = service.notify_webhook_failure(
            organization_id=DEFAULT_ORG_ID,
            webhook_type="invoice.created",
            endpoint_url="https://example.com/hook",
            error="HTTP 500",
            webhook_id=wid,
        )
        assert n.category == CATEGORY_WEBHOOK
        assert "invoice.created" in n.message
        assert "example.com" in n.message
        assert "HTTP 500" in n.message
        assert n.resource_type == "webhook"
        assert n.resource_id == wid

    def test_notify_webhook_failure_no_error(self, service):
        n = service.notify_webhook_failure(
            organization_id=DEFAULT_ORG_ID,
            webhook_type="payment.failed",
            endpoint_url="https://hook.example.com",
        )
        assert "Error" not in n.message
        assert n.resource_id is None

    def test_notify_dunning_alert(self, service):
        prid = uuid4()
        n = service.notify_dunning_alert(
            organization_id=DEFAULT_ORG_ID,
            customer_name="Acme Corp",
            amount_cents=15000,
            currency="usd",
            payment_request_id=prid,
        )
        assert n.category == CATEGORY_DUNNING
        assert "Acme Corp" in n.message
        assert "150.00" in n.message
        assert "USD" in n.message
        assert n.resource_type == "payment_request"
        assert n.resource_id == prid

    def test_notify_wallet_expiring(self, service):
        wid = uuid4()
        n = service.notify_wallet_expiring(
            organization_id=DEFAULT_ORG_ID,
            wallet_name="Main Wallet",
            days_remaining=7,
            wallet_id=wid,
        )
        assert n.category == CATEGORY_WALLET
        assert "Main Wallet" in n.message
        assert "7 days" in n.message
        assert n.resource_type == "wallet"
        assert n.resource_id == wid

    def test_notify_wallet_expiring_singular(self, service):
        n = service.notify_wallet_expiring(
            organization_id=DEFAULT_ORG_ID,
            wallet_name="Wallet X",
            days_remaining=1,
        )
        assert "1 day." in n.message
        assert "days" not in n.message.replace("1 day.", "")

    def test_notify_invoice_overdue(self, service):
        iid = uuid4()
        n = service.notify_invoice_overdue(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="INV-2024-001",
            customer_name="Contoso",
            amount_cents=50000,
            currency="eur",
            invoice_id=iid,
        )
        assert n.category == CATEGORY_INVOICE
        assert "INV-2024-001" in n.message
        assert "Contoso" in n.message
        assert "500.00" in n.message
        assert "EUR" in n.message
        assert n.resource_type == "invoice"
        assert n.resource_id == iid

    def test_notify_payment_failed(self, service):
        pid = uuid4()
        n = service.notify_payment_failed(
            organization_id=DEFAULT_ORG_ID,
            customer_name="WidgetCo",
            amount_cents=9900,
            currency="gbp",
            payment_id=pid,
        )
        assert n.category == CATEGORY_PAYMENT
        assert "WidgetCo" in n.message
        assert "99.00" in n.message
        assert "GBP" in n.message
        assert n.resource_type == "payment"
        assert n.resource_id == pid


# ── Schema Tests ──────────────────────────────────────────────────


class TestNotificationSchemas:
    def test_notification_response_schema(self, repo):
        n = repo.create(
            organization_id=DEFAULT_ORG_ID,
            category="webhook",
            title="Test",
            message="Test message",
            resource_type="webhook",
            resource_id=uuid4(),
        )
        response = NotificationResponse.model_validate(n)
        assert response.id == n.id
        assert response.category == "webhook"
        assert response.is_read is False
        assert response.resource_type == "webhook"

    def test_notification_count_response_schema(self):
        response = NotificationCountResponse(unread_count=5)
        assert response.unread_count == 5


# ── API Tests ─────────────────────────────────────────────────────


class TestNotificationAPI:
    def test_list_notifications(self, client, seed_notifications):
        resp = client.get("/v1/notifications/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_list_notifications_filter_category(self, client, seed_notifications):
        resp = client.get("/v1/notifications/?category=webhook")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["category"] == "webhook"

    def test_list_notifications_filter_is_read(self, client, seed_notifications):
        resp = client.get("/v1/notifications/?is_read=false")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    def test_list_notifications_pagination(self, client, seed_notifications):
        resp = client.get("/v1/notifications/?skip=0&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_notifications_order_by(self, client, seed_notifications):
        resp = client.get("/v1/notifications/?order_by=category")
        assert resp.status_code == 200
        data = resp.json()
        categories = [n["category"] for n in data]
        assert categories == sorted(categories)

    def test_unread_count(self, client, seed_notifications):
        resp = client.get("/v1/notifications/unread_count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 3

    def test_unread_count_empty(self, client):
        resp = client.get("/v1/notifications/unread_count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    def test_mark_as_read(self, client, seed_notifications):
        n1, _, _ = seed_notifications
        resp = client.post(f"/v1/notifications/{n1.id}/read")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_read"] is True
        # Verify count updated
        count_resp = client.get("/v1/notifications/unread_count")
        assert count_resp.json()["unread_count"] == 2

    def test_mark_as_read_not_found(self, client):
        resp = client.post(f"/v1/notifications/{uuid4()}/read")
        assert resp.status_code == 404

    def test_mark_as_read_wrong_org(self, client, db_session):
        """Notification from a different org should return 404."""
        repo = NotificationRepository(db_session)
        other_org_id = uuid4()
        # Create org first
        from app.models.organization import Organization
        org = Organization(id=other_org_id, name="Other Org")
        db_session.add(org)
        db_session.commit()
        n = repo.create(
            organization_id=other_org_id,
            category="webhook",
            title="Other org notification",
            message="Test",
        )
        resp = client.post(f"/v1/notifications/{n.id}/read")
        assert resp.status_code == 404

    def test_mark_all_as_read(self, client, seed_notifications):
        resp = client.post("/v1/notifications/read_all")
        assert resp.status_code == 200
        # Verify all marked
        count_resp = client.get("/v1/notifications/unread_count")
        assert count_resp.json()["unread_count"] == 0

    def test_mark_all_as_read_empty(self, client):
        resp = client.post("/v1/notifications/read_all")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    def test_list_after_mark_read(self, client, seed_notifications):
        n1, _, _ = seed_notifications
        client.post(f"/v1/notifications/{n1.id}/read")
        resp = client.get("/v1/notifications/?is_read=true")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["id"] == str(n1.id)
