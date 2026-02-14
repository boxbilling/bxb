"""Tests for InvoiceSettlement model, repository, and payment flow integration."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.invoice_settlement import InvoiceSettlement, SettlementType, generate_uuid
from app.models.payment import PaymentProvider
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.invoice_settlement_repository import InvoiceSettlementRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.routers.payments import _record_settlement_and_maybe_mark_paid
from app.schemas.customer import CustomerCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.invoice_settlement import InvoiceSettlementCreate, InvoiceSettlementResponse
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
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
            external_id=f"settle_test_cust_{uuid4()}",
            name="Settlement Test Customer",
            email="settle@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"settle_test_plan_{uuid4()}",
            name="Settlement Test Plan",
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
            external_id=f"settle_test_sub_{uuid4()}",
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
    return repo.finalize(invoice.id)


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


class TestInvoiceSettlementModel:
    """Tests for InvoiceSettlement model helpers."""

    def test_generate_uuid(self):
        """Test UUID generation."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        assert uuid1 != uuid2
        assert str(uuid1)

    def test_settlement_type_enum(self):
        """Test SettlementType enum values."""
        assert SettlementType.PAYMENT.value == "payment"
        assert SettlementType.CREDIT_NOTE.value == "credit_note"
        assert SettlementType.WALLET_CREDIT.value == "wallet_credit"


class TestInvoiceSettlementSchema:
    """Tests for InvoiceSettlement schemas."""

    def test_create_schema(self):
        """Test InvoiceSettlementCreate schema."""
        data = InvoiceSettlementCreate(
            invoice_id=uuid4(),
            settlement_type=SettlementType.PAYMENT,
            source_id=uuid4(),
            amount_cents=Decimal("100.00"),
        )
        assert data.settlement_type == SettlementType.PAYMENT
        assert data.amount_cents == Decimal("100.00")

    def test_response_schema(self):
        """Test InvoiceSettlementResponse schema with from_attributes."""
        settlement = InvoiceSettlement()
        settlement.id = uuid4()
        settlement.invoice_id = uuid4()
        settlement.settlement_type = SettlementType.PAYMENT.value
        settlement.source_id = uuid4()
        settlement.amount_cents = Decimal("50.00")
        settlement.created_at = datetime.now(UTC)

        response = InvoiceSettlementResponse.model_validate(settlement)
        assert response.settlement_type == "payment"
        assert response.amount_cents == Decimal("50.00")


class TestInvoiceSettlementRepository:
    """Tests for InvoiceSettlementRepository."""

    def test_create_settlement(self, db_session, finalized_invoice):
        """Test creating an invoice settlement."""
        repo = InvoiceSettlementRepository(db_session)
        source_id = uuid4()
        settlement = repo.create(
            InvoiceSettlementCreate(
                invoice_id=finalized_invoice.id,
                settlement_type=SettlementType.PAYMENT,
                source_id=source_id,
                amount_cents=Decimal("50.00"),
            )
        )
        assert settlement.id is not None
        assert settlement.settlement_type == SettlementType.PAYMENT.value
        assert settlement.amount_cents == Decimal("50.00")
        assert settlement.created_at is not None

    def test_get_by_invoice_id(self, db_session, finalized_invoice):
        """Test getting settlements by invoice ID."""
        repo = InvoiceSettlementRepository(db_session)
        source1 = uuid4()
        source2 = uuid4()

        repo.create(
            InvoiceSettlementCreate(
                invoice_id=finalized_invoice.id,
                settlement_type=SettlementType.PAYMENT,
                source_id=source1,
                amount_cents=Decimal("60.00"),
            )
        )
        repo.create(
            InvoiceSettlementCreate(
                invoice_id=finalized_invoice.id,
                settlement_type=SettlementType.CREDIT_NOTE,
                source_id=source2,
                amount_cents=Decimal("40.00"),
            )
        )

        settlements = repo.get_by_invoice_id(finalized_invoice.id)
        assert len(settlements) == 2

    def test_get_by_invoice_id_empty(self, db_session):
        """Test getting settlements for non-existent invoice."""
        repo = InvoiceSettlementRepository(db_session)
        settlements = repo.get_by_invoice_id(uuid4())
        assert settlements == []

    def test_get_total_settled(self, db_session, finalized_invoice):
        """Test getting total settled amount for an invoice."""
        repo = InvoiceSettlementRepository(db_session)

        repo.create(
            InvoiceSettlementCreate(
                invoice_id=finalized_invoice.id,
                settlement_type=SettlementType.PAYMENT,
                source_id=uuid4(),
                amount_cents=Decimal("60.00"),
            )
        )
        repo.create(
            InvoiceSettlementCreate(
                invoice_id=finalized_invoice.id,
                settlement_type=SettlementType.WALLET_CREDIT,
                source_id=uuid4(),
                amount_cents=Decimal("40.00"),
            )
        )

        total = repo.get_total_settled(finalized_invoice.id)
        assert total == Decimal("100.00")

    def test_get_total_settled_no_settlements(self, db_session):
        """Test getting total settled when no settlements exist."""
        repo = InvoiceSettlementRepository(db_session)
        total = repo.get_total_settled(uuid4())
        assert total == Decimal("0")


class TestRecordSettlementAndMaybeMarkPaid:
    """Tests for the _record_settlement_and_maybe_mark_paid helper."""

    def test_settlement_marks_invoice_paid_when_fully_settled(self, db_session, finalized_invoice):
        """Test that creating a settlement >= invoice total auto-marks invoice as paid."""
        _record_settlement_and_maybe_mark_paid(
            db_session,
            invoice_id=finalized_invoice.id,
            settlement_type=SettlementType.PAYMENT,
            source_id=uuid4(),
            amount_cents=float(finalized_invoice.total),
        )

        invoice_repo = InvoiceRepository(db_session)
        invoice = invoice_repo.get_by_id(finalized_invoice.id)
        assert invoice.status == "paid"

    def test_settlement_does_not_mark_paid_when_partially_settled(
        self, db_session, finalized_invoice
    ):
        """Test that a partial settlement does not auto-mark invoice as paid."""
        _record_settlement_and_maybe_mark_paid(
            db_session,
            invoice_id=finalized_invoice.id,
            settlement_type=SettlementType.PAYMENT,
            source_id=uuid4(),
            amount_cents=50.0,
        )

        invoice_repo = InvoiceRepository(db_session)
        invoice = invoice_repo.get_by_id(finalized_invoice.id)
        assert invoice.status == "finalized"

    def test_multiple_settlements_mark_paid(self, db_session, finalized_invoice):
        """Test multiple partial settlements eventually auto-mark as paid."""
        _record_settlement_and_maybe_mark_paid(
            db_session,
            invoice_id=finalized_invoice.id,
            settlement_type=SettlementType.PAYMENT,
            source_id=uuid4(),
            amount_cents=60.0,
        )

        invoice_repo = InvoiceRepository(db_session)
        invoice = invoice_repo.get_by_id(finalized_invoice.id)
        assert invoice.status == "finalized"

        _record_settlement_and_maybe_mark_paid(
            db_session,
            invoice_id=finalized_invoice.id,
            settlement_type=SettlementType.WALLET_CREDIT,
            source_id=uuid4(),
            amount_cents=40.0,
        )

        invoice = invoice_repo.get_by_id(finalized_invoice.id)
        assert invoice.status == "paid"

    def test_settlement_for_nonexistent_invoice(self, db_session):
        """Test settlement creation for nonexistent invoice (no crash)."""
        fake_invoice_id = uuid4()
        _record_settlement_and_maybe_mark_paid(
            db_session,
            invoice_id=fake_invoice_id,
            settlement_type=SettlementType.PAYMENT,
            source_id=uuid4(),
            amount_cents=100.0,
        )
        settlement_repo = InvoiceSettlementRepository(db_session)
        settlements = settlement_repo.get_by_invoice_id(fake_invoice_id)
        assert len(settlements) == 1


class TestPaymentWebhookSettlement:
    """Tests for settlement creation via payment webhooks."""

    @patch("app.services.payment_provider.StripeProvider.verify_webhook_signature")
    def test_webhook_succeeded_creates_settlement(self, mock_verify, client, payment, db_session):
        """Test that a succeeded webhook creates an InvoiceSettlement."""
        mock_verify.return_value = True

        repo = PaymentRepository(db_session)
        repo.set_provider_ids(
            payment_id=payment.id,
            provider_checkout_id="cs_settle_test",
        )

        response = client.post(
            "/v1/payments/webhook/stripe",
            json={
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_settle_test",
                        "payment_intent": "pi_settle",
                        "payment_status": "paid",
                    }
                },
            },
            headers={"Stripe-Signature": "valid"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

        # Verify settlement was created
        settlement_repo = InvoiceSettlementRepository(db_session)
        settlements = settlement_repo.get_by_invoice_id(payment.invoice_id)
        assert len(settlements) == 1
        assert settlements[0].settlement_type == SettlementType.PAYMENT.value

    def test_mark_paid_creates_settlement(self, client, payment, db_session):
        """Test that manually marking as paid creates an InvoiceSettlement."""
        response = client.post(f"/v1/payments/{payment.id}/mark-paid")
        assert response.status_code == 200
        assert response.json()["status"] == "succeeded"

        # Verify settlement was created
        settlement_repo = InvoiceSettlementRepository(db_session)
        settlements = settlement_repo.get_by_invoice_id(payment.invoice_id)
        assert len(settlements) == 1
        assert settlements[0].settlement_type == SettlementType.PAYMENT.value
        assert Decimal(str(settlements[0].amount_cents)) == Decimal(str(payment.amount))


class TestListInvoiceSettlementsAPI:
    """Tests for the GET /v1/invoices/{invoice_id}/settlements endpoint."""

    def test_list_settlements(self, client, db_session, finalized_invoice):
        """Test listing settlements for an invoice."""
        repo = InvoiceSettlementRepository(db_session)
        repo.create(
            InvoiceSettlementCreate(
                invoice_id=finalized_invoice.id,
                settlement_type=SettlementType.PAYMENT,
                source_id=uuid4(),
                amount_cents=Decimal("60.00"),
            )
        )
        repo.create(
            InvoiceSettlementCreate(
                invoice_id=finalized_invoice.id,
                settlement_type=SettlementType.WALLET_CREDIT,
                source_id=uuid4(),
                amount_cents=Decimal("40.00"),
            )
        )
        response = client.get(f"/v1/invoices/{finalized_invoice.id}/settlements")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_settlements_empty(self, client, finalized_invoice):
        """Test listing settlements when none exist."""
        response = client.get(f"/v1/invoices/{finalized_invoice.id}/settlements")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_settlements_invoice_not_found(self, client):
        """Test listing settlements for a non-existent invoice."""
        fake_id = str(uuid4())
        response = client.get(f"/v1/invoices/{fake_id}/settlements")
        assert response.status_code == 404
        assert response.json()["detail"] == "Invoice not found"


class TestCreditNoteSettlement:
    """Tests for settlement creation when applying credit notes."""

    def test_apply_credit_creates_settlement(self, db_session, finalized_invoice, customer):
        """Test that applying credit note credit creates a settlement."""
        from app.models.credit_note import CreditNoteReason, CreditNoteType
        from app.repositories.credit_note_repository import CreditNoteRepository
        from app.repositories.fee_repository import FeeRepository
        from app.schemas.credit_note import CreditNoteCreate
        from app.schemas.fee import FeeCreate
        from app.services.credit_note_service import CreditNoteService

        # Create a fee for the invoice
        fee_repo = FeeRepository(db_session)
        fee_repo.create(
            FeeCreate(
                invoice_id=finalized_invoice.id,
                subscription_id=finalized_invoice.subscription_id,
                customer_id=customer.id,
                fee_type="subscription",
                amount_cents=Decimal("100.00"),
                units=Decimal("1"),
            )
        )

        # Create and finalize a credit note
        cn_repo = CreditNoteRepository(db_session)
        cn = cn_repo.create(
            CreditNoteCreate(
                number=f"CN-TEST-{uuid4()}",
                invoice_id=finalized_invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                credit_amount_cents=Decimal("100.00"),
                total_amount_cents=Decimal("100.00"),
                currency="USD",
                items=[],
            )
        )
        cn_repo.finalize(cn.id)

        # Apply credit to invoice
        service = CreditNoteService(db_session)
        service.apply_credit_to_invoice(
            credit_note_id=cn.id,
            invoice_id=finalized_invoice.id,
            amount=Decimal("100.00"),
        )

        # Verify settlement was created
        settlement_repo = InvoiceSettlementRepository(db_session)
        settlements = settlement_repo.get_by_invoice_id(finalized_invoice.id)
        assert len(settlements) == 1
        assert settlements[0].settlement_type == SettlementType.CREDIT_NOTE.value
        assert Decimal(str(settlements[0].amount_cents)) == Decimal("100.00")


class TestWalletCreditSettlement:
    """Tests for settlement creation when consuming wallet credits."""

    def test_consume_credits_creates_settlement(self, db_session, finalized_invoice, customer):
        """Test that consuming wallet credits creates a settlement."""
        from app.services.wallet_service import WalletService

        wallet_service = WalletService(db_session)
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Test Wallet",
            currency="USD",
            initial_granted_credits=Decimal("200"),
        )

        result = wallet_service.consume_credits(
            customer_id=customer.id,
            amount_cents=Decimal("100.00"),
            invoice_id=finalized_invoice.id,
        )

        assert result.total_consumed == Decimal("100.00")

        # Verify settlement was created
        settlement_repo = InvoiceSettlementRepository(db_session)
        settlements = settlement_repo.get_by_invoice_id(finalized_invoice.id)
        assert len(settlements) == 1
        assert settlements[0].settlement_type == SettlementType.WALLET_CREDIT.value

    def test_consume_credits_without_invoice_no_settlement(self, db_session, customer):
        """Test that consuming credits without invoice_id creates no settlement."""
        from app.services.wallet_service import WalletService

        wallet_service = WalletService(db_session)
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Test Wallet",
            currency="USD",
            initial_granted_credits=Decimal("200"),
        )

        result = wallet_service.consume_credits(
            customer_id=customer.id,
            amount_cents=Decimal("50.00"),
            invoice_id=None,
        )

        assert result.total_consumed == Decimal("50.00")
