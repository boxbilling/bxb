"""Tests for AddOn and AppliedAddOn models, schemas, repositories, and CRUD operations."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.database import Base, engine, get_db
from app.models.add_on import AddOn
from app.models.applied_add_on import AppliedAddOn
from app.repositories.add_on_repository import AddOnRepository
from app.repositories.applied_add_on_repository import AppliedAddOnRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.add_on import (
    AddOnCreate,
    AddOnResponse,
    AddOnUpdate,
    AppliedAddOnResponse,
    ApplyAddOnRequest,
)
from app.schemas.customer import CustomerCreate


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
            external_id=f"addon_test_cust_{uuid4()}",
            name="AddOn Test Customer",
            email="addon@test.com",
        )
    )


@pytest.fixture
def customer2(db_session):
    """Create a second test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"addon_test_cust2_{uuid4()}",
            name="AddOn Test Customer 2",
        )
    )


@pytest.fixture
def basic_add_on(db_session):
    """Create a basic add-on."""
    repo = AddOnRepository(db_session)
    return repo.create(
        AddOnCreate(
            code="SETUP_FEE",
            name="Setup Fee",
            description="One-time setup fee",
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        )
    )


@pytest.fixture
def premium_add_on(db_session):
    """Create a premium add-on."""
    repo = AddOnRepository(db_session)
    return repo.create(
        AddOnCreate(
            code="PREMIUM_SUPPORT",
            name="Premium Support",
            description="Premium support add-on",
            amount_cents=Decimal("9999.0000"),
            amount_currency="USD",
            invoice_display_name="Premium Support Package",
        )
    )


class TestAddOnModel:
    """Tests for AddOn SQLAlchemy model."""

    def test_add_on_defaults(self, db_session):
        """Test AddOn model default values."""
        add_on = AddOn(
            code="TEST1",
            name="Test Add-On",
            amount_cents=Decimal("1000.0000"),
        )
        db_session.add(add_on)
        db_session.commit()
        db_session.refresh(add_on)

        assert add_on.id is not None
        assert add_on.code == "TEST1"
        assert add_on.name == "Test Add-On"
        assert add_on.description is None
        assert add_on.amount_cents == Decimal("1000.0000")
        assert add_on.amount_currency == "USD"
        assert add_on.invoice_display_name is None
        assert add_on.created_at is not None
        assert add_on.updated_at is not None

    def test_add_on_with_all_fields(self, db_session):
        """Test AddOn model with all fields populated."""
        add_on = AddOn(
            code="FULL",
            name="Full Add-On",
            description="A fully populated add-on",
            amount_cents=Decimal("2500.5000"),
            amount_currency="EUR",
            invoice_display_name="Custom Display Name",
        )
        db_session.add(add_on)
        db_session.commit()
        db_session.refresh(add_on)

        assert add_on.code == "FULL"
        assert add_on.name == "Full Add-On"
        assert add_on.description == "A fully populated add-on"
        assert add_on.amount_cents == Decimal("2500.5000")
        assert add_on.amount_currency == "EUR"
        assert add_on.invoice_display_name == "Custom Display Name"


class TestAppliedAddOnModel:
    """Tests for AppliedAddOn SQLAlchemy model."""

    def test_applied_add_on_creation(self, db_session, customer, basic_add_on):
        """Test AppliedAddOn model creation."""
        applied = AppliedAddOn(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        )
        db_session.add(applied)
        db_session.commit()
        db_session.refresh(applied)

        assert applied.id is not None
        assert applied.add_on_id == basic_add_on.id
        assert applied.customer_id == customer.id
        assert applied.amount_cents == Decimal("5000.0000")
        assert applied.amount_currency == "USD"
        assert applied.created_at is not None

    def test_applied_add_on_with_override_amount(self, db_session, customer, basic_add_on):
        """Test AppliedAddOn with override amount."""
        applied = AppliedAddOn(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("3000.0000"),
            amount_currency="EUR",
        )
        db_session.add(applied)
        db_session.commit()
        db_session.refresh(applied)

        assert applied.amount_cents == Decimal("3000.0000")
        assert applied.amount_currency == "EUR"


class TestAddOnRepository:
    """Tests for AddOnRepository CRUD and query methods."""

    def test_create_add_on(self, db_session):
        """Test creating an add-on."""
        repo = AddOnRepository(db_session)
        add_on = repo.create(
            AddOnCreate(
                code="NEW_FEE",
                name="New Fee",
                description="A new fee",
                amount_cents=Decimal("1500.0000"),
                amount_currency="USD",
            )
        )
        assert add_on.id is not None
        assert add_on.code == "NEW_FEE"
        assert add_on.name == "New Fee"
        assert add_on.description == "A new fee"
        assert add_on.amount_cents == Decimal("1500.0000")
        assert add_on.amount_currency == "USD"
        assert add_on.invoice_display_name is None

    def test_create_add_on_with_display_name(self, db_session):
        """Test creating an add-on with invoice display name."""
        repo = AddOnRepository(db_session)
        add_on = repo.create(
            AddOnCreate(
                code="DISPLAY",
                name="Display Test",
                amount_cents=Decimal("2000.0000"),
                invoice_display_name="Custom Invoice Line",
            )
        )
        assert add_on.invoice_display_name == "Custom Invoice Line"

    def test_create_add_on_with_non_usd_currency(self, db_session):
        """Test creating an add-on with non-USD currency."""
        repo = AddOnRepository(db_session)
        add_on = repo.create(
            AddOnCreate(
                code="EUR_FEE",
                name="Euro Fee",
                amount_cents=Decimal("1000.0000"),
                amount_currency="EUR",
            )
        )
        assert add_on.amount_currency == "EUR"

    def test_get_by_id(self, db_session, basic_add_on):
        """Test getting an add-on by ID."""
        repo = AddOnRepository(db_session)
        fetched = repo.get_by_id(basic_add_on.id)
        assert fetched is not None
        assert fetched.id == basic_add_on.id
        assert fetched.code == "SETUP_FEE"

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent add-on."""
        repo = AddOnRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_code(self, db_session, basic_add_on):
        """Test getting an add-on by code."""
        repo = AddOnRepository(db_session)
        fetched = repo.get_by_code("SETUP_FEE")
        assert fetched is not None
        assert fetched.code == "SETUP_FEE"
        assert fetched.id == basic_add_on.id

    def test_get_by_code_not_found(self, db_session):
        """Test getting a non-existent add-on by code."""
        repo = AddOnRepository(db_session)
        assert repo.get_by_code("NONEXISTENT") is None

    def test_get_all(self, db_session, basic_add_on, premium_add_on):
        """Test getting all add-ons."""
        repo = AddOnRepository(db_session)
        add_ons = repo.get_all()
        assert len(add_ons) == 2

    def test_get_all_pagination(self, db_session):
        """Test pagination for get_all."""
        repo = AddOnRepository(db_session)
        for i in range(5):
            repo.create(
                AddOnCreate(
                    code=f"PAGE{i}",
                    name=f"Page {i}",
                    amount_cents=Decimal("100.0000"),
                )
            )
        result = repo.get_all(skip=2, limit=2)
        assert len(result) == 2

    def test_get_all_empty(self, db_session):
        """Test getting all add-ons when none exist."""
        repo = AddOnRepository(db_session)
        assert repo.get_all() == []

    def test_update(self, db_session, basic_add_on):
        """Test updating an add-on."""
        repo = AddOnRepository(db_session)
        updated = repo.update("SETUP_FEE", AddOnUpdate(name="Updated Name"))
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.code == "SETUP_FEE"

    def test_update_amount(self, db_session, basic_add_on):
        """Test updating add-on amount."""
        repo = AddOnRepository(db_session)
        updated = repo.update(
            "SETUP_FEE",
            AddOnUpdate(amount_cents=Decimal("7500.0000"), amount_currency="EUR"),
        )
        assert updated is not None
        assert updated.amount_cents == Decimal("7500.0000")
        assert updated.amount_currency == "EUR"

    def test_update_description(self, db_session, basic_add_on):
        """Test updating add-on description."""
        repo = AddOnRepository(db_session)
        updated = repo.update("SETUP_FEE", AddOnUpdate(description="New description"))
        assert updated is not None
        assert updated.description == "New description"

    def test_update_invoice_display_name(self, db_session, basic_add_on):
        """Test updating add-on invoice display name."""
        repo = AddOnRepository(db_session)
        updated = repo.update("SETUP_FEE", AddOnUpdate(invoice_display_name="New Display"))
        assert updated is not None
        assert updated.invoice_display_name == "New Display"

    def test_update_not_found(self, db_session):
        """Test updating a non-existent add-on."""
        repo = AddOnRepository(db_session)
        assert repo.update("NONEXISTENT", AddOnUpdate(name="nope")) is None

    def test_delete(self, db_session, basic_add_on):
        """Test deleting an add-on."""
        repo = AddOnRepository(db_session)
        assert repo.delete("SETUP_FEE") is True
        assert repo.get_by_code("SETUP_FEE") is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent add-on."""
        repo = AddOnRepository(db_session)
        assert repo.delete("NONEXISTENT") is False


class TestAppliedAddOnRepository:
    """Tests for AppliedAddOnRepository CRUD and query methods."""

    def test_create_applied_add_on(self, db_session, customer, basic_add_on):
        """Test creating an applied add-on."""
        repo = AppliedAddOnRepository(db_session)
        applied = repo.create(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        )
        assert applied.id is not None
        assert applied.add_on_id == basic_add_on.id
        assert applied.customer_id == customer.id
        assert applied.amount_cents == Decimal("5000.0000")
        assert applied.amount_currency == "USD"
        assert applied.created_at is not None

    def test_create_applied_add_on_with_override(self, db_session, customer, basic_add_on):
        """Test creating an applied add-on with amount override."""
        repo = AppliedAddOnRepository(db_session)
        applied = repo.create(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("3000.0000"),
            amount_currency="EUR",
        )
        assert applied.amount_cents == Decimal("3000.0000")
        assert applied.amount_currency == "EUR"

    def test_get_by_id(self, db_session, customer, basic_add_on):
        """Test getting an applied add-on by ID."""
        repo = AppliedAddOnRepository(db_session)
        applied = repo.create(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        )
        fetched = repo.get_by_id(applied.id)
        assert fetched is not None
        assert fetched.id == applied.id

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent applied add-on."""
        repo = AppliedAddOnRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_customer_id(self, db_session, customer, basic_add_on, premium_add_on):
        """Test getting applied add-ons by customer ID."""
        repo = AppliedAddOnRepository(db_session)
        repo.create(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        )
        repo.create(
            add_on_id=premium_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("9999.0000"),
            amount_currency="USD",
        )
        results = repo.get_by_customer_id(customer.id)
        assert len(results) == 2

    def test_get_by_customer_id_empty(self, db_session, customer):
        """Test getting applied add-ons for customer with none."""
        repo = AppliedAddOnRepository(db_session)
        assert repo.get_by_customer_id(customer.id) == []

    def test_get_all(self, db_session, customer, customer2, basic_add_on, premium_add_on):
        """Test getting all applied add-ons."""
        repo = AppliedAddOnRepository(db_session)
        repo.create(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        )
        repo.create(
            add_on_id=premium_add_on.id,
            customer_id=customer2.id,
            amount_cents=Decimal("9999.0000"),
            amount_currency="USD",
        )

        all_applied = repo.get_all()
        assert len(all_applied) == 2

    def test_get_all_filter_by_customer(self, db_session, customer, customer2, basic_add_on, premium_add_on):
        """Test getting applied add-ons filtered by customer."""
        repo = AppliedAddOnRepository(db_session)
        repo.create(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        )
        repo.create(
            add_on_id=premium_add_on.id,
            customer_id=customer2.id,
            amount_cents=Decimal("9999.0000"),
            amount_currency="USD",
        )

        c1_applied = repo.get_all(customer_id=customer.id)
        assert len(c1_applied) == 1

        c2_applied = repo.get_all(customer_id=customer2.id)
        assert len(c2_applied) == 1

    def test_get_all_pagination(self, db_session, customer, basic_add_on):
        """Test pagination for get_all applied add-ons."""
        repo = AppliedAddOnRepository(db_session)
        add_on_repo = AddOnRepository(db_session)
        for i in range(5):
            a = add_on_repo.create(
                AddOnCreate(
                    code=f"PAG{i}",
                    name=f"Pag {i}",
                    amount_cents=Decimal("100.0000"),
                )
            )
            repo.create(
                add_on_id=a.id,
                customer_id=customer.id,
                amount_cents=Decimal("100.0000"),
                amount_currency="USD",
            )
        result = repo.get_all(skip=2, limit=2)
        assert len(result) == 2

    def test_multiple_applications_same_add_on(self, db_session, customer, basic_add_on):
        """Test applying the same add-on multiple times to the same customer."""
        repo = AppliedAddOnRepository(db_session)
        applied1 = repo.create(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        )
        applied2 = repo.create(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        )
        assert applied1.id != applied2.id
        results = repo.get_by_customer_id(customer.id)
        assert len(results) == 2


class TestAddOnSchema:
    """Tests for AddOn Pydantic schemas."""

    def test_add_on_create_basic(self):
        """Test AddOnCreate with required fields."""
        schema = AddOnCreate(
            code="FEE1",
            name="Fee One",
            amount_cents=Decimal("1000.0000"),
        )
        assert schema.code == "FEE1"
        assert schema.name == "Fee One"
        assert schema.amount_cents == Decimal("1000.0000")
        assert schema.amount_currency == "USD"
        assert schema.description is None
        assert schema.invoice_display_name is None

    def test_add_on_create_full(self):
        """Test AddOnCreate with all fields."""
        schema = AddOnCreate(
            code="FEE2",
            name="Fee Two",
            description="A complete add-on",
            amount_cents=Decimal("2500.5000"),
            amount_currency="EUR",
            invoice_display_name="Custom Line",
        )
        assert schema.description == "A complete add-on"
        assert schema.amount_currency == "EUR"
        assert schema.invoice_display_name == "Custom Line"

    def test_add_on_create_code_max_length(self):
        """Test AddOnCreate code max length."""
        with pytest.raises(ValidationError):
            AddOnCreate(
                code="A" * 256,
                name="Too long",
                amount_cents=Decimal("100"),
            )

    def test_add_on_create_name_max_length(self):
        """Test AddOnCreate name max length."""
        with pytest.raises(ValidationError):
            AddOnCreate(
                code="OK",
                name="A" * 256,
                amount_cents=Decimal("100"),
            )

    def test_add_on_create_invalid_currency_length(self):
        """Test AddOnCreate with invalid currency."""
        with pytest.raises(ValidationError):
            AddOnCreate(
                code="BAD",
                name="Bad",
                amount_cents=Decimal("100"),
                amount_currency="US",
            )

    def test_add_on_create_invalid_currency_too_long(self):
        """Test AddOnCreate with currency too long."""
        with pytest.raises(ValidationError):
            AddOnCreate(
                code="BAD2",
                name="Bad2",
                amount_cents=Decimal("100"),
                amount_currency="ABCD",
            )

    def test_add_on_create_invoice_display_name_max_length(self):
        """Test AddOnCreate invoice_display_name max length."""
        with pytest.raises(ValidationError):
            AddOnCreate(
                code="MAX",
                name="Max",
                amount_cents=Decimal("100"),
                invoice_display_name="A" * 256,
            )

    def test_add_on_update_partial(self):
        """Test AddOnUpdate partial update."""
        schema = AddOnUpdate(name="New Name")
        dumped = schema.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "description" not in dumped
        assert "amount_cents" not in dumped

    def test_add_on_update_multiple_fields(self):
        """Test AddOnUpdate with multiple fields."""
        schema = AddOnUpdate(
            name="Updated",
            amount_cents=Decimal("999.0000"),
            description="Updated desc",
        )
        dumped = schema.model_dump(exclude_unset=True)
        assert dumped["name"] == "Updated"
        assert dumped["amount_cents"] == Decimal("999.0000")
        assert dumped["description"] == "Updated desc"

    def test_add_on_update_invalid_currency(self):
        """Test AddOnUpdate with invalid currency."""
        with pytest.raises(ValidationError):
            AddOnUpdate(amount_currency="US")

    def test_add_on_update_invoice_display_name_max_length(self):
        """Test AddOnUpdate invoice_display_name max length."""
        with pytest.raises(ValidationError):
            AddOnUpdate(invoice_display_name="A" * 256)

    def test_add_on_response_from_attributes(self, db_session):
        """Test AddOnResponse can serialize from ORM object."""
        add_on = AddOn(
            code="RESP",
            name="Response Test",
            amount_cents=Decimal("1000.0000"),
            amount_currency="USD",
        )
        db_session.add(add_on)
        db_session.commit()
        db_session.refresh(add_on)

        response = AddOnResponse.model_validate(add_on)
        assert response.code == "RESP"
        assert response.name == "Response Test"
        assert response.amount_cents == Decimal("1000.0000")
        assert response.amount_currency == "USD"
        assert response.invoice_display_name is None

    def test_add_on_response_with_display_name(self, db_session):
        """Test AddOnResponse with invoice_display_name."""
        add_on = AddOn(
            code="DISP",
            name="Display Test",
            amount_cents=Decimal("2000.0000"),
            amount_currency="EUR",
            invoice_display_name="Custom Display",
        )
        db_session.add(add_on)
        db_session.commit()
        db_session.refresh(add_on)

        response = AddOnResponse.model_validate(add_on)
        assert response.invoice_display_name == "Custom Display"
        assert response.amount_currency == "EUR"

    def test_apply_add_on_request(self):
        """Test ApplyAddOnRequest schema."""
        cid = uuid4()
        schema = ApplyAddOnRequest(
            add_on_code="SETUP_FEE",
            customer_id=cid,
        )
        assert schema.add_on_code == "SETUP_FEE"
        assert schema.customer_id == cid
        assert schema.amount_cents is None
        assert schema.amount_currency is None

    def test_apply_add_on_request_with_overrides(self):
        """Test ApplyAddOnRequest with amount override."""
        cid = uuid4()
        schema = ApplyAddOnRequest(
            add_on_code="SETUP_FEE",
            customer_id=cid,
            amount_cents=Decimal("3000.0000"),
            amount_currency="EUR",
        )
        assert schema.amount_cents == Decimal("3000.0000")
        assert schema.amount_currency == "EUR"

    def test_apply_add_on_request_invalid_currency(self):
        """Test ApplyAddOnRequest with invalid currency."""
        with pytest.raises(ValidationError):
            ApplyAddOnRequest(
                add_on_code="X",
                customer_id=uuid4(),
                amount_currency="ABCD",
            )

    def test_applied_add_on_response_from_attributes(self, db_session, customer, basic_add_on):
        """Test AppliedAddOnResponse can serialize from ORM object."""
        applied = AppliedAddOn(
            add_on_id=basic_add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("5000.0000"),
            amount_currency="USD",
        )
        db_session.add(applied)
        db_session.commit()
        db_session.refresh(applied)

        response = AppliedAddOnResponse.model_validate(applied)
        assert response.add_on_id == basic_add_on.id
        assert response.customer_id == customer.id
        assert response.amount_cents == Decimal("5000.0000")
        assert response.amount_currency == "USD"
