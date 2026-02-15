"""Tests for Webhook API routers and webhook trigger integration."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.webhook_endpoint_repository import WebhookEndpointRepository
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.webhook import WebhookEndpointCreate
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


@pytest.fixture
def failed_webhook(db_session, active_endpoint):
    """Create a failed webhook."""
    repo = WebhookRepository(db_session)
    wh = repo.create(
        webhook_endpoint_id=active_endpoint.id,
        webhook_type="invoice.created",
        object_type="invoice",
        object_id=uuid4(),
        payload={"event": "invoice.created"},
    )
    repo.mark_failed(wh.id, http_status=500, response="Internal Server Error")
    return repo.get_by_id(wh.id)


class TestWebhookEndpointAPI:
    """Tests for webhook endpoint CRUD API."""

    def test_create_webhook_endpoint(self, client: TestClient):
        """Test creating a webhook endpoint."""
        response = client.post(
            "/v1/webhook_endpoints/",
            json={"url": "https://example.com/hook"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["url"] == "https://example.com/hook"
        assert data["signature_algo"] == "hmac"
        assert data["status"] == "active"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_webhook_endpoint_with_jwt(self, client: TestClient):
        """Test creating a webhook endpoint with JWT signature."""
        response = client.post(
            "/v1/webhook_endpoints/",
            json={
                "url": "https://example.com/jwt-hook",
                "signature_algo": "jwt",
            },
        )
        assert response.status_code == 201
        assert response.json()["signature_algo"] == "jwt"

    def test_list_webhook_endpoints_empty(self, client: TestClient):
        """Test listing webhook endpoints when none exist."""
        response = client.get("/v1/webhook_endpoints/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_webhook_endpoints(self, client: TestClient):
        """Test listing webhook endpoints."""
        client.post(
            "/v1/webhook_endpoints/",
            json={"url": "https://example.com/hook1"},
        )
        client.post(
            "/v1/webhook_endpoints/",
            json={"url": "https://example.com/hook2"},
        )
        response = client.get("/v1/webhook_endpoints/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_webhook_endpoints_pagination(self, client: TestClient):
        """Test listing webhook endpoints with pagination."""
        for i in range(3):
            client.post(
                "/v1/webhook_endpoints/",
                json={"url": f"https://example.com/hook{i}"},
            )
        response = client.get("/v1/webhook_endpoints/?skip=1&limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_get_webhook_endpoint(self, client: TestClient):
        """Test getting a webhook endpoint by ID."""
        create_resp = client.post(
            "/v1/webhook_endpoints/",
            json={"url": "https://example.com/get-hook"},
        )
        endpoint_id = create_resp.json()["id"]

        response = client.get(f"/v1/webhook_endpoints/{endpoint_id}")
        assert response.status_code == 200
        assert response.json()["url"] == "https://example.com/get-hook"

    def test_get_webhook_endpoint_not_found(self, client: TestClient):
        """Test getting a non-existent webhook endpoint."""
        response = client.get(f"/v1/webhook_endpoints/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook endpoint not found"

    def test_update_webhook_endpoint(self, client: TestClient):
        """Test updating a webhook endpoint."""
        create_resp = client.post(
            "/v1/webhook_endpoints/",
            json={"url": "https://example.com/update-hook"},
        )
        endpoint_id = create_resp.json()["id"]

        response = client.put(
            f"/v1/webhook_endpoints/{endpoint_id}",
            json={"url": "https://new-url.com/hook"},
        )
        assert response.status_code == 200
        assert response.json()["url"] == "https://new-url.com/hook"

    def test_update_webhook_endpoint_status(self, client: TestClient):
        """Test updating a webhook endpoint status."""
        create_resp = client.post(
            "/v1/webhook_endpoints/",
            json={"url": "https://example.com/status-hook"},
        )
        endpoint_id = create_resp.json()["id"]

        response = client.put(
            f"/v1/webhook_endpoints/{endpoint_id}",
            json={"status": "inactive"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "inactive"

    def test_update_webhook_endpoint_not_found(self, client: TestClient):
        """Test updating a non-existent webhook endpoint."""
        response = client.put(
            f"/v1/webhook_endpoints/{uuid4()}",
            json={"url": "https://x.com"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook endpoint not found"

    def test_delete_webhook_endpoint(self, client: TestClient):
        """Test deleting a webhook endpoint."""
        create_resp = client.post(
            "/v1/webhook_endpoints/",
            json={"url": "https://example.com/delete-hook"},
        )
        endpoint_id = create_resp.json()["id"]

        response = client.delete(f"/v1/webhook_endpoints/{endpoint_id}")
        assert response.status_code == 204

        # Confirm deleted
        get_resp = client.get(f"/v1/webhook_endpoints/{endpoint_id}")
        assert get_resp.status_code == 404

    def test_delete_webhook_endpoint_not_found(self, client: TestClient):
        """Test deleting a non-existent webhook endpoint."""
        response = client.delete(f"/v1/webhook_endpoints/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook endpoint not found"


class TestDeliveryStatsAPI:
    """Tests for webhook delivery stats API endpoint."""

    def test_delivery_stats_empty(self, client: TestClient):
        """Test delivery stats with no webhooks."""
        response = client.get("/v1/webhook_endpoints/delivery_stats")
        assert response.status_code == 200
        assert response.json() == []

    def test_delivery_stats_with_data(self, client: TestClient, db_session, active_endpoint):
        """Test delivery stats with mixed webhook statuses."""
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
        wh4 = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.finalized",
            payload={"event": "4"},
        )
        repo.mark_succeeded(wh1.id, 200)
        repo.mark_succeeded(wh2.id, 200)
        repo.mark_succeeded(wh3.id, 200)
        repo.mark_failed(wh4.id, http_status=500)

        response = client.get("/v1/webhook_endpoints/delivery_stats")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        stats = data[0]
        assert stats["endpoint_id"] == str(active_endpoint.id)
        assert stats["total"] == 4
        assert stats["succeeded"] == 3
        assert stats["failed"] == 1
        assert stats["success_rate"] == 75.0

    def test_delivery_stats_all_succeeded(self, client: TestClient, db_session, active_endpoint):
        """Test delivery stats when all webhooks succeeded."""
        repo = WebhookRepository(db_session)
        wh = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        repo.mark_succeeded(wh.id, 200)

        response = client.get("/v1/webhook_endpoints/delivery_stats")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["success_rate"] == 100.0

    def test_delivery_stats_pending_webhooks(self, client: TestClient, db_session, active_endpoint):
        """Test delivery stats includes pending webhooks in total but not succeeded/failed."""
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

        response = client.get("/v1/webhook_endpoints/delivery_stats")
        assert response.status_code == 200
        data = response.json()
        stats = data[0]
        assert stats["total"] == 2
        assert stats["succeeded"] == 1
        assert stats["failed"] == 0
        assert stats["success_rate"] == 50.0


class TestWebhookListAPI:
    """Tests for webhook list/detail/retry API endpoints."""

    def test_list_webhooks_empty(self, client: TestClient):
        """Test listing webhooks when none exist."""
        response = client.get("/v1/webhook_endpoints/hooks/list")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_webhooks(self, client: TestClient, sample_webhook):
        """Test listing webhooks."""
        response = client.get("/v1/webhook_endpoints/hooks/list")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["webhook_type"] == "invoice.created"

    def test_list_webhooks_filter_by_type(self, client: TestClient, db_session, active_endpoint):
        """Test listing webhooks filtered by type."""
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

        response = client.get("/v1/webhook_endpoints/hooks/list?webhook_type=invoice.created")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["webhook_type"] == "invoice.created"

    def test_list_webhooks_filter_by_status(self, client: TestClient, db_session, active_endpoint):
        """Test listing webhooks filtered by status."""
        repo = WebhookRepository(db_session)
        wh = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        repo.mark_succeeded(wh.id, 200)
        repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            payload={"event": "2"},
        )

        response = client.get("/v1/webhook_endpoints/hooks/list?status=succeeded")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "succeeded"

    def test_list_webhooks_pagination(self, client: TestClient, db_session, active_endpoint):
        """Test listing webhooks with pagination."""
        repo = WebhookRepository(db_session)
        for i in range(3):
            repo.create(
                webhook_endpoint_id=active_endpoint.id,
                webhook_type="invoice.created",
                payload={"event": str(i)},
            )

        response = client.get("/v1/webhook_endpoints/hooks/list?skip=1&limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_get_webhook(self, client: TestClient, sample_webhook):
        """Test getting a webhook by ID."""
        response = client.get(f"/v1/webhook_endpoints/hooks/{sample_webhook.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["webhook_type"] == "invoice.created"
        assert data["status"] == "pending"

    def test_get_webhook_not_found(self, client: TestClient):
        """Test getting a non-existent webhook."""
        response = client.get(f"/v1/webhook_endpoints/hooks/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook not found"

    def test_retry_failed_webhook(self, client: TestClient, failed_webhook):
        """Test manually retrying a failed webhook."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            response = client.post(f"/v1/webhook_endpoints/hooks/{failed_webhook.id}/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "succeeded"

    def test_retry_non_failed_webhook(self, client: TestClient, sample_webhook):
        """Test retrying a webhook that is not in failed status."""
        response = client.post(f"/v1/webhook_endpoints/hooks/{sample_webhook.id}/retry")
        assert response.status_code == 400
        assert response.json()["detail"] == "Only failed webhooks can be retried"

    def test_retry_webhook_not_found(self, client: TestClient):
        """Test retrying a non-existent webhook."""
        response = client.post(f"/v1/webhook_endpoints/hooks/{uuid4()}/retry")
        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook not found"

    def test_retry_failed_webhook_delivery_fails(self, client: TestClient, failed_webhook):
        """Test retry when delivery also fails."""
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.text = "Bad Gateway"

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            response = client.post(f"/v1/webhook_endpoints/hooks/{failed_webhook.id}/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"


class TestDeliveryAttemptsAPI:
    """Tests for webhook delivery attempts API endpoint."""

    def test_delivery_attempts_empty(self, client: TestClient, sample_webhook):
        """Test fetching delivery attempts when none exist."""
        response = client.get(
            f"/v1/webhook_endpoints/hooks/{sample_webhook.id}/delivery_attempts"
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_delivery_attempts_after_successful_delivery(
        self, client: TestClient, db_session, active_endpoint
    ):
        """Test that successful delivery creates a delivery attempt record."""
        repo = WebhookRepository(db_session)
        webhook = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "invoice.created"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            from app.services.webhook_service import WebhookService

            svc = WebhookService(db_session)
            svc.deliver_webhook(webhook.id)

        response = client.get(
            f"/v1/webhook_endpoints/hooks/{webhook.id}/delivery_attempts"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["attempt_number"] == 0
        assert data[0]["success"] is True
        assert data[0]["http_status"] == 200
        assert data[0]["response_body"] == "OK"
        assert data[0]["error_message"] is None

    def test_delivery_attempts_after_failed_delivery(
        self, client: TestClient, db_session, active_endpoint
    ):
        """Test that failed delivery creates a delivery attempt record."""
        repo = WebhookRepository(db_session)
        webhook = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "invoice.created"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            from app.services.webhook_service import WebhookService

            svc = WebhookService(db_session)
            svc.deliver_webhook(webhook.id)

        response = client.get(
            f"/v1/webhook_endpoints/hooks/{webhook.id}/delivery_attempts"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["attempt_number"] == 0
        assert data[0]["success"] is False
        assert data[0]["http_status"] == 500
        assert data[0]["response_body"] == "Internal Server Error"

    def test_delivery_attempts_multiple_retries(
        self, client: TestClient, db_session, active_endpoint
    ):
        """Test delivery attempts accumulate across retries."""
        repo = WebhookRepository(db_session)
        webhook = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "invoice.created"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.text = "Bad Gateway"

        from app.services.webhook_service import WebhookService

        svc = WebhookService(db_session)

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            # Initial delivery (attempt 0) — fails
            svc.deliver_webhook(webhook.id)

            # Retry (attempt 1) — also fails
            repo.increment_retry(webhook.id)
            svc.deliver_webhook(webhook.id)

            # Retry (attempt 2) — succeeds
            repo.increment_retry(webhook.id)
            mock_response.status_code = 200
            mock_response.text = "OK"
            svc.deliver_webhook(webhook.id)

        response = client.get(
            f"/v1/webhook_endpoints/hooks/{webhook.id}/delivery_attempts"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Ordered by attempt_number ascending
        assert data[0]["attempt_number"] == 0
        assert data[0]["success"] is False
        assert data[0]["http_status"] == 502

        assert data[1]["attempt_number"] == 1
        assert data[1]["success"] is False
        assert data[1]["http_status"] == 502

        assert data[2]["attempt_number"] == 2
        assert data[2]["success"] is True
        assert data[2]["http_status"] == 200

    def test_delivery_attempts_not_found(self, client: TestClient):
        """Test 404 when webhook doesn't exist."""
        response = client.get(
            f"/v1/webhook_endpoints/hooks/{uuid4()}/delivery_attempts"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook not found"

    def test_delivery_attempts_http_error(
        self, client: TestClient, db_session, active_endpoint
    ):
        """Test that HTTP errors record delivery attempts with error_message."""
        import httpx

        repo = WebhookRepository(db_session)
        webhook = repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_cls.return_value = mock_client

            from app.services.webhook_service import WebhookService

            svc = WebhookService(db_session)
            svc.deliver_webhook(webhook.id)

        response = client.get(
            f"/v1/webhook_endpoints/hooks/{webhook.id}/delivery_attempts"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["success"] is False
        assert data[0]["http_status"] is None
        assert "Connection refused" in data[0]["error_message"]

    def test_delivery_attempts_endpoint_not_found(
        self, client: TestClient, db_session
    ):
        """Test delivery attempt recorded when endpoint is missing."""
        from app.models.webhook import Webhook as WebhookModel

        fake_wh = WebhookModel(
            webhook_endpoint_id=uuid4(),
            webhook_type="test",
            payload={"x": 1},
        )
        db_session.add(fake_wh)
        db_session.commit()
        db_session.refresh(fake_wh)

        from app.services.webhook_service import WebhookService

        svc = WebhookService(db_session)
        svc.deliver_webhook(fake_wh.id)

        response = client.get(
            f"/v1/webhook_endpoints/hooks/{fake_wh.id}/delivery_attempts"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["success"] is False
        assert data[0]["error_message"] == "Endpoint not found"


class TestInvoiceWebhookTriggers:
    """Tests for webhook triggers in the invoice router."""

    @pytest.fixture
    def invoice_fixtures(self, client: TestClient, db_session):
        """Create required fixtures for invoice tests."""
        # Create customer
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "wh_inv_cust", "name": "Webhook Invoice Customer"},
        ).json()

        # Create plan
        plan = client.post(
            "/v1/plans/",
            json={"code": "wh_inv_plan", "name": "Webhook Invoice Plan", "interval": "monthly"},
        ).json()

        # Create subscription
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "wh_inv_sub",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
            },
        ).json()

        # Create invoice
        now = datetime.now()
        repo = InvoiceRepository(db_session)
        invoice = repo.create(
            InvoiceCreate(
                customer_id=customer["id"],
                subscription_id=sub["id"],
                currency="USD",
                billing_period_start=now,
                billing_period_end=now + timedelta(days=30),
                line_items=[
                    InvoiceLineItem(
                        description="Test item",
                        quantity=Decimal("1"),
                        unit_price=Decimal("10.00"),
                        amount=Decimal("10.00"),
                    )
                ],
            )
        )

        return {"customer": customer, "plan": plan, "subscription": sub, "invoice": invoice}

    def test_finalize_invoice_triggers_webhook(self, client: TestClient, invoice_fixtures):
        """Test that finalizing an invoice triggers a webhook."""
        invoice = invoice_fixtures["invoice"]

        with patch("app.routers.invoices.WebhookService") as mock_webhook_cls:
            mock_service = MagicMock()
            mock_webhook_cls.return_value = mock_service

            response = client.post(f"/v1/invoices/{invoice.id}/finalize")

        assert response.status_code == 200
        mock_service.send_webhook.assert_called_once()
        call_kwargs = mock_service.send_webhook.call_args.kwargs
        assert call_kwargs["webhook_type"] == "invoice.finalized"
        assert call_kwargs["object_type"] == "invoice"

    def test_pay_invoice_triggers_webhook(self, client: TestClient, db_session, invoice_fixtures):
        """Test that paying an invoice triggers a webhook."""
        invoice = invoice_fixtures["invoice"]

        # Finalize first
        repo = InvoiceRepository(db_session)
        repo.finalize(invoice.id)

        with patch("app.routers.invoices.WebhookService") as mock_webhook_cls:
            mock_service = MagicMock()
            mock_webhook_cls.return_value = mock_service

            response = client.post(f"/v1/invoices/{invoice.id}/pay")

        assert response.status_code == 200
        mock_service.send_webhook.assert_called_once()
        call_kwargs = mock_service.send_webhook.call_args.kwargs
        assert call_kwargs["webhook_type"] == "invoice.paid"
        assert call_kwargs["object_type"] == "invoice"

    def test_void_invoice_triggers_webhook(self, client: TestClient, db_session, invoice_fixtures):
        """Test that voiding an invoice triggers a webhook."""
        invoice = invoice_fixtures["invoice"]

        # Finalize first
        repo = InvoiceRepository(db_session)
        repo.finalize(invoice.id)

        with patch("app.routers.invoices.WebhookService") as mock_webhook_cls:
            mock_service = MagicMock()
            mock_webhook_cls.return_value = mock_service

            response = client.post(f"/v1/invoices/{invoice.id}/void")

        assert response.status_code == 200
        mock_service.send_webhook.assert_called_once()
        call_kwargs = mock_service.send_webhook.call_args.kwargs
        assert call_kwargs["webhook_type"] == "invoice.voided"
        assert call_kwargs["object_type"] == "invoice"


class TestSubscriptionWebhookTriggers:
    """Tests for webhook triggers in the subscription router."""

    def test_create_subscription_triggers_webhook(self, client: TestClient):
        """Test that creating a subscription triggers a webhook."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "wh_sub_cust", "name": "Webhook Sub Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "wh_sub_plan", "name": "Webhook Sub Plan", "interval": "monthly"},
        ).json()

        with patch("app.routers.subscriptions.WebhookService") as mock_webhook_cls:
            mock_service = MagicMock()
            mock_webhook_cls.return_value = mock_service

            response = client.post(
                "/v1/subscriptions/",
                json={
                    "external_id": "wh_sub_create",
                    "customer_id": customer["id"],
                    "plan_id": plan["id"],
                },
            )

        assert response.status_code == 201
        mock_service.send_webhook.assert_called_once()
        call_kwargs = mock_service.send_webhook.call_args.kwargs
        assert call_kwargs["webhook_type"] == "subscription.created"
        assert call_kwargs["object_type"] == "subscription"

    def test_terminate_subscription_triggers_webhook(self, client: TestClient):
        """Test that terminating a subscription triggers a webhook."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "wh_term_cust", "name": "Webhook Term Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "wh_term_plan", "name": "Webhook Term Plan", "interval": "monthly"},
        ).json()

        with patch("app.routers.subscriptions.WebhookService") as mock_cls:
            mock_svc = MagicMock()
            mock_cls.return_value = mock_svc

            sub = client.post(
                "/v1/subscriptions/",
                json={
                    "external_id": "wh_sub_term",
                    "customer_id": customer["id"],
                    "plan_id": plan["id"],
                },
            ).json()

        mock_path = "app.services.subscription_lifecycle.WebhookService"
        with patch(mock_path) as mock_webhook_cls:
            mock_service = MagicMock()
            mock_webhook_cls.return_value = mock_service

            response = client.delete(f"/v1/subscriptions/{sub['id']}?on_termination_action=skip")

        assert response.status_code == 204
        mock_service.send_webhook.assert_called_once()
        call_kwargs = mock_service.send_webhook.call_args.kwargs
        assert call_kwargs["webhook_type"] == "subscription.terminated"
        assert call_kwargs["object_type"] == "subscription"

    def test_cancel_subscription_triggers_webhook(self, client: TestClient):
        """Test that canceling a subscription triggers a webhook."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "wh_cancel_cust", "name": "Webhook Cancel Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "wh_cancel_plan", "name": "Webhook Cancel Plan", "interval": "monthly"},
        ).json()

        with patch("app.routers.subscriptions.WebhookService") as mock_cls:
            mock_svc = MagicMock()
            mock_cls.return_value = mock_svc

            sub = client.post(
                "/v1/subscriptions/",
                json={
                    "external_id": "wh_sub_cancel",
                    "customer_id": customer["id"],
                    "plan_id": plan["id"],
                },
            ).json()

        mock_path = "app.services.subscription_lifecycle.WebhookService"
        with patch(mock_path) as mock_webhook_cls:
            mock_service = MagicMock()
            mock_webhook_cls.return_value = mock_service

            response = client.post(
                f"/v1/subscriptions/{sub['id']}/cancel?on_termination_action=skip"
            )

        assert response.status_code == 200
        mock_service.send_webhook.assert_called_once()
        call_kwargs = mock_service.send_webhook.call_args.kwargs
        assert call_kwargs["webhook_type"] == "subscription.canceled"
        assert call_kwargs["object_type"] == "subscription"


class TestPaymentWebhookTriggers:
    """Tests for webhook triggers in the payment router."""

    def test_mark_paid_triggers_webhook(self, client: TestClient, db_session):
        """Test that marking a payment as paid triggers a webhook."""
        customer = Customer(
            external_id="wh_pay_cust",
            name="Webhook Payment Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        # Create a finalized invoice
        now = datetime.now()
        invoice = Invoice(
            customer_id=customer.id,
            invoice_number="WH-PAY-001",
            status=InvoiceStatus.FINALIZED.value,
            currency="USD",
            subtotal=1000,
            total=1000,
            billing_period_start=now,
            billing_period_end=now + timedelta(days=30),
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)

        # Create a pending payment
        payment = Payment(
            invoice_id=invoice.id,
            customer_id=customer.id,
            amount=1000,
            currency="USD",
            provider="manual",
            status="pending",
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        with patch("app.routers.payments.WebhookService") as mock_webhook_cls:
            mock_service = MagicMock()
            mock_webhook_cls.return_value = mock_service

            response = client.post(f"/v1/payments/{payment.id}/mark-paid")

        assert response.status_code == 200
        mock_service.send_webhook.assert_called_once()
        call_kwargs = mock_service.send_webhook.call_args.kwargs
        assert call_kwargs["webhook_type"] == "payment.succeeded"
        assert call_kwargs["object_type"] == "payment"

    def test_payment_webhook_succeeded_triggers_webhook(self, client: TestClient, db_session):
        """Test that a succeeded payment provider webhook triggers our webhook."""
        customer = Customer(
            external_id="wh_prov_cust",
            name="Webhook Provider Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        now = datetime.now()
        invoice = Invoice(
            customer_id=customer.id,
            invoice_number="WH-PROV-001",
            status=InvoiceStatus.FINALIZED.value,
            currency="USD",
            subtotal=2000,
            total=2000,
            billing_period_start=now,
            billing_period_end=now + timedelta(days=30),
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)

        payment = Payment(
            invoice_id=invoice.id,
            customer_id=customer.id,
            amount=2000,
            currency="USD",
            provider="manual",
            status="pending",
            provider_checkout_id="checkout_123",
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        # Mock the payment provider
        mock_provider = MagicMock()
        mock_provider.verify_webhook_signature.return_value = True
        mock_result = MagicMock()
        mock_result.status = "succeeded"
        mock_result.provider_checkout_id = "checkout_123"
        mock_result.provider_payment_id = "pay_123"
        mock_result.event_type = "payment.succeeded"
        mock_result.metadata = {}
        mock_result.failure_reason = None
        mock_provider.parse_webhook.return_value = mock_result

        with (
            patch("app.routers.payments.get_payment_provider", return_value=mock_provider),
            patch("app.routers.payments.WebhookService") as mock_webhook_cls,
        ):
            mock_service = MagicMock()
            mock_webhook_cls.return_value = mock_service

            response = client.post(
                "/v1/payments/webhook/manual",
                content=b'{"event": "payment.succeeded"}',
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        mock_service.send_webhook.assert_called_once()
        call_kwargs = mock_service.send_webhook.call_args.kwargs
        assert call_kwargs["webhook_type"] == "payment.succeeded"

    def test_payment_webhook_failed_triggers_webhook(self, client: TestClient, db_session):
        """Test that a failed payment provider webhook triggers our webhook."""

        customer = Customer(
            external_id="wh_fail_cust",
            name="Webhook Fail Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        now = datetime.now()
        invoice = Invoice(
            customer_id=customer.id,
            invoice_number="WH-FAIL-001",
            status=InvoiceStatus.FINALIZED.value,
            currency="USD",
            subtotal=3000,
            total=3000,
            billing_period_start=now,
            billing_period_end=now + timedelta(days=30),
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)

        payment = Payment(
            invoice_id=invoice.id,
            customer_id=customer.id,
            amount=3000,
            currency="USD",
            provider="manual",
            status="pending",
            provider_checkout_id="checkout_fail_123",
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        mock_provider = MagicMock()
        mock_provider.verify_webhook_signature.return_value = True
        mock_result = MagicMock()
        mock_result.status = "failed"
        mock_result.provider_checkout_id = "checkout_fail_123"
        mock_result.provider_payment_id = "pay_fail_123"
        mock_result.event_type = "payment.failed"
        mock_result.metadata = {}
        mock_result.failure_reason = "Card declined"
        mock_provider.parse_webhook.return_value = mock_result

        with (
            patch("app.routers.payments.get_payment_provider", return_value=mock_provider),
            patch("app.routers.payments.WebhookService") as mock_webhook_cls,
        ):
            mock_service = MagicMock()
            mock_webhook_cls.return_value = mock_service

            response = client.post(
                "/v1/payments/webhook/manual",
                content=b'{"event": "payment.failed"}',
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        mock_service.send_webhook.assert_called_once()
        call_kwargs = mock_service.send_webhook.call_args.kwargs
        assert call_kwargs["webhook_type"] == "payment.failed"
