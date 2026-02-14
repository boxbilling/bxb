"""Tests for GoCardless payment provider."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.payment import PaymentProvider, PaymentStatus
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.customer import CustomerCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
from app.services.payment_provider import get_payment_provider
from app.services.payment_providers.gocardless import GoCardlessProvider
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
def customer(db_session):
    """Create a test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"gc_test_cust_{uuid4()}",
            name="GoCardless Test Customer",
            email="gc@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"gc_test_plan_{uuid4()}",
            name="GC Test Plan",
            interval="monthly",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def subscription(db_session, customer, plan):
    """Create a test subscription."""
    repo = SubscriptionRepository(db_session)
    return repo.create(
        SubscriptionCreate(
            external_id=f"gc_test_sub_{uuid4()}",
            customer_id=customer.id,
            plan_id=plan.id,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def finalized_invoice(db_session, customer, subscription):
    """Create a finalized test invoice."""
    repo = InvoiceRepository(db_session)
    invoice = repo.create(
        InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            due_date=datetime.now(UTC) + timedelta(days=14),
            line_items=[
                InvoiceLineItem(
                    description="GC Test Service",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    amount=Decimal("100.00"),
                )
            ],
        )
    )
    return repo.finalize(invoice.id)


class TestGoCardlessProviderInit:
    """Tests for GoCardless provider initialization."""

    def test_get_gocardless_provider(self):
        """Test getting GoCardless provider from factory."""
        provider = get_payment_provider(PaymentProvider.GOCARDLESS)
        assert isinstance(provider, GoCardlessProvider)
        assert provider.provider_name == PaymentProvider.GOCARDLESS

    def test_gocardless_provider_initialization(self):
        """Test GoCardless provider initialization with custom values."""
        provider = GoCardlessProvider(
            access_token="test_token",
            webhook_secret="test_secret",
            environment="live",
        )
        assert provider.access_token == "test_token"
        assert provider.webhook_secret == "test_secret"
        assert provider.environment == "live"
        assert provider._base_url == "https://api.gocardless.com"

    def test_gocardless_provider_sandbox_url(self):
        """Test GoCardless provider uses sandbox URL by default."""
        provider = GoCardlessProvider(
            access_token="test_token",
            environment="sandbox",
        )
        assert provider._base_url == "https://api-sandbox.gocardless.com"


class TestGoCardlessCheckoutSession:
    """Tests for GoCardless checkout session creation."""

    @patch("app.services.payment_providers.gocardless.urlopen")
    def test_create_checkout_session(self, mock_urlopen):
        """Test creating a GoCardless redirect flow."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"redirect_flows": {"id": "RE000123", "redirect_url": "https://pay.gocardless.com/flow/static/auth"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = GoCardlessProvider(
            access_token="test_token",
            environment="sandbox",
        )

        session = provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("100.00"),
            currency="GBP",
            customer_email="test@example.com",
            invoice_number="INV-GC-001",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            metadata={"custom": "data"},
        )

        assert session.provider_checkout_id == "RE000123"
        assert session.checkout_url == "https://pay.gocardless.com/flow/static/auth"
        assert session.expires_at is not None
        mock_urlopen.assert_called_once()

    @patch("app.services.payment_providers.gocardless.urlopen")
    def test_create_checkout_session_without_email(self, mock_urlopen):
        """Test creating a GoCardless redirect flow without email."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"redirect_flows": {"id": "RE000456", "redirect_url": "https://pay.gocardless.com/flow/auth"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = GoCardlessProvider(
            access_token="test_token",
            environment="sandbox",
        )

        session = provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("50.00"),
            currency="EUR",
            customer_email=None,
            invoice_number="INV-GC-002",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert session.provider_checkout_id == "RE000456"

        # Verify no prefilled_customer in request body
        call_args = mock_urlopen.call_args
        import json

        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode())
        assert "prefilled_customer" not in body["redirect_flows"]

    @patch("app.services.payment_providers.gocardless.urlopen")
    def test_create_checkout_session_gbp_scheme(self, mock_urlopen):
        """Test GoCardless uses bacs scheme for GBP."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"redirect_flows": {"id": "RE_GBP", "redirect_url": "https://pay.gocardless.com/flow"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = GoCardlessProvider(access_token="test_token", environment="sandbox")

        provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("75.00"),
            currency="GBP",
            customer_email="test@example.com",
            invoice_number="INV-GBP",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        import json

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode())
        assert body["redirect_flows"]["scheme"] == "bacs"

    @patch("app.services.payment_providers.gocardless.urlopen")
    def test_create_checkout_session_eur_scheme(self, mock_urlopen):
        """Test GoCardless uses sepa_core scheme for EUR."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"redirect_flows": {"id": "RE_EUR", "redirect_url": "https://pay.gocardless.com/flow"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = GoCardlessProvider(access_token="test_token", environment="sandbox")

        provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("75.00"),
            currency="EUR",
            customer_email=None,
            invoice_number="INV-EUR",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        import json

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode())
        assert body["redirect_flows"]["scheme"] == "sepa_core"

    @patch("app.services.payment_providers.gocardless.urlopen")
    def test_create_checkout_session_api_error(self, mock_urlopen):
        """Test GoCardless checkout session handles API errors."""
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        provider = GoCardlessProvider(
            access_token="test_token",
            environment="sandbox",
        )

        with pytest.raises(RuntimeError, match="GoCardless API request failed"):
            provider.create_checkout_session(
                payment_id=uuid4(),
                amount=Decimal("100.00"),
                currency="GBP",
                customer_email="test@example.com",
                invoice_number="INV-ERR",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    @patch("app.services.payment_providers.gocardless.urlopen")
    def test_create_checkout_session_empty_response(self, mock_urlopen):
        """Test GoCardless checkout session with empty/minimal response."""
        payment_id = uuid4()
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"redirect_flows": {}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = GoCardlessProvider(access_token="test_token", environment="sandbox")

        session = provider.create_checkout_session(
            payment_id=payment_id,
            amount=Decimal("100.00"),
            currency="GBP",
            customer_email=None,
            invoice_number="INV-EMPTY",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert session.provider_checkout_id == f"gc_rf_{payment_id}"
        assert session.checkout_url == ""

    @patch("app.services.payment_providers.gocardless.urlopen")
    def test_make_request_headers(self, mock_urlopen):
        """Test GoCardless API request headers."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": "ok"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = GoCardlessProvider(
            access_token="gc_test_token_123",
            environment="sandbox",
        )

        provider._make_request("POST", "/redirect_flows", {"test": "data"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        assert request_obj.get_header("Content-type") == "application/json"
        assert request_obj.get_header("Authorization") == "Bearer gc_test_token_123"
        assert (
            "Gocardless-version" in request_obj.headers
            or "GoCardless-Version" in request_obj.headers
        )


class TestGoCardlessWebhookSignature:
    """Tests for GoCardless webhook signature verification."""

    def test_verify_signature_no_secret(self):
        """Test signature verification without secret."""
        provider = GoCardlessProvider(webhook_secret="")
        result = provider.verify_webhook_signature(b"payload", "signature")
        assert result is False

    def test_verify_signature_valid(self):
        """Test signature verification with valid signature."""
        provider = GoCardlessProvider(webhook_secret="gc_secret")
        payload = b'{"events": [{"id": "EV123"}]}'
        expected_sig = hmac.new(b"gc_secret", payload, hashlib.sha256).hexdigest()
        result = provider.verify_webhook_signature(payload, expected_sig)
        assert result is True

    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        provider = GoCardlessProvider(webhook_secret="gc_secret")
        result = provider.verify_webhook_signature(b"payload", "invalid_sig")
        assert result is False


class TestGoCardlessWebhookParsing:
    """Tests for GoCardless webhook parsing."""

    def test_parse_webhook_no_events(self):
        """Test parsing webhook with no events."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook({"events": []})
        assert result.event_type == "gocardless.no_events"

    def test_parse_webhook_empty_payload(self):
        """Test parsing webhook with empty payload."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook({})
        assert result.event_type == "gocardless.no_events"

    def test_parse_webhook_payment_confirmed(self):
        """Test parsing payment confirmed event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "payments",
                        "action": "confirmed",
                        "links": {"payment": "PM000123", "mandate": "MD000456"},
                        "metadata": {"payment_id": "abc"},
                    }
                ]
            }
        )
        assert result.event_type == "payments.confirmed"
        assert result.provider_payment_id == "PM000123"
        assert result.provider_checkout_id == "MD000456"
        assert result.status == "succeeded"
        assert result.metadata["payment_id"] == "abc"

    def test_parse_webhook_payment_paid_out(self):
        """Test parsing payment paid_out event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "payments",
                        "action": "paid_out",
                        "links": {"payment": "PM_PO"},
                        "metadata": {},
                    }
                ]
            }
        )
        assert result.status == "succeeded"

    def test_parse_webhook_payment_failed(self):
        """Test parsing payment failed event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "payments",
                        "action": "failed",
                        "links": {"payment": "PM_FAIL"},
                        "metadata": {},
                        "details": {"description": "Insufficient funds"},
                    }
                ]
            }
        )
        assert result.event_type == "payments.failed"
        assert result.status == "failed"
        assert result.failure_reason == "Insufficient funds"

    def test_parse_webhook_payment_failed_with_message(self):
        """Test parsing payment failed event with message fallback."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "payments",
                        "action": "failed",
                        "links": {"payment": "PM_FAIL2"},
                        "metadata": {},
                        "details": {"message": "Bank declined"},
                    }
                ]
            }
        )
        assert result.failure_reason == "Bank declined"

    def test_parse_webhook_payment_failed_default_message(self):
        """Test parsing payment failed with default message."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "payments",
                        "action": "failed",
                        "links": {"payment": "PM_FAIL3"},
                        "metadata": {},
                        "details": {},
                    }
                ]
            }
        )
        assert result.failure_reason == "Payment failed"

    def test_parse_webhook_payment_cancelled(self):
        """Test parsing payment cancelled event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "payments",
                        "action": "cancelled",
                        "links": {"payment": "PM_CANCEL"},
                        "metadata": {},
                    }
                ]
            }
        )
        assert result.status == "canceled"

    def test_parse_webhook_payment_created(self):
        """Test parsing payment created event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "payments",
                        "action": "created",
                        "links": {"payment": "PM_NEW"},
                        "metadata": {},
                    }
                ]
            }
        )
        assert result.status == "pending"

    def test_parse_webhook_payment_submitted(self):
        """Test parsing payment submitted event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "payments",
                        "action": "submitted",
                        "links": {"payment": "PM_SUB"},
                        "metadata": {},
                    }
                ]
            }
        )
        assert result.status == "pending"

    def test_parse_webhook_mandate_active(self):
        """Test parsing mandate active event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "mandates",
                        "action": "active",
                        "links": {"mandate": "MD_ACTIVE"},
                        "metadata": {},
                    }
                ]
            }
        )
        assert result.event_type == "mandates.active"
        assert result.provider_checkout_id == "MD_ACTIVE"
        assert result.status == "succeeded"

    def test_parse_webhook_mandate_failed(self):
        """Test parsing mandate failed event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "mandates",
                        "action": "failed",
                        "links": {"mandate": "MD_FAIL"},
                        "metadata": {},
                        "details": {"description": "Bank rejected"},
                    }
                ]
            }
        )
        assert result.status == "failed"
        assert result.failure_reason == "Bank rejected"

    def test_parse_webhook_mandate_failed_with_message(self):
        """Test parsing mandate failed event with message fallback."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "mandates",
                        "action": "failed",
                        "links": {"mandate": "MD_FAIL2"},
                        "metadata": {},
                        "details": {"message": "Invalid bank details"},
                    }
                ]
            }
        )
        assert result.failure_reason == "Invalid bank details"

    def test_parse_webhook_mandate_failed_default_message(self):
        """Test parsing mandate failed with default message."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "mandates",
                        "action": "failed",
                        "links": {"mandate": "MD_FAIL3"},
                        "metadata": {},
                        "details": {},
                    }
                ]
            }
        )
        assert result.failure_reason == "Mandate setup failed"

    def test_parse_webhook_mandate_cancelled(self):
        """Test parsing mandate cancelled event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "mandates",
                        "action": "cancelled",
                        "links": {"mandate": "MD_CANCEL"},
                        "metadata": {},
                    }
                ]
            }
        )
        assert result.status == "canceled"

    def test_parse_webhook_mandate_created(self):
        """Test parsing mandate created event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "mandates",
                        "action": "created",
                        "links": {"mandate": "MD_NEW"},
                        "metadata": {},
                    }
                ]
            }
        )
        assert result.status == "pending"

    def test_parse_webhook_mandate_submitted(self):
        """Test parsing mandate submitted event."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "mandates",
                        "action": "submitted",
                        "links": {"mandate": "MD_SUB"},
                        "metadata": {},
                    }
                ]
            }
        )
        assert result.status == "pending"

    def test_parse_webhook_unknown_resource_type(self):
        """Test parsing webhook with unknown resource type."""
        provider = GoCardlessProvider()
        result = provider.parse_webhook(
            {
                "events": [
                    {
                        "resource_type": "subscriptions",
                        "action": "created",
                        "links": {},
                        "metadata": {"key": "value"},
                    }
                ]
            }
        )
        assert result.event_type == "subscriptions.created"
        assert result.status is None
        assert result.metadata == {"key": "value"}


class TestGoCardlessAPI:
    """Tests for GoCardless payment provider via the API."""

    @patch("app.routers.payments.get_payment_provider")
    def test_create_checkout_with_gocardless(self, mock_get_provider, client, finalized_invoice):
        """Test creating checkout session with GoCardless provider."""
        from app.services.payment_provider import CheckoutSession

        mock_provider = MagicMock()
        mock_provider.create_checkout_session.return_value = CheckoutSession(
            provider_checkout_id="RE_GC_123",
            checkout_url="https://pay.gocardless.com/flow/auth",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(finalized_invoice.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
                "provider": "gocardless",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["checkout_url"] == "https://pay.gocardless.com/flow/auth"
        assert data["provider"] == "gocardless"

    @patch("app.routers.payments.get_payment_provider")
    def test_gocardless_webhook_payment_confirmed(
        self, mock_get_provider, client, db_session, finalized_invoice, customer
    ):
        """Test GoCardless webhook for payment confirmation."""
        from app.services.payment_provider import WebhookResult

        mock_provider = MagicMock()
        mock_provider.verify_webhook_signature.return_value = True
        mock_provider.parse_webhook.return_value = WebhookResult(
            event_type="payments.confirmed",
            provider_payment_id="PM_GC_HOOK",
            provider_checkout_id="MD_GC_HOOK",
            status="succeeded",
        )
        mock_get_provider.return_value = mock_provider

        repo = PaymentRepository(db_session)
        gc_payment = repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=100.0,
            currency="GBP",
            provider=PaymentProvider.GOCARDLESS,
        )
        repo.set_provider_ids(
            payment_id=gc_payment.id,
            provider_checkout_id="MD_GC_HOOK",
        )

        response = client.post(
            "/v1/payments/webhook/gocardless",
            json={
                "events": [
                    {
                        "resource_type": "payments",
                        "action": "confirmed",
                        "links": {"payment": "PM_GC_HOOK", "mandate": "MD_GC_HOOK"},
                    }
                ]
            },
            headers={"Webhook-Signature": "valid_sig"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

    @patch("app.routers.payments.get_payment_provider")
    def test_gocardless_webhook_payment_failed(
        self, mock_get_provider, client, db_session, finalized_invoice, customer
    ):
        """Test GoCardless webhook for payment failure."""
        from app.services.payment_provider import WebhookResult

        mock_provider = MagicMock()
        mock_provider.verify_webhook_signature.return_value = True
        mock_provider.parse_webhook.return_value = WebhookResult(
            event_type="payments.failed",
            provider_payment_id="PM_GC_FAIL",
            provider_checkout_id="MD_GC_FAIL",
            status="failed",
            failure_reason="Insufficient funds",
        )
        mock_get_provider.return_value = mock_provider

        repo = PaymentRepository(db_session)
        gc_payment = repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=100.0,
            currency="GBP",
            provider=PaymentProvider.GOCARDLESS,
        )
        repo.set_provider_ids(
            payment_id=gc_payment.id,
            provider_checkout_id="MD_GC_FAIL",
        )

        response = client.post(
            "/v1/payments/webhook/gocardless",
            json={
                "events": [
                    {
                        "resource_type": "payments",
                        "action": "failed",
                        "links": {"payment": "PM_GC_FAIL", "mandate": "MD_GC_FAIL"},
                    }
                ]
            },
            headers={"Webhook-Signature": "valid_sig"},
        )
        assert response.status_code == 200

        db_session.expire_all()
        updated = repo.get_by_id(gc_payment.id)
        assert updated.status == PaymentStatus.FAILED.value

    def test_gocardless_webhook_invalid_signature(self, client):
        """Test GoCardless webhook with invalid signature."""
        response = client.post(
            "/v1/payments/webhook/gocardless",
            json={"events": [{"resource_type": "payments", "action": "confirmed"}]},
            headers={"Webhook-Signature": "invalid"},
        )
        assert response.status_code == 401

    def test_list_payments_by_gocardless_provider(
        self, client, db_session, finalized_invoice, customer
    ):
        """Test filtering payments by GoCardless provider."""
        repo = PaymentRepository(db_session)
        repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=75.0,
            currency="GBP",
            provider=PaymentProvider.GOCARDLESS,
        )

        response = client.get("/v1/payments/?provider=gocardless")
        assert response.status_code == 200
        assert len(response.json()) >= 1
        assert all(p["provider"] == "gocardless" for p in response.json())
