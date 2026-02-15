"""Tests for WebhookEndpoint and Webhook models, schemas, repositories."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.database import get_db
from app.models.webhook import Webhook
from app.models.webhook_endpoint import WebhookEndpoint
from app.repositories.webhook_endpoint_repository import WebhookEndpointRepository
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.webhook import (
    EndpointDeliveryStats,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    WebhookEndpointUpdate,
    WebhookEventPayload,
    WebhookResponse,
)
from tests.conftest import DEFAULT_ORG_ID


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
def active_endpoint(db_session):
    """Create an active webhook endpoint."""
    repo = WebhookEndpointRepository(db_session)
    return repo.create(
        WebhookEndpointCreate(
            url="https://example.com/webhooks",
            signature_algo="hmac",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def inactive_endpoint(db_session):
    """Create an inactive webhook endpoint."""
    repo = WebhookEndpointRepository(db_session)
    endpoint = repo.create(
        WebhookEndpointCreate(
            url="https://example.com/webhooks-inactive",
        ),
        DEFAULT_ORG_ID,
    )
    return repo.update(endpoint.id, WebhookEndpointUpdate(status="inactive"), DEFAULT_ORG_ID)


@pytest.fixture
def sample_webhook(db_session, active_endpoint):
    """Create a sample webhook."""
    repo = WebhookRepository(db_session)
    return repo.create(
        webhook_endpoint_id=active_endpoint.id,
        webhook_type="invoice.created",
        object_type="invoice",
        object_id=uuid4(),
        payload={"event": "invoice.created", "data": {"id": "test"}},
    )


class TestWebhookEndpointModel:
    """Tests for WebhookEndpoint SQLAlchemy model."""

    def test_webhook_endpoint_defaults(self, db_session):
        """Test WebhookEndpoint model default values."""
        endpoint = WebhookEndpoint(
            url="https://example.com/hook",
        )
        db_session.add(endpoint)
        db_session.commit()
        db_session.refresh(endpoint)

        assert endpoint.id is not None
        assert endpoint.url == "https://example.com/hook"
        assert endpoint.signature_algo == "hmac"
        assert endpoint.status == "active"
        assert endpoint.created_at is not None
        assert endpoint.updated_at is not None

    def test_webhook_endpoint_with_all_fields(self, db_session):
        """Test WebhookEndpoint model with all fields set."""
        endpoint = WebhookEndpoint(
            url="https://example.com/jwt-hook",
            signature_algo="jwt",
            status="inactive",
        )
        db_session.add(endpoint)
        db_session.commit()
        db_session.refresh(endpoint)

        assert endpoint.url == "https://example.com/jwt-hook"
        assert endpoint.signature_algo == "jwt"
        assert endpoint.status == "inactive"


class TestWebhookModel:
    """Tests for Webhook SQLAlchemy model."""

    def test_webhook_defaults(self, db_session, active_endpoint):
        """Test Webhook model default values."""
        webhook = Webhook(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )
        db_session.add(webhook)
        db_session.commit()
        db_session.refresh(webhook)

        assert webhook.id is not None
        assert webhook.webhook_endpoint_id == active_endpoint.id
        assert webhook.webhook_type == "invoice.created"
        assert webhook.object_type is None
        assert webhook.object_id is None
        assert webhook.payload == {"event": "test"}
        assert webhook.status == "pending"
        assert webhook.retries == 0
        assert webhook.max_retries == 5
        assert webhook.last_retried_at is None
        assert webhook.http_status is None
        assert webhook.response is None
        assert webhook.created_at is not None
        assert webhook.updated_at is not None

    def test_webhook_with_all_fields(self, db_session, active_endpoint):
        """Test Webhook model with all fields set."""
        object_id = uuid4()
        webhook = Webhook(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            object_type="payment",
            object_id=object_id,
            payload={"event": "payment.succeeded", "amount": 1000},
            status="succeeded",
            retries=2,
            max_retries=5,
            http_status=200,
            response='{"ok": true}',
        )
        db_session.add(webhook)
        db_session.commit()
        db_session.refresh(webhook)

        assert webhook.webhook_type == "payment.succeeded"
        assert webhook.object_type == "payment"
        assert webhook.object_id == object_id
        assert webhook.status == "succeeded"
        assert webhook.retries == 2
        assert webhook.http_status == 200
        assert webhook.response == '{"ok": true}'


class TestWebhookEndpointRepository:
    """Tests for WebhookEndpointRepository."""

    def test_create_endpoint(self, db_session):
        """Test creating a webhook endpoint."""
        repo = WebhookEndpointRepository(db_session)
        endpoint = repo.create(
            WebhookEndpointCreate(
                url="https://example.com/new-hook",
            ),
            DEFAULT_ORG_ID,
        )
        assert endpoint.id is not None
        assert endpoint.url == "https://example.com/new-hook"
        assert endpoint.signature_algo == "hmac"

    def test_create_endpoint_with_jwt(self, db_session):
        """Test creating a webhook endpoint with JWT signature."""
        repo = WebhookEndpointRepository(db_session)
        endpoint = repo.create(
            WebhookEndpointCreate(
                url="https://example.com/jwt",
                signature_algo="jwt",
            ),
            DEFAULT_ORG_ID,
        )
        assert endpoint.signature_algo == "jwt"

    def test_get_by_id(self, db_session, active_endpoint):
        """Test getting a webhook endpoint by ID."""
        repo = WebhookEndpointRepository(db_session)
        endpoint = repo.get_by_id(active_endpoint.id)
        assert endpoint is not None
        assert endpoint.url == "https://example.com/webhooks"

    def test_get_by_id_not_found(self, db_session):
        """Test getting a webhook endpoint by non-existent ID."""
        repo = WebhookEndpointRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_all(self, db_session, active_endpoint, inactive_endpoint):
        """Test getting all webhook endpoints."""
        repo = WebhookEndpointRepository(db_session)
        endpoints = repo.get_all(DEFAULT_ORG_ID)
        assert len(endpoints) == 2

    def test_get_all_pagination(self, db_session, active_endpoint, inactive_endpoint):
        """Test get_all with pagination."""
        repo = WebhookEndpointRepository(db_session)
        endpoints = repo.get_all(DEFAULT_ORG_ID, skip=0, limit=1)
        assert len(endpoints) == 1

    def test_get_all_empty(self, db_session):
        """Test get_all with no endpoints."""
        repo = WebhookEndpointRepository(db_session)
        assert repo.get_all(DEFAULT_ORG_ID) == []

    def test_get_active(self, db_session, active_endpoint, inactive_endpoint):
        """Test getting only active webhook endpoints."""
        repo = WebhookEndpointRepository(db_session)
        active = repo.get_active()
        assert len(active) == 1
        assert active[0].url == "https://example.com/webhooks"

    def test_get_active_with_org_filter(self, db_session, active_endpoint):
        """Test getting active endpoints scoped to an organization."""
        repo = WebhookEndpointRepository(db_session)
        active = repo.get_active(organization_id=DEFAULT_ORG_ID)
        assert len(active) == 1
        # Wrong org returns empty
        assert repo.get_active(organization_id=uuid4()) == []

    def test_get_active_empty(self, db_session, inactive_endpoint):
        """Test getting active endpoints when none are active."""
        repo = WebhookEndpointRepository(db_session)
        active = repo.get_active()
        assert active == []

    def test_update(self, db_session, active_endpoint):
        """Test updating a webhook endpoint."""
        repo = WebhookEndpointRepository(db_session)
        updated = repo.update(
            active_endpoint.id,
            WebhookEndpointUpdate(url="https://new-url.com/hook"),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.url == "https://new-url.com/hook"
        assert updated.signature_algo == "hmac"  # unchanged

    def test_update_status(self, db_session, active_endpoint):
        """Test updating a webhook endpoint status."""
        repo = WebhookEndpointRepository(db_session)
        updated = repo.update(
            active_endpoint.id,
            WebhookEndpointUpdate(status="inactive"),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.status == "inactive"

    def test_update_signature_algo(self, db_session, active_endpoint):
        """Test updating a webhook endpoint signature algorithm."""
        repo = WebhookEndpointRepository(db_session)
        updated = repo.update(
            active_endpoint.id,
            WebhookEndpointUpdate(signature_algo="jwt"),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.signature_algo == "jwt"

    def test_update_not_found(self, db_session):
        """Test updating a non-existent webhook endpoint."""
        repo = WebhookEndpointRepository(db_session)
        assert (
            repo.update(uuid4(), WebhookEndpointUpdate(url="https://x.com"), DEFAULT_ORG_ID) is None
        )

    def test_delete(self, db_session, active_endpoint):
        """Test deleting a webhook endpoint."""
        repo = WebhookEndpointRepository(db_session)
        assert repo.delete(active_endpoint.id, DEFAULT_ORG_ID) is True
        assert repo.get_by_id(active_endpoint.id) is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent webhook endpoint."""
        repo = WebhookEndpointRepository(db_session)
        assert repo.delete(uuid4(), DEFAULT_ORG_ID) is False


class TestWebhookRepository:
    """Tests for WebhookRepository."""

    def test_create_webhook(self, db_session, active_endpoint):
        """Test creating a webhook."""
        repo = WebhookRepository(db_session)
        webhook = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "invoice.created"},
        )
        assert webhook.id is not None
        assert webhook.webhook_endpoint_id == active_endpoint.id
        assert webhook.webhook_type == "invoice.created"
        assert webhook.status == "pending"

    def test_create_webhook_with_all_fields(self, db_session, active_endpoint):
        """Test creating a webhook with all optional fields."""
        object_id = uuid4()
        repo = WebhookRepository(db_session)
        webhook = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            object_type="payment",
            object_id=object_id,
            payload={"event": "payment.succeeded", "amount": 5000},
        )
        assert webhook.object_type == "payment"
        assert webhook.object_id == object_id

    def test_get_by_id(self, db_session, sample_webhook):
        """Test getting a webhook by ID."""
        repo = WebhookRepository(db_session)
        webhook = repo.get_by_id(sample_webhook.id)
        assert webhook is not None
        assert webhook.webhook_type == "invoice.created"

    def test_get_by_id_not_found(self, db_session):
        """Test getting a webhook by non-existent ID."""
        repo = WebhookRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_all(self, db_session, active_endpoint):
        """Test getting all webhooks."""
        repo = WebhookRepository(db_session)
        repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            payload={"event": "2"},
        )
        webhooks = repo.get_all()
        assert len(webhooks) == 2

    def test_get_all_pagination(self, db_session, active_endpoint):
        """Test get_all with pagination."""
        repo = WebhookRepository(db_session)
        repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            payload={"event": "2"},
        )
        webhooks = repo.get_all(skip=0, limit=1)
        assert len(webhooks) == 1

    def test_get_all_filter_by_type(self, db_session, active_endpoint):
        """Test get_all filtered by webhook_type."""
        repo = WebhookRepository(db_session)
        repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            payload={"event": "2"},
        )
        webhooks = repo.get_all(webhook_type="invoice.created")
        assert len(webhooks) == 1
        assert webhooks[0].webhook_type == "invoice.created"

    def test_get_all_filter_by_status(self, db_session, active_endpoint):
        """Test get_all filtered by status."""
        repo = WebhookRepository(db_session)
        wh1 = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            payload={"event": "2"},
        )
        repo.mark_succeeded(wh1.id, 200)
        webhooks = repo.get_all(status="succeeded")
        assert len(webhooks) == 1

    def test_get_all_empty(self, db_session):
        """Test get_all with no webhooks."""
        repo = WebhookRepository(db_session)
        assert repo.get_all() == []

    def test_get_pending(self, db_session, active_endpoint):
        """Test getting pending webhooks."""
        repo = WebhookRepository(db_session)
        repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        wh2 = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            payload={"event": "2"},
        )
        repo.mark_succeeded(wh2.id, 200)
        pending = repo.get_pending()
        assert len(pending) == 1
        assert pending[0].webhook_type == "invoice.created"

    def test_get_pending_empty(self, db_session):
        """Test getting pending webhooks when none exist."""
        repo = WebhookRepository(db_session)
        assert repo.get_pending() == []

    def test_get_failed_for_retry(self, db_session, active_endpoint):
        """Test getting failed webhooks eligible for retry."""
        repo = WebhookRepository(db_session)
        wh = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        repo.mark_failed(wh.id, http_status=500, response="Internal Server Error")
        failed = repo.get_failed_for_retry()
        assert len(failed) == 1
        assert failed[0].id == wh.id

    def test_get_failed_for_retry_excludes_max_retries(self, db_session, active_endpoint):
        """Test that webhooks at max retries are excluded."""
        repo = WebhookRepository(db_session)
        wh = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        repo.mark_failed(wh.id, http_status=500)
        # Manually set retries to max
        webhook = repo.get_by_id(wh.id)
        assert webhook is not None
        webhook.retries = 5  # type: ignore[assignment]
        db_session.commit()
        failed = repo.get_failed_for_retry()
        assert len(failed) == 0

    def test_get_failed_for_retry_empty(self, db_session):
        """Test getting failed for retry when none exist."""
        repo = WebhookRepository(db_session)
        assert repo.get_failed_for_retry() == []

    def test_mark_succeeded(self, db_session, sample_webhook):
        """Test marking a webhook as succeeded."""
        repo = WebhookRepository(db_session)
        updated = repo.mark_succeeded(sample_webhook.id, 200)
        assert updated is not None
        assert updated.status == "succeeded"
        assert updated.http_status == 200

    def test_mark_succeeded_not_found(self, db_session):
        """Test marking a non-existent webhook as succeeded."""
        repo = WebhookRepository(db_session)
        assert repo.mark_succeeded(uuid4(), 200) is None

    def test_mark_failed(self, db_session, sample_webhook):
        """Test marking a webhook as failed."""
        repo = WebhookRepository(db_session)
        updated = repo.mark_failed(
            sample_webhook.id,
            http_status=500,
            response="Internal Server Error",
        )
        assert updated is not None
        assert updated.status == "failed"
        assert updated.http_status == 500
        assert updated.response == "Internal Server Error"

    def test_mark_failed_without_details(self, db_session, sample_webhook):
        """Test marking a webhook as failed without http_status/response."""
        repo = WebhookRepository(db_session)
        updated = repo.mark_failed(sample_webhook.id)
        assert updated is not None
        assert updated.status == "failed"
        assert updated.http_status is None
        assert updated.response is None

    def test_mark_failed_not_found(self, db_session):
        """Test marking a non-existent webhook as failed."""
        repo = WebhookRepository(db_session)
        assert repo.mark_failed(uuid4()) is None

    def test_increment_retry(self, db_session, sample_webhook):
        """Test incrementing a webhook retry count."""
        repo = WebhookRepository(db_session)
        updated = repo.increment_retry(sample_webhook.id)
        assert updated is not None
        assert updated.retries == 1
        assert updated.status == "pending"
        assert updated.last_retried_at is not None

    def test_increment_retry_multiple(self, db_session, sample_webhook):
        """Test incrementing retry count multiple times."""
        repo = WebhookRepository(db_session)
        repo.increment_retry(sample_webhook.id)
        updated = repo.increment_retry(sample_webhook.id)
        assert updated is not None
        assert updated.retries == 2

    def test_increment_retry_not_found(self, db_session):
        """Test incrementing retry on non-existent webhook."""
        repo = WebhookRepository(db_session)
        assert repo.increment_retry(uuid4()) is None

    def test_delivery_stats_by_endpoint_empty(self, db_session):
        """Test delivery stats with no webhooks."""
        repo = WebhookRepository(db_session)
        assert repo.delivery_stats_by_endpoint() == []

    def test_delivery_stats_by_endpoint(self, db_session, active_endpoint):
        """Test delivery stats grouped by endpoint."""
        repo = WebhookRepository(db_session)
        wh1 = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        wh2 = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            payload={"event": "2"},
        )
        wh3 = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="customer.created",
            payload={"event": "3"},
        )
        repo.mark_succeeded(wh1.id, 200)
        repo.mark_succeeded(wh2.id, 200)
        repo.mark_failed(wh3.id, http_status=500)

        stats = repo.delivery_stats_by_endpoint()
        assert len(stats) == 1
        assert stats[0]["endpoint_id"] == str(active_endpoint.id)
        assert stats[0]["total"] == 3
        assert stats[0]["succeeded"] == 2
        assert stats[0]["failed"] == 1

    def test_delivery_stats_multiple_endpoints(self, db_session):
        """Test delivery stats with multiple endpoints."""
        ep_repo = WebhookEndpointRepository(db_session)
        ep1 = ep_repo.create(
            WebhookEndpointCreate(url="https://ep1.com/hook"),
            DEFAULT_ORG_ID,
        )
        ep2 = ep_repo.create(
            WebhookEndpointCreate(url="https://ep2.com/hook"),
            DEFAULT_ORG_ID,
        )
        repo = WebhookRepository(db_session)
        wh1 = repo.create(
            webhook_endpoint_id=ep1.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        repo.mark_succeeded(wh1.id, 200)
        wh2 = repo.create(
            webhook_endpoint_id=ep2.id,
            webhook_type="invoice.created",
            payload={"event": "2"},
        )
        repo.mark_failed(wh2.id, http_status=500)

        stats = repo.delivery_stats_by_endpoint()
        assert len(stats) == 2
        stats_by_id = {s["endpoint_id"]: s for s in stats}
        assert stats_by_id[str(ep1.id)]["succeeded"] == 1
        assert stats_by_id[str(ep1.id)]["failed"] == 0
        assert stats_by_id[str(ep2.id)]["succeeded"] == 0
        assert stats_by_id[str(ep2.id)]["failed"] == 1


class TestWebhookEndpointSchema:
    """Tests for WebhookEndpoint Pydantic schemas."""

    def test_endpoint_create_basic(self):
        """Test WebhookEndpointCreate with required fields."""
        schema = WebhookEndpointCreate(url="https://example.com/hook")
        assert schema.url == "https://example.com/hook"
        assert schema.signature_algo == "hmac"

    def test_endpoint_create_with_jwt(self):
        """Test WebhookEndpointCreate with JWT signature."""
        schema = WebhookEndpointCreate(
            url="https://example.com/hook",
            signature_algo="jwt",
        )
        assert schema.signature_algo == "jwt"

    def test_endpoint_create_url_max_length(self):
        """Test WebhookEndpointCreate url max length validation."""
        with pytest.raises(ValidationError):
            WebhookEndpointCreate(url="https://x.com/" + "a" * 2048)

    def test_endpoint_create_signature_algo_max_length(self):
        """Test WebhookEndpointCreate signature_algo max length validation."""
        with pytest.raises(ValidationError):
            WebhookEndpointCreate(
                url="https://example.com/hook",
                signature_algo="x" * 51,
            )

    def test_endpoint_update_partial(self):
        """Test WebhookEndpointUpdate with partial fields."""
        schema = WebhookEndpointUpdate(url="https://new-url.com/hook")
        data = schema.model_dump(exclude_unset=True)
        assert data == {"url": "https://new-url.com/hook"}

    def test_endpoint_update_all_fields(self):
        """Test WebhookEndpointUpdate with all fields."""
        schema = WebhookEndpointUpdate(
            url="https://new.com",
            signature_algo="jwt",
            status="inactive",
        )
        data = schema.model_dump(exclude_unset=True)
        assert len(data) == 3

    def test_endpoint_update_url_max_length(self):
        """Test WebhookEndpointUpdate url max length validation."""
        with pytest.raises(ValidationError):
            WebhookEndpointUpdate(url="https://x.com/" + "a" * 2048)

    def test_endpoint_update_status_max_length(self):
        """Test WebhookEndpointUpdate status max length validation."""
        with pytest.raises(ValidationError):
            WebhookEndpointUpdate(status="x" * 51)

    def test_endpoint_response(self, db_session, active_endpoint):
        """Test WebhookEndpointResponse from ORM object."""
        response = WebhookEndpointResponse.model_validate(active_endpoint)
        assert response.url == "https://example.com/webhooks"
        assert response.signature_algo == "hmac"
        assert response.status == "active"
        assert response.created_at is not None
        assert response.updated_at is not None


class TestWebhookSchema:
    """Tests for Webhook Pydantic schemas."""

    def test_webhook_response(self, db_session, sample_webhook):
        """Test WebhookResponse from ORM object."""
        response = WebhookResponse.model_validate(sample_webhook)
        assert response.webhook_type == "invoice.created"
        assert response.object_type == "invoice"
        assert response.status == "pending"
        assert response.retries == 0
        assert response.max_retries == 5
        assert response.created_at is not None
        assert response.updated_at is not None

    def test_webhook_response_minimal(self, db_session, active_endpoint):
        """Test WebhookResponse with minimal fields set."""
        repo = WebhookRepository(db_session)
        webhook = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="test.event",
            payload={"data": "test"},
        )
        response = WebhookResponse.model_validate(webhook)
        assert response.object_type is None
        assert response.object_id is None
        assert response.last_retried_at is None
        assert response.http_status is None
        assert response.response is None

    def test_webhook_event_payload(self):
        """Test WebhookEventPayload schema."""
        payload = WebhookEventPayload(
            webhook_type="invoice.created",
            object_type="invoice",
            object_id=uuid4(),
            payload={"key": "value"},
        )
        assert payload.webhook_type == "invoice.created"
        assert payload.object_type == "invoice"

    def test_webhook_event_payload_minimal(self):
        """Test WebhookEventPayload with minimal fields."""
        payload = WebhookEventPayload(
            webhook_type="test.event",
            payload={"data": "test"},
        )
        assert payload.object_type is None
        assert payload.object_id is None

    def test_webhook_event_payload_type_max_length(self):
        """Test WebhookEventPayload webhook_type max length validation."""
        with pytest.raises(ValidationError):
            WebhookEventPayload(
                webhook_type="x" * 101,
                payload={"data": "test"},
            )

    def test_webhook_event_payload_object_type_max_length(self):
        """Test WebhookEventPayload object_type max length validation."""
        with pytest.raises(ValidationError):
            WebhookEventPayload(
                webhook_type="test.event",
                object_type="x" * 51,
                payload={"data": "test"},
            )

    def test_endpoint_delivery_stats_schema(self):
        """Test EndpointDeliveryStats schema."""
        stats = EndpointDeliveryStats(
            endpoint_id="abc-123",
            total=10,
            succeeded=8,
            failed=2,
            success_rate=80.0,
        )
        assert stats.total == 10
        assert stats.succeeded == 8
        assert stats.failed == 2
        assert stats.success_rate == 80.0
