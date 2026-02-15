"""Tests for WebhookService — webhook delivery, HMAC signing, and retry logic."""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.core.database import get_db
from app.repositories.webhook_endpoint_repository import WebhookEndpointRepository
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.webhook import WebhookEndpointCreate, WebhookEndpointUpdate
from app.services.webhook_service import (
    WEBHOOK_EVENT_TYPES,
    WebhookService,
    generate_hmac_signature,
)
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def service(db_session):
    """Create a WebhookService instance."""
    return WebhookService(db_session)


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
def second_active_endpoint(db_session):
    """Create a second active webhook endpoint."""
    repo = WebhookEndpointRepository(db_session)
    return repo.create(
        WebhookEndpointCreate(
            url="https://example.com/webhooks-2",
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


class TestDeliveryAttemptRepository:
    """Tests for WebhookRepository delivery attempt methods."""

    def test_create_delivery_attempt(self, db_session, active_endpoint):
        """Test creating a delivery attempt record."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )

        attempt = webhook_repo.create_delivery_attempt(
            webhook_id=webhook.id,
            attempt_number=0,
            success=True,
            http_status=200,
            response_body="OK",
        )

        assert attempt.webhook_id == webhook.id
        assert attempt.attempt_number == 0
        assert attempt.success is True
        assert attempt.http_status == 200
        assert attempt.response_body == "OK"
        assert attempt.error_message is None
        assert attempt.attempted_at is not None

    def test_create_delivery_attempt_with_error(self, db_session, active_endpoint):
        """Test creating a failed delivery attempt with error message."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )

        attempt = webhook_repo.create_delivery_attempt(
            webhook_id=webhook.id,
            attempt_number=0,
            success=False,
            error_message="Connection refused",
        )

        assert attempt.success is False
        assert attempt.http_status is None
        assert attempt.error_message == "Connection refused"

    def test_get_delivery_attempts_empty(self, db_session, active_endpoint):
        """Test getting delivery attempts when none exist."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )

        attempts = webhook_repo.get_delivery_attempts(webhook.id)
        assert attempts == []

    def test_get_delivery_attempts_ordered(self, db_session, active_endpoint):
        """Test that delivery attempts are returned in order."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )

        webhook_repo.create_delivery_attempt(
            webhook_id=webhook.id,
            attempt_number=2,
            success=True,
            http_status=200,
        )
        webhook_repo.create_delivery_attempt(
            webhook_id=webhook.id,
            attempt_number=0,
            success=False,
            http_status=500,
        )
        webhook_repo.create_delivery_attempt(
            webhook_id=webhook.id,
            attempt_number=1,
            success=False,
            http_status=502,
        )

        attempts = webhook_repo.get_delivery_attempts(webhook.id)
        assert len(attempts) == 3
        assert [a.attempt_number for a in attempts] == [0, 1, 2]

    def test_get_delivery_attempts_scoped_to_webhook(self, db_session, active_endpoint):
        """Test that delivery attempts are scoped to the correct webhook."""
        webhook_repo = WebhookRepository(db_session)
        wh1 = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        wh2 = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            payload={"event": "2"},
        )

        webhook_repo.create_delivery_attempt(
            webhook_id=wh1.id,
            attempt_number=0,
            success=True,
            http_status=200,
        )
        webhook_repo.create_delivery_attempt(
            webhook_id=wh2.id,
            attempt_number=0,
            success=False,
            http_status=500,
        )

        attempts_wh1 = webhook_repo.get_delivery_attempts(wh1.id)
        assert len(attempts_wh1) == 1
        assert attempts_wh1[0].success is True

        attempts_wh2 = webhook_repo.get_delivery_attempts(wh2.id)
        assert len(attempts_wh2) == 1
        assert attempts_wh2[0].success is False


class TestDeliveryAttemptSchema:
    """Tests for WebhookDeliveryAttemptResponse schema."""

    def test_schema_from_model(self, db_session, active_endpoint):
        """Test schema serialization from model."""
        from app.schemas.webhook import WebhookDeliveryAttemptResponse

        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="test",
            payload={"event": "test"},
        )
        attempt = webhook_repo.create_delivery_attempt(
            webhook_id=webhook.id,
            attempt_number=1,
            success=False,
            http_status=503,
            response_body="Service Unavailable",
            error_message=None,
        )

        response = WebhookDeliveryAttemptResponse.model_validate(attempt)
        assert response.webhook_id == webhook.id
        assert response.attempt_number == 1
        assert response.success is False
        assert response.http_status == 503
        assert response.response_body == "Service Unavailable"
        assert response.error_message is None

    def test_schema_optional_fields(self, db_session, active_endpoint):
        """Test schema with optional fields as None."""
        from app.schemas.webhook import WebhookDeliveryAttemptResponse

        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="test",
            payload={"event": "test"},
        )
        attempt = webhook_repo.create_delivery_attempt(
            webhook_id=webhook.id,
            attempt_number=0,
            success=False,
            error_message="Timeout",
        )

        response = WebhookDeliveryAttemptResponse.model_validate(attempt)
        assert response.http_status is None
        assert response.response_body is None
        assert response.error_message == "Timeout"


class TestGenerateHmacSignature:
    """Tests for the generate_hmac_signature function."""

    def test_generates_valid_hmac_sha256(self):
        """Test that HMAC-SHA256 signature is generated correctly."""
        payload = b'{"event": "test"}'
        secret = "test_secret"
        result = generate_hmac_signature(payload, secret)

        expected = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        assert result == expected

    def test_different_payloads_produce_different_signatures(self):
        """Test that different payloads produce different signatures."""
        secret = "test_secret"
        sig1 = generate_hmac_signature(b"payload_1", secret)
        sig2 = generate_hmac_signature(b"payload_2", secret)
        assert sig1 != sig2

    def test_different_secrets_produce_different_signatures(self):
        """Test that different secrets produce different signatures."""
        payload = b'{"event": "test"}'
        sig1 = generate_hmac_signature(payload, "secret_1")
        sig2 = generate_hmac_signature(payload, "secret_2")
        assert sig1 != sig2

    def test_same_inputs_produce_same_signature(self):
        """Test deterministic signature generation."""
        payload = b'{"event": "test"}'
        secret = "test_secret"
        sig1 = generate_hmac_signature(payload, secret)
        sig2 = generate_hmac_signature(payload, secret)
        assert sig1 == sig2

    def test_returns_hex_string(self):
        """Test that the signature is a hex-encoded string."""
        result = generate_hmac_signature(b"test", "secret")
        assert isinstance(result, str)
        # SHA-256 hex digest is 64 characters
        assert len(result) == 64
        # All characters should be valid hex
        int(result, 16)

    def test_empty_payload(self):
        """Test HMAC with empty payload."""
        result = generate_hmac_signature(b"", "secret")
        assert isinstance(result, str)
        assert len(result) == 64


class TestWebhookEventTypes:
    """Tests for the WEBHOOK_EVENT_TYPES constant."""

    def test_contains_invoice_events(self):
        """Test that invoice event types are defined."""
        assert "invoice.created" in WEBHOOK_EVENT_TYPES
        assert "invoice.finalized" in WEBHOOK_EVENT_TYPES
        assert "invoice.paid" in WEBHOOK_EVENT_TYPES
        assert "invoice.voided" in WEBHOOK_EVENT_TYPES

    def test_contains_payment_events(self):
        """Test that payment event types are defined."""
        assert "payment.created" in WEBHOOK_EVENT_TYPES
        assert "payment.succeeded" in WEBHOOK_EVENT_TYPES
        assert "payment.failed" in WEBHOOK_EVENT_TYPES

    def test_contains_subscription_events(self):
        """Test that subscription event types are defined."""
        assert "subscription.created" in WEBHOOK_EVENT_TYPES
        assert "subscription.terminated" in WEBHOOK_EVENT_TYPES
        assert "subscription.canceled" in WEBHOOK_EVENT_TYPES

    def test_contains_customer_events(self):
        """Test that customer event types are defined."""
        assert "customer.created" in WEBHOOK_EVENT_TYPES
        assert "customer.updated" in WEBHOOK_EVENT_TYPES

    def test_contains_credit_note_events(self):
        """Test that credit note event types are defined."""
        assert "credit_note.created" in WEBHOOK_EVENT_TYPES
        assert "credit_note.finalized" in WEBHOOK_EVENT_TYPES

    def test_contains_wallet_events(self):
        """Test that wallet event types are defined."""
        assert "wallet.created" in WEBHOOK_EVENT_TYPES
        assert "wallet.terminated" in WEBHOOK_EVENT_TYPES
        assert "wallet.transaction.created" in WEBHOOK_EVENT_TYPES


class TestSendWebhook:
    """Tests for WebhookService.send_webhook."""

    def test_creates_webhook_for_active_endpoint(self, service, active_endpoint):
        """Test that a webhook is created for an active endpoint."""
        object_id = uuid4()
        webhooks = service.send_webhook(
            webhook_type="invoice.created",
            object_type="invoice",
            object_id=object_id,
            payload={"event": "invoice.created", "data": {"id": str(object_id)}},
        )
        assert len(webhooks) == 1
        assert webhooks[0].webhook_type == "invoice.created"
        assert webhooks[0].webhook_endpoint_id == active_endpoint.id
        assert webhooks[0].object_type == "invoice"
        assert webhooks[0].object_id == object_id
        assert webhooks[0].status == "pending"

    def test_creates_webhooks_for_multiple_active_endpoints(
        self, service, active_endpoint, second_active_endpoint
    ):
        """Test that webhooks are created for all active endpoints."""
        webhooks = service.send_webhook(
            webhook_type="payment.succeeded",
            payload={"event": "payment.succeeded"},
        )
        assert len(webhooks) == 2
        endpoint_ids = {w.webhook_endpoint_id for w in webhooks}
        assert active_endpoint.id in endpoint_ids
        assert second_active_endpoint.id in endpoint_ids

    def test_skips_inactive_endpoints(self, service, active_endpoint, inactive_endpoint):
        """Test that inactive endpoints are skipped."""
        webhooks = service.send_webhook(
            webhook_type="invoice.created",
            payload={"event": "invoice.created"},
        )
        assert len(webhooks) == 1
        assert webhooks[0].webhook_endpoint_id == active_endpoint.id

    def test_returns_empty_list_when_no_active_endpoints(self, service, inactive_endpoint):
        """Test with no active endpoints."""
        webhooks = service.send_webhook(
            webhook_type="invoice.created",
            payload={"event": "invoice.created"},
        )
        assert webhooks == []

    def test_returns_empty_list_when_no_endpoints(self, service):
        """Test with no endpoints at all."""
        webhooks = service.send_webhook(
            webhook_type="invoice.created",
            payload={"event": "test"},
        )
        assert webhooks == []

    def test_send_webhook_with_none_payload(self, service, active_endpoint):
        """Test that None payload defaults to empty dict."""
        webhooks = service.send_webhook(
            webhook_type="test.event",
        )
        assert len(webhooks) == 1
        assert webhooks[0].payload == {}

    def test_send_webhook_without_object_fields(self, service, active_endpoint):
        """Test sending webhook without object_type and object_id."""
        webhooks = service.send_webhook(
            webhook_type="test.event",
            payload={"key": "value"},
        )
        assert len(webhooks) == 1
        assert webhooks[0].object_type is None
        assert webhooks[0].object_id is None


class TestDeliverWebhook:
    """Tests for WebhookService.deliver_webhook."""

    def test_successful_delivery(self, service, db_session, active_endpoint):
        """Test successful webhook delivery with 200 response."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
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

            result = service.deliver_webhook(webhook.id)

        assert result is True
        updated = webhook_repo.get_by_id(webhook.id)
        assert updated is not None
        assert updated.status == "succeeded"
        assert updated.http_status == 200

    def test_successful_delivery_201(self, service, db_session, active_endpoint):
        """Test successful webhook delivery with 201 response."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "invoice.created"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = "Created"

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = service.deliver_webhook(webhook.id)

        assert result is True
        updated = webhook_repo.get_by_id(webhook.id)
        assert updated is not None
        assert updated.status == "succeeded"

    def test_failed_delivery_500(self, service, db_session, active_endpoint):
        """Test failed webhook delivery with 500 response."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
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

            result = service.deliver_webhook(webhook.id)

        assert result is False
        updated = webhook_repo.get_by_id(webhook.id)
        assert updated is not None
        assert updated.status == "failed"
        assert updated.http_status == 500
        assert updated.response == "Internal Server Error"

    def test_failed_delivery_404(self, service, db_session, active_endpoint):
        """Test failed webhook delivery with 404 response."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = service.deliver_webhook(webhook.id)

        assert result is False
        updated = webhook_repo.get_by_id(webhook.id)
        assert updated is not None
        assert updated.status == "failed"
        assert updated.http_status == 404

    def test_failed_delivery_empty_response_text(self, service, db_session, active_endpoint):
        """Test failed delivery when response text is empty."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = ""

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = service.deliver_webhook(webhook.id)

        assert result is False
        updated = webhook_repo.get_by_id(webhook.id)
        assert updated is not None
        assert updated.response is None

    def test_delivery_http_error(self, service, db_session, active_endpoint):
        """Test webhook delivery when HTTP error occurs."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
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

            result = service.deliver_webhook(webhook.id)

        assert result is False
        updated = webhook_repo.get_by_id(webhook.id)
        assert updated is not None
        assert updated.status == "failed"
        assert "Connection refused" in (updated.response or "")

    def test_delivery_timeout_error(self, service, db_session, active_endpoint):
        """Test webhook delivery when timeout occurs."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ReadTimeout("Read timed out")
            mock_client_cls.return_value = mock_client

            result = service.deliver_webhook(webhook.id)

        assert result is False

    def test_deliver_nonexistent_webhook(self, service):
        """Test delivering a webhook that doesn't exist."""
        result = service.deliver_webhook(uuid4())
        assert result is False

    def test_deliver_webhook_with_deleted_endpoint(self, service, db_session, active_endpoint):
        """Test delivering a webhook whose endpoint has been deleted."""
        webhook_repo = WebhookRepository(db_session)
        # We can't delete because of RESTRICT FK, so simulate by
        # creating a webhook with a fake endpoint id
        from app.models.webhook import Webhook

        fake_wh = Webhook(
            webhook_endpoint_id=uuid4(),
            webhook_type="test",
            payload={"x": 1},
        )
        db_session.add(fake_wh)
        db_session.commit()
        db_session.refresh(fake_wh)

        result = service.deliver_webhook(fake_wh.id)
        assert result is False
        updated = webhook_repo.get_by_id(fake_wh.id)
        assert updated is not None
        assert updated.status == "failed"
        assert updated.response == "Endpoint not found"

    def test_delivery_sends_correct_headers(self, service, db_session, active_endpoint):
        """Test that delivery sends the correct headers."""
        webhook_repo = WebhookRepository(db_session)
        payload = {"event": "invoice.created", "data": {"id": "123"}}
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload=payload,
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

            service.deliver_webhook(webhook.id)

            call_args = mock_client.post.call_args
            headers = call_args.kwargs["headers"]
            assert headers["Content-Type"] == "application/json"
            assert "X-Bxb-Signature" in headers
            assert headers["X-Bxb-Signature-Algorithm"] == "hmac"
            assert headers["X-Bxb-Webhook-Id"] == str(webhook.id)

    def test_delivery_sends_correct_payload(self, service, db_session, active_endpoint):
        """Test that the correct payload is sent to the endpoint."""
        webhook_repo = WebhookRepository(db_session)
        payload = {"event": "invoice.created", "amount": 1000}
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload=payload,
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

            service.deliver_webhook(webhook.id)

            call_args = mock_client.post.call_args
            sent_content = call_args.kwargs["content"]
            assert json.loads(sent_content) == payload

    def test_delivery_posts_to_correct_url(self, service, db_session, active_endpoint):
        """Test that the POST is sent to the correct endpoint URL."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
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

            service.deliver_webhook(webhook.id)

            call_args = mock_client.post.call_args
            assert call_args.args[0] == "https://example.com/webhooks"

    def test_delivery_signature_matches_payload(self, service, db_session, active_endpoint):
        """Test that the signature in the header matches the payload."""
        webhook_repo = WebhookRepository(db_session)
        payload = {"event": "invoice.created", "data": {"amount": 500}}
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload=payload,
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

            with patch("app.services.webhook_service.settings") as mock_settings:
                mock_settings.webhook_secret = "test_secret_123"
                service.deliver_webhook(webhook.id)

            call_args = mock_client.post.call_args
            headers = call_args.kwargs["headers"]
            sent_content = call_args.kwargs["content"]

            expected_sig = generate_hmac_signature(sent_content, "test_secret_123")
            assert headers["X-Bxb-Signature"] == expected_sig

    def test_long_response_text_truncated(self, service, db_session, active_endpoint):
        """Test that long response text is truncated to 1000 chars."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "x" * 2000

        with patch("app.services.webhook_service.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            service.deliver_webhook(webhook.id)

        updated = webhook_repo.get_by_id(webhook.id)
        assert updated is not None
        assert len(updated.response) == 1000


class TestRetryFailedWebhooks:
    """Tests for WebhookService.retry_failed_webhooks."""

    def test_retries_eligible_failed_webhooks(self, service, db_session, active_endpoint):
        """Test that failed webhooks with retries < max_retries are retried."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )
        webhook_repo.mark_failed(webhook.id, http_status=500)

        with patch.object(service, "deliver_webhook") as mock_deliver:
            count = service.retry_failed_webhooks()

        assert count == 1
        mock_deliver.assert_called_once()

    def test_skips_webhooks_within_backoff_period(self, service, db_session, active_endpoint):
        """Test that webhooks within backoff period are skipped."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )
        webhook_repo.mark_failed(webhook.id, http_status=500)
        # Increment retry so last_retried_at is set to now
        webhook_repo.increment_retry(webhook.id)
        # Mark as failed again
        webhook_repo.mark_failed(webhook.id, http_status=500)

        with patch.object(service, "deliver_webhook") as mock_deliver:
            count = service.retry_failed_webhooks()

        assert count == 0
        mock_deliver.assert_not_called()

    def test_retries_webhook_after_backoff_period(self, service, db_session, active_endpoint):
        """Test that webhooks past the backoff period are retried."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )
        webhook_repo.mark_failed(webhook.id, http_status=500)
        webhook_repo.increment_retry(webhook.id)

        # Set last_retried_at to far in the past
        wh = webhook_repo.get_by_id(webhook.id)
        assert wh is not None
        wh.last_retried_at = datetime.now(UTC) - timedelta(hours=1)  # type: ignore[assignment]
        wh.status = "failed"  # type: ignore[assignment]
        db_session.commit()

        with patch.object(service, "deliver_webhook") as mock_deliver:
            count = service.retry_failed_webhooks()

        assert count == 1
        mock_deliver.assert_called_once()

    def test_does_not_retry_max_retries_reached(self, service, db_session, active_endpoint):
        """Test that webhooks at max_retries are not retried."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )
        webhook_repo.mark_failed(webhook.id, http_status=500)

        # Set retries to max
        wh = webhook_repo.get_by_id(webhook.id)
        assert wh is not None
        wh.retries = 5  # type: ignore[assignment]
        db_session.commit()

        with patch.object(service, "deliver_webhook") as mock_deliver:
            count = service.retry_failed_webhooks()

        assert count == 0
        mock_deliver.assert_not_called()

    def test_returns_zero_when_no_failed_webhooks(self, service):
        """Test retry returns 0 when there are no failed webhooks."""
        with patch.object(service, "deliver_webhook") as mock_deliver:
            count = service.retry_failed_webhooks()

        assert count == 0
        mock_deliver.assert_not_called()

    def test_retries_multiple_eligible_webhooks(self, service, db_session, active_endpoint):
        """Test that multiple eligible webhooks are retried."""
        webhook_repo = WebhookRepository(db_session)
        wh1 = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "1"},
        )
        wh2 = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="payment.succeeded",
            payload={"event": "2"},
        )
        webhook_repo.mark_failed(wh1.id, http_status=500)
        webhook_repo.mark_failed(wh2.id, http_status=502)

        with patch.object(service, "deliver_webhook") as mock_deliver:
            count = service.retry_failed_webhooks()

        assert count == 2
        assert mock_deliver.call_count == 2

    def test_retry_increments_retry_count(self, service, db_session, active_endpoint):
        """Test that retry increments the retry count before delivery."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )
        webhook_repo.mark_failed(webhook.id, http_status=500)

        with patch.object(service, "deliver_webhook"):
            service.retry_failed_webhooks()

        updated = webhook_repo.get_by_id(webhook.id)
        assert updated is not None
        # increment_retry sets status to "pending" and increments retries
        # then deliver_webhook is called which may change status again
        assert updated.retries >= 1

    def test_exponential_backoff_first_retry(self, service, db_session, active_endpoint):
        """Test backoff: first retry (retries=1) needs 2^1=2 minutes."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )
        webhook_repo.mark_failed(webhook.id, http_status=500)
        webhook_repo.increment_retry(webhook.id)

        # Set last_retried_at to 1 minute ago (less than 2^1=2 min backoff)
        wh = webhook_repo.get_by_id(webhook.id)
        assert wh is not None
        wh.last_retried_at = datetime.now(UTC) - timedelta(minutes=1)  # type: ignore[assignment]
        wh.status = "failed"  # type: ignore[assignment]
        db_session.commit()

        with patch.object(service, "deliver_webhook") as mock_deliver:
            count = service.retry_failed_webhooks()

        # Should not retry — 1 min < 2^1=2 min backoff
        assert count == 0
        mock_deliver.assert_not_called()

    def test_exponential_backoff_second_retry(self, service, db_session, active_endpoint):
        """Test backoff: second retry (retries=2) needs 2^2=4 minutes."""
        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=active_endpoint.id,
            webhook_type="invoice.created",
            payload={"event": "test"},
        )
        webhook_repo.mark_failed(webhook.id, http_status=500)
        webhook_repo.increment_retry(webhook.id)
        webhook_repo.increment_retry(webhook.id)

        # Set last_retried_at to 3 minutes ago (less than 2^2=4 min backoff)
        wh = webhook_repo.get_by_id(webhook.id)
        assert wh is not None
        wh.last_retried_at = datetime.now(UTC) - timedelta(minutes=3)  # type: ignore[assignment]
        wh.status = "failed"  # type: ignore[assignment]
        db_session.commit()

        with patch.object(service, "deliver_webhook") as mock_deliver:
            count = service.retry_failed_webhooks()

        # Should not retry — 3 min < 2^2=4 min backoff
        assert count == 0
        mock_deliver.assert_not_called()
