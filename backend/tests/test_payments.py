"""Tests for payment API and repository."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.payment import PaymentProvider, PaymentStatus, generate_uuid, utc_now
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.customer import CustomerCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.payment import PaymentUpdate
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
from app.services.payment_provider import (
    ChargeResult,
    ManualProvider,
    RefundResult,
    StripeProvider,
    UCPProvider,
    WebhookResult,
    get_payment_provider,
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
def customer(db_session):
    """Create a test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"pay_test_cust_{uuid4()}",
            name="Payment Test Customer",
            email="payment@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"pay_test_plan_{uuid4()}",
            name="Payment Test Plan",
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
            external_id=f"pay_test_sub_{uuid4()}",
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
                    description="Test Service",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    amount=Decimal("100.00"),
                )
            ],
        )
    )
    # Finalize it
    return repo.finalize(invoice.id)


@pytest.fixture
def draft_invoice(db_session, customer, subscription):
    """Create a draft test invoice."""
    repo = InvoiceRepository(db_session)
    return repo.create(
        InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            due_date=datetime.now(UTC) + timedelta(days=14),
            line_items=[
                InvoiceLineItem(
                    description="Draft Service",
                    quantity=Decimal("1"),
                    unit_price=Decimal("50.00"),
                    amount=Decimal("50.00"),
                )
            ],
        )
    )


@pytest.fixture
def payment(db_session, finalized_invoice, customer):
    """Create a test payment."""
    repo = PaymentRepository(db_session)
    return repo.create(
        invoice_id=finalized_invoice.id,
        customer_id=customer.id,
        amount=float(finalized_invoice.total),
        currency=finalized_invoice.currency,
        provider=PaymentProvider.STRIPE,
    )


class TestPaymentModel:
    """Tests for payment model helper functions."""

    def test_generate_uuid(self):
        """Test UUID generation."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        assert uuid1 != uuid2
        assert str(uuid1)

    def test_utc_now(self):
        """Test UTC datetime generation."""
        now = utc_now()
        assert now.tzinfo is not None


class TestPaymentRepository:
    """Tests for PaymentRepository."""

    def test_create_payment(self, db_session, finalized_invoice, customer):
        """Test creating a payment."""
        repo = PaymentRepository(db_session)
        payment = repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=100.0,
            currency="USD",
            provider=PaymentProvider.STRIPE,
            metadata={"test": "value"},
        )
        assert payment.id is not None
        assert payment.status == PaymentStatus.PENDING.value
        assert payment.provider == PaymentProvider.STRIPE.value

    def test_get_by_id(self, db_session, payment):
        """Test getting a payment by ID."""
        repo = PaymentRepository(db_session)
        found = repo.get_by_id(payment.id)
        assert found is not None
        assert found.id == payment.id

    def test_get_by_id_not_found(self, db_session):
        """Test getting non-existent payment."""
        repo = PaymentRepository(db_session)
        found = repo.get_by_id(uuid4())
        assert found is None

    def test_get_by_provider_payment_id(self, db_session, payment):
        """Test getting a payment by provider payment ID."""
        repo = PaymentRepository(db_session)
        repo.set_provider_ids(payment_id=payment.id, provider_payment_id="pi_test123")
        found = repo.get_by_provider_payment_id("pi_test123")
        assert found is not None
        assert found.id == payment.id

    def test_get_by_provider_checkout_id(self, db_session, payment):
        """Test getting a payment by provider checkout ID."""
        repo = PaymentRepository(db_session)
        repo.set_provider_ids(payment_id=payment.id, provider_checkout_id="cs_test123")
        found = repo.get_by_provider_checkout_id("cs_test123")
        assert found is not None
        assert found.id == payment.id

    def test_get_all_with_filters(self, db_session, payment, finalized_invoice, customer):
        """Test listing payments with filters."""
        repo = PaymentRepository(db_session)

        # Test invoice_id filter
        payments = repo.get_all(invoice_id=finalized_invoice.id)
        assert len(payments) >= 1

        # Test customer_id filter
        payments = repo.get_all(customer_id=customer.id)
        assert len(payments) >= 1

        # Test status filter
        payments = repo.get_all(status=PaymentStatus.PENDING)
        assert len(payments) >= 1

        # Test provider filter
        payments = repo.get_all(provider=PaymentProvider.STRIPE)
        assert len(payments) >= 1

    def test_update_payment(self, db_session, payment):
        """Test updating a payment."""
        repo = PaymentRepository(db_session)
        updated = repo.update(
            payment.id,
            PaymentUpdate(
                status=PaymentStatus.PROCESSING,
                provider_payment_id="pi_updated",
            ),
        )
        assert updated is not None
        assert updated.status == PaymentStatus.PROCESSING.value
        assert updated.provider_payment_id == "pi_updated"

    def test_update_payment_not_found(self, db_session):
        """Test updating non-existent payment."""
        repo = PaymentRepository(db_session)
        result = repo.update(uuid4(), PaymentUpdate(status=PaymentStatus.PROCESSING))
        assert result is None

    def test_update_payment_with_none_status(self, db_session, payment):
        """Test updating a payment with status explicitly set to None."""
        repo = PaymentRepository(db_session)
        # This tests the branch where status is in update_data but is None
        updated = repo.update(
            payment.id,
            PaymentUpdate(
                status=None,
                provider_payment_id="pi_with_none_status",
            ),
        )
        assert updated is not None
        # Status should remain unchanged (pending)
        assert updated.status == PaymentStatus.PENDING.value
        assert updated.provider_payment_id == "pi_with_none_status"

    def test_update_payment_without_status(self, db_session, payment):
        """Test updating a payment without including status field."""
        repo = PaymentRepository(db_session)
        # This tests the branch where status is NOT in update_data
        updated = repo.update(
            payment.id,
            PaymentUpdate(
                provider_payment_id="pi_no_status_field",
            ),
        )
        assert updated is not None
        # Status should remain unchanged (pending)
        assert updated.status == PaymentStatus.PENDING.value
        assert updated.provider_payment_id == "pi_no_status_field"

    def test_set_provider_ids(self, db_session, payment):
        """Test setting provider IDs."""
        repo = PaymentRepository(db_session)
        updated = repo.set_provider_ids(
            payment_id=payment.id,
            provider_payment_id="pi_123",
            provider_checkout_id="cs_456",
            provider_checkout_url="https://checkout.stripe.com/cs_456",
        )
        assert updated is not None
        assert updated.provider_payment_id == "pi_123"
        assert updated.provider_checkout_id == "cs_456"
        assert updated.provider_checkout_url == "https://checkout.stripe.com/cs_456"

    def test_set_provider_ids_not_found(self, db_session):
        """Test setting provider IDs for non-existent payment."""
        repo = PaymentRepository(db_session)
        result = repo.set_provider_ids(payment_id=uuid4(), provider_payment_id="pi_123")
        assert result is None

    def test_mark_processing(self, db_session, payment):
        """Test marking payment as processing."""
        repo = PaymentRepository(db_session)
        updated = repo.mark_processing(payment.id)
        assert updated is not None
        assert updated.status == PaymentStatus.PROCESSING.value

    def test_mark_processing_not_found(self, db_session):
        """Test marking non-existent payment as processing."""
        repo = PaymentRepository(db_session)
        result = repo.mark_processing(uuid4())
        assert result is None

    def test_mark_succeeded(self, db_session, payment):
        """Test marking payment as succeeded."""
        repo = PaymentRepository(db_session)
        updated = repo.mark_succeeded(payment.id)
        assert updated is not None
        assert updated.status == PaymentStatus.SUCCEEDED.value
        assert updated.completed_at is not None

    def test_mark_succeeded_not_found(self, db_session):
        """Test marking non-existent payment as succeeded."""
        repo = PaymentRepository(db_session)
        result = repo.mark_succeeded(uuid4())
        assert result is None

    def test_mark_failed(self, db_session, payment):
        """Test marking payment as failed."""
        repo = PaymentRepository(db_session)
        updated = repo.mark_failed(payment.id, "Card declined")
        assert updated is not None
        assert updated.status == PaymentStatus.FAILED.value
        assert updated.failure_reason == "Card declined"

    def test_mark_failed_not_found(self, db_session):
        """Test marking non-existent payment as failed."""
        repo = PaymentRepository(db_session)
        result = repo.mark_failed(uuid4(), "Error")
        assert result is None

    def test_mark_failed_no_reason(self, db_session, payment):
        """Test marking payment as failed without reason."""
        repo = PaymentRepository(db_session)
        updated = repo.mark_failed(payment.id)
        assert updated is not None
        assert updated.status == PaymentStatus.FAILED.value

    def test_mark_canceled(self, db_session, payment):
        """Test marking payment as canceled."""
        repo = PaymentRepository(db_session)
        updated = repo.mark_canceled(payment.id)
        assert updated is not None
        assert updated.status == PaymentStatus.CANCELED.value

    def test_mark_canceled_not_found(self, db_session):
        """Test marking non-existent payment as canceled."""
        repo = PaymentRepository(db_session)
        result = repo.mark_canceled(uuid4())
        assert result is None

    def test_mark_refunded(self, db_session, payment):
        """Test marking payment as refunded."""
        repo = PaymentRepository(db_session)
        repo.mark_succeeded(payment.id)
        updated = repo.mark_refunded(payment.id)
        assert updated is not None
        assert updated.status == PaymentStatus.REFUNDED.value

    def test_mark_refunded_not_succeeded(self, db_session, payment):
        """Test marking non-succeeded payment as refunded fails."""
        repo = PaymentRepository(db_session)
        with pytest.raises(ValueError, match="Only succeeded payments can be refunded"):
            repo.mark_refunded(payment.id)

    def test_mark_refunded_not_found(self, db_session):
        """Test marking non-existent payment as refunded."""
        repo = PaymentRepository(db_session)
        result = repo.mark_refunded(uuid4())
        assert result is None

    def test_delete_payment(self, db_session, payment):
        """Test deleting a pending payment."""
        repo = PaymentRepository(db_session)
        result = repo.delete(payment.id)
        assert result is True
        assert repo.get_by_id(payment.id) is None

    def test_delete_payment_not_found(self, db_session):
        """Test deleting non-existent payment."""
        repo = PaymentRepository(db_session)
        result = repo.delete(uuid4())
        assert result is False

    def test_delete_non_pending_payment(self, db_session, payment):
        """Test deleting non-pending payment fails."""
        repo = PaymentRepository(db_session)
        repo.mark_succeeded(payment.id)
        with pytest.raises(ValueError, match="Only pending payments can be deleted"):
            repo.delete(payment.id)


class TestPaymentProviders:
    """Tests for payment providers."""

    def test_get_stripe_provider(self):
        """Test getting Stripe provider."""
        provider = get_payment_provider(PaymentProvider.STRIPE)
        assert isinstance(provider, StripeProvider)
        assert provider.provider_name == PaymentProvider.STRIPE

    def test_get_manual_provider(self):
        """Test getting Manual provider."""
        provider = get_payment_provider(PaymentProvider.MANUAL)
        assert isinstance(provider, ManualProvider)
        assert provider.provider_name == PaymentProvider.MANUAL

    def test_get_invalid_provider(self):
        """Test getting invalid provider raises error."""
        with pytest.raises(ValueError, match="Unsupported payment provider"):
            get_payment_provider("invalid")  # type: ignore[arg-type]

    def test_manual_provider_checkout_session(self):
        """Test manual provider checkout session."""
        provider = ManualProvider()
        session = provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("100.00"),
            currency="USD",
            customer_email="test@example.com",
            invoice_number="INV-001",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        assert session.provider_checkout_id.startswith("manual_")
        assert session.checkout_url == ""
        assert session.expires_at is not None

    def test_manual_provider_verify_signature_no_secret(self):
        """Test manual provider signature verification without secret."""
        provider = ManualProvider()
        result = provider.verify_webhook_signature(b"payload", "signature")
        assert result is False

    @patch("app.services.payment_provider.settings")
    def test_manual_provider_verify_signature_valid(self, mock_settings):
        """Test manual provider signature verification with valid signature."""
        import hashlib
        import hmac

        mock_settings.manual_webhook_secret = "test_secret"
        provider = ManualProvider()
        payload = b'{"event": "test"}'
        expected_sig = hmac.new(b"test_secret", payload, hashlib.sha256).hexdigest()
        result = provider.verify_webhook_signature(payload, expected_sig)
        assert result is True

    def test_manual_provider_parse_webhook(self):
        """Test manual provider webhook parsing."""
        provider = ManualProvider()
        result = provider.parse_webhook(
            {"event_type": "payment.manual", "payment_id": "123", "status": "succeeded"}
        )
        assert result.event_type == "payment.manual"
        assert result.provider_payment_id == "123"
        assert result.status == "succeeded"

    def test_manual_provider_parse_webhook_defaults(self):
        """Test manual provider webhook parsing with defaults."""
        provider = ManualProvider()
        result = provider.parse_webhook({})
        assert result.event_type == "payment.manual"
        assert result.status == "succeeded"

    @patch("app.services.payment_provider.settings")
    def test_stripe_provider_verify_signature_no_secret(self, mock_settings):
        """Test Stripe provider signature verification without secret."""
        mock_settings.stripe_api_key = ""
        mock_settings.stripe_webhook_secret = ""
        provider = StripeProvider(api_key="test", webhook_secret="")
        result = provider.verify_webhook_signature(b"payload", "signature")
        assert result is False

    def test_stripe_provider_parse_webhook_checkout_completed(self):
        """Test Stripe provider webhook parsing for checkout.session.completed."""
        provider = StripeProvider(api_key="test")
        result = provider.parse_webhook(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_123",
                        "payment_intent": "pi_123",
                        "payment_status": "paid",
                        "metadata": {"payment_id": "abc"},
                    }
                },
            }
        )
        assert result.event_type == "checkout.session.completed"
        assert result.provider_checkout_id == "cs_123"
        assert result.provider_payment_id == "pi_123"
        assert result.status == "succeeded"

    def test_stripe_provider_parse_webhook_checkout_not_paid(self):
        """Test Stripe provider webhook parsing for unpaid checkout."""
        provider = StripeProvider(api_key="test")
        result = provider.parse_webhook(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_123",
                        "payment_intent": "pi_123",
                        "payment_status": "unpaid",
                    }
                },
            }
        )
        assert result.status == "pending"

    def test_stripe_provider_parse_webhook_payment_succeeded(self):
        """Test Stripe provider webhook parsing for payment_intent.succeeded."""
        provider = StripeProvider(api_key="test")
        result = provider.parse_webhook(
            {
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_123"}},
            }
        )
        assert result.event_type == "payment_intent.succeeded"
        assert result.provider_payment_id == "pi_123"
        assert result.status == "succeeded"

    def test_stripe_provider_parse_webhook_payment_failed(self):
        """Test Stripe provider webhook parsing for payment_intent.payment_failed."""
        provider = StripeProvider(api_key="test")
        result = provider.parse_webhook(
            {
                "type": "payment_intent.payment_failed",
                "data": {
                    "object": {
                        "id": "pi_123",
                        "last_payment_error": {"message": "Card declined"},
                    }
                },
            }
        )
        assert result.event_type == "payment_intent.payment_failed"
        assert result.status == "failed"
        assert result.failure_reason == "Card declined"

    def test_stripe_provider_parse_webhook_payment_failed_no_error(self):
        """Test Stripe webhook parsing for failed payment without error message."""
        provider = StripeProvider(api_key="test")
        result = provider.parse_webhook(
            {
                "type": "payment_intent.payment_failed",
                "data": {"object": {"id": "pi_123"}},
            }
        )
        assert result.failure_reason == "Payment failed"

    def test_stripe_provider_parse_webhook_checkout_expired(self):
        """Test Stripe provider webhook parsing for checkout.session.expired."""
        provider = StripeProvider(api_key="test")
        result = provider.parse_webhook(
            {
                "type": "checkout.session.expired",
                "data": {"object": {"id": "cs_123"}},
            }
        )
        assert result.event_type == "checkout.session.expired"
        assert result.provider_checkout_id == "cs_123"
        assert result.status == "canceled"

    def test_stripe_provider_parse_webhook_unknown_event(self):
        """Test Stripe provider webhook parsing for unknown event."""
        provider = StripeProvider(api_key="test")
        result = provider.parse_webhook(
            {
                "type": "unknown.event",
                "data": {"object": {"id": "obj_123"}},
            }
        )
        assert result.event_type == "unknown.event"
        assert result.status is None


class TestStripeProviderWithMock:
    """Tests for Stripe provider with mocked stripe module."""

    def test_stripe_provider_lazy_import(self):
        """Test that Stripe provider lazy loads the stripe module."""
        provider = StripeProvider(api_key="sk_test_123")
        # Before accessing, _stripe should be None
        assert provider._stripe is None
        # After accessing, stripe should be loaded
        stripe_module = provider.stripe
        assert stripe_module is not None
        assert provider._stripe is not None

    def test_stripe_provider_import_error_handling(self):
        """Test that Stripe provider raises ImportError when stripe fails to import."""
        provider = StripeProvider(api_key="sk_test_123")

        # Temporarily remove stripe from sys.modules to simulate import failure
        import sys

        original_stripe = sys.modules.get("stripe")
        sys.modules["stripe"] = None  # type: ignore[assignment]

        try:
            # Reset the internal stripe reference
            provider._stripe = None

            # Now accessing stripe should try to import and fail
            with pytest.raises(ImportError, match="stripe package not installed"):
                _ = provider.stripe
        finally:
            # Restore original stripe module
            if original_stripe is not None:
                sys.modules["stripe"] = original_stripe
            else:
                del sys.modules["stripe"]

    def test_stripe_checkout_with_real_module(self):
        """Test Stripe checkout using real stripe module with mocked API."""
        import stripe

        mock_session = MagicMock()
        mock_session.id = "cs_real_mock"
        mock_session.url = "https://checkout.stripe.com/cs_real_mock"
        mock_session.expires_at = 1234567890

        provider = StripeProvider(api_key="sk_test_key")
        # Pre-load the stripe module
        _ = provider.stripe

        with patch.object(
            stripe.checkout.Session, "create", return_value=mock_session
        ) as mock_create:
            session = provider.create_checkout_session(
                payment_id=uuid4(),
                amount=Decimal("150.00"),
                currency="USD",
                customer_email="real@test.com",
                invoice_number="INV-REAL-001",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                metadata={"source": "test"},
            )

            assert session.provider_checkout_id == "cs_real_mock"
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["customer_email"] == "real@test.com"
            assert call_kwargs["mode"] == "payment"

    def test_stripe_checkout_without_email(self):
        """Test Stripe checkout without customer email."""
        import stripe

        mock_session = MagicMock()
        mock_session.id = "cs_no_email"
        mock_session.url = "https://checkout.stripe.com/cs_no_email"
        mock_session.expires_at = None

        provider = StripeProvider(api_key="sk_test_key")
        _ = provider.stripe

        with patch.object(
            stripe.checkout.Session, "create", return_value=mock_session
        ) as mock_create:
            session = provider.create_checkout_session(
                payment_id=uuid4(),
                amount=Decimal("75.50"),
                currency="EUR",
                customer_email=None,
                invoice_number="INV-NO-EMAIL",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

            assert session.provider_checkout_id == "cs_no_email"
            assert session.expires_at is None
            call_kwargs = mock_create.call_args[1]
            assert "customer_email" not in call_kwargs

    @patch("stripe.Webhook.construct_event")
    def test_stripe_verify_webhook_with_real_module(self, mock_construct):
        """Test Stripe webhook verification using real stripe module."""
        mock_construct.return_value = {"type": "test.event"}

        provider = StripeProvider(api_key="sk_test", webhook_secret="whsec_real")
        result = provider.verify_webhook_signature(b"test payload", "test_sig")

        assert result is True
        mock_construct.assert_called_once_with(b"test payload", "test_sig", "whsec_real")

    @patch("stripe.Webhook.construct_event")
    def test_stripe_verify_webhook_invalid_sig(self, mock_construct):
        """Test Stripe webhook verification with invalid signature."""
        import stripe

        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", "sig_header"
        )

        provider = StripeProvider(api_key="sk_test", webhook_secret="whsec_real")
        result = provider.verify_webhook_signature(b"payload", "bad_sig")

        assert result is False

    @patch("app.services.payment_provider.settings")
    def test_stripe_checkout_session_creation(self, mock_settings):
        """Test Stripe checkout session creation with mocked stripe."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        # Create a mock stripe module
        mock_stripe = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "cs_test_created"
        mock_session.url = "https://checkout.stripe.com/cs_test_created"
        mock_session.expires_at = 1234567890
        mock_stripe.checkout.Session.create.return_value = mock_session

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        session = provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("99.99"),
            currency="USD",
            customer_email="test@example.com",
            invoice_number="INV-001",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            metadata={"custom": "data"},
        )

        assert session.provider_checkout_id == "cs_test_created"
        assert session.checkout_url == "https://checkout.stripe.com/cs_test_created"
        assert session.expires_at is not None

    @patch("app.services.payment_provider.settings")
    def test_stripe_checkout_session_no_email(self, mock_settings):
        """Test Stripe checkout session creation without email."""
        mock_settings.stripe_api_key = "sk_test_123"

        mock_stripe = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "cs_no_email"
        mock_session.url = "https://checkout.stripe.com/cs_no_email"
        mock_session.expires_at = None
        mock_stripe.checkout.Session.create.return_value = mock_session

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        session = provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("50.00"),
            currency="EUR",
            customer_email=None,  # No email
            invoice_number="INV-002",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert session.provider_checkout_id == "cs_no_email"
        # Verify customer_email was not passed
        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        assert "customer_email" not in call_kwargs

    @patch("app.services.payment_provider.settings")
    def test_stripe_verify_webhook_valid(self, mock_settings):
        """Test Stripe webhook signature verification."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        mock_stripe = MagicMock()
        mock_stripe.Webhook.construct_event.return_value = {"type": "test"}

        provider = StripeProvider(api_key="sk_test_123", webhook_secret="whsec_test")
        provider._stripe = mock_stripe

        result = provider.verify_webhook_signature(b"payload", "sig")
        assert result is True

    @patch("app.services.payment_provider.settings")
    def test_stripe_verify_webhook_invalid(self, mock_settings):
        """Test Stripe webhook signature verification fails."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        mock_stripe = MagicMock()
        mock_stripe.error = MagicMock()
        mock_stripe.error.SignatureVerificationError = Exception
        mock_stripe.Webhook.construct_event.side_effect = ValueError("Invalid sig")

        provider = StripeProvider(api_key="sk_test_123", webhook_secret="whsec_test")
        provider._stripe = mock_stripe

        result = provider.verify_webhook_signature(b"payload", "invalid_sig")
        assert result is False


class TestPaymentsAPI:
    """Tests for payments API endpoints."""

    def test_list_payments_empty(self, client):
        """Test listing payments when empty."""
        response = client.get("/v1/payments/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_payments_with_data(self, client, payment):
        """Test listing payments with data."""
        response = client.get("/v1/payments/")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_list_payments_with_filters(self, client, payment, finalized_invoice, customer):
        """Test listing payments with filters."""
        response = client.get(f"/v1/payments/?invoice_id={finalized_invoice.id}")
        assert response.status_code == 200

        response = client.get(f"/v1/payments/?customer_id={customer.id}")
        assert response.status_code == 200

        response = client.get("/v1/payments/?status=pending")
        assert response.status_code == 200

        response = client.get("/v1/payments/?provider=stripe")
        assert response.status_code == 200

    def test_get_payment(self, client, payment):
        """Test getting a single payment."""
        response = client.get(f"/v1/payments/{payment.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(payment.id)

    def test_get_payment_not_found(self, client):
        """Test getting non-existent payment."""
        response = client.get(f"/v1/payments/{uuid4()}")
        assert response.status_code == 404

    def test_create_checkout_invoice_not_found(self, client):
        """Test creating checkout for non-existent invoice."""
        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(uuid4()),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 404

    def test_create_checkout_draft_invoice(self, client, draft_invoice):
        """Test creating checkout for draft invoice fails."""
        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(draft_invoice.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 400
        assert "finalized" in response.json()["detail"].lower()

    @patch("app.routers.payments.get_payment_provider")
    def test_create_checkout_success(self, mock_get_provider, client, finalized_invoice):
        """Test creating checkout session successfully."""
        from app.services.payment_provider import CheckoutSession

        mock_provider = MagicMock()
        mock_provider.create_checkout_session.return_value = CheckoutSession(
            provider_checkout_id="cs_mock_123",
            checkout_url="https://checkout.example.com/cs_mock_123",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(finalized_invoice.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["checkout_url"] == "https://checkout.example.com/cs_mock_123"
        assert data["provider"] == "stripe"
        assert "payment_id" in data

    @patch("app.repositories.customer_repository.CustomerRepository.get_by_id")
    @patch("app.routers.payments.get_payment_provider")
    def test_create_checkout_customer_not_found(
        self, mock_get_provider, mock_get_by_id, client, finalized_invoice
    ):
        """Test creating checkout when customer is not found (email is None)."""
        from app.services.payment_provider import CheckoutSession

        # Mock customer repo get_by_id to return None
        mock_get_by_id.return_value = None

        mock_provider = MagicMock()
        mock_provider.create_checkout_session.return_value = CheckoutSession(
            provider_checkout_id="cs_no_customer",
            checkout_url="https://checkout.example.com/cs_no_customer",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(finalized_invoice.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["checkout_url"] == "https://checkout.example.com/cs_no_customer"

        # Verify customer_email was None when passed to provider
        call_kwargs = mock_provider.create_checkout_session.call_args[1]
        assert call_kwargs["customer_email"] is None

    @patch("app.routers.payments.get_payment_provider")
    def test_create_checkout_returns_existing(
        self, mock_get_provider, client, finalized_invoice, db_session, customer
    ):
        """Test creating checkout returns existing pending payment."""
        # Create an existing pending payment with checkout URL
        repo = PaymentRepository(db_session)
        existing = repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=float(finalized_invoice.total),
            currency=finalized_invoice.currency,
        )
        repo.set_provider_ids(
            payment_id=existing.id,
            provider_checkout_url="https://existing.checkout.com/existing",
        )

        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(finalized_invoice.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should return existing checkout URL
        assert data["checkout_url"] == "https://existing.checkout.com/existing"
        assert data["payment_id"] == str(existing.id)
        # Provider should not have been called
        mock_get_provider.assert_not_called()

    @patch("app.routers.payments.get_payment_provider")
    def test_create_checkout_existing_without_url(
        self, mock_get_provider, client, finalized_invoice, db_session, customer
    ):
        """Test creating checkout when existing payment has no URL creates new session."""
        from app.services.payment_provider import CheckoutSession

        # Create an existing pending payment WITHOUT checkout URL
        repo = PaymentRepository(db_session)
        existing = repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=float(finalized_invoice.total),
            currency=finalized_invoice.currency,
        )
        # Don't set checkout URL - payment exists but has no URL yet

        # Mock provider to return new session
        mock_provider = MagicMock()
        mock_provider.create_checkout_session.return_value = CheckoutSession(
            provider_checkout_id="cs_new_for_existing",
            checkout_url="https://checkout.example.com/cs_new_for_existing",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(finalized_invoice.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should create a new checkout session (new payment record)
        assert data["checkout_url"] == "https://checkout.example.com/cs_new_for_existing"
        # A new payment should be created since existing one has no URL
        assert data["payment_id"] != str(existing.id)

    @patch("app.routers.payments.get_payment_provider")
    def test_create_checkout_provider_error(self, mock_get_provider, client, finalized_invoice):
        """Test creating checkout handles provider error."""
        mock_provider = MagicMock()
        mock_provider.create_checkout_session.side_effect = Exception("Provider error")
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(finalized_invoice.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 500
        assert "Failed to create checkout session" in response.json()["detail"]

    @patch("app.routers.payments.get_payment_provider")
    def test_create_checkout_stripe_not_installed(
        self, mock_get_provider, client, finalized_invoice
    ):
        """Test creating checkout when stripe not installed."""
        mock_provider = MagicMock()
        mock_provider.create_checkout_session.side_effect = ImportError("stripe not installed")
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(finalized_invoice.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]

    def test_mark_payment_paid(self, client, payment):
        """Test marking a payment as paid manually."""
        response = client.post(f"/v1/payments/{payment.id}/mark-paid")
        assert response.status_code == 200
        assert response.json()["status"] == "succeeded"

    def test_mark_payment_paid_not_found(self, client):
        """Test marking non-existent payment as paid."""
        response = client.post(f"/v1/payments/{uuid4()}/mark-paid")
        assert response.status_code == 404

    def test_mark_payment_paid_not_pending(self, client, payment, db_session):
        """Test marking non-pending payment as paid fails."""
        repo = PaymentRepository(db_session)
        repo.mark_succeeded(payment.id)

        response = client.post(f"/v1/payments/{payment.id}/mark-paid")
        assert response.status_code == 400

    def test_refund_payment(self, client, payment, db_session):
        """Test refunding a payment."""
        repo = PaymentRepository(db_session)
        repo.mark_succeeded(payment.id)

        response = client.post(f"/v1/payments/{payment.id}/refund")
        assert response.status_code == 200
        assert response.json()["status"] == "refunded"

    def test_refund_payment_not_found(self, client):
        """Test refunding non-existent payment."""
        response = client.post(f"/v1/payments/{uuid4()}/refund")
        assert response.status_code == 404

    def test_refund_pending_payment(self, client, payment):
        """Test refunding pending payment fails."""
        response = client.post(f"/v1/payments/{payment.id}/refund")
        assert response.status_code == 400

    def test_delete_payment(self, client, payment):
        """Test deleting a pending payment."""
        response = client.delete(f"/v1/payments/{payment.id}")
        assert response.status_code == 204

    def test_delete_payment_not_found(self, client):
        """Test deleting non-existent payment."""
        response = client.delete(f"/v1/payments/{uuid4()}")
        assert response.status_code == 404

    def test_delete_non_pending_payment(self, client, payment, db_session):
        """Test deleting non-pending payment fails."""
        repo = PaymentRepository(db_session)
        repo.mark_succeeded(payment.id)

        response = client.delete(f"/v1/payments/{payment.id}")
        assert response.status_code == 400

    def test_webhook_invalid_signature(self, client):
        """Test webhook with invalid signature."""
        response = client.post(
            "/v1/payments/webhook/stripe",
            json={"type": "test"},
            headers={"Stripe-Signature": "invalid"},
        )
        assert response.status_code == 401

    @patch("app.routers.payments.get_payment_provider")
    def test_webhook_invalid_provider_value_error(self, mock_get_provider, client):
        """Test webhook with invalid provider raises 400."""
        mock_get_provider.side_effect = ValueError("Unsupported provider")

        response = client.post(
            "/v1/payments/webhook/stripe",
            json={"type": "test"},
        )
        assert response.status_code == 400
        assert "Invalid provider" in response.json()["detail"]

    @patch("app.services.payment_provider.StripeProvider.verify_webhook_signature")
    def test_webhook_invalid_json_payload(self, mock_verify, client):
        """Test webhook with invalid JSON payload."""
        mock_verify.return_value = True

        # Send invalid JSON
        response = client.post(
            "/v1/payments/webhook/stripe",
            content=b"not valid json {{{",
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "valid",
            },
        )
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    @patch("app.services.payment_provider.StripeProvider.verify_webhook_signature")
    def test_webhook_payment_not_found(self, mock_verify, client):
        """Test webhook for unknown payment returns ignored."""
        mock_verify.return_value = True
        response = client.post(
            "/v1/payments/webhook/stripe",
            json={
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_unknown",
                        "payment_intent": "pi_unknown",
                        "payment_status": "paid",
                    }
                },
            },
            headers={"Stripe-Signature": "valid"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    @patch("app.services.payment_provider.StripeProvider.verify_webhook_signature")
    def test_webhook_payment_succeeded(self, mock_verify, client, payment, db_session):
        """Test webhook marks payment and invoice as paid."""
        mock_verify.return_value = True

        repo = PaymentRepository(db_session)
        repo.set_provider_ids(
            payment_id=payment.id,
            provider_checkout_id="cs_test_webhook",
        )

        response = client.post(
            "/v1/payments/webhook/stripe",
            json={
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_webhook",
                        "payment_intent": "pi_webhook",
                        "payment_status": "paid",
                    }
                },
            },
            headers={"Stripe-Signature": "valid"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

    @patch("app.services.payment_provider.StripeProvider.verify_webhook_signature")
    def test_webhook_payment_failed(self, mock_verify, client, payment, db_session):
        """Test webhook marks payment as failed."""
        mock_verify.return_value = True

        repo = PaymentRepository(db_session)
        repo.set_provider_ids(
            payment_id=payment.id,
            provider_payment_id="pi_test_failed",
        )

        response = client.post(
            "/v1/payments/webhook/stripe",
            json={
                "type": "payment_intent.payment_failed",
                "data": {
                    "object": {
                        "id": "pi_test_failed",
                        "last_payment_error": {"message": "Insufficient funds"},
                    }
                },
            },
            headers={"Stripe-Signature": "valid"},
        )
        assert response.status_code == 200

    @patch("app.services.payment_provider.StripeProvider.verify_webhook_signature")
    def test_webhook_checkout_canceled(self, mock_verify, client, payment, db_session):
        """Test webhook marks payment as canceled."""
        mock_verify.return_value = True

        repo = PaymentRepository(db_session)
        repo.set_provider_ids(
            payment_id=payment.id,
            provider_checkout_id="cs_test_canceled",
        )

        response = client.post(
            "/v1/payments/webhook/stripe",
            json={
                "type": "checkout.session.expired",
                "data": {"object": {"id": "cs_test_canceled"}},
            },
            headers={"Stripe-Signature": "valid"},
        )
        assert response.status_code == 200

    @patch("app.services.payment_provider.StripeProvider.verify_webhook_signature")
    def test_webhook_finds_payment_by_metadata(self, mock_verify, client, payment):
        """Test webhook finds payment by metadata payment_id."""
        mock_verify.return_value = True

        response = client.post(
            "/v1/payments/webhook/stripe",
            json={
                "type": "payment_intent.succeeded",
                "data": {
                    "object": {
                        "id": "pi_new",
                        "metadata": {"payment_id": str(payment.id)},
                    }
                },
            },
            headers={"Stripe-Signature": "valid"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

    @patch("app.services.payment_provider.StripeProvider.verify_webhook_signature")
    def test_webhook_updates_provider_payment_id(self, mock_verify, client, payment, db_session):
        """Test webhook updates provider payment ID if not set."""
        mock_verify.return_value = True

        repo = PaymentRepository(db_session)
        repo.set_provider_ids(
            payment_id=payment.id,
            provider_checkout_id="cs_update_test",
        )

        response = client.post(
            "/v1/payments/webhook/stripe",
            json={
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_update_test",
                        "payment_intent": "pi_new_id",
                        "payment_status": "paid",
                    }
                },
            },
            headers={"Stripe-Signature": "valid"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

    @patch("app.services.payment_provider.StripeProvider.verify_webhook_signature")
    @patch("app.services.payment_provider.StripeProvider.parse_webhook")
    def test_webhook_unknown_status(self, mock_parse, mock_verify, client, payment, db_session):
        """Test webhook with unknown status (no status update action)."""
        mock_verify.return_value = True
        # Return a result with status that's not succeeded/failed/canceled
        mock_parse.return_value = WebhookResult(
            event_type="some.unknown.event",
            provider_payment_id=None,
            provider_checkout_id="cs_unknown_status",
            status=None,  # No status to process
        )

        repo = PaymentRepository(db_session)
        repo.set_provider_ids(
            payment_id=payment.id,
            provider_checkout_id="cs_unknown_status",
        )

        response = client.post(
            "/v1/payments/webhook/stripe",
            json={"type": "some.unknown.event", "data": {}},
            headers={"Stripe-Signature": "valid"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        # Payment status should remain unchanged (pending)
        updated = repo.get_by_id(payment.id)
        assert updated.status == PaymentStatus.PENDING.value


class TestUCPProvider:
    """Tests for UCP (Universal Commerce Protocol) provider."""

    def test_get_ucp_provider(self):
        """Test getting UCP provider."""
        provider = get_payment_provider(PaymentProvider.UCP)
        assert isinstance(provider, UCPProvider)
        assert provider.provider_name == PaymentProvider.UCP

    def test_ucp_provider_initialization(self):
        """Test UCP provider initialization with custom values."""
        provider = UCPProvider(
            base_url="https://ucp.example.com/",
            api_key="test_key",
            webhook_secret="test_secret",
            merchant_id="merchant_123",
        )
        assert provider.base_url == "https://ucp.example.com"  # Trailing slash stripped
        assert provider.api_key == "test_key"
        assert provider.webhook_secret == "test_secret"
        assert provider.merchant_id == "merchant_123"

    def test_ucp_provider_verify_signature_no_secret(self):
        """Test UCP signature verification without secret."""
        provider = UCPProvider(webhook_secret="")
        result = provider.verify_webhook_signature(b"payload", "signature")
        assert result is False

    @patch("app.services.payment_provider.settings")
    def test_ucp_provider_verify_signature_valid(self, mock_settings):
        """Test UCP signature verification with valid signature."""
        import hashlib
        import hmac

        mock_settings.ucp_webhook_secret = "ucp_secret"
        mock_settings.ucp_base_url = ""
        mock_settings.ucp_api_key = ""
        mock_settings.ucp_merchant_id = ""

        provider = UCPProvider(webhook_secret="ucp_secret")
        payload = b'{"type": "checkout.completed"}'
        expected_sig = hmac.new(b"ucp_secret", payload, hashlib.sha256).hexdigest()
        result = provider.verify_webhook_signature(payload, expected_sig)
        assert result is True

    @patch("app.services.payment_provider.settings")
    def test_ucp_provider_verify_signature_with_prefix(self, mock_settings):
        """Test UCP signature verification with sha256= prefix."""
        import hashlib
        import hmac

        mock_settings.ucp_webhook_secret = "ucp_secret"
        mock_settings.ucp_base_url = ""
        mock_settings.ucp_api_key = ""
        mock_settings.ucp_merchant_id = ""

        provider = UCPProvider(webhook_secret="ucp_secret")
        payload = b'{"type": "checkout.completed"}'
        raw_sig = hmac.new(b"ucp_secret", payload, hashlib.sha256).hexdigest()
        result = provider.verify_webhook_signature(payload, f"sha256={raw_sig}")
        assert result is True

    def test_ucp_provider_verify_signature_invalid(self):
        """Test UCP signature verification with invalid signature."""
        provider = UCPProvider(webhook_secret="secret")
        result = provider.verify_webhook_signature(b"payload", "invalid")
        assert result is False

    def test_ucp_provider_parse_webhook_completed(self):
        """Test UCP webhook parsing for completed checkout."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.completed",
                "data": {
                    "id": "chk_123",
                    "order_id": "ord_456",
                    "status": "completed",
                    "metadata": {"payment_id": "abc", "invoice_number": "INV-001"},
                },
            }
        )
        assert result.event_type == "checkout.completed"
        assert result.provider_checkout_id == "chk_123"
        assert result.provider_payment_id == "ord_456"
        assert result.status == "succeeded"
        assert result.metadata["payment_id"] == "abc"

    def test_ucp_provider_parse_webhook_canceled(self):
        """Test UCP webhook parsing for canceled checkout."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.canceled",
                "data": {"id": "chk_789", "status": "canceled"},
            }
        )
        assert result.event_type == "checkout.canceled"
        assert result.status == "canceled"

    def test_ucp_provider_parse_webhook_failed(self):
        """Test UCP webhook parsing for failed checkout with error message."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.failed",
                "data": {
                    "id": "chk_fail",
                    "status": "failed",
                    "messages": [{"type": "error", "content": "Card declined by issuer"}],
                },
            }
        )
        assert result.event_type == "checkout.failed"
        assert result.status == "failed"
        assert result.failure_reason == "Card declined by issuer"

    def test_ucp_provider_parse_webhook_failed_no_message(self):
        """Test UCP webhook parsing for failed checkout without error message."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.failed",
                "data": {"id": "chk_fail", "status": "failed"},
            }
        )
        assert result.failure_reason == "Payment failed"

    def test_ucp_provider_parse_webhook_incomplete(self):
        """Test UCP webhook parsing for incomplete checkout."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.updated",
                "data": {"id": "chk_incomplete", "status": "incomplete"},
            }
        )
        assert result.status == "pending"

    def test_ucp_provider_parse_webhook_ready_for_complete(self):
        """Test UCP webhook parsing for ready_for_complete status."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.updated",
                "data": {"id": "chk_ready", "status": "ready_for_complete"},
            }
        )
        assert result.status == "pending"

    def test_ucp_provider_parse_webhook_unknown_status(self):
        """Test UCP webhook parsing for unknown status."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.updated",
                "data": {"id": "chk_unknown", "status": "some_new_status"},
            }
        )
        assert result.status is None

    def test_ucp_provider_parse_webhook_extract_metadata_from_line_items(self):
        """Test UCP webhook extracts invoice from line items when no metadata."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.completed",
                "data": {
                    "id": "chk_li",
                    "status": "completed",
                    "line_items": [
                        {
                            "id": "li_1",
                            "item": {"id": "inv_INV-002", "title": "Invoice INV-002"},
                        }
                    ],
                },
            }
        )
        assert result.metadata.get("invoice_number") == "INV-002"

    def test_ucp_provider_parse_webhook_no_matching_line_items(self):
        """Test UCP webhook when line items don't have inv_ prefix."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.completed",
                "data": {
                    "id": "chk_no_inv",
                    "status": "completed",
                    "line_items": [
                        {
                            "id": "li_1",
                            "item": {"id": "product_123", "title": "Some Product"},
                        },
                        {
                            "id": "li_2",
                            "item": {"id": "sku_456", "title": "Another Item"},
                        },
                    ],
                },
            }
        )
        # No invoice_number should be extracted
        assert result.metadata.get("invoice_number") is None

    def test_ucp_provider_parse_webhook_empty_line_items(self):
        """Test UCP webhook with empty line items array."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.completed",
                "data": {
                    "id": "chk_empty_li",
                    "status": "completed",
                    "line_items": [],
                },
            }
        )
        assert result.metadata == {}

    def test_ucp_provider_parse_webhook_failed_no_error_messages(self):
        """Test UCP webhook for failed checkout with non-error messages."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.failed",
                "data": {
                    "id": "chk_fail_no_err",
                    "status": "failed",
                    "messages": [
                        {"type": "info", "content": "Some info"},
                        {"type": "warning", "content": "Some warning"},
                    ],
                },
            }
        )
        assert result.failure_reason == "Payment failed"

    def test_ucp_provider_parse_webhook_failed_empty_messages(self):
        """Test UCP webhook for failed checkout with empty messages array."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.failed",
                "data": {
                    "id": "chk_fail_empty_msg",
                    "status": "failed",
                    "messages": [],
                },
            }
        )
        assert result.failure_reason == "Payment failed"

    def test_ucp_provider_parse_webhook_with_event_type_fallback(self):
        """Test UCP webhook parsing with event_type instead of type."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {"event_type": "order.created", "id": "ord_123", "status": "completed"}
        )
        assert result.event_type == "order.created"
        assert result.provider_checkout_id == "ord_123"

    def test_ucp_provider_parse_webhook_same_checkout_and_order_id(self):
        """Test UCP webhook when checkout_id equals order_id."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "checkout.completed",
                "data": {"id": "chk_same", "checkout_id": "chk_same", "status": "completed"},
            }
        )
        # When checkout_id equals id, provider_payment_id should be None
        assert result.provider_checkout_id == "chk_same"
        assert result.provider_payment_id is None

    def test_ucp_provider_parse_webhook_refunded(self):
        """Test UCP webhook parsing for refunded status."""
        provider = UCPProvider()
        result = provider.parse_webhook(
            {
                "type": "order.refunded",
                "data": {"id": "ord_refund", "status": "refunded"},
            }
        )
        assert result.status == "refunded"

    @patch("app.services.payment_provider.urlopen")
    def test_ucp_provider_create_checkout_session(self, mock_urlopen):
        """Test UCP checkout session creation."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"id": "chk_new_123", "status": "incomplete", "permalink_url": "https://checkout.ucp.dev/chk_new_123"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = UCPProvider(
            base_url="https://api.ucp.dev",
            api_key="ucp_test_key",
        )

        session = provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("99.99"),
            currency="USD",
            customer_email="test@example.com",
            invoice_number="INV-UCP-001",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            metadata={"custom": "data"},
        )

        assert session.provider_checkout_id == "chk_new_123"
        assert session.checkout_url == "https://checkout.ucp.dev/chk_new_123"
        assert session.expires_at is not None
        mock_urlopen.assert_called_once()

    @patch("app.services.payment_provider.urlopen")
    def test_ucp_provider_create_checkout_session_no_email(self, mock_urlopen):
        """Test UCP checkout session creation without email."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"id": "chk_no_email", "status": "incomplete"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = UCPProvider(
            base_url="https://api.ucp.dev",
            api_key="ucp_test_key",
        )

        session = provider.create_checkout_session(
            payment_id=uuid4(),
            amount=Decimal("50.00"),
            currency="EUR",
            customer_email=None,
            invoice_number="INV-UCP-002",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert session.provider_checkout_id == "chk_no_email"
        # Should construct URL from base_url when permalink_url not in response
        assert "api.ucp.dev/checkout/chk_no_email" in session.checkout_url

    @patch("app.services.payment_provider.urlopen")
    def test_ucp_provider_create_checkout_session_api_error(self, mock_urlopen):
        """Test UCP checkout session creation handles API errors."""
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        provider = UCPProvider(
            base_url="https://api.ucp.dev",
            api_key="ucp_test_key",
        )

        with pytest.raises(RuntimeError, match="UCP API request failed"):
            provider.create_checkout_session(
                payment_id=uuid4(),
                amount=Decimal("100.00"),
                currency="USD",
                customer_email="test@example.com",
                invoice_number="INV-ERR",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    @patch("app.services.payment_provider.urlopen")
    def test_ucp_provider_make_request_headers(self, mock_urlopen):
        """Test UCP provider sets correct request headers."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"id": "chk_headers"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = UCPProvider(
            base_url="https://api.ucp.dev",
            api_key="ucp_test_key_123",
        )

        provider._make_request("POST", "/checkout-sessions", {"test": "data"})

        # Verify the request was made with correct headers
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.get_header("Content-type") == "application/json"
        assert request.get_header("Authorization") == "Bearer ucp_test_key_123"
        # Note: urllib.request normalizes headers to title case (Ucp-agent)
        assert "Ucp-agent" in request.headers or "UCP-Agent" in request.headers


class TestUCPPaymentsAPI:
    """Tests for UCP payments via the API."""

    @patch("app.routers.payments.get_payment_provider")
    def test_create_checkout_with_ucp_provider(self, mock_get_provider, client, finalized_invoice):
        """Test creating checkout session with UCP provider."""
        from app.services.payment_provider import CheckoutSession

        mock_provider = MagicMock()
        mock_provider.create_checkout_session.return_value = CheckoutSession(
            provider_checkout_id="ucp_chk_123",
            checkout_url="https://checkout.ucp.dev/ucp_chk_123",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payments/checkout",
            json={
                "invoice_id": str(finalized_invoice.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
                "provider": "ucp",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["checkout_url"] == "https://checkout.ucp.dev/ucp_chk_123"
        assert data["provider"] == "ucp"

    @patch("app.routers.payments.get_payment_provider")
    def test_ucp_webhook_with_signature_header(
        self, mock_get_provider, client, payment, db_session
    ):
        """Test UCP webhook with X-UCP-Signature header."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook_signature.return_value = True
        mock_provider.parse_webhook.return_value = WebhookResult(
            event_type="checkout.completed",
            provider_checkout_id="ucp_chk_webhook",
            status="succeeded",
        )
        mock_get_provider.return_value = mock_provider

        # Create a UCP payment
        repo = PaymentRepository(db_session)
        ucp_payment = repo.create(
            invoice_id=payment.invoice_id,
            customer_id=payment.customer_id,
            amount=100.0,
            currency="USD",
            provider=PaymentProvider.UCP,
        )
        repo.set_provider_ids(
            payment_id=ucp_payment.id,
            provider_checkout_id="ucp_chk_webhook",
        )

        response = client.post(
            "/v1/payments/webhook/ucp",
            json={
                "type": "checkout.completed",
                "data": {
                    "id": "ucp_chk_webhook",
                    "status": "completed",
                },
            },
            headers={"X-UCP-Signature": "valid_sig"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

    @patch("app.routers.payments.get_payment_provider")
    def test_ucp_webhook_payment_failed(self, mock_get_provider, client, payment, db_session):
        """Test UCP webhook marks payment as failed."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook_signature.return_value = True
        mock_provider.parse_webhook.return_value = WebhookResult(
            event_type="checkout.failed",
            provider_checkout_id="ucp_chk_fail",
            status="failed",
            failure_reason="Insufficient funds",
        )
        mock_get_provider.return_value = mock_provider

        repo = PaymentRepository(db_session)
        ucp_payment = repo.create(
            invoice_id=payment.invoice_id,
            customer_id=payment.customer_id,
            amount=100.0,
            currency="USD",
            provider=PaymentProvider.UCP,
        )
        repo.set_provider_ids(
            payment_id=ucp_payment.id,
            provider_checkout_id="ucp_chk_fail",
        )

        response = client.post(
            "/v1/payments/webhook/ucp",
            json={
                "type": "checkout.failed",
                "data": {
                    "id": "ucp_chk_fail",
                    "status": "failed",
                    "messages": [{"type": "error", "content": "Insufficient funds"}],
                },
            },
            headers={"X-UCP-Signature": "valid"},
        )
        assert response.status_code == 200

        # Refresh the session to get the updated payment from the database
        db_session.expire_all()
        updated = repo.get_by_id(ucp_payment.id)
        assert updated.status == PaymentStatus.FAILED.value

    @patch("app.routers.payments.get_payment_provider")
    def test_ucp_webhook_checkout_canceled(self, mock_get_provider, client, payment, db_session):
        """Test UCP webhook marks payment as canceled."""
        mock_provider = MagicMock()
        mock_provider.verify_webhook_signature.return_value = True
        mock_provider.parse_webhook.return_value = WebhookResult(
            event_type="checkout.canceled",
            provider_checkout_id="ucp_chk_cancel",
            status="canceled",
        )
        mock_get_provider.return_value = mock_provider

        repo = PaymentRepository(db_session)
        ucp_payment = repo.create(
            invoice_id=payment.invoice_id,
            customer_id=payment.customer_id,
            amount=100.0,
            currency="USD",
            provider=PaymentProvider.UCP,
        )
        repo.set_provider_ids(
            payment_id=ucp_payment.id,
            provider_checkout_id="ucp_chk_cancel",
        )

        response = client.post(
            "/v1/payments/webhook/ucp",
            json={
                "type": "checkout.canceled",
                "data": {"id": "ucp_chk_cancel", "status": "canceled"},
            },
            headers={"X-UCP-Signature": "valid"},
        )
        assert response.status_code == 200

        # Refresh the session to get the updated payment from the database
        db_session.expire_all()
        updated = repo.get_by_id(ucp_payment.id)
        assert updated.status == PaymentStatus.CANCELED.value

    def test_ucp_webhook_invalid_signature(self, client):
        """Test UCP webhook with invalid signature."""
        response = client.post(
            "/v1/payments/webhook/ucp",
            json={"type": "test"},
            headers={"X-UCP-Signature": "invalid"},
        )
        assert response.status_code == 401

    def test_list_payments_by_ucp_provider(
        self, client, payment, db_session, finalized_invoice, customer
    ):
        """Test filtering payments by UCP provider."""
        # Create a UCP payment
        repo = PaymentRepository(db_session)
        repo.create(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            amount=75.0,
            currency="USD",
            provider=PaymentProvider.UCP,
        )

        response = client.get("/v1/payments/?provider=ucp")
        assert response.status_code == 200
        assert len(response.json()) >= 1
        assert all(p["provider"] == "ucp" for p in response.json())


class TestChargePaymentMethod:
    """Tests for charge_payment_method on providers."""

    def test_base_provider_raises_not_implemented(self):
        """Test that the base class charge_payment_method raises NotImplementedError."""
        provider = ManualProvider()
        with pytest.raises(
            NotImplementedError, match="manual does not support charging payment methods"
        ):
            provider.charge_payment_method(
                payment_method_id="pm_test",
                amount=Decimal("50.00"),
                currency="USD",
            )

    @patch("app.services.payment_provider.settings")
    def test_stripe_charge_payment_method_success(self, mock_settings):
        """Test Stripe charge_payment_method with successful charge."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        mock_stripe = MagicMock()
        mock_intent = MagicMock()
        mock_intent.id = "pi_success_123"
        mock_intent.status = "succeeded"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        result = provider.charge_payment_method(
            payment_method_id="pm_test_123",
            amount=Decimal("99.99"),
            currency="USD",
            metadata={"invoice_id": "inv_123"},
        )

        assert isinstance(result, ChargeResult)
        assert result.provider_payment_id == "pi_success_123"
        assert result.status == "succeeded"
        assert result.failure_reason is None

        mock_stripe.PaymentIntent.create.assert_called_once_with(
            amount=9999,
            currency="usd",
            payment_method="pm_test_123",
            confirm=True,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            metadata={"invoice_id": "inv_123"},
        )

    @patch("app.services.payment_provider.settings")
    def test_stripe_charge_payment_method_non_succeeded(self, mock_settings):
        """Test Stripe charge_payment_method when intent status is not succeeded."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        mock_stripe = MagicMock()
        mock_intent = MagicMock()
        mock_intent.id = "pi_pending_123"
        mock_intent.status = "requires_action"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        result = provider.charge_payment_method(
            payment_method_id="pm_test_123",
            amount=Decimal("50.00"),
            currency="EUR",
        )

        assert result.provider_payment_id == "pi_pending_123"
        assert result.status == "failed"
        assert result.failure_reason == "Payment intent status: requires_action"

    @patch("app.services.payment_provider.settings")
    def test_stripe_charge_payment_method_card_error(self, mock_settings):
        """Test Stripe charge_payment_method with card error."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        mock_stripe = MagicMock()
        card_error = Exception("Your card was declined.")
        card_error.json_body = {"error": {"payment_intent": {"id": "pi_failed_123"}}}  # type: ignore[attr-defined]
        card_error.user_message = "Your card was declined."  # type: ignore[attr-defined]
        mock_stripe.error.CardError = type(card_error)
        mock_stripe.PaymentIntent.create.side_effect = card_error

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        result = provider.charge_payment_method(
            payment_method_id="pm_test_123",
            amount=Decimal("75.00"),
            currency="USD",
        )

        assert result.provider_payment_id == "pi_failed_123"
        assert result.status == "failed"
        assert result.failure_reason == "Your card was declined."

    @patch("app.services.payment_provider.settings")
    def test_stripe_charge_payment_method_without_metadata(self, mock_settings):
        """Test Stripe charge_payment_method without metadata uses empty dict."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        mock_stripe = MagicMock()
        mock_intent = MagicMock()
        mock_intent.id = "pi_no_meta"
        mock_intent.status = "succeeded"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        result = provider.charge_payment_method(
            payment_method_id="pm_test_123",
            amount=Decimal("10.00"),
            currency="USD",
        )

        assert result.status == "succeeded"
        call_kwargs = mock_stripe.PaymentIntent.create.call_args[1]
        assert call_kwargs["metadata"] == {}


class TestStripeRefund:
    """Tests for StripeProvider.create_refund."""

    @patch("app.services.payment_provider.settings")
    def test_stripe_refund_success(self, mock_settings):
        """Test successful Stripe refund."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        mock_stripe = MagicMock()
        mock_refund = MagicMock()
        mock_refund.id = "re_123"
        mock_refund.status = "succeeded"
        mock_stripe.Refund.create.return_value = mock_refund

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        result = provider.create_refund(
            provider_payment_id="pi_123",
            amount=Decimal("50.00"),
            currency="USD",
            metadata={"reason": "customer_request"},
        )

        assert isinstance(result, RefundResult)
        assert result.provider_refund_id == "re_123"
        assert result.status == "succeeded"
        assert result.failure_reason is None

        mock_stripe.Refund.create.assert_called_once_with(
            payment_intent="pi_123",
            amount=5000,
            metadata={"reason": "customer_request"},
        )

    @patch("app.services.payment_provider.settings")
    def test_stripe_refund_partial_amount(self, mock_settings):
        """Test Stripe partial refund."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        mock_stripe = MagicMock()
        mock_refund = MagicMock()
        mock_refund.id = "re_partial_123"
        mock_refund.status = "succeeded"
        mock_stripe.Refund.create.return_value = mock_refund

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        result = provider.create_refund(
            provider_payment_id="pi_123",
            amount=Decimal("25.50"),
            currency="USD",
        )

        assert result.provider_refund_id == "re_partial_123"
        assert result.status == "succeeded"

        mock_stripe.Refund.create.assert_called_once_with(
            payment_intent="pi_123",
            amount=2550,
            metadata={},
        )

    @patch("app.services.payment_provider.settings")
    def test_stripe_refund_pending_status(self, mock_settings):
        """Test Stripe refund with pending status."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        mock_stripe = MagicMock()
        mock_refund = MagicMock()
        mock_refund.id = "re_pending_123"
        mock_refund.status = "pending"
        mock_stripe.Refund.create.return_value = mock_refund

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        result = provider.create_refund(
            provider_payment_id="pi_123",
            amount=Decimal("100.00"),
            currency="USD",
        )

        assert result.provider_refund_id == "re_pending_123"
        assert result.status == "pending"

    @patch("app.services.payment_provider.settings")
    def test_stripe_refund_failure(self, mock_settings):
        """Test Stripe refund failure (invalid request)."""
        mock_settings.stripe_api_key = "sk_test_123"
        mock_settings.stripe_webhook_secret = "whsec_test"

        mock_stripe = MagicMock()
        error = Exception("No such payment_intent: pi_invalid")
        mock_stripe.error.InvalidRequestError = type(error)
        mock_stripe.Refund.create.side_effect = error

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        result = provider.create_refund(
            provider_payment_id="pi_invalid",
            amount=Decimal("50.00"),
            currency="USD",
        )

        assert result.provider_refund_id == ""
        assert result.status == "failed"
        assert "No such payment_intent" in result.failure_reason


class TestManualRefund:
    """Tests for ManualProvider.create_refund."""

    def test_manual_refund_success(self):
        """Test manual refund always succeeds."""
        provider = ManualProvider()
        result = provider.create_refund(
            provider_payment_id="manual_pay_123",
            amount=Decimal("50.00"),
            currency="USD",
        )

        assert isinstance(result, RefundResult)
        assert result.provider_refund_id == "manual_refund_manual_pay_123"
        assert result.status == "succeeded"
        assert result.failure_reason is None

    def test_manual_refund_partial(self):
        """Test manual partial refund."""
        provider = ManualProvider()
        result = provider.create_refund(
            provider_payment_id="manual_pay_456",
            amount=Decimal("25.00"),
            currency="EUR",
            metadata={"note": "partial refund"},
        )

        assert result.provider_refund_id == "manual_refund_manual_pay_456"
        assert result.status == "succeeded"


class TestUCPRefund:
    """Tests for UCPProvider.create_refund."""

    @patch("app.services.payment_provider.urlopen")
    def test_ucp_refund_success(self, mock_urlopen):
        """Test successful UCP refund."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"id": "ucp_re_123", "status": "completed"}
        ).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = UCPProvider(
            base_url="https://ucp.example.com",
            api_key="test_key",
            webhook_secret="test_secret",
        )

        result = provider.create_refund(
            provider_payment_id="ucp_pay_123",
            amount=Decimal("75.00"),
            currency="USD",
            metadata={"reason": "refund"},
        )

        assert isinstance(result, RefundResult)
        assert result.provider_refund_id == "ucp_re_123"
        assert result.status == "succeeded"
        assert result.failure_reason is None

    @patch("app.services.payment_provider.urlopen")
    def test_ucp_refund_pending(self, mock_urlopen):
        """Test UCP refund with pending status."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"id": "ucp_re_456", "status": "pending"}
        ).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = UCPProvider(
            base_url="https://ucp.example.com",
            api_key="test_key",
            webhook_secret="test_secret",
        )

        result = provider.create_refund(
            provider_payment_id="ucp_pay_456",
            amount=Decimal("30.00"),
            currency="EUR",
        )

        assert result.provider_refund_id == "ucp_re_456"
        assert result.status == "pending"

    @patch("app.services.payment_provider.urlopen")
    def test_ucp_refund_failed_status(self, mock_urlopen):
        """Test UCP refund with failed status from API."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"id": "ucp_re_789", "status": "failed"}
        ).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = UCPProvider(
            base_url="https://ucp.example.com",
            api_key="test_key",
            webhook_secret="test_secret",
        )

        result = provider.create_refund(
            provider_payment_id="ucp_pay_789",
            amount=Decimal("10.00"),
            currency="USD",
        )

        assert result.provider_refund_id == "ucp_re_789"
        assert result.status == "failed"

    @patch("app.services.payment_provider.urlopen")
    def test_ucp_refund_unknown_status(self, mock_urlopen):
        """Test UCP refund with unknown status defaults to pending."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"id": "ucp_re_unknown", "status": "processing"}
        ).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = UCPProvider(
            base_url="https://ucp.example.com",
            api_key="test_key",
            webhook_secret="test_secret",
        )

        result = provider.create_refund(
            provider_payment_id="ucp_pay_unknown",
            amount=Decimal("10.00"),
            currency="USD",
        )

        assert result.provider_refund_id == "ucp_re_unknown"
        assert result.status == "pending"

    @patch("app.services.payment_provider.urlopen")
    def test_ucp_refund_api_error(self, mock_urlopen):
        """Test UCP refund with API error."""
        mock_urlopen.side_effect = URLError("Connection refused")

        provider = UCPProvider(
            base_url="https://ucp.example.com",
            api_key="test_key",
            webhook_secret="test_secret",
        )

        result = provider.create_refund(
            provider_payment_id="ucp_pay_err",
            amount=Decimal("50.00"),
            currency="USD",
        )

        assert result.provider_refund_id == ""
        assert result.status == "failed"
        assert result.failure_reason is not None

    @patch("app.services.payment_provider.urlopen")
    def test_ucp_refund_empty_response(self, mock_urlopen):
        """Test UCP refund with empty response uses fallback values."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        provider = UCPProvider(
            base_url="https://ucp.example.com",
            api_key="test_key",
            webhook_secret="test_secret",
        )

        result = provider.create_refund(
            provider_payment_id="ucp_pay_empty",
            amount=Decimal("10.00"),
            currency="USD",
        )

        assert result.provider_refund_id == "ucp_refund_ucp_pay_empty"
        assert result.status == "pending"


class TestPaymentRepositoryCount:
    """Tests for PaymentRepository.count branch coverage."""

    def test_count_without_organization_id(self, db_session):
        """Test count() without org_id returns total count across all orgs."""
        repo = PaymentRepository(db_session)
        result = repo.count()
        assert isinstance(result, int)
        assert result >= 0
