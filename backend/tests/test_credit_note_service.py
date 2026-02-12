"""Tests for CreditNoteService business logic."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import Base, engine, get_db
from app.models.credit_note import CreditNoteStatus, CreditStatus
from app.models.fee import FeeType
from app.repositories.credit_note_repository import CreditNoteRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.credit_note import CreditNoteItemCreate
from app.schemas.customer import CustomerCreate
from app.schemas.fee import FeeCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
from app.services.credit_note_service import CreditNoteService


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
            external_id=f"cn_svc_test_{uuid4()}",
            name="CreditNote Service Test Customer",
            email="creditnoteservice@test.com",
        )
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(code=f"cn_svc_plan_{uuid4()}", name="CN Service Test Plan", interval="monthly")
    )


@pytest.fixture
def subscription(db_session, customer, plan):
    """Create a test subscription."""
    repo = SubscriptionRepository(db_session)
    return repo.create(
        SubscriptionCreate(
            external_id=f"cn_svc_sub_{uuid4()}",
            customer_id=customer.id,
            plan_id=plan.id,
        )
    )


@pytest.fixture
def finalized_invoice(db_session, customer, subscription):
    """Create a finalized invoice with fees."""
    from datetime import datetime

    invoice_repo = InvoiceRepository(db_session)
    invoice = invoice_repo.create(
        InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(),
            billing_period_end=datetime.now(),
            line_items=[
                InvoiceLineItem(
                    description="Test line item",
                    quantity=Decimal("1"),
                    unit_price=Decimal("10000.0000"),
                    amount=Decimal("10000.0000"),
                )
            ],
        )
    )
    # Finalize the invoice
    invoice_repo.finalize(invoice.id)
    db_session.refresh(invoice)
    return invoice


@pytest.fixture
def invoice_fees(db_session, finalized_invoice, customer):
    """Create fees for the finalized invoice."""
    fee_repo = FeeRepository(db_session)
    fee1 = fee_repo.create(
        FeeCreate(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            fee_type=FeeType.CHARGE,
            amount_cents=Decimal("5000.0000"),
            total_amount_cents=Decimal("5000.0000"),
            units=Decimal("1"),
            unit_amount_cents=Decimal("5000.0000"),
            description="Fee 1",
        )
    )
    fee2 = fee_repo.create(
        FeeCreate(
            invoice_id=finalized_invoice.id,
            customer_id=customer.id,
            fee_type=FeeType.CHARGE,
            amount_cents=Decimal("5000.0000"),
            total_amount_cents=Decimal("5000.0000"),
            units=Decimal("1"),
            unit_amount_cents=Decimal("5000.0000"),
            description="Fee 2",
        )
    )
    return [fee1, fee2]


@pytest.fixture
def credit_note_service(db_session):
    """Create a CreditNoteService instance."""
    return CreditNoteService(db_session)


@pytest.fixture
def credit_note_repo(db_session):
    """Create a CreditNoteRepository instance."""
    return CreditNoteRepository(db_session)


class TestCreateCreditNote:
    """Tests for CreditNoteService.create_credit_note()."""

    def test_create_credit_note_basic(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test creating a basic credit note for a finalized invoice."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("3000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        assert cn.invoice_id == finalized_invoice.id
        assert cn.credit_amount_cents == Decimal("3000.0000")
        assert cn.total_amount_cents == Decimal("3000.0000")
        assert cn.status == CreditNoteStatus.DRAFT.value
        assert cn.number.startswith("CN-")

    def test_create_credit_note_multiple_items(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test creating a credit note with multiple items."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("2000.0000"),
            ),
            CreditNoteItemCreate(
                fee_id=invoice_fees[1].id,
                amount_cents=Decimal("1500.0000"),
            ),
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="duplicated_charge",
            description="Duplicate charge adjustment",
        )
        assert cn.total_amount_cents == Decimal("3500.0000")
        assert cn.credit_amount_cents == Decimal("3500.0000")
        assert cn.description == "Duplicate charge adjustment"

    def test_create_credit_note_with_reason_codes(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test creating credit notes with different reason codes."""
        reasons = [
            "duplicated_charge",
            "product_unsatisfactory",
            "order_change",
            "order_cancellation",
            "fraudulent_charge",
            "other",
        ]
        for reason in reasons:
            items = [
                CreditNoteItemCreate(
                    fee_id=invoice_fees[0].id,
                    amount_cents=Decimal("100.0000"),
                )
            ]
            cn = credit_note_service.create_credit_note(
                invoice_id=finalized_invoice.id,
                items=items,
                reason=reason,
            )
            assert cn.reason == reason

    def test_create_credit_note_with_types(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test creating credit notes with different types."""
        for cn_type in ["credit", "refund", "offset"]:
            items = [
                CreditNoteItemCreate(
                    fee_id=invoice_fees[0].id,
                    amount_cents=Decimal("100.0000"),
                )
            ]
            cn = credit_note_service.create_credit_note(
                invoice_id=finalized_invoice.id,
                items=items,
                reason="other",
                credit_note_type=cn_type,
            )
            assert cn.credit_note_type == cn_type

    def test_create_credit_note_invoice_not_found(self, credit_note_service):
        """Test creating a credit note for a non-existent invoice."""
        items = [
            CreditNoteItemCreate(fee_id=uuid4(), amount_cents=Decimal("100.0000"))
        ]
        with pytest.raises(ValueError, match="not found"):
            credit_note_service.create_credit_note(
                invoice_id=uuid4(),
                items=items,
                reason="other",
            )

    def test_create_credit_note_invoice_not_finalized(
        self, credit_note_service, db_session, customer, subscription
    ):
        """Test creating a credit note for a draft invoice raises ValueError."""
        from datetime import datetime

        invoice_repo = InvoiceRepository(db_session)
        draft_invoice = invoice_repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(),
                billing_period_end=datetime.now(),
            )
        )
        items = [
            CreditNoteItemCreate(fee_id=uuid4(), amount_cents=Decimal("100.0000"))
        ]
        with pytest.raises(ValueError, match="finalized"):
            credit_note_service.create_credit_note(
                invoice_id=draft_invoice.id,
                items=items,
                reason="other",
            )

    def test_create_credit_note_empty_items(
        self, credit_note_service, finalized_invoice
    ):
        """Test creating a credit note with no items raises ValueError."""
        with pytest.raises(ValueError, match="at least one item"):
            credit_note_service.create_credit_note(
                invoice_id=finalized_invoice.id,
                items=[],
                reason="other",
            )

    def test_create_credit_note_fee_not_on_invoice(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test creating a credit note with a fee not belonging to the invoice."""
        items = [
            CreditNoteItemCreate(
                fee_id=uuid4(),
                amount_cents=Decimal("100.0000"),
            )
        ]
        with pytest.raises(ValueError, match="does not belong"):
            credit_note_service.create_credit_note(
                invoice_id=finalized_invoice.id,
                items=items,
                reason="other",
            )

    def test_create_credit_note_unique_numbers(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test that multiple credit notes get unique numbers."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("100.0000"),
            )
        ]
        cn1 = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        cn2 = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        assert cn1.number != cn2.number


class TestFinalizeCreditNote:
    """Tests for CreditNoteService.finalize_credit_note()."""

    def test_finalize_credit_note(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test finalizing a draft credit note."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("3000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        finalized = credit_note_service.finalize_credit_note(cn.id)
        assert finalized.status == CreditNoteStatus.FINALIZED.value
        assert finalized.issued_at is not None
        assert finalized.balance_amount_cents == Decimal("3000.0000")
        assert finalized.credit_status == CreditStatus.AVAILABLE.value

    def test_finalize_credit_note_not_found(self, credit_note_service):
        """Test finalizing a non-existent credit note raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            credit_note_service.finalize_credit_note(uuid4())

    def test_finalize_already_finalized(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test finalizing an already finalized credit note raises ValueError."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("1000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        credit_note_service.finalize_credit_note(cn.id)
        with pytest.raises(ValueError, match="draft"):
            credit_note_service.finalize_credit_note(cn.id)


class TestVoidCreditNote:
    """Tests for CreditNoteService.void_credit_note()."""

    def test_void_credit_note(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test voiding a finalized credit note."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("2000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        credit_note_service.finalize_credit_note(cn.id)
        voided = credit_note_service.void_credit_note(cn.id)
        assert voided.credit_status == CreditStatus.VOIDED.value
        assert voided.voided_at is not None
        assert voided.balance_amount_cents == Decimal("0")

    def test_void_credit_note_not_found(self, credit_note_service):
        """Test voiding a non-existent credit note raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            credit_note_service.void_credit_note(uuid4())

    def test_void_draft_credit_note(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test voiding a draft credit note raises ValueError."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("1000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        with pytest.raises(ValueError, match="finalized"):
            credit_note_service.void_credit_note(cn.id)


class TestApplyCreditToInvoice:
    """Tests for CreditNoteService.apply_credit_to_invoice()."""

    def test_apply_credit_to_invoice(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test applying credit from a finalized credit note to an invoice."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("5000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        credit_note_service.finalize_credit_note(cn.id)

        updated = credit_note_service.apply_credit_to_invoice(
            credit_note_id=cn.id,
            invoice_id=finalized_invoice.id,
            amount=Decimal("2000.0000"),
        )
        assert updated.balance_amount_cents == Decimal("3000.0000")
        assert updated.credit_status == CreditStatus.AVAILABLE.value

    def test_apply_credit_fully_consumed(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test applying full credit consumes the credit note."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("3000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        credit_note_service.finalize_credit_note(cn.id)

        updated = credit_note_service.apply_credit_to_invoice(
            credit_note_id=cn.id,
            invoice_id=finalized_invoice.id,
            amount=Decimal("3000.0000"),
        )
        assert updated.balance_amount_cents == Decimal("0")
        assert updated.credit_status == CreditStatus.CONSUMED.value

    def test_apply_credit_exceeds_balance(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test applying more credit than available raises ValueError."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("2000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        credit_note_service.finalize_credit_note(cn.id)

        with pytest.raises(ValueError, match="exceeds"):
            credit_note_service.apply_credit_to_invoice(
                credit_note_id=cn.id,
                invoice_id=finalized_invoice.id,
                amount=Decimal("3000.0000"),
            )

    def test_apply_credit_negative_amount(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test applying negative credit raises ValueError."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("2000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        credit_note_service.finalize_credit_note(cn.id)

        with pytest.raises(ValueError, match="positive"):
            credit_note_service.apply_credit_to_invoice(
                credit_note_id=cn.id,
                invoice_id=finalized_invoice.id,
                amount=Decimal("-100"),
            )

    def test_apply_credit_zero_amount(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test applying zero credit raises ValueError."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("2000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        credit_note_service.finalize_credit_note(cn.id)

        with pytest.raises(ValueError, match="positive"):
            credit_note_service.apply_credit_to_invoice(
                credit_note_id=cn.id,
                invoice_id=finalized_invoice.id,
                amount=Decimal("0"),
            )

    def test_apply_credit_not_found(self, credit_note_service, finalized_invoice):
        """Test applying credit from a non-existent credit note raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            credit_note_service.apply_credit_to_invoice(
                credit_note_id=uuid4(),
                invoice_id=finalized_invoice.id,
                amount=Decimal("100"),
            )

    def test_apply_credit_invoice_not_found(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test applying credit to a non-existent invoice raises ValueError."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("2000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        credit_note_service.finalize_credit_note(cn.id)

        with pytest.raises(ValueError, match="not found"):
            credit_note_service.apply_credit_to_invoice(
                credit_note_id=cn.id,
                invoice_id=uuid4(),
                amount=Decimal("100"),
            )

    def test_apply_credit_draft_credit_note(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test applying credit from a draft credit note raises ValueError."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("2000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        with pytest.raises(ValueError, match="finalized"):
            credit_note_service.apply_credit_to_invoice(
                credit_note_id=cn.id,
                invoice_id=finalized_invoice.id,
                amount=Decimal("100"),
            )

    def test_apply_credit_voided_credit_note(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test applying credit from a voided credit note raises ValueError."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("2000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        credit_note_service.finalize_credit_note(cn.id)
        credit_note_service.void_credit_note(cn.id)

        with pytest.raises(ValueError, match="no available credit"):
            credit_note_service.apply_credit_to_invoice(
                credit_note_id=cn.id,
                invoice_id=finalized_invoice.id,
                amount=Decimal("100"),
            )

    def test_apply_credit_partial_then_remaining(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test applying credit in multiple partial amounts."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("5000.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        credit_note_service.finalize_credit_note(cn.id)

        # First partial application
        updated = credit_note_service.apply_credit_to_invoice(
            credit_note_id=cn.id,
            invoice_id=finalized_invoice.id,
            amount=Decimal("2000.0000"),
        )
        assert updated.balance_amount_cents == Decimal("3000.0000")
        assert updated.credit_status == CreditStatus.AVAILABLE.value

        # Second partial application consuming remaining
        updated = credit_note_service.apply_credit_to_invoice(
            credit_note_id=cn.id,
            invoice_id=finalized_invoice.id,
            amount=Decimal("3000.0000"),
        )
        assert updated.balance_amount_cents == Decimal("0")
        assert updated.credit_status == CreditStatus.CONSUMED.value


class TestGenerateCreditNoteNumber:
    """Tests for CreditNoteService._generate_credit_note_number()."""

    def test_generate_number_format(self, credit_note_service):
        """Test the generated number has correct format."""
        number = credit_note_service._generate_credit_note_number()
        assert number.startswith("CN-")
        parts = number.split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 4  # 0001

    def test_generate_sequential_numbers(
        self, credit_note_service, finalized_invoice, invoice_fees
    ):
        """Test that sequential credit notes get incrementing numbers."""
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("100.0000"),
            )
        ]
        cn1 = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        cn2 = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        # Extract the sequence numbers
        num1 = int(str(cn1.number).split("-")[-1])
        num2 = int(str(cn2.number).split("-")[-1])
        assert num2 == num1 + 1

    def test_generate_number_ignores_different_prefix(
        self, credit_note_service, credit_note_repo, finalized_invoice, invoice_fees, customer
    ):
        """Test number generation ignores credit notes with different date prefixes."""
        from app.models.credit_note import CreditNoteReason, CreditNoteType
        from app.schemas.credit_note import CreditNoteCreate as CNCreate

        # Create a credit note with a different date prefix
        credit_note_repo.create(
            CNCreate(
                number="CN-19700101-0005",
                invoice_id=finalized_invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                credit_amount_cents=Decimal("100"),
                total_amount_cents=Decimal("100"),
                currency="USD",
            )
        )

        # Generate number — should start at 0001 since existing has different prefix
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("100.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        assert str(cn.number).endswith("-0001")

    def test_generate_number_skips_lower_sequence(
        self, credit_note_service, credit_note_repo, finalized_invoice, invoice_fees, customer
    ):
        """Test number generation finds max among multiple existing numbers."""
        from datetime import datetime as dt

        from app.models.credit_note import CreditNoteReason, CreditNoteType
        from app.schemas.credit_note import CreditNoteCreate as CNCreate

        today = dt.now().strftime("%Y%m%d")

        # Create two credit notes with today's prefix — one higher, one lower
        credit_note_repo.create(
            CNCreate(
                number=f"CN-{today}-0003",
                invoice_id=finalized_invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                credit_amount_cents=Decimal("100"),
                total_amount_cents=Decimal("100"),
                currency="USD",
            )
        )
        credit_note_repo.create(
            CNCreate(
                number=f"CN-{today}-0001",
                invoice_id=finalized_invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                credit_amount_cents=Decimal("100"),
                total_amount_cents=Decimal("100"),
                currency="USD",
            )
        )

        # Next number should be 0004, not 0002
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("100.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        assert str(cn.number) == f"CN-{today}-0004"

    def test_generate_number_handles_malformed_number(
        self, credit_note_service, credit_note_repo, finalized_invoice, invoice_fees, customer
    ):
        """Test number generation handles malformed existing credit note numbers."""
        from datetime import datetime as dt

        from app.models.credit_note import CreditNoteReason, CreditNoteType
        from app.schemas.credit_note import CreditNoteCreate as CNCreate

        today = dt.now().strftime("%Y%m%d")

        # Create a credit note with a malformed number (non-numeric suffix)
        credit_note_repo.create(
            CNCreate(
                number=f"CN-{today}-abcd",
                invoice_id=finalized_invoice.id,
                customer_id=customer.id,
                credit_note_type=CreditNoteType.CREDIT,
                reason=CreditNoteReason.OTHER,
                credit_amount_cents=Decimal("100"),
                total_amount_cents=Decimal("100"),
                currency="USD",
            )
        )

        # Generate number — should handle ValueError from int() parsing
        items = [
            CreditNoteItemCreate(
                fee_id=invoice_fees[0].id,
                amount_cents=Decimal("100.0000"),
            )
        ]
        cn = credit_note_service.create_credit_note(
            invoice_id=finalized_invoice.id,
            items=items,
            reason="other",
        )
        assert str(cn.number).endswith("-0001")
