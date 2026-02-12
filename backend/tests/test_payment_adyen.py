"""Tests for Adyen payment provider."""

import base64
import hashlib
import hmac
from datetime import datetime, timedelta
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
from app.services.payment_providers.adyen import AdyenProvider
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
            external_id=f"adyen_test_cust_{uuid4()}",
            name="Adyen Test Customer",
            email="adyen@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"adyen_test_plan_{uuid4()}",
            name="Adyen Test Plan",
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
            external_id=f"adyen_test_sub_{uuid4()}",
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
            billing_period_start=datetime.utcnow(),
            billing_period_end=datetime.utcnow() + timedelta(days=30),
            due_date=datetime.utcnow() + timedelta(days=14),
            line_items=[
                InvoiceLineItem(
                    description="Adyen Test Service",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    amount=Decimal("100.00"),
                )
            ],
        )
    )
    return repo.finalize(invoice.id)


class TestAdyenProviderInit:
    """Tests for Adyen provider initialization."""

    def test_get_adyen_provider(self):
        """Test getting Adyen provider from factory."""
        provider = get_payment_provider(PaymentProvider.ADYEN)
        assert isinstance(provider, AdyenProvider)
        assert provider.provider_name == PaymentProvider.ADYEN

    def test_adyen_provider_initialization_test_env(self):
        """Test Adyen provider initialization with test environment."""
        provider = AdyenProvider(
            api_key="test_api_key",
            merchant_account="TestMerchant",
            webhook_hmac_key="test_hmac",
            environment="test",
        )
        assert provider.api_key == "test_api_key"
        assert provider.merchant_account == "TestMerchant"
        assert provider.webhook_hmac_key == "test_hmac"
        assert provider.environment == "test"
        assert provider._base_url == "https://checkout-test.adyen.com/v71"

    def test_adyen_provider_initialization_live_env(self):
        """Test Adyen provider initialization with live environment."""
        provider = AdyenProvider(
            api_key="live_api_key",
            merchant_account="LiveMerchant",
            environment="live",
            live_url_prefix="abc123def456",
        )
        assert provider._base_url == (
            "https://abc123def456-checkout-live.adyenpayments.com/checkout/v71"
        )

    def test_adyen_provider_initialization_live_no_prefix(self):
        """Test Adyen provider initialization with live env but no prefix falls back to test URL."""
        provider = AdyenProvider(
            api_key="live_api_key",
            merchant_account="LiveMerchant",
            environment="live",
            live_url_prefix="",
        )
        assert provider._base_url == "https://checkout-test.adyen.com/v71"


class TestAdyenCheckoutSession:
    """Tests for Adyen checkout session creation."""

    @patch("app.services.payment_providers.adyen.urlopen")
    def test_create_checkout_session(self, mock_urlopen):
        """Test creating an Adyen payment session."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"id": "CS_ADYEN_123", "url": "https://checkoutshopper-test.adyen.com/session/CS_ADYEN_123"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = AdyenProvider(
            api_key="test_key",
            merchant_account="TestMerchant",
            environment="test",
        )

        session = provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("100.00"),
            currency="EUR",
            customer_email="test@example.com",
            invoice_number="INV-ADYEN-001",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            metadata={"custom": "data"},
        )

        assert session.provider_checkout_id == "CS_ADYEN_123"
        assert "checkoutshopper" in session.checkout_url
        assert session.expires_at is not None
        mock_urlopen.assert_called_once()

    @patch("app.services.payment_providers.adyen.urlopen")
    def test_create_checkout_session_without_email(self, mock_urlopen):
        """Test creating Adyen session without email."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"id": "CS_NO_EMAIL", "url": "https://checkout.adyen.com/session"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = AdyenProvider(
            api_key="test_key",
            merchant_account="TestMerchant",
            environment="test",
        )

        session = provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("50.00"),
            currency="USD",
            customer_email=None,
            invoice_number="INV-ADYEN-002",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert session.provider_checkout_id == "CS_NO_EMAIL"

        # Verify shopperEmail not in request body
        import json

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        body = json.loads(request_obj.data.decode())
        assert "shopperEmail" not in body

    @patch("app.services.payment_providers.adyen.urlopen")
    def test_create_checkout_session_redirect_url_fallback(self, mock_urlopen):
        """Test Adyen checkout session falls back to redirectUrl."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"id": "CS_REDIRECT", "redirectUrl": "https://checkout.adyen.com/redirect"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = AdyenProvider(
            api_key="test_key",
            merchant_account="TestMerchant",
            environment="test",
        )

        session = provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("75.00"),
            currency="EUR",
            customer_email=None,
            invoice_number="INV-REDIRECT",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert session.checkout_url == "https://checkout.adyen.com/redirect"

    @patch("app.services.payment_providers.adyen.urlopen")
    def test_create_checkout_session_empty_response(self, mock_urlopen):
        """Test Adyen checkout session with minimal response."""
        payment_id = uuid4()
        mock_response = MagicMock()
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = AdyenProvider(
            api_key="test_key",
            merchant_account="TestMerchant",
            environment="test",
        )

        session = provider.create_checkout_session(
            payment_id=payment_id,
            amount=Decimal("100.00"),
            currency="EUR",
            customer_email=None,
            invoice_number="INV-EMPTY",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert session.provider_checkout_id == f"adyen_{payment_id}"
        assert session.checkout_url == ""

    @patch("app.services.payment_providers.adyen.urlopen")
    def test_create_checkout_session_api_error(self, mock_urlopen):
        """Test Adyen checkout session handles API errors."""
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        provider = AdyenProvider(
            api_key="test_key",
            merchant_account="TestMerchant",
            environment="test",
        )

        with pytest.raises(RuntimeError, match="Adyen API request failed"):
            provider.create_checkout_session(
                payment_id=uuid4(),
                amount=Decimal("100.00"),
                currency="EUR",
                customer_email="test@example.com",
                invoice_number="INV-ERR",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    @patch("app.services.payment_providers.adyen.urlopen")
    def test_make_request_headers(self, mock_urlopen):
        """Test Adyen API request headers."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": "ok"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = AdyenProvider(
            api_key="adyen_test_key_123",
            merchant_account="TestMerchant",
            environment="test",
        )

        provider._make_request("POST", "/sessions", {"test": "data"})

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        assert request_obj.get_header("Content-type") == "application/json"
        assert "X-api-key" in request_obj.headers or "X-API-Key" in request_obj.headers


class TestAdyenWebhookSignature:
    """Tests for Adyen webhook signature verification."""

    def test_verify_signature_no_secret(self):
        """Test signature verification without secret."""
        provider = AdyenProvider(webhook_hmac_key="")
        result = provider.verify_webhook_signature(b"payload", "signature")
        assert result is False

    def test_verify_signature_valid_hex_key(self):
        """Test signature verification with valid hex key."""
        hex_key = "0123456789abcdef0123456789abcdef"
        key_bytes = bytes.fromhex(hex_key)
        provider = AdyenProvider(webhook_hmac_key=hex_key)
        payload = b'{"notificationItems": []}'
        expected_sig = base64.b64encode(
            hmac.new(key_bytes, payload, hashlib.sha256).digest()
        ).decode()
        result = provider.verify_webhook_signature(payload, expected_sig)
        assert result is True

    def test_verify_signature_valid_string_key(self):
        """Test signature verification with non-hex string key."""
        string_key = "not_a_hex_key_at_all!"
        provider = AdyenProvider(webhook_hmac_key=string_key)
        payload = b'{"notificationItems": []}'
        expected_sig = base64.b64encode(
            hmac.new(string_key.encode(), payload, hashlib.sha256).digest()
        ).decode()
        result = provider.verify_webhook_signature(payload, expected_sig)
        assert result is True

    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        provider = AdyenProvider(webhook_hmac_key="0123456789abcdef0123456789abcdef")
        result = provider.verify_webhook_signature(b"payload", "invalid_sig")
        assert result is False


class TestAdyenWebhookParsing:
    """Tests for Adyen webhook parsing."""

    def test_parse_webhook_no_items(self):
        """Test parsing webhook with no notification items."""
        provider = AdyenProvider()
        result = provider.parse_webhook({"notificationItems": []})
        assert result.event_type == "adyen.no_items"

    def test_parse_webhook_empty_payload(self):
        """Test parsing webhook with empty payload."""
        provider = AdyenProvider()
        result = provider.parse_webhook({})
        assert result.event_type == "adyen.no_items"

    def test_parse_webhook_authorisation_success(self):
        """Test parsing successful AUTHORISATION event."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "AUTHORISATION",
                            "success": "true",
                            "pspReference": "PSP_AUTH_123",
                            "merchantReference": "payment_abc",
                            "additionalData": {"cardBin": "411111"},
                        }
                    }
                ]
            }
        )
        assert result.event_type == "adyen.AUTHORISATION"
        assert result.provider_payment_id == "PSP_AUTH_123"
        assert result.provider_checkout_id == "payment_abc"
        assert result.status == "succeeded"
        assert result.metadata["payment_id"] == "payment_abc"
        assert result.metadata["additional_data"]["cardBin"] == "411111"

    def test_parse_webhook_authorisation_failed(self):
        """Test parsing failed AUTHORISATION event."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "AUTHORISATION",
                            "success": "false",
                            "pspReference": "PSP_AUTH_FAIL",
                            "merchantReference": "payment_fail",
                            "reason": "Card expired",
                        }
                    }
                ]
            }
        )
        assert result.status == "failed"
        assert result.failure_reason == "Card expired"

    def test_parse_webhook_authorisation_failed_default_message(self):
        """Test parsing failed AUTHORISATION event without reason."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "AUTHORISATION",
                            "success": "false",
                            "pspReference": "PSP_FAIL_DEF",
                            "merchantReference": "payment_def",
                        }
                    }
                ]
            }
        )
        assert result.failure_reason == "Payment authorization failed"

    def test_parse_webhook_cancellation(self):
        """Test parsing CANCELLATION event."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "CANCELLATION",
                            "success": "true",
                            "pspReference": "PSP_CANCEL",
                            "merchantReference": "payment_cancel",
                        }
                    }
                ]
            }
        )
        assert result.event_type == "adyen.CANCELLATION"
        assert result.status == "canceled"

    def test_parse_webhook_refund_success(self):
        """Test parsing successful REFUND event."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "REFUND",
                            "success": "true",
                            "pspReference": "PSP_REFUND",
                            "merchantReference": "payment_refund",
                        }
                    }
                ]
            }
        )
        assert result.event_type == "adyen.REFUND"
        assert result.status == "refunded"

    def test_parse_webhook_refund_failed(self):
        """Test parsing failed REFUND event."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "REFUND",
                            "success": "false",
                            "pspReference": "PSP_REFUND_FAIL",
                            "merchantReference": "payment_refund_fail",
                        }
                    }
                ]
            }
        )
        assert result.status is None

    def test_parse_webhook_capture_success(self):
        """Test parsing successful CAPTURE event."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "CAPTURE",
                            "success": "true",
                            "pspReference": "PSP_CAPTURE",
                            "merchantReference": "payment_capture",
                        }
                    }
                ]
            }
        )
        assert result.event_type == "adyen.CAPTURE"
        assert result.status == "succeeded"

    def test_parse_webhook_capture_failed(self):
        """Test parsing failed CAPTURE event."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "CAPTURE",
                            "success": "false",
                            "pspReference": "PSP_CAPTURE_FAIL",
                            "merchantReference": "payment_capture_fail",
                            "reason": "Capture declined",
                        }
                    }
                ]
            }
        )
        assert result.status == "failed"
        assert result.failure_reason == "Capture declined"

    def test_parse_webhook_capture_failed_default_message(self):
        """Test parsing failed CAPTURE event without reason."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "CAPTURE",
                            "success": "false",
                            "pspReference": "PSP_CAPTURE_DEF",
                            "merchantReference": "payment_capture_def",
                        }
                    }
                ]
            }
        )
        assert result.failure_reason == "Payment capture failed"

    def test_parse_webhook_unknown_event(self):
        """Test parsing unknown event type."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "REPORT_AVAILABLE",
                            "success": "true",
                            "pspReference": "PSP_REPORT",
                            "merchantReference": "payment_report",
                        }
                    }
                ]
            }
        )
        assert result.event_type == "adyen.REPORT_AVAILABLE"
        assert result.status is None

    def test_parse_webhook_no_additional_data(self):
        """Test parsing webhook without additional data."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "AUTHORISATION",
                            "success": "true",
                            "pspReference": "PSP_NO_AD",
                            "merchantReference": "payment_no_ad",
                        }
                    }
                ]
            }
        )
        assert result.metadata["payment_id"] == "payment_no_ad"
        assert "additional_data" not in result.metadata

    def test_parse_webhook_no_merchant_reference(self):
        """Test parsing webhook without merchant reference."""
        provider = AdyenProvider()
        result = provider.parse_webhook(
            {
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "AUTHORISATION",
                            "success": "true",
                            "pspReference": "PSP_NO_REF",
                        }
                    }
                ]
            }
        )
        assert result.provider_checkout_id is None
        assert "payment_id" not in result.metadata


class TestAdyenAPI:
    """Tests for Adyen payment provider via the API."""

    @patch("app.routers.payments.get_payment_provider")
    def test_create_checkout_with_adyen(self, mock_get_provider, client, finalized_invoice):
        """Test creating checkout session with Adyen provider."""
        from app.services.payment_provider import CheckoutSession

        mock_provider = MagicMock()
        mock_provider.create_checkout_session.return_value = CheckoutSession(
            provider_checkout_id="CS_ADYEN_API",
            checkout_url="https://checkoutshopper-test.adyen.com/session/CS_ADYEN_API",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(finalized_invoice.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
                "provider": "adyen",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["checkout_url"] == "https://checkoutshopper-test.adyen.com/session/CS_ADYEN_API"
        assert data["provider"] == "adyen"

    @patch("app.routers.payments.get_payment_provider")
    def test_adyen_webhook_authorisation_success(
        self, mock_get_provider, client, db_session, finalized_invoice, customer
    ):
        """Test Adyen webhook for successful authorization."""
        from app.services.payment_provider import WebhookResult

        mock_provider = MagicMock()
        mock_provider.verify_webhook_signature.return_value = True
        mock_provider.parse_webhook.return_value = WebhookResult(
            event_type="adyen.AUTHORISATION",
            provider_payment_id="PSP_WEBHOOK",
            provider_checkout_id="ADYEN_PAYMENT_REF",
            status="succeeded",
        )
        mock_get_provider.return_value = mock_provider

        repo = PaymentRepository(db_session)
        adyen_payment = repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=100.0,
            currency="EUR",
            provider=PaymentProvider.ADYEN,
        )
        repo.set_provider_ids(
            payment_id=adyen_payment.id,
            provider_checkout_id="ADYEN_PAYMENT_REF",
        )

        response = client.post(
            "/v1/payments/webhook/adyen",
            json={
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "AUTHORISATION",
                            "success": "true",
                            "pspReference": "PSP_WEBHOOK",
                            "merchantReference": "ADYEN_PAYMENT_REF",
                        }
                    }
                ]
            },
            headers={"X-Webhook-Signature": "valid_sig"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

    @patch("app.routers.payments.get_payment_provider")
    def test_adyen_webhook_authorisation_failed(
        self, mock_get_provider, client, db_session, finalized_invoice, customer
    ):
        """Test Adyen webhook for failed authorization."""
        from app.services.payment_provider import WebhookResult

        mock_provider = MagicMock()
        mock_provider.verify_webhook_signature.return_value = True
        mock_provider.parse_webhook.return_value = WebhookResult(
            event_type="adyen.AUTHORISATION",
            provider_payment_id="PSP_FAIL_HOOK",
            provider_checkout_id="ADYEN_FAIL_REF",
            status="failed",
            failure_reason="Card expired",
        )
        mock_get_provider.return_value = mock_provider

        repo = PaymentRepository(db_session)
        adyen_payment = repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=100.0,
            currency="EUR",
            provider=PaymentProvider.ADYEN,
        )
        repo.set_provider_ids(
            payment_id=adyen_payment.id,
            provider_checkout_id="ADYEN_FAIL_REF",
        )

        response = client.post(
            "/v1/payments/webhook/adyen",
            json={
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "AUTHORISATION",
                            "success": "false",
                            "pspReference": "PSP_FAIL_HOOK",
                            "merchantReference": "ADYEN_FAIL_REF",
                        }
                    }
                ]
            },
            headers={"X-Webhook-Signature": "valid_sig"},
        )
        assert response.status_code == 200

        db_session.expire_all()
        updated = repo.get_by_id(adyen_payment.id)
        assert updated.status == PaymentStatus.FAILED.value

    @patch("app.routers.payments.get_payment_provider")
    def test_adyen_webhook_cancellation(
        self, mock_get_provider, client, db_session, finalized_invoice, customer
    ):
        """Test Adyen webhook for cancellation."""
        from app.services.payment_provider import WebhookResult

        mock_provider = MagicMock()
        mock_provider.verify_webhook_signature.return_value = True
        mock_provider.parse_webhook.return_value = WebhookResult(
            event_type="adyen.CANCELLATION",
            provider_payment_id="PSP_CANCEL_HOOK",
            provider_checkout_id="ADYEN_CANCEL_REF",
            status="canceled",
        )
        mock_get_provider.return_value = mock_provider

        repo = PaymentRepository(db_session)
        adyen_payment = repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=100.0,
            currency="EUR",
            provider=PaymentProvider.ADYEN,
        )
        repo.set_provider_ids(
            payment_id=adyen_payment.id,
            provider_checkout_id="ADYEN_CANCEL_REF",
        )

        response = client.post(
            "/v1/payments/webhook/adyen",
            json={
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "CANCELLATION",
                            "success": "true",
                            "pspReference": "PSP_CANCEL_HOOK",
                            "merchantReference": "ADYEN_CANCEL_REF",
                        }
                    }
                ]
            },
            headers={"X-Webhook-Signature": "valid_sig"},
        )
        assert response.status_code == 200

        db_session.expire_all()
        updated = repo.get_by_id(adyen_payment.id)
        assert updated.status == PaymentStatus.CANCELED.value

    def test_adyen_webhook_invalid_signature(self, client):
        """Test Adyen webhook with invalid signature."""
        response = client.post(
            "/v1/payments/webhook/adyen",
            json={
                "notificationItems": [
                    {
                        "NotificationRequestItem": {
                            "eventCode": "AUTHORISATION",
                            "success": "true",
                        }
                    }
                ]
            },
            headers={"X-Webhook-Signature": "invalid"},
        )
        assert response.status_code == 401

    def test_list_payments_by_adyen_provider(
        self, client, db_session, finalized_invoice, customer
    ):
        """Test filtering payments by Adyen provider."""
        repo = PaymentRepository(db_session)
        repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=75.0,
            currency="EUR",
            provider=PaymentProvider.ADYEN,
        )

        response = client.get("/v1/payments/?provider=adyen")
        assert response.status_code == 200
        assert len(response.json()) >= 1
        assert all(p["provider"] == "adyen" for p in response.json())
