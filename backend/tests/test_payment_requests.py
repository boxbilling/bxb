"""Tests for PaymentRequest models, schemas, and repository."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import Customer
from app.models.dunning_campaign import DunningCampaign
from app.models.invoice import Invoice
from app.models.payment_request import PaymentRequest
from app.models.payment_request_invoice import PaymentRequestInvoice
from app.repositories.payment_request_repository import PaymentRequestRepository
from app.schemas.payment_request import (
    PaymentRequestCreate,
    PaymentRequestInvoiceResponse,
    PaymentRequestResponse,
)
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def db_session():
    """Get a database session."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def customer(db_session: Session) -> Customer:
    """Create a test customer."""
    c = Customer(
        organization_id=DEFAULT_ORG_ID,
        external_id="cust-pr-001",
        name="PR Test Customer",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def invoices(db_session: Session, customer: Customer) -> list[Invoice]:
    """Create test invoices."""
    invs = []
    for i in range(3):
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number=f"INV-PR-{i:04d}",
            customer_id=customer.id,
            status="finalized",
            billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
            billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
            subtotal=Decimal("100"),
            tax_amount=Decimal("0"),
            total=Decimal("100"),
        )
        db_session.add(inv)
        invs.append(inv)
    db_session.commit()
    for inv in invs:
        db_session.refresh(inv)
    return invs


class TestPaymentRequestModel:
    """Test PaymentRequest model defaults and fields."""

    def test_payment_request_defaults(self, db_session: Session, customer: Customer) -> None:
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("500"),
            amount_currency="USD",
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        assert pr.id is not None
        assert pr.organization_id == DEFAULT_ORG_ID
        assert pr.customer_id == customer.id
        assert pr.dunning_campaign_id is None
        assert pr.amount_cents == Decimal("500")
        assert pr.amount_currency == "USD"
        assert pr.payment_status == "pending"
        assert pr.payment_attempts == 0
        assert pr.ready_for_payment_processing is True
        assert pr.created_at is not None
        assert pr.updated_at is not None

    def test_payment_request_with_campaign(
        self,
        db_session: Session,
        customer: Customer,
    ) -> None:
        campaign = DunningCampaign(
            organization_id=DEFAULT_ORG_ID,
            code="dc-pr",
            name="PR Campaign",
        )
        db_session.add(campaign)
        db_session.commit()

        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            dunning_campaign_id=campaign.id,
            amount_cents=Decimal("1000"),
            amount_currency="EUR",
            payment_status="succeeded",
            payment_attempts=2,
            ready_for_payment_processing=False,
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        assert pr.dunning_campaign_id == campaign.id
        assert pr.payment_status == "succeeded"
        assert pr.payment_attempts == 2
        assert pr.ready_for_payment_processing is False


class TestPaymentRequestInvoiceModel:
    """Test PaymentRequestInvoice join table."""

    def test_join_creation(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("300"),
            amount_currency="USD",
        )
        db_session.add(pr)
        db_session.commit()

        join_row = PaymentRequestInvoice(
            payment_request_id=pr.id,
            invoice_id=invoices[0].id,
        )
        db_session.add(join_row)
        db_session.commit()
        db_session.refresh(join_row)

        assert join_row.id is not None
        assert join_row.payment_request_id == pr.id
        assert join_row.invoice_id == invoices[0].id
        assert join_row.created_at is not None


class TestPaymentRequestSchemas:
    """Test PaymentRequest Pydantic schemas."""

    def test_create_schema(self) -> None:
        data = PaymentRequestCreate(
            customer_id=uuid.uuid4(),
            invoice_ids=[uuid.uuid4(), uuid.uuid4()],
        )
        assert len(data.invoice_ids) == 2

    def test_create_schema_empty_invoices(self) -> None:
        with pytest.raises(ValidationError):
            PaymentRequestCreate(customer_id=uuid.uuid4(), invoice_ids=[])

    def test_response_schema(
        self,
        db_session: Session,
        customer: Customer,
    ) -> None:
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        resp = PaymentRequestResponse.model_validate(pr)
        assert resp.id == pr.id
        assert resp.payment_status == "pending"
        assert resp.invoices == []

    def test_invoice_response_schema(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
        )
        db_session.add(pr)
        db_session.commit()

        join_row = PaymentRequestInvoice(
            payment_request_id=pr.id,
            invoice_id=invoices[0].id,
        )
        db_session.add(join_row)
        db_session.commit()
        db_session.refresh(join_row)

        resp = PaymentRequestInvoiceResponse.model_validate(join_row)
        assert resp.payment_request_id == pr.id
        assert resp.invoice_id == invoices[0].id


class TestPaymentRequestRepository:
    """Test PaymentRequestRepository CRUD operations."""

    def test_create_payment_request(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        repo = PaymentRequestRepository(db_session)
        pr = repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("300"),
            amount_currency="USD",
            invoice_ids=[inv.id for inv in invoices],
        )

        assert pr.id is not None
        assert pr.customer_id == customer.id
        assert pr.amount_cents == Decimal("300")

        join_rows = repo.get_invoices(pr.id)
        assert len(join_rows) == 3

    def test_create_with_dunning_campaign(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        campaign = DunningCampaign(
            organization_id=DEFAULT_ORG_ID,
            code="dc-repo-pr",
            name="Repo Campaign",
        )
        db_session.add(campaign)
        db_session.commit()

        repo = PaymentRequestRepository(db_session)
        pr = repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("200"),
            amount_currency="EUR",
            invoice_ids=[invoices[0].id],
            dunning_campaign_id=campaign.id,
        )
        assert pr.dunning_campaign_id == campaign.id

    def test_get_by_id(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        repo = PaymentRequestRepository(db_session)
        created = repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[invoices[0].id],
        )

        found = repo.get_by_id(created.id, DEFAULT_ORG_ID)
        assert found is not None
        assert found.id == created.id

    def test_get_by_id_not_found(self, db_session: Session) -> None:
        repo = PaymentRequestRepository(db_session)
        result = repo.get_by_id(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is None

    def test_get_all(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        repo = PaymentRequestRepository(db_session)
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[invoices[0].id],
        )
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("200"),
            amount_currency="USD",
            invoice_ids=[invoices[1].id],
        )

        all_prs = repo.get_all(DEFAULT_ORG_ID)
        assert len(all_prs) == 2

    def test_get_all_filter_by_customer(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        # Create a second customer
        c2 = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-pr-other",
            name="Other Customer",
        )
        db_session.add(c2)
        db_session.commit()
        db_session.refresh(c2)

        repo = PaymentRequestRepository(db_session)
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[invoices[0].id],
        )

        filtered = repo.get_all(DEFAULT_ORG_ID, customer_id=customer.id)
        assert len(filtered) == 1

        filtered_other = repo.get_all(DEFAULT_ORG_ID, customer_id=c2.id)
        assert len(filtered_other) == 0

    def test_get_all_filter_by_status(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        repo = PaymentRequestRepository(db_session)
        pr = repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[invoices[0].id],
        )
        repo.update_status(pr.id, DEFAULT_ORG_ID, "succeeded")

        pending = repo.get_all(DEFAULT_ORG_ID, payment_status="pending")
        assert len(pending) == 0

        succeeded = repo.get_all(DEFAULT_ORG_ID, payment_status="succeeded")
        assert len(succeeded) == 1

    def test_get_all_pagination(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        repo = PaymentRequestRepository(db_session)
        for i, inv in enumerate(invoices):
            repo.create(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                amount_cents=Decimal(str((i + 1) * 100)),
                amount_currency="USD",
                invoice_ids=[inv.id],
            )

        page = repo.get_all(DEFAULT_ORG_ID, skip=1, limit=1)
        assert len(page) == 1

    def test_update_status(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        repo = PaymentRequestRepository(db_session)
        pr = repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[invoices[0].id],
        )

        updated = repo.update_status(pr.id, DEFAULT_ORG_ID, "succeeded")
        assert updated is not None
        assert updated.payment_status == "succeeded"

    def test_update_status_not_found(self, db_session: Session) -> None:
        repo = PaymentRequestRepository(db_session)
        result = repo.update_status(uuid.uuid4(), DEFAULT_ORG_ID, "succeeded")
        assert result is None

    def test_increment_attempts(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        repo = PaymentRequestRepository(db_session)
        pr = repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[invoices[0].id],
        )
        assert pr.payment_attempts == 0

        updated = repo.increment_attempts(pr.id, DEFAULT_ORG_ID)
        assert updated is not None
        assert updated.payment_attempts == 1

        updated2 = repo.increment_attempts(pr.id, DEFAULT_ORG_ID)
        assert updated2 is not None
        assert updated2.payment_attempts == 2

    def test_increment_attempts_not_found(self, db_session: Session) -> None:
        repo = PaymentRequestRepository(db_session)
        result = repo.increment_attempts(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is None

    def test_get_invoices(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        repo = PaymentRequestRepository(db_session)
        pr = repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("200"),
            amount_currency="USD",
            invoice_ids=[invoices[0].id, invoices[1].id],
        )

        join_rows = repo.get_invoices(pr.id)
        assert len(join_rows) == 2
        invoice_ids = {jr.invoice_id for jr in join_rows}
        assert invoices[0].id in invoice_ids
        assert invoices[1].id in invoice_ids

    def test_get_invoices_empty(self, db_session: Session) -> None:
        repo = PaymentRequestRepository(db_session)
        result = repo.get_invoices(uuid.uuid4())
        assert result == []

    def test_delete_payment_request(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        repo = PaymentRequestRepository(db_session)
        pr = repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[invoices[0].id],
        )

        result = repo.delete(pr.id, DEFAULT_ORG_ID)
        assert result is True
        assert repo.get_by_id(pr.id, DEFAULT_ORG_ID) is None

    def test_delete_not_found(self, db_session: Session) -> None:
        repo = PaymentRequestRepository(db_session)
        result = repo.delete(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is False

    def test_delete_non_pending_raises(
        self,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        repo = PaymentRequestRepository(db_session)
        pr = repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[invoices[0].id],
        )
        repo.update_status(pr.id, DEFAULT_ORG_ID, "succeeded")

        with pytest.raises(ValueError, match="Only pending payment requests can be deleted"):
            repo.delete(pr.id, DEFAULT_ORG_ID)
