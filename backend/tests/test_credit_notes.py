"""Tests for CreditNote and CreditNoteItem models, schemas, repositories, and CRUD operations."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.database import get_db
from app.main import app
from app.models.credit_note import (
    CreditNote,
    CreditNoteReason,
    CreditNoteStatus,
    CreditNoteType,
    CreditStatus,
    RefundStatus,
)
from app.models.credit_note_item import CreditNoteItem
from app.repositories.credit_note_item_repository import CreditNoteItemRepository
from app.repositories.credit_note_repository import CreditNoteRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.credit_note import (
    CreditNoteCreate,
    CreditNoteItemCreate,
    CreditNoteItemResponse,
    CreditNoteResponse,
    CreditNoteUpdate,
)
from app.schemas.customer import CustomerCreate
from app.schemas.fee import FeeCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate


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
            external_id=f"cn_test_cust_{uuid4()}",
            name="Credit Note Test Customer",
            email="cn@test.com",
        )
    )


@pytest.fixture
def customer2(db_session):
    """Create a second test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"cn_test_cust2_{uuid4()}",
            name="Credit Note Test Customer 2",
        )
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"cn_test_plan_{uuid4()}",
            name="Credit Note Test Plan",
            interval="monthly",
        )
    )


@pytest.fixture
def subscription(db_session, customer, plan):
    """Create a test subscription."""
    repo = SubscriptionRepository(db_session)
    return repo.create(
        SubscriptionCreate(
            external_id=f"cn_test_sub_{uuid4()}",
            customer_id=customer.id,
            plan_id=plan.id,
        )
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
def invoice2(db_session, customer, subscription):
    """Create a second test invoice."""
    repo = InvoiceRepository(db_session)
    return repo.create(
        InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC) + timedelta(days=30),
            billing_period_end=datetime.now(UTC) + timedelta(days=60),
            currency="USD",
            line_items=[
                InvoiceLineItem(
                    description="Test item 2",
                    quantity=Decimal("1"),
                    unit_price=Decimal("200.00"),
                    amount=Decimal("200.00"),
                )
            ],
        )
    )


@pytest.fixture
def fee(db_session, customer, invoice):
    """Create a test fee."""
    repo = FeeRepository(db_session)
    return repo.create(
        FeeCreate(
            customer_id=customer.id,
            invoice_id=invoice.id,
            amount_cents=Decimal("10000"),
            total_amount_cents=Decimal("10000"),
            units=Decimal("100"),
            events_count=50,
            unit_amount_cents=Decimal("100"),
            description="API calls charge",
            metric_code="api_calls",
        )
    )


@pytest.fixture
def fee2(db_session, customer, invoice):
    """Create a second test fee."""
    repo = FeeRepository(db_session)
    return repo.create(
        FeeCreate(
            customer_id=customer.id,
            invoice_id=invoice.id,
            amount_cents=Decimal("5000"),
            total_amount_cents=Decimal("5000"),
            units=Decimal("50"),
            events_count=25,
            unit_amount_cents=Decimal("100"),
            description="Storage charge",
            metric_code="storage",
        )
    )


@pytest.fixture
def credit_note(db_session, customer, invoice):
    """Create a test credit note."""
    repo = CreditNoteRepository(db_session)
    return repo.create(
        CreditNoteCreate(
            number="CN-0001",
            invoice_id=invoice.id,
            customer_id=customer.id,
            credit_note_type=CreditNoteType.CREDIT,
            reason=CreditNoteReason.DUPLICATED_CHARGE,
            description="Duplicate charge credit",
            credit_amount_cents=Decimal("5000.0000"),
            total_amount_cents=Decimal("5000.0000"),
            currency="USD",
        )
    )


@pytest.fixture
def refund_note(db_session, customer, invoice):
    """Create a refund-type credit note."""
    repo = CreditNoteRepository(db_session)
    return repo.create(
        CreditNoteCreate(
            number="CN-0002",
            invoice_id=invoice.id,
            customer_id=customer.id,
            credit_note_type=CreditNoteType.REFUND,
            reason=CreditNoteReason.PRODUCT_UNSATISFACTORY,
            refund_amount_cents=Decimal("3000.0000"),
            total_amount_cents=Decimal("3000.0000"),
            currency="USD",
        )
    )


class TestCreditNoteModel:
    """Tests for CreditNote SQLAlchemy model."""

    def test_credit_note_defaults(self, db_session, customer, invoice):
        """Test CreditNote model default values."""
        cn = CreditNote(
            number="CN-TEST-001",
            invoice_id=invoice.id,
            customer_id=customer.id,
            credit_note_type=CreditNoteType.CREDIT.value,
            reason=CreditNoteReason.OTHER.value,
            currency="USD",
        )
        db_session.add(cn)
        db_session.commit()
        db_session.refresh(cn)

        assert cn.id is not None
        assert cn.number == "CN-TEST-001"
        assert cn.invoice_id == invoice.id
        assert cn.customer_id == customer.id
        assert cn.credit_note_type == "credit"
        assert cn.status == CreditNoteStatus.DRAFT.value
        assert cn.credit_status is None
        assert cn.refund_status is None
        assert cn.reason == "other"
        assert cn.description is None
        assert cn.credit_amount_cents == 0
        assert cn.refund_amount_cents == 0
        assert cn.balance_amount_cents == 0
        assert cn.total_amount_cents == 0
        assert cn.taxes_amount_cents == 0
        assert cn.currency == "USD"
        assert cn.issued_at is None
        assert cn.voided_at is None
        assert cn.created_at is not None
        assert cn.updated_at is not None

    def test_credit_note_with_all_fields(self, db_session, customer, invoice):
        """Test CreditNote model with all fields populated."""
        now = datetime.now(UTC)
        cn = CreditNote(
            number="CN-FULL-001",
            invoice_id=invoice.id,
            customer_id=customer.id,
            credit_note_type=CreditNoteType.REFUND.value,
            status=CreditNoteStatus.FINALIZED.value,
            credit_status=CreditStatus.AVAILABLE.value,
            refund_status=RefundStatus.SUCCEEDED.value,
            reason=CreditNoteReason.FRAUDULENT_CHARGE.value,
            description="Full credit note description",
            credit_amount_cents=Decimal("10000.0000"),
            refund_amount_cents=Decimal("5000.0000"),
            balance_amount_cents=Decimal("10000.0000"),
            total_amount_cents=Decimal("15000.0000"),
            taxes_amount_cents=Decimal("1500.0000"),
            currency="EUR",
            issued_at=now,
        )
        db_session.add(cn)
        db_session.commit()
        db_session.refresh(cn)

        assert cn.number == "CN-FULL-001"
        assert cn.credit_note_type == "refund"
        assert cn.status == "finalized"
        assert cn.credit_status == "available"
        assert cn.refund_status == "succeeded"
        assert cn.reason == "fraudulent_charge"
        assert cn.description == "Full credit note description"
        assert cn.credit_amount_cents == Decimal("10000.0000")
        assert cn.refund_amount_cents == Decimal("5000.0000")
        assert cn.balance_amount_cents == Decimal("10000.0000")
        assert cn.total_amount_cents == Decimal("15000.0000")
        assert cn.taxes_amount_cents == Decimal("1500.0000")
        assert cn.currency == "EUR"
        assert cn.issued_at is not None

    def test_credit_note_type_enum(self):
        """Test CreditNoteType enum values."""
        assert CreditNoteType.CREDIT.value == "credit"
        assert CreditNoteType.REFUND.value == "refund"
        assert CreditNoteType.OFFSET.value == "offset"

    def test_credit_note_status_enum(self):
        """Test CreditNoteStatus enum values."""
        assert CreditNoteStatus.DRAFT.value == "draft"
        assert CreditNoteStatus.FINALIZED.value == "finalized"

    def test_credit_status_enum(self):
        """Test CreditStatus enum values."""
        assert CreditStatus.AVAILABLE.value == "available"
        assert CreditStatus.CONSUMED.value == "consumed"
        assert CreditStatus.VOIDED.value == "voided"

    def test_refund_status_enum(self):
        """Test RefundStatus enum values."""
        assert RefundStatus.PENDING.value == "pending"
        assert RefundStatus.SUCCEEDED.value == "succeeded"
        assert RefundStatus.FAILED.value == "failed"

    def test_credit_note_reason_enum(self):
        """Test CreditNoteReason enum values."""
        assert CreditNoteReason.DUPLICATED_CHARGE.value == "duplicated_charge"
        assert CreditNoteReason.PRODUCT_UNSATISFACTORY.value == "product_unsatisfactory"
        assert CreditNoteReason.ORDER_CHANGE.value == "order_change"
        assert CreditNoteReason.ORDER_CANCELLATION.value == "order_cancellation"
        assert CreditNoteReason.FRAUDULENT_CHARGE.value == "fraudulent_charge"
        assert CreditNoteReason.OTHER.value == "other"


class TestCreditNoteItemModel:
    """Tests for CreditNoteItem SQLAlchemy model."""

    def test_credit_note_item_creation(self, db_session, credit_note, fee):
        """Test CreditNoteItem model creation."""
        item = CreditNoteItem(
            credit_note_id=credit_note.id,
            fee_id=fee.id,
            amount_cents=Decimal("2500.0000"),
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        assert item.id is not None
        assert item.credit_note_id == credit_note.id
        assert item.fee_id == fee.id
        assert item.amount_cents == Decimal("2500.0000")
        assert item.created_at is not None

    def test_multiple_items_per_credit_note(self, db_session, credit_note, fee, fee2):
        """Test multiple items linked to a single credit note."""
        item1 = CreditNoteItem(
            credit_note_id=credit_note.id,
            fee_id=fee.id,
            amount_cents=Decimal("3000.0000"),
        )
        item2 = CreditNoteItem(
            credit_note_id=credit_note.id,
            fee_id=fee2.id,
            amount_cents=Decimal("2000.0000"),
        )
        db_session.add_all([item1, item2])
        db_session.commit()

        items = (
            db_session.query(CreditNoteItem)
            .filter(CreditNoteItem.credit_note_id == credit_note.id)
            .all()
        )
        assert len(items) == 2


class TestCreditNoteRepository:
    """Tests for CreditNoteRepository."""

    def test_create_credit_note(self, db_session, customer, invoice):
        """Test creating a credit note via repository."""
        repo = CreditNoteRepository(db_session)
        cn = repo.create(
            CreditNoteCreate(
                number="CN-REPO-001",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.ORDER_CHANGE,
                description="Repo test credit note",
                credit_amount_cents=Decimal("7500.0000"),
                total_amount_cents=Decimal("7500.0000"),
                currency="USD",
            )
        )

        assert cn.id is not None
        assert cn.number == "CN-REPO-001"
        assert cn.credit_note_type == "credit"
        assert cn.reason == "order_change"
        assert cn.description == "Repo test credit note"
        assert cn.credit_amount_cents == Decimal("7500.0000")
        assert cn.status == CreditNoteStatus.DRAFT.value

    def test_get_by_id(self, db_session, credit_note):
        """Test getting a credit note by ID."""
        repo = CreditNoteRepository(db_session)
        found = repo.get_by_id(credit_note.id)
        assert found is not None
        assert found.id == credit_note.id
        assert found.number == "CN-0001"

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent credit note by ID."""
        repo = CreditNoteRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_number(self, db_session, credit_note):
        """Test getting a credit note by number."""
        repo = CreditNoteRepository(db_session)
        found = repo.get_by_number("CN-0001")
        assert found is not None
        assert found.id == credit_note.id

    def test_get_by_number_not_found(self, db_session):
        """Test getting a non-existent credit note by number."""
        repo = CreditNoteRepository(db_session)
        assert repo.get_by_number("NONEXISTENT") is None

    def test_get_by_invoice_id(self, db_session, credit_note, refund_note, invoice):
        """Test getting credit notes by invoice ID."""
        repo = CreditNoteRepository(db_session)
        notes = repo.get_by_invoice_id(invoice.id)
        assert len(notes) == 2

    def test_get_by_invoice_id_empty(self, db_session):
        """Test getting credit notes for an invoice with none."""
        repo = CreditNoteRepository(db_session)
        notes = repo.get_by_invoice_id(uuid4())
        assert notes == []

    def test_get_by_customer_id(self, db_session, credit_note, refund_note, customer):
        """Test getting credit notes by customer ID."""
        repo = CreditNoteRepository(db_session)
        notes = repo.get_by_customer_id(customer.id)
        assert len(notes) == 2

    def test_get_by_customer_id_with_pagination(self, db_session, credit_note, refund_note, customer):
        """Test getting credit notes with pagination."""
        repo = CreditNoteRepository(db_session)
        notes = repo.get_by_customer_id(customer.id, skip=0, limit=1)
        assert len(notes) == 1

    def test_get_by_customer_id_empty(self, db_session):
        """Test getting credit notes for a customer with none."""
        repo = CreditNoteRepository(db_session)
        notes = repo.get_by_customer_id(uuid4())
        assert notes == []

    def test_get_all(self, db_session, credit_note, refund_note):
        """Test getting all credit notes."""
        repo = CreditNoteRepository(db_session)
        notes = repo.get_all()
        assert len(notes) == 2

    def test_get_all_with_status_filter(self, db_session, credit_note, refund_note):
        """Test getting all credit notes filtered by status."""
        repo = CreditNoteRepository(db_session)
        notes = repo.get_all(status=CreditNoteStatus.DRAFT)
        assert len(notes) == 2

        notes = repo.get_all(status=CreditNoteStatus.FINALIZED)
        assert len(notes) == 0

    def test_get_all_with_customer_filter(self, db_session, credit_note, customer):
        """Test getting all credit notes filtered by customer."""
        repo = CreditNoteRepository(db_session)
        notes = repo.get_all(customer_id=customer.id)
        assert len(notes) >= 1

    def test_get_all_with_invoice_filter(self, db_session, credit_note, invoice):
        """Test getting all credit notes filtered by invoice."""
        repo = CreditNoteRepository(db_session)
        notes = repo.get_all(invoice_id=invoice.id)
        assert len(notes) >= 1

    def test_get_all_with_pagination(self, db_session, credit_note, refund_note):
        """Test getting all credit notes with pagination."""
        repo = CreditNoteRepository(db_session)
        notes = repo.get_all(skip=0, limit=1)
        assert len(notes) == 1

        notes = repo.get_all(skip=1, limit=1)
        assert len(notes) == 1

    def test_update_credit_note(self, db_session, credit_note):
        """Test updating a credit note."""
        repo = CreditNoteRepository(db_session)
        updated = repo.update(
            credit_note.id,
            CreditNoteUpdate(
                description="Updated description",
                credit_amount_cents=Decimal("6000.0000"),
            ),
        )
        assert updated is not None
        assert updated.description == "Updated description"
        assert updated.credit_amount_cents == Decimal("6000.0000")

    def test_update_credit_note_not_found(self, db_session):
        """Test updating a non-existent credit note."""
        repo = CreditNoteRepository(db_session)
        result = repo.update(uuid4(), CreditNoteUpdate(description="Test"))
        assert result is None

    def test_update_credit_note_status(self, db_session, credit_note):
        """Test updating credit note status via update method."""
        repo = CreditNoteRepository(db_session)
        updated = repo.update(
            credit_note.id,
            CreditNoteUpdate(status=CreditNoteStatus.FINALIZED),
        )
        assert updated is not None
        assert updated.status == CreditNoteStatus.FINALIZED.value

    def test_update_credit_note_credit_status(self, db_session, credit_note):
        """Test updating credit note credit_status via update method."""
        repo = CreditNoteRepository(db_session)
        updated = repo.update(
            credit_note.id,
            CreditNoteUpdate(credit_status=CreditStatus.AVAILABLE),
        )
        assert updated is not None
        assert updated.credit_status == CreditStatus.AVAILABLE.value

    def test_update_credit_note_refund_status(self, db_session, credit_note):
        """Test updating credit note refund_status via update method."""
        repo = CreditNoteRepository(db_session)
        updated = repo.update(
            credit_note.id,
            CreditNoteUpdate(refund_status=RefundStatus.SUCCEEDED),
        )
        assert updated is not None
        assert updated.refund_status == RefundStatus.SUCCEEDED.value

    def test_update_credit_note_reason(self, db_session, credit_note):
        """Test updating credit note reason via update method."""
        repo = CreditNoteRepository(db_session)
        updated = repo.update(
            credit_note.id,
            CreditNoteUpdate(reason=CreditNoteReason.OTHER),
        )
        assert updated is not None
        assert updated.reason == CreditNoteReason.OTHER.value

    def test_finalize_credit_note(self, db_session, credit_note):
        """Test finalizing a credit note."""
        repo = CreditNoteRepository(db_session)
        finalized = repo.finalize(credit_note.id)

        assert finalized is not None
        assert finalized.status == CreditNoteStatus.FINALIZED.value
        assert finalized.issued_at is not None
        assert finalized.balance_amount_cents == finalized.credit_amount_cents
        assert finalized.credit_status == CreditStatus.AVAILABLE.value

    def test_finalize_credit_note_not_found(self, db_session):
        """Test finalizing a non-existent credit note."""
        repo = CreditNoteRepository(db_session)
        result = repo.finalize(uuid4())
        assert result is None

    def test_void_credit_note(self, db_session, credit_note):
        """Test voiding a credit note."""
        repo = CreditNoteRepository(db_session)
        # First finalize, then void
        repo.finalize(credit_note.id)
        voided = repo.void(credit_note.id)

        assert voided is not None
        assert voided.credit_status == CreditStatus.VOIDED.value
        assert voided.voided_at is not None
        assert voided.balance_amount_cents == Decimal("0")

    def test_void_credit_note_not_found(self, db_session):
        """Test voiding a non-existent credit note."""
        repo = CreditNoteRepository(db_session)
        result = repo.void(uuid4())
        assert result is None

    def test_consume_credit_partial(self, db_session, credit_note):
        """Test partially consuming credit from a credit note."""
        repo = CreditNoteRepository(db_session)
        # Finalize first to set balance
        repo.finalize(credit_note.id)

        consumed = repo.consume_credit(credit_note.id, Decimal("2000.0000"))
        assert consumed is not None
        assert consumed.balance_amount_cents == Decimal("3000.0000")
        assert consumed.credit_status == CreditStatus.AVAILABLE.value

    def test_consume_credit_full(self, db_session, credit_note):
        """Test fully consuming credit from a credit note."""
        repo = CreditNoteRepository(db_session)
        repo.finalize(credit_note.id)

        consumed = repo.consume_credit(credit_note.id, Decimal("5000.0000"))
        assert consumed is not None
        assert consumed.balance_amount_cents == Decimal("0")
        assert consumed.credit_status == CreditStatus.CONSUMED.value

    def test_consume_credit_over_balance(self, db_session, credit_note):
        """Test consuming more than the available balance."""
        repo = CreditNoteRepository(db_session)
        repo.finalize(credit_note.id)

        consumed = repo.consume_credit(credit_note.id, Decimal("9999.0000"))
        assert consumed is not None
        assert consumed.balance_amount_cents == Decimal("0")
        assert consumed.credit_status == CreditStatus.CONSUMED.value

    def test_consume_credit_not_found(self, db_session):
        """Test consuming credit from a non-existent credit note."""
        repo = CreditNoteRepository(db_session)
        result = repo.consume_credit(uuid4(), Decimal("1000"))
        assert result is None

    def test_get_available_credit_by_customer_id(self, db_session, customer, invoice):
        """Test getting total available credit for a customer."""
        repo = CreditNoteRepository(db_session)

        # Create and finalize two credit notes
        cn1 = repo.create(
            CreditNoteCreate(
                number="CN-AVAIL-001",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                credit_amount_cents=Decimal("3000.0000"),
                total_amount_cents=Decimal("3000.0000"),
                currency="USD",
            )
        )
        cn2 = repo.create(
            CreditNoteCreate(
                number="CN-AVAIL-002",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                credit_amount_cents=Decimal("2000.0000"),
                total_amount_cents=Decimal("2000.0000"),
                currency="USD",
            )
        )
        repo.finalize(cn1.id)
        repo.finalize(cn2.id)

        total = repo.get_available_credit_by_customer_id(customer.id)
        assert total == Decimal("5000.0000")

    def test_get_available_credit_excludes_voided(self, db_session, customer, invoice):
        """Test that voided credit notes are excluded from available credit."""
        repo = CreditNoteRepository(db_session)

        cn = repo.create(
            CreditNoteCreate(
                number="CN-VOID-001",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                credit_amount_cents=Decimal("3000.0000"),
                total_amount_cents=Decimal("3000.0000"),
                currency="USD",
            )
        )
        repo.finalize(cn.id)
        repo.void(cn.id)

        total = repo.get_available_credit_by_customer_id(customer.id)
        assert total == Decimal("0")

    def test_get_available_credit_excludes_drafts(self, db_session, customer, invoice):
        """Test that draft credit notes are excluded from available credit."""
        repo = CreditNoteRepository(db_session)

        repo.create(
            CreditNoteCreate(
                number="CN-DRAFT-001",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                credit_amount_cents=Decimal("3000.0000"),
                total_amount_cents=Decimal("3000.0000"),
                currency="USD",
            )
        )

        total = repo.get_available_credit_by_customer_id(customer.id)
        assert total == Decimal("0")

    def test_get_available_credit_no_notes(self, db_session):
        """Test available credit for customer with no credit notes."""
        repo = CreditNoteRepository(db_session)
        total = repo.get_available_credit_by_customer_id(uuid4())
        assert total == Decimal("0")

    def test_delete_credit_note(self, db_session, credit_note):
        """Test deleting a credit note."""
        repo = CreditNoteRepository(db_session)
        assert repo.delete(credit_note.id) is True
        assert repo.get_by_id(credit_note.id) is None

    def test_delete_credit_note_not_found(self, db_session):
        """Test deleting a non-existent credit note."""
        repo = CreditNoteRepository(db_session)
        assert repo.delete(uuid4()) is False


class TestCreditNoteItemRepository:
    """Tests for CreditNoteItemRepository."""

    def test_create_item(self, db_session, credit_note, fee):
        """Test creating a credit note item."""
        repo = CreditNoteItemRepository(db_session)
        item = repo.create(
            credit_note_id=credit_note.id,
            fee_id=fee.id,
            amount_cents=Decimal("2500.0000"),
        )

        assert item.id is not None
        assert item.credit_note_id == credit_note.id
        assert item.fee_id == fee.id
        assert item.amount_cents == Decimal("2500.0000")
        assert item.created_at is not None

    def test_get_by_id(self, db_session, credit_note, fee):
        """Test getting a credit note item by ID."""
        repo = CreditNoteItemRepository(db_session)
        item = repo.create(
            credit_note_id=credit_note.id,
            fee_id=fee.id,
            amount_cents=Decimal("1500.0000"),
        )
        found = repo.get_by_id(item.id)
        assert found is not None
        assert found.id == item.id

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent credit note item."""
        repo = CreditNoteItemRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_credit_note_id(self, db_session, credit_note, fee, fee2):
        """Test getting all items for a credit note."""
        repo = CreditNoteItemRepository(db_session)
        repo.create(
            credit_note_id=credit_note.id,
            fee_id=fee.id,
            amount_cents=Decimal("3000.0000"),
        )
        repo.create(
            credit_note_id=credit_note.id,
            fee_id=fee2.id,
            amount_cents=Decimal("2000.0000"),
        )

        items = repo.get_by_credit_note_id(credit_note.id)
        assert len(items) == 2

    def test_get_by_credit_note_id_empty(self, db_session):
        """Test getting items for a credit note with none."""
        repo = CreditNoteItemRepository(db_session)
        items = repo.get_by_credit_note_id(uuid4())
        assert items == []

    def test_get_all(self, db_session, credit_note, fee, fee2):
        """Test getting all credit note items."""
        repo = CreditNoteItemRepository(db_session)
        repo.create(
            credit_note_id=credit_note.id,
            fee_id=fee.id,
            amount_cents=Decimal("3000.0000"),
        )
        repo.create(
            credit_note_id=credit_note.id,
            fee_id=fee2.id,
            amount_cents=Decimal("2000.0000"),
        )

        items = repo.get_all()
        assert len(items) == 2

    def test_get_all_with_filter(self, db_session, credit_note, fee):
        """Test getting credit note items with credit_note_id filter."""
        repo = CreditNoteItemRepository(db_session)
        repo.create(
            credit_note_id=credit_note.id,
            fee_id=fee.id,
            amount_cents=Decimal("1000.0000"),
        )

        items = repo.get_all(credit_note_id=credit_note.id)
        assert len(items) == 1

    def test_get_all_with_pagination(self, db_session, credit_note, fee, fee2):
        """Test getting credit note items with pagination."""
        repo = CreditNoteItemRepository(db_session)
        repo.create(
            credit_note_id=credit_note.id,
            fee_id=fee.id,
            amount_cents=Decimal("3000.0000"),
        )
        repo.create(
            credit_note_id=credit_note.id,
            fee_id=fee2.id,
            amount_cents=Decimal("2000.0000"),
        )

        items = repo.get_all(skip=0, limit=1)
        assert len(items) == 1

    def test_create_bulk(self, db_session, credit_note, fee, fee2):
        """Test bulk creation of credit note items."""
        repo = CreditNoteItemRepository(db_session)
        items = repo.create_bulk([
            {
                "credit_note_id": credit_note.id,
                "fee_id": fee.id,
                "amount_cents": Decimal("3000.0000"),
            },
            {
                "credit_note_id": credit_note.id,
                "fee_id": fee2.id,
                "amount_cents": Decimal("2000.0000"),
            },
        ])

        assert len(items) == 2
        assert items[0].amount_cents == Decimal("3000.0000")
        assert items[1].amount_cents == Decimal("2000.0000")

    def test_delete_item(self, db_session, credit_note, fee):
        """Test deleting a credit note item."""
        repo = CreditNoteItemRepository(db_session)
        item = repo.create(
            credit_note_id=credit_note.id,
            fee_id=fee.id,
            amount_cents=Decimal("1000.0000"),
        )
        assert repo.delete(item.id) is True
        assert repo.get_by_id(item.id) is None

    def test_delete_item_not_found(self, db_session):
        """Test deleting a non-existent credit note item."""
        repo = CreditNoteItemRepository(db_session)
        assert repo.delete(uuid4()) is False


class TestCreditNoteSchemas:
    """Tests for CreditNote Pydantic schemas."""

    def test_credit_note_create_valid(self):
        """Test valid CreditNoteCreate schema."""
        data = CreditNoteCreate(
            number="CN-VALID-001",
            invoice_id=uuid4(),
            customer_id=uuid4(),
            credit_note_type=CreditNoteType.CREDIT,
            reason=CreditNoteReason.DUPLICATED_CHARGE,
            description="Test credit note",
            credit_amount_cents=Decimal("5000.0000"),
            total_amount_cents=Decimal("5000.0000"),
            currency="USD",
        )
        assert data.number == "CN-VALID-001"
        assert data.credit_note_type == CreditNoteType.CREDIT
        assert data.reason == CreditNoteReason.DUPLICATED_CHARGE

    def test_credit_note_create_minimal(self):
        """Test minimal CreditNoteCreate schema."""
        data = CreditNoteCreate(
            number="CN-MIN",
            invoice_id=uuid4(),
            customer_id=uuid4(),
            credit_note_type=CreditNoteType.REFUND,
            reason=CreditNoteReason.OTHER,
            currency="EUR",
        )
        assert data.description is None
        assert data.credit_amount_cents == Decimal("0")
        assert data.refund_amount_cents == Decimal("0")
        assert data.items == []

    def test_credit_note_create_with_items(self):
        """Test CreditNoteCreate with items."""
        data = CreditNoteCreate(
            number="CN-ITEMS",
            invoice_id=uuid4(),
            customer_id=uuid4(),
            credit_note_type=CreditNoteType.CREDIT,
            reason=CreditNoteReason.ORDER_CHANGE,
            currency="USD",
            items=[
                CreditNoteItemCreate(
                    fee_id=uuid4(),
                    amount_cents=Decimal("3000"),
                ),
                CreditNoteItemCreate(
                    fee_id=uuid4(),
                    amount_cents=Decimal("2000"),
                ),
            ],
        )
        assert len(data.items) == 2

    def test_credit_note_create_invalid_currency_short(self):
        """Test CreditNoteCreate with invalid currency (too short)."""
        with pytest.raises(ValidationError):
            CreditNoteCreate(
                number="CN-BAD",
                invoice_id=uuid4(),
                customer_id=uuid4(),
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                currency="US",
            )

    def test_credit_note_create_invalid_currency_long(self):
        """Test CreditNoteCreate with invalid currency (too long)."""
        with pytest.raises(ValidationError):
            CreditNoteCreate(
                number="CN-BAD",
                invoice_id=uuid4(),
                customer_id=uuid4(),
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                currency="USDD",
            )

    def test_credit_note_create_number_too_long(self):
        """Test CreditNoteCreate with number exceeding max length."""
        with pytest.raises(ValidationError):
            CreditNoteCreate(
                number="X" * 51,
                invoice_id=uuid4(),
                customer_id=uuid4(),
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                currency="USD",
            )

    def test_credit_note_update_partial(self):
        """Test partial CreditNoteUpdate schema."""
        data = CreditNoteUpdate(description="New description")
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"description": "New description"}

    def test_credit_note_update_all_fields(self):
        """Test CreditNoteUpdate with all fields."""
        data = CreditNoteUpdate(
            description="Updated",
            credit_amount_cents=Decimal("1000"),
            refund_amount_cents=Decimal("500"),
            total_amount_cents=Decimal("1500"),
            taxes_amount_cents=Decimal("150"),
            reason=CreditNoteReason.ORDER_CANCELLATION,
            status=CreditNoteStatus.FINALIZED,
            credit_status=CreditStatus.AVAILABLE,
            refund_status=RefundStatus.PENDING,
        )
        assert data.reason == CreditNoteReason.ORDER_CANCELLATION
        assert data.status == CreditNoteStatus.FINALIZED
        assert data.credit_status == CreditStatus.AVAILABLE
        assert data.refund_status == RefundStatus.PENDING

    def test_credit_note_response(self, db_session, credit_note):
        """Test CreditNoteResponse from ORM model."""
        response = CreditNoteResponse.model_validate(credit_note)
        assert response.id == credit_note.id
        assert response.number == "CN-0001"
        assert response.credit_note_type == "credit"
        assert response.status == "draft"
        assert response.reason == "duplicated_charge"

    def test_credit_note_item_create_valid(self):
        """Test valid CreditNoteItemCreate schema."""
        data = CreditNoteItemCreate(
            fee_id=uuid4(),
            amount_cents=Decimal("5000.0000"),
        )
        assert data.amount_cents == Decimal("5000.0000")

    def test_credit_note_item_response(self, db_session, credit_note, fee):
        """Test CreditNoteItemResponse from ORM model."""
        item = CreditNoteItem(
            credit_note_id=credit_note.id,
            fee_id=fee.id,
            amount_cents=Decimal("2500.0000"),
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        response = CreditNoteItemResponse.model_validate(item)
        assert response.id == item.id
        assert response.credit_note_id == credit_note.id
        assert response.fee_id == fee.id
        assert response.amount_cents == Decimal("2500.0000")


class TestCreditNoteWithOffsetType:
    """Tests for offset-type credit notes."""

    def test_create_offset_credit_note(self, db_session, customer, invoice):
        """Test creating an offset-type credit note."""
        repo = CreditNoteRepository(db_session)
        cn = repo.create(
            CreditNoteCreate(
                number="CN-OFFSET-001",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.OFFSET,
                reason=CreditNoteReason.ORDER_CHANGE,
                credit_amount_cents=Decimal("2000.0000"),
                total_amount_cents=Decimal("2000.0000"),
                currency="USD",
            )
        )
        assert cn.credit_note_type == "offset"


class TestCreditNoteWithTaxes:
    """Tests for credit notes with taxes."""

    def test_create_credit_note_with_taxes(self, db_session, customer, invoice):
        """Test creating a credit note with tax amounts."""
        repo = CreditNoteRepository(db_session)
        cn = repo.create(
            CreditNoteCreate(
                number="CN-TAX-001",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.DUPLICATED_CHARGE,
                credit_amount_cents=Decimal("5000.0000"),
                taxes_amount_cents=Decimal("500.0000"),
                total_amount_cents=Decimal("5500.0000"),
                currency="USD",
            )
        )
        assert cn.taxes_amount_cents == Decimal("500.0000")
        assert cn.total_amount_cents == Decimal("5500.0000")


class TestCreditNoteWithMultipleReasons:
    """Tests for credit notes with various reason codes."""

    @pytest.mark.parametrize(
        "reason",
        [
            CreditNoteReason.DUPLICATED_CHARGE,
            CreditNoteReason.PRODUCT_UNSATISFACTORY,
            CreditNoteReason.ORDER_CHANGE,
            CreditNoteReason.ORDER_CANCELLATION,
            CreditNoteReason.FRAUDULENT_CHARGE,
            CreditNoteReason.OTHER,
        ],
    )
    def test_create_credit_note_with_each_reason(self, db_session, customer, invoice, reason):
        """Test creating credit notes with each valid reason."""
        repo = CreditNoteRepository(db_session)
        cn = repo.create(
            CreditNoteCreate(
                number=f"CN-REASON-{reason.value}",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=reason,
                credit_amount_cents=Decimal("1000.0000"),
                total_amount_cents=Decimal("1000.0000"),
                currency="USD",
            )
        )
        assert cn.reason == reason.value


class TestCreditNoteAPI:
    """Tests for CreditNote API endpoints."""

    def test_create_credit_note(self, client, db_session, customer, invoice):
        """Test POST /v1/credit_notes/ creates a credit note."""
        response = client.post("/v1/credit_notes/", json={
            "number": "CN-API-001",
            "invoice_id": str(invoice.id),
            "customer_id": str(customer.id),
            "credit_note_type": "credit",
            "reason": "duplicated_charge",
            "description": "API test credit note",
            "credit_amount_cents": "5000.0000",
            "total_amount_cents": "5000.0000",
            "currency": "USD",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["number"] == "CN-API-001"
        assert data["credit_note_type"] == "credit"
        assert data["status"] == "draft"
        assert data["reason"] == "duplicated_charge"

    def test_create_credit_note_with_items(self, client, db_session, customer, invoice, fee):
        """Test POST /v1/credit_notes/ with items."""
        response = client.post("/v1/credit_notes/", json={
            "number": "CN-API-ITEMS",
            "invoice_id": str(invoice.id),
            "customer_id": str(customer.id),
            "credit_note_type": "credit",
            "reason": "order_change",
            "credit_amount_cents": "3000.0000",
            "total_amount_cents": "3000.0000",
            "currency": "USD",
            "items": [
                {
                    "fee_id": str(fee.id),
                    "amount_cents": "3000.0000",
                }
            ],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["number"] == "CN-API-ITEMS"

    def test_create_credit_note_duplicate_number(self, client, db_session, customer, invoice):
        """Test POST /v1/credit_notes/ returns 409 for duplicate number."""
        client.post("/v1/credit_notes/", json={
            "number": "CN-DUP",
            "invoice_id": str(invoice.id),
            "customer_id": str(customer.id),
            "credit_note_type": "credit",
            "reason": "other",
            "credit_amount_cents": "1000",
            "total_amount_cents": "1000",
            "currency": "USD",
        })
        response = client.post("/v1/credit_notes/", json={
            "number": "CN-DUP",
            "invoice_id": str(invoice.id),
            "customer_id": str(customer.id),
            "credit_note_type": "credit",
            "reason": "other",
            "credit_amount_cents": "2000",
            "total_amount_cents": "2000",
            "currency": "USD",
        })
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_list_credit_notes(self, client, db_session, credit_note, refund_note):
        """Test GET /v1/credit_notes/ lists credit notes."""
        response = client.get("/v1/credit_notes/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_credit_notes_empty(self, client):
        """Test GET /v1/credit_notes/ returns empty list."""
        response = client.get("/v1/credit_notes/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_credit_notes_filter_by_customer(self, client, db_session, credit_note, customer):
        """Test GET /v1/credit_notes/ filtered by customer_id."""
        response = client.get(f"/v1/credit_notes/?customer_id={customer.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_list_credit_notes_filter_by_invoice(self, client, db_session, credit_note, invoice):
        """Test GET /v1/credit_notes/ filtered by invoice_id."""
        response = client.get(f"/v1/credit_notes/?invoice_id={invoice.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_list_credit_notes_filter_by_status(self, client, db_session, credit_note):
        """Test GET /v1/credit_notes/ filtered by status."""
        response = client.get("/v1/credit_notes/?status=draft")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_list_credit_notes_pagination(self, client, db_session, customer, invoice):
        """Test GET /v1/credit_notes/ with pagination."""
        repo = CreditNoteRepository(db_session)
        for i in range(5):
            repo.create(CreditNoteCreate(
                number=f"CN-PAG-{i}",
                invoice_id=invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                credit_amount_cents=Decimal("1000"),
                total_amount_cents=Decimal("1000"),
                currency="USD",
            ))
        response = client.get("/v1/credit_notes/?skip=2&limit=2")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_credit_note(self, client, db_session, credit_note):
        """Test GET /v1/credit_notes/{id} returns credit note."""
        response = client.get(f"/v1/credit_notes/{credit_note.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(credit_note.id)
        assert data["number"] == "CN-0001"

    def test_get_credit_note_not_found(self, client):
        """Test GET /v1/credit_notes/{id} returns 404."""
        response = client.get(f"/v1/credit_notes/{uuid4()}")
        assert response.status_code == 404

    def test_update_credit_note(self, client, db_session, credit_note):
        """Test PUT /v1/credit_notes/{id} updates a draft credit note."""
        response = client.put(f"/v1/credit_notes/{credit_note.id}", json={
            "description": "Updated description",
            "credit_amount_cents": "6000.0000",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["credit_amount_cents"] == "6000.0000"

    def test_update_credit_note_not_found(self, client):
        """Test PUT /v1/credit_notes/{id} returns 404."""
        response = client.put(f"/v1/credit_notes/{uuid4()}", json={
            "description": "Nope",
        })
        assert response.status_code == 404

    def test_update_credit_note_not_draft(self, client, db_session, credit_note):
        """Test PUT /v1/credit_notes/{id} returns 400 for finalized note."""
        repo = CreditNoteRepository(db_session)
        repo.finalize(credit_note.id)

        response = client.put(f"/v1/credit_notes/{credit_note.id}", json={
            "description": "Should fail",
        })
        assert response.status_code == 400
        assert "draft" in response.json()["detail"].lower()

    def test_finalize_credit_note(self, client, db_session, credit_note):
        """Test POST /v1/credit_notes/{id}/finalize finalizes credit note."""
        response = client.post(f"/v1/credit_notes/{credit_note.id}/finalize")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "finalized"
        assert data["credit_status"] == "available"
        assert data["issued_at"] is not None

    def test_finalize_credit_note_not_found(self, client):
        """Test POST /v1/credit_notes/{id}/finalize returns 404."""
        response = client.post(f"/v1/credit_notes/{uuid4()}/finalize")
        assert response.status_code == 404

    def test_finalize_credit_note_already_finalized(self, client, db_session, credit_note):
        """Test POST /v1/credit_notes/{id}/finalize returns 400 for already finalized."""
        repo = CreditNoteRepository(db_session)
        repo.finalize(credit_note.id)

        response = client.post(f"/v1/credit_notes/{credit_note.id}/finalize")
        assert response.status_code == 400
        assert "draft" in response.json()["detail"].lower()

    def test_void_credit_note(self, client, db_session, credit_note):
        """Test POST /v1/credit_notes/{id}/void voids credit note."""
        repo = CreditNoteRepository(db_session)
        repo.finalize(credit_note.id)

        response = client.post(f"/v1/credit_notes/{credit_note.id}/void")
        assert response.status_code == 200
        data = response.json()
        assert data["credit_status"] == "voided"
        assert data["voided_at"] is not None

    def test_void_credit_note_not_found(self, client):
        """Test POST /v1/credit_notes/{id}/void returns 404."""
        response = client.post(f"/v1/credit_notes/{uuid4()}/void")
        assert response.status_code == 404

    def test_void_credit_note_not_finalized(self, client, db_session, credit_note):
        """Test POST /v1/credit_notes/{id}/void returns 400 for draft note."""
        response = client.post(f"/v1/credit_notes/{credit_note.id}/void")
        assert response.status_code == 400
        assert "finalized" in response.json()["detail"].lower()
