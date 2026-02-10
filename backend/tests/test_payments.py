"""Tests for payment API and repository."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine, get_db
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
    ManualProvider,
    StripeProvider,
    get_payment_provider,
)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
        )
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
        )
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
        )
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
            billing_period_start=datetime.utcnow(),
            billing_period_end=datetime.utcnow() + timedelta(days=30),
            due_date=datetime.utcnow() + timedelta(days=14),
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

        with patch.object(stripe.checkout.Session, "create", return_value=mock_session) as mock_create:
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

        with patch.object(stripe.checkout.Session, "create", return_value=mock_session) as mock_create:
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
            expires_at=datetime.utcnow() + timedelta(hours=1),
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
            expires_at=datetime.utcnow() + timedelta(hours=1),
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
            expires_at=datetime.utcnow() + timedelta(hours=1),
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
    def test_create_checkout_stripe_not_installed(self, mock_get_provider, client, finalized_invoice):
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
    def test_webhook_unknown_status(
        self, mock_parse, mock_verify, client, payment, db_session
    ):
        """Test webhook with unknown status (no status update action)."""
        from app.services.payment_provider import WebhookResult

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
