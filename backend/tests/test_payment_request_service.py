"""Tests for PaymentRequestService — manual payment request management."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.services.payment_request_service import PaymentRequestService
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def db_session():
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def customer(db_session: Session) -> Customer:
    c = Customer(
        organization_id=DEFAULT_ORG_ID,
        external_id="cust-prs-001",
        name="PR Service Test Customer",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def finalized_invoices(db_session: Session, customer: Customer) -> list[Invoice]:
    invs = []
    for i in range(3):
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number=f"INV-PRS-{i:04d}",
            customer_id=customer.id,
            status=InvoiceStatus.FINALIZED.value,
            billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
            billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
            subtotal=Decimal("100"),
            tax_amount=Decimal("0"),
            total=Decimal("100"),
            currency="USD",
        )
        db_session.add(inv)
        invs.append(inv)
    db_session.commit()
    for inv in invs:
        db_session.refresh(inv)
    return invs


class TestCreateManualPaymentRequest:
    """Tests for PaymentRequestService.create_manual_payment_request."""

    def test_creates_payment_request(
        self,
        db_session: Session,
        customer: Customer,
        finalized_invoices: list[Invoice],
    ) -> None:
        service = PaymentRequestService(db_session)
        with patch.object(service.webhook_service, "send_webhook"):
            pr = service.create_manual_payment_request(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                invoice_ids=[finalized_invoices[0].id, finalized_invoices[1].id],
            )

        assert pr.customer_id == customer.id
        assert pr.amount_cents == Decimal("200")
        assert pr.amount_currency == "USD"
        assert pr.payment_status == "pending"

    def test_single_invoice(
        self,
        db_session: Session,
        customer: Customer,
        finalized_invoices: list[Invoice],
    ) -> None:
        service = PaymentRequestService(db_session)
        with patch.object(service.webhook_service, "send_webhook"):
            pr = service.create_manual_payment_request(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                invoice_ids=[finalized_invoices[0].id],
            )

        assert pr.amount_cents == Decimal("100")

    def test_triggers_webhook(
        self,
        db_session: Session,
        customer: Customer,
        finalized_invoices: list[Invoice],
    ) -> None:
        service = PaymentRequestService(db_session)
        with patch.object(service.webhook_service, "send_webhook") as mock_wh:
            service.create_manual_payment_request(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                invoice_ids=[finalized_invoices[0].id],
            )

        mock_wh.assert_called_once()
        assert mock_wh.call_args.kwargs["webhook_type"] == "payment_request.created"

    def test_customer_not_found_raises(self, db_session: Session) -> None:
        service = PaymentRequestService(db_session)
        with pytest.raises(ValueError, match="Customer .* not found"):
            service.create_manual_payment_request(
                organization_id=DEFAULT_ORG_ID,
                customer_id=uuid.uuid4(),
                invoice_ids=[uuid.uuid4()],
            )

    def test_invoice_not_found_raises(
        self, db_session: Session, customer: Customer,
    ) -> None:
        service = PaymentRequestService(db_session)
        with pytest.raises(ValueError, match="Invoice .* not found"):
            service.create_manual_payment_request(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                invoice_ids=[uuid.uuid4()],
            )

    def test_invoice_wrong_customer_raises(
        self,
        db_session: Session,
        customer: Customer,
        finalized_invoices: list[Invoice],
    ) -> None:
        # Create another customer
        other = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-prs-other",
            name="Other Customer",
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        service = PaymentRequestService(db_session)
        with pytest.raises(ValueError, match="does not belong to customer"):
            service.create_manual_payment_request(
                organization_id=DEFAULT_ORG_ID,
                customer_id=other.id,
                invoice_ids=[finalized_invoices[0].id],
            )

    def test_invoice_not_finalized_raises(
        self, db_session: Session, customer: Customer,
    ) -> None:
        draft_inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="INV-PRS-DRAFT",
            customer_id=customer.id,
            status=InvoiceStatus.DRAFT.value,
            billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
            billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
            subtotal=Decimal("100"),
            tax_amount=Decimal("0"),
            total=Decimal("100"),
        )
        db_session.add(draft_inv)
        db_session.commit()
        db_session.refresh(draft_inv)

        service = PaymentRequestService(db_session)
        with pytest.raises(ValueError, match="not in finalized status"):
            service.create_manual_payment_request(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                invoice_ids=[draft_inv.id],
            )

    def test_empty_invoice_ids_raises(
        self, db_session: Session, customer: Customer,
    ) -> None:
        service = PaymentRequestService(db_session)
        with pytest.raises(ValueError, match="No invoices provided"):
            service.create_manual_payment_request(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                invoice_ids=[],
            )

    def test_mixed_currency_raises(
        self, db_session: Session, customer: Customer, finalized_invoices: list[Invoice],
    ) -> None:
        eur_inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="INV-PRS-EUR",
            customer_id=customer.id,
            status=InvoiceStatus.FINALIZED.value,
            billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
            billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
            subtotal=Decimal("100"),
            tax_amount=Decimal("0"),
            total=Decimal("100"),
            currency="EUR",
        )
        db_session.add(eur_inv)
        db_session.commit()
        db_session.refresh(eur_inv)

        service = PaymentRequestService(db_session)
        with pytest.raises(ValueError, match="same currency"):
            service.create_manual_payment_request(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                invoice_ids=[finalized_invoices[0].id, eur_inv.id],
            )


class TestGetCustomerOutstanding:
    """Tests for PaymentRequestService.get_customer_outstanding."""

    def test_sums_finalized_invoices(
        self,
        db_session: Session,
        customer: Customer,
        finalized_invoices: list[Invoice],
    ) -> None:
        service = PaymentRequestService(db_session)
        total = service.get_customer_outstanding(customer.id, DEFAULT_ORG_ID)
        assert total == Decimal("300")

    def test_excludes_paid_invoices(
        self,
        db_session: Session,
        customer: Customer,
        finalized_invoices: list[Invoice],
    ) -> None:
        # Mark one invoice as paid
        finalized_invoices[0].status = InvoiceStatus.PAID.value  # type: ignore[assignment]
        db_session.commit()

        service = PaymentRequestService(db_session)
        total = service.get_customer_outstanding(customer.id, DEFAULT_ORG_ID)
        assert total == Decimal("200")

    def test_excludes_draft_invoices(
        self, db_session: Session, customer: Customer,
    ) -> None:
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="INV-PRS-DRAFT2",
            customer_id=customer.id,
            status=InvoiceStatus.DRAFT.value,
            billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
            billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
            subtotal=Decimal("1000"),
            tax_amount=Decimal("0"),
            total=Decimal("1000"),
        )
        db_session.add(inv)
        db_session.commit()

        service = PaymentRequestService(db_session)
        total = service.get_customer_outstanding(customer.id, DEFAULT_ORG_ID)
        assert total == Decimal("0")

    def test_no_invoices_returns_zero(
        self, db_session: Session, customer: Customer,
    ) -> None:
        service = PaymentRequestService(db_session)
        total = service.get_customer_outstanding(customer.id, DEFAULT_ORG_ID)
        assert total == Decimal("0")
