"""Tests for RefundService — refund execution through payment providers."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.credit_note import (
    CreditNoteReason,
    CreditNoteType,
    RefundStatus,
)
from app.models.invoice_settlement import SettlementType
from app.models.payment import PaymentProvider
from app.repositories.credit_note_repository import CreditNoteRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.invoice_settlement_repository import InvoiceSettlementRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.credit_note import CreditNoteCreate
from app.schemas.customer import CustomerCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.invoice_settlement import InvoiceSettlementCreate
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
from app.services.payment_provider import RefundResult
from app.services.refund_service import RefundService
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
def customer(db_session):
    """Create a test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"refund_test_cust_{uuid4()}",
            name="Refund Test Customer",
            email="refund@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"refund_test_plan_{uuid4()}",
            name="Refund Test Plan",
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
            external_id=f"refund_test_sub_{uuid4()}",
            customer_id=customer.id,
            plan_id=plan.id,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def invoice(db_session, customer, subscription):
    """Create a test invoice."""
    repo = InvoiceRepository(db_session)
    return repo.create(
        InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            currency="USD",
            line_items=[
                InvoiceLineItem(
                    description="Test item",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    amount=Decimal("100.00"),
                )
            ],
        )
    )


@pytest.fixture
def refund_note(db_session, customer, invoice):
    """Create a refund-type credit note."""
    repo = CreditNoteRepository(db_session)
    return repo.create(
        CreditNoteCreate(
            number=f"CN-REFUND-{uuid4().hex[:8]}",
            invoice_id=invoice.id,
            customer_id=customer.id,
            credit_note_type=CreditNoteType.REFUND,
            reason=CreditNoteReason.PRODUCT_UNSATISFACTORY,
            refund_amount_cents=Decimal("3000.0000"),
            total_amount_cents=Decimal("3000.0000"),
            currency="USD",
        )
    )


@pytest.fixture
def credit_note(db_session, customer, invoice):
    """Create a credit-type credit note (not refund)."""
    repo = CreditNoteRepository(db_session)
    return repo.create(
        CreditNoteCreate(
            number=f"CN-CREDIT-{uuid4().hex[:8]}",
            invoice_id=invoice.id,
            customer_id=customer.id,
            credit_note_type=CreditNoteType.CREDIT,
            reason=CreditNoteReason.DUPLICATED_CHARGE,
            credit_amount_cents=Decimal("5000.0000"),
            total_amount_cents=Decimal("5000.0000"),
            currency="USD",
        )
    )


@pytest.fixture
def payment(db_session, invoice, customer):
    """Create a succeeded payment for the invoice."""
    repo = PaymentRepository(db_session)
    payment = repo.create(
        invoice_id=invoice.id,
        customer_id=customer.id,
        amount=100.00,
        currency="USD",
        provider=PaymentProvider.STRIPE,
        organization_id=DEFAULT_ORG_ID,
    )
    repo.set_provider_ids(payment.id, provider_payment_id="pi_test_123")
    repo.mark_succeeded(payment.id)
    return repo.get_by_id(payment.id)


@pytest.fixture
def payment_settlement(db_session, invoice, payment):
    """Create a payment settlement linking the payment to the invoice."""
    repo = InvoiceSettlementRepository(db_session)
    return repo.create(
        InvoiceSettlementCreate(
            invoice_id=invoice.id,
            settlement_type=SettlementType.PAYMENT,
            source_id=payment.id,
            amount_cents=Decimal("10000.0000"),
        )
    )


class TestRefundServiceSuccessfulRefund:
    """Tests for successful refund processing through Stripe."""

    def test_successful_refund_through_stripe(
        self, db_session, refund_note, payment, payment_settlement
    ):
        """Test processing a refund that succeeds via Stripe."""
        mock_result = RefundResult(
            provider_refund_id="re_test_abc",
            status="succeeded",
        )

        with patch(
            "app.services.refund_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.create_refund.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            service = RefundService(db_session)
            result = service.process_refund(UUID(str(refund_note.id)))

        assert result is True

        # Verify refund_status is updated
        cn_repo = CreditNoteRepository(db_session)
        updated = cn_repo.get_by_id(refund_note.id)
        assert updated is not None
        assert updated.refund_status == RefundStatus.SUCCEEDED.value

        # Verify provider was called correctly
        mock_provider.create_refund.assert_called_once_with(
            provider_payment_id="pi_test_123",
            amount=Decimal("3000.0000"),
            currency="USD",
            metadata={"credit_note_id": str(refund_note.id)},
        )

    def test_refund_with_pending_status(
        self, db_session, refund_note, payment, payment_settlement
    ):
        """Test refund that returns pending status from provider."""
        mock_result = RefundResult(
            provider_refund_id="re_test_pending",
            status="pending",
        )

        with patch(
            "app.services.refund_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.create_refund.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            service = RefundService(db_session)
            result = service.process_refund(UUID(str(refund_note.id)))

        assert result is True

        cn_repo = CreditNoteRepository(db_session)
        updated = cn_repo.get_by_id(refund_note.id)
        assert updated is not None
        assert updated.refund_status == RefundStatus.PENDING.value


class TestRefundServiceFailedRefund:
    """Tests for failed refund scenarios."""

    def test_refund_failure_from_provider(
        self, db_session, refund_note, payment, payment_settlement
    ):
        """Test refund that fails at the provider level."""
        mock_result = RefundResult(
            provider_refund_id="",
            status="failed",
            failure_reason="Charge already refunded",
        )

        with patch(
            "app.services.refund_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.create_refund.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            service = RefundService(db_session)
            result = service.process_refund(UUID(str(refund_note.id)))

        assert result is False

        cn_repo = CreditNoteRepository(db_session)
        updated = cn_repo.get_by_id(refund_note.id)
        assert updated is not None
        assert updated.refund_status == RefundStatus.FAILED.value


class TestRefundServiceNoPayment:
    """Tests for credit notes with no associated payment."""

    def test_no_payment_settlement_sets_failed(self, db_session, refund_note):
        """Test refund when no payment settlement exists for the invoice."""
        service = RefundService(db_session)
        result = service.process_refund(UUID(str(refund_note.id)))

        assert result is False

        cn_repo = CreditNoteRepository(db_session)
        updated = cn_repo.get_by_id(refund_note.id)
        assert updated is not None
        assert updated.refund_status == RefundStatus.FAILED.value

    def test_payment_without_provider_id(
        self, db_session, refund_note, invoice, customer
    ):
        """Test refund when payment has no provider_payment_id."""
        # Create a payment without setting provider IDs
        payment_repo = PaymentRepository(db_session)
        payment = payment_repo.create(
            invoice_id=invoice.id,
            customer_id=customer.id,
            amount=100.00,
            currency="USD",
            provider=PaymentProvider.STRIPE,
            organization_id=DEFAULT_ORG_ID,
        )

        # Create settlement
        settlement_repo = InvoiceSettlementRepository(db_session)
        settlement_repo.create(
            InvoiceSettlementCreate(
                invoice_id=invoice.id,
                settlement_type=SettlementType.PAYMENT,
                source_id=payment.id,
                amount_cents=Decimal("10000.0000"),
            )
        )

        service = RefundService(db_session)
        result = service.process_refund(UUID(str(refund_note.id)))

        assert result is False

        cn_repo = CreditNoteRepository(db_session)
        updated = cn_repo.get_by_id(refund_note.id)
        assert updated is not None
        assert updated.refund_status == RefundStatus.FAILED.value


class TestRefundServicePartialRefund:
    """Tests for partial refund amounts."""

    def test_partial_refund_amount(
        self, db_session, customer, invoice, payment, payment_settlement
    ):
        """Test partial refund where credit note amount < payment amount."""
        cn_repo = CreditNoteRepository(db_session)
        partial_note = cn_repo.create(
            CreditNoteCreate(
                number=f"CN-PARTIAL-{uuid4().hex[:8]}",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.REFUND,
                reason=CreditNoteReason.ORDER_CHANGE,
                refund_amount_cents=Decimal("1500.0000"),
                total_amount_cents=Decimal("1500.0000"),
                currency="USD",
            )
        )

        mock_result = RefundResult(
            provider_refund_id="re_test_partial",
            status="succeeded",
        )

        with patch(
            "app.services.refund_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.create_refund.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            service = RefundService(db_session)
            result = service.process_refund(UUID(str(partial_note.id)))

        assert result is True

        # Verify the partial amount was passed to the provider
        mock_provider.create_refund.assert_called_once_with(
            provider_payment_id="pi_test_123",
            amount=Decimal("1500.0000"),
            currency="USD",
            metadata={"credit_note_id": str(partial_note.id)},
        )

        updated = cn_repo.get_by_id(partial_note.id)
        assert updated is not None
        assert updated.refund_status == RefundStatus.SUCCEEDED.value


class TestRefundServiceEdgeCases:
    """Tests for edge cases in refund processing."""

    def test_credit_note_not_found(self, db_session):
        """Test refund when credit note doesn't exist."""
        service = RefundService(db_session)
        result = service.process_refund(uuid4())
        assert result is False

    def test_non_refund_credit_note_type(self, db_session, credit_note):
        """Test that non-refund type credit notes are rejected."""
        service = RefundService(db_session)
        result = service.process_refund(UUID(str(credit_note.id)))
        assert result is False

    def test_webhook_sent_on_success(
        self, db_session, refund_note, payment, payment_settlement
    ):
        """Test that a success webhook is sent when refund succeeds."""
        mock_result = RefundResult(
            provider_refund_id="re_test_webhook",
            status="succeeded",
        )

        with (
            patch(
                "app.services.refund_service.get_payment_provider"
            ) as mock_get_provider,
            patch.object(
                RefundService, "__init__", lambda self, db: None
            ),
        ):
            # Manually set up service to capture webhook calls
            pass

        # Use a simpler approach: patch WebhookService.send_webhook
        with (
            patch(
                "app.services.refund_service.get_payment_provider"
            ) as mock_get_provider,
            patch(
                "app.services.refund_service.WebhookService"
            ) as mock_webhook_cls,
        ):
            mock_provider = MagicMock()
            mock_provider.create_refund.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            mock_webhook = MagicMock()
            mock_webhook_cls.return_value = mock_webhook

            service = RefundService(db_session)
            service.webhook_service = mock_webhook
            result = service.process_refund(UUID(str(refund_note.id)))

        assert result is True
        # Verify webhook was sent for success
        webhook_calls = mock_webhook.send_webhook.call_args_list
        success_calls = [
            c for c in webhook_calls
            if c.kwargs.get("webhook_type") == "credit_note.refund.succeeded"
            or (c.args and c.args[0] == "credit_note.refund.succeeded")
        ]
        assert len(success_calls) == 1

    def test_webhook_sent_on_failure_no_payment(self, db_session, refund_note):
        """Test that a failure webhook is sent when no payment found."""
        with patch(
            "app.services.refund_service.WebhookService"
        ) as mock_webhook_cls:
            mock_webhook = MagicMock()
            mock_webhook_cls.return_value = mock_webhook

            service = RefundService(db_session)
            service.webhook_service = mock_webhook
            result = service.process_refund(UUID(str(refund_note.id)))

        assert result is False
        webhook_calls = mock_webhook.send_webhook.call_args_list
        fail_calls = [
            c for c in webhook_calls
            if c.kwargs.get("webhook_type") == "credit_note.refund.failed"
            or (c.args and c.args[0] == "credit_note.refund.failed")
        ]
        assert len(fail_calls) == 1

    def test_webhook_sent_on_provider_failure(
        self, db_session, refund_note, payment, payment_settlement
    ):
        """Test that a failure webhook is sent when provider returns failed."""
        mock_result = RefundResult(
            provider_refund_id="",
            status="failed",
            failure_reason="Insufficient funds",
        )

        with (
            patch(
                "app.services.refund_service.get_payment_provider"
            ) as mock_get_provider,
            patch(
                "app.services.refund_service.WebhookService"
            ) as mock_webhook_cls,
        ):
            mock_provider = MagicMock()
            mock_provider.create_refund.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            mock_webhook = MagicMock()
            mock_webhook_cls.return_value = mock_webhook

            service = RefundService(db_session)
            service.webhook_service = mock_webhook
            result = service.process_refund(UUID(str(refund_note.id)))

        assert result is False
        webhook_calls = mock_webhook.send_webhook.call_args_list
        fail_calls = [
            c for c in webhook_calls
            if c.kwargs.get("webhook_type") == "credit_note.refund.failed"
            or (c.args and c.args[0] == "credit_note.refund.failed")
        ]
        assert len(fail_calls) == 1

    def test_manual_provider_refund(
        self, db_session, customer, invoice
    ):
        """Test refund through the manual payment provider."""
        # Create a manual payment
        payment_repo = PaymentRepository(db_session)
        payment = payment_repo.create(
            invoice_id=invoice.id,
            customer_id=customer.id,
            amount=100.00,
            currency="USD",
            provider=PaymentProvider.MANUAL,
            organization_id=DEFAULT_ORG_ID,
        )
        payment_repo.set_provider_ids(payment.id, provider_payment_id="manual_pay_123")
        payment_repo.mark_succeeded(payment.id)

        # Create settlement
        settlement_repo = InvoiceSettlementRepository(db_session)
        settlement_repo.create(
            InvoiceSettlementCreate(
                invoice_id=invoice.id,
                settlement_type=SettlementType.PAYMENT,
                source_id=payment.id,
                amount_cents=Decimal("10000.0000"),
            )
        )

        # Create refund note
        cn_repo = CreditNoteRepository(db_session)
        refund_note = cn_repo.create(
            CreditNoteCreate(
                number=f"CN-MANUAL-{uuid4().hex[:8]}",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.REFUND,
                reason=CreditNoteReason.ORDER_CANCELLATION,
                refund_amount_cents=Decimal("5000.0000"),
                total_amount_cents=Decimal("5000.0000"),
                currency="USD",
            )
        )

        # Manual provider always succeeds — no need to mock
        service = RefundService(db_session)
        result = service.process_refund(UUID(str(refund_note.id)))

        assert result is True

        updated = cn_repo.get_by_id(refund_note.id)
        assert updated is not None
        assert updated.refund_status == RefundStatus.SUCCEEDED.value

    def test_only_payment_settlements_considered(
        self, db_session, refund_note, invoice
    ):
        """Test that credit_note settlements are ignored, only payment type used."""
        # Add a credit_note settlement (should be ignored)
        settlement_repo = InvoiceSettlementRepository(db_session)
        settlement_repo.create(
            InvoiceSettlementCreate(
                invoice_id=invoice.id,
                settlement_type=SettlementType.CREDIT_NOTE,
                source_id=uuid4(),
                amount_cents=Decimal("5000.0000"),
            )
        )

        service = RefundService(db_session)
        result = service.process_refund(UUID(str(refund_note.id)))

        # Should fail because there are no PAYMENT-type settlements
        assert result is False

        cn_repo = CreditNoteRepository(db_session)
        updated = cn_repo.get_by_id(refund_note.id)
        assert updated is not None
        assert updated.refund_status == RefundStatus.FAILED.value


class TestFinalizeEndpointRefundIntegration:
    """Tests for the finalize API endpoint triggering refund processing."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_finalize_refund_note_triggers_refund(
        self, client, db_session, refund_note, payment, payment_settlement
    ):
        """Test POST /v1/credit_notes/{id}/finalize triggers refund for refund-type notes."""
        mock_result = RefundResult(
            provider_refund_id="re_finalize_test",
            status="succeeded",
        )

        with patch(
            "app.services.refund_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.create_refund.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            response = client.post(
                f"/v1/credit_notes/{refund_note.id}/finalize"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "finalized"
        assert data["refund_status"] == "succeeded"

        # Verify provider was called
        mock_provider.create_refund.assert_called_once()
