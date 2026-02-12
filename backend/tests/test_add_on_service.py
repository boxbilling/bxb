"""Tests for AddOnService business logic."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import get_db
from app.models.fee import FeeType
from app.repositories.add_on_repository import AddOnRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.schemas.add_on import AddOnCreate
from app.schemas.customer import CustomerCreate
from app.services.add_on_service import AddOnService
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
            external_id=f"addon_svc_test_{uuid4()}",
            name="AddOnService Test Customer",
            email="addonservice@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def add_on_service(db_session):
    """Create an AddOnService instance."""
    return AddOnService(db_session)


@pytest.fixture
def add_on_repo(db_session):
    """Create an AddOnRepository instance."""
    return AddOnRepository(db_session)


@pytest.fixture
def fee_repo(db_session):
    """Create a FeeRepository instance."""
    return FeeRepository(db_session)


@pytest.fixture
def basic_add_on(add_on_repo):
    """Create a basic add-on ($50)."""
    return add_on_repo.create(
        AddOnCreate(
            code="SVC_ADDON_BASIC",
            name="Basic Add-On",
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def add_on_with_display_name(add_on_repo):
    """Create an add-on with a custom invoice display name."""
    return add_on_repo.create(
        AddOnCreate(
            code="SVC_ADDON_DISPLAY",
            name="Display Add-On",
            amount_cents=Decimal("2500.0000"),
            amount_currency="USD",
            invoice_display_name="Custom Display Name",
        ),
        DEFAULT_ORG_ID,
    )


class TestApplyAddOn:
    """Tests for AddOnService.apply_add_on()."""

    def test_apply_basic_add_on(self, add_on_service, basic_add_on, customer):
        """Test applying a basic add-on creates AppliedAddOn and Invoice."""
        applied, invoice = add_on_service.apply_add_on(
            add_on_code="SVC_ADDON_BASIC",
            customer_id=customer.id,
        )
        assert applied.add_on_id == basic_add_on.id
        assert applied.customer_id == customer.id
        assert applied.amount_cents == Decimal("5000.0000")
        assert applied.amount_currency == "USD"

        assert invoice.customer_id == customer.id
        assert invoice.total == Decimal("5000.0000")
        assert invoice.currency == "USD"

    def test_apply_add_on_creates_fee(self, add_on_service, basic_add_on, customer, fee_repo):
        """Test applying an add-on creates a Fee of type ADD_ON."""
        _, invoice = add_on_service.apply_add_on(
            add_on_code="SVC_ADDON_BASIC",
            customer_id=customer.id,
        )
        fees = fee_repo.get_by_invoice_id(invoice.id)
        assert len(fees) == 1
        assert fees[0].fee_type == FeeType.ADD_ON.value
        assert fees[0].amount_cents == Decimal("5000.0000")
        assert fees[0].total_amount_cents == Decimal("5000.0000")
        assert fees[0].units == Decimal("1")
        assert fees[0].description == "Basic Add-On"

    def test_apply_add_on_with_amount_override(self, add_on_service, basic_add_on, customer):
        """Test applying an add-on with an amount override."""
        applied, invoice = add_on_service.apply_add_on(
            add_on_code="SVC_ADDON_BASIC",
            customer_id=customer.id,
            amount_override=Decimal("7500.0000"),
        )
        assert applied.amount_cents == Decimal("7500.0000")
        assert invoice.total == Decimal("7500.0000")

    def test_apply_add_on_with_display_name(
        self, add_on_service, add_on_with_display_name, customer, fee_repo
    ):
        """Test that invoice_display_name is used in Fee description."""
        _, invoice = add_on_service.apply_add_on(
            add_on_code="SVC_ADDON_DISPLAY",
            customer_id=customer.id,
        )
        fees = fee_repo.get_by_invoice_id(invoice.id)
        assert len(fees) == 1
        assert fees[0].description == "Custom Display Name"

    def test_apply_add_on_not_found(self, add_on_service, customer):
        """Test applying a non-existent add-on raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            add_on_service.apply_add_on(
                add_on_code="NONEXISTENT",
                customer_id=customer.id,
            )

    def test_apply_add_on_customer_not_found(self, add_on_service, basic_add_on):
        """Test applying an add-on to a non-existent customer raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            add_on_service.apply_add_on(
                add_on_code="SVC_ADDON_BASIC",
                customer_id=uuid4(),
            )

    def test_apply_add_on_invoice_has_no_subscription(self, add_on_service, basic_add_on, customer):
        """Test that one-off invoice has no subscription_id."""
        _, invoice = add_on_service.apply_add_on(
            add_on_code="SVC_ADDON_BASIC",
            customer_id=customer.id,
        )
        assert invoice.subscription_id is None

    def test_apply_add_on_multiple_times(self, add_on_service, basic_add_on, customer):
        """Test applying the same add-on multiple times creates separate records."""
        applied1, invoice1 = add_on_service.apply_add_on(
            add_on_code="SVC_ADDON_BASIC",
            customer_id=customer.id,
        )
        applied2, invoice2 = add_on_service.apply_add_on(
            add_on_code="SVC_ADDON_BASIC",
            customer_id=customer.id,
        )
        assert applied1.id != applied2.id
        assert invoice1.id != invoice2.id

    def test_apply_add_on_zero_override(self, add_on_service, basic_add_on, customer):
        """Test applying an add-on with zero amount override."""
        applied, invoice = add_on_service.apply_add_on(
            add_on_code="SVC_ADDON_BASIC",
            customer_id=customer.id,
            amount_override=Decimal("0"),
        )
        assert applied.amount_cents == Decimal("0")
        assert invoice.total == Decimal("0")

    def test_apply_add_on_invoice_line_items(self, add_on_service, basic_add_on, customer):
        """Test that the invoice has correct line items."""
        _, invoice = add_on_service.apply_add_on(
            add_on_code="SVC_ADDON_BASIC",
            customer_id=customer.id,
        )
        assert len(invoice.line_items) == 1
        line_item = invoice.line_items[0]
        assert line_item["description"] == "Basic Add-On"
        assert Decimal(str(line_item["amount"])) == Decimal("5000.0000")
