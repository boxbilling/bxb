"""Tests for Tax and AppliedTax models, schemas, repositories."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.database import get_db
from app.models.applied_tax import AppliedTax
from app.models.tax import Tax
from app.repositories.applied_tax_repository import AppliedTaxRepository
from app.repositories.tax_repository import TaxRepository
from app.schemas.tax import (
    AppliedTaxResponse,
    ApplyTaxRequest,
    TaxCreate,
    TaxResponse,
    TaxUpdate,
)
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
def basic_tax(db_session):
    """Create a basic tax."""
    repo = TaxRepository(db_session)
    return repo.create(
        TaxCreate(
            code="VAT_20",
            name="VAT 20%",
            rate=Decimal("0.2000"),
            description="Standard VAT rate",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def org_tax(db_session):
    """Create an organization-default tax."""
    repo = TaxRepository(db_session)
    return repo.create(
        TaxCreate(
            code="SALES_TAX",
            name="Sales Tax",
            rate=Decimal("0.0800"),
            applied_to_organization=True,
        ),
        DEFAULT_ORG_ID,
    )


class TestTaxModel:
    """Tests for Tax SQLAlchemy model."""

    def test_tax_defaults(self, db_session):
        """Test Tax model default values."""
        tax = Tax(
            code="TEST_TAX",
            name="Test Tax",
            rate=Decimal("0.1000"),
        )
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        assert tax.id is not None
        assert tax.code == "TEST_TAX"
        assert tax.name == "Test Tax"
        assert tax.rate == Decimal("0.1000")
        assert tax.description is None
        assert tax.applied_to_organization is False
        assert tax.created_at is not None
        assert tax.updated_at is not None

    def test_tax_with_all_fields(self, db_session):
        """Test Tax model with all fields."""
        tax = Tax(
            code="FULL_TAX",
            name="Full Tax",
            rate=Decimal("0.2500"),
            description="A tax with all fields set",
            applied_to_organization=True,
        )
        db_session.add(tax)
        db_session.commit()
        db_session.refresh(tax)

        assert tax.code == "FULL_TAX"
        assert tax.description == "A tax with all fields set"
        assert tax.applied_to_organization is True


class TestAppliedTaxModel:
    """Tests for AppliedTax SQLAlchemy model."""

    def test_applied_tax_creation(self, db_session, basic_tax):
        """Test AppliedTax model creation."""
        taxable_id = uuid4()
        applied = AppliedTax(
            tax_id=basic_tax.id,
            taxable_type="customer",
            taxable_id=taxable_id,
            tax_rate=Decimal("0.2000"),
            tax_amount_cents=Decimal("500.0000"),
        )
        db_session.add(applied)
        db_session.commit()
        db_session.refresh(applied)

        assert applied.id is not None
        assert applied.tax_id == basic_tax.id
        assert applied.taxable_type == "customer"
        assert applied.taxable_id == taxable_id
        assert applied.tax_rate == Decimal("0.2000")
        assert applied.tax_amount_cents == Decimal("500.0000")
        assert applied.created_at is not None

    def test_applied_tax_defaults(self, db_session, basic_tax):
        """Test AppliedTax model default values."""
        applied = AppliedTax(
            tax_id=basic_tax.id,
            taxable_type="invoice",
            taxable_id=uuid4(),
        )
        db_session.add(applied)
        db_session.commit()
        db_session.refresh(applied)

        assert applied.tax_rate is None
        assert applied.tax_amount_cents == Decimal("0")


class TestTaxRepository:
    """Tests for TaxRepository."""

    def test_create_tax(self, db_session):
        """Test creating a tax."""
        repo = TaxRepository(db_session)
        tax = repo.create(
            TaxCreate(
                code="NEW_TAX",
                name="New Tax",
                rate=Decimal("0.1500"),
            ),
            DEFAULT_ORG_ID,
        )
        assert tax.id is not None
        assert tax.code == "NEW_TAX"
        assert tax.rate == Decimal("0.1500")

    def test_get_by_id(self, db_session, basic_tax):
        """Test getting a tax by ID."""
        repo = TaxRepository(db_session)
        tax = repo.get_by_id(basic_tax.id)
        assert tax is not None
        assert tax.code == "VAT_20"

    def test_get_by_id_with_org_filter(self, db_session, basic_tax):
        """Test getting a tax by ID scoped to an organization."""
        repo = TaxRepository(db_session)
        tax = repo.get_by_id(basic_tax.id, organization_id=DEFAULT_ORG_ID)
        assert tax is not None
        assert tax.code == "VAT_20"
        # Wrong org returns None
        assert repo.get_by_id(basic_tax.id, organization_id=uuid4()) is None

    def test_get_by_id_not_found(self, db_session):
        """Test getting a tax by non-existent ID."""
        repo = TaxRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_code(self, db_session, basic_tax):
        """Test getting a tax by code."""
        repo = TaxRepository(db_session)
        tax = repo.get_by_code("VAT_20", DEFAULT_ORG_ID)
        assert tax is not None
        assert tax.name == "VAT 20%"

    def test_get_by_code_not_found(self, db_session):
        """Test getting a tax by non-existent code."""
        repo = TaxRepository(db_session)
        assert repo.get_by_code("NONEXISTENT", DEFAULT_ORG_ID) is None

    def test_get_all(self, db_session, basic_tax, org_tax):
        """Test getting all taxes."""
        repo = TaxRepository(db_session)
        taxes = repo.get_all(DEFAULT_ORG_ID)
        assert len(taxes) == 2

    def test_get_all_pagination(self, db_session, basic_tax, org_tax):
        """Test get_all with pagination."""
        repo = TaxRepository(db_session)
        taxes = repo.get_all(DEFAULT_ORG_ID, skip=0, limit=1)
        assert len(taxes) == 1

    def test_get_all_empty(self, db_session):
        """Test get_all with no taxes."""
        repo = TaxRepository(db_session)
        assert repo.get_all(DEFAULT_ORG_ID) == []

    def test_get_organization_defaults(self, db_session, basic_tax, org_tax):
        """Test getting organization default taxes."""
        repo = TaxRepository(db_session)
        defaults = repo.get_organization_defaults(DEFAULT_ORG_ID)
        assert len(defaults) == 1
        assert defaults[0].code == "SALES_TAX"

    def test_get_organization_defaults_empty(self, db_session, basic_tax):
        """Test getting organization defaults when none exist."""
        repo = TaxRepository(db_session)
        defaults = repo.get_organization_defaults(DEFAULT_ORG_ID)
        assert defaults == []

    def test_update(self, db_session, basic_tax):
        """Test updating a tax."""
        repo = TaxRepository(db_session)
        updated = repo.update("VAT_20", TaxUpdate(name="VAT Updated"), DEFAULT_ORG_ID)
        assert updated is not None
        assert updated.name == "VAT Updated"
        assert updated.rate == Decimal("0.2000")  # unchanged

    def test_update_rate(self, db_session, basic_tax):
        """Test updating a tax rate."""
        repo = TaxRepository(db_session)
        updated = repo.update("VAT_20", TaxUpdate(rate=Decimal("0.2500")), DEFAULT_ORG_ID)
        assert updated is not None
        assert updated.rate == Decimal("0.2500")

    def test_update_applied_to_organization(self, db_session, basic_tax):
        """Test updating applied_to_organization flag."""
        repo = TaxRepository(db_session)
        updated = repo.update("VAT_20", TaxUpdate(applied_to_organization=True), DEFAULT_ORG_ID)
        assert updated is not None
        assert updated.applied_to_organization is True

    def test_update_not_found(self, db_session):
        """Test updating a non-existent tax."""
        repo = TaxRepository(db_session)
        assert repo.update("NONEXISTENT", TaxUpdate(name="X"), DEFAULT_ORG_ID) is None

    def test_delete(self, db_session, basic_tax):
        """Test deleting a tax."""
        repo = TaxRepository(db_session)
        assert repo.delete("VAT_20", DEFAULT_ORG_ID) is True
        assert repo.get_by_code("VAT_20", DEFAULT_ORG_ID) is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent tax."""
        repo = TaxRepository(db_session)
        assert repo.delete("NONEXISTENT", DEFAULT_ORG_ID) is False


class TestAppliedTaxRepository:
    """Tests for AppliedTaxRepository."""

    def test_create_applied_tax(self, db_session, basic_tax):
        """Test creating an applied tax."""
        repo = AppliedTaxRepository(db_session)
        taxable_id = uuid4()
        applied = repo.create(
            tax_id=basic_tax.id,
            taxable_type="customer",
            taxable_id=taxable_id,
            tax_rate=Decimal("0.2000"),
            tax_amount_cents=Decimal("100.0000"),
        )
        assert applied.id is not None
        assert applied.tax_id == basic_tax.id
        assert applied.taxable_type == "customer"
        assert applied.tax_rate == Decimal("0.2000")
        assert applied.tax_amount_cents == Decimal("100.0000")

    def test_create_applied_tax_defaults(self, db_session, basic_tax):
        """Test creating an applied tax with default values."""
        repo = AppliedTaxRepository(db_session)
        applied = repo.create(
            tax_id=basic_tax.id,
            taxable_type="plan",
            taxable_id=uuid4(),
        )
        assert applied.tax_rate is None
        assert applied.tax_amount_cents == Decimal("0")

    def test_get_by_id(self, db_session, basic_tax):
        """Test getting an applied tax by ID."""
        repo = AppliedTaxRepository(db_session)
        applied = repo.create(
            tax_id=basic_tax.id,
            taxable_type="fee",
            taxable_id=uuid4(),
        )
        found = repo.get_by_id(applied.id)
        assert found is not None
        assert found.id == applied.id

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent applied tax."""
        repo = AppliedTaxRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_taxable(self, db_session, basic_tax, org_tax):
        """Test getting applied taxes by taxable entity."""
        repo = AppliedTaxRepository(db_session)
        taxable_id = uuid4()
        repo.create(
            tax_id=basic_tax.id,
            taxable_type="invoice",
            taxable_id=taxable_id,
        )
        repo.create(
            tax_id=org_tax.id,
            taxable_type="invoice",
            taxable_id=taxable_id,
        )
        results = repo.get_by_taxable("invoice", taxable_id)
        assert len(results) == 2

    def test_get_by_taxable_empty(self, db_session):
        """Test getting applied taxes for entity with none."""
        repo = AppliedTaxRepository(db_session)
        assert repo.get_by_taxable("customer", uuid4()) == []

    def test_get_taxes_for_entity(self, db_session, basic_tax):
        """Test get_taxes_for_entity alias."""
        repo = AppliedTaxRepository(db_session)
        taxable_id = uuid4()
        repo.create(
            tax_id=basic_tax.id,
            taxable_type="charge",
            taxable_id=taxable_id,
        )
        results = repo.get_taxes_for_entity("charge", taxable_id)
        assert len(results) == 1

    def test_delete_by_taxable(self, db_session, basic_tax, org_tax):
        """Test deleting all applied taxes for an entity."""
        repo = AppliedTaxRepository(db_session)
        taxable_id = uuid4()
        repo.create(
            tax_id=basic_tax.id,
            taxable_type="fee",
            taxable_id=taxable_id,
        )
        repo.create(
            tax_id=org_tax.id,
            taxable_type="fee",
            taxable_id=taxable_id,
        )
        count = repo.delete_by_taxable("fee", taxable_id)
        assert count == 2
        assert repo.get_by_taxable("fee", taxable_id) == []

    def test_delete_by_taxable_none(self, db_session):
        """Test deleting applied taxes when none exist."""
        repo = AppliedTaxRepository(db_session)
        count = repo.delete_by_taxable("customer", uuid4())
        assert count == 0

    def test_delete_by_id(self, db_session, basic_tax):
        """Test deleting an applied tax by ID."""
        repo = AppliedTaxRepository(db_session)
        applied = repo.create(
            tax_id=basic_tax.id,
            taxable_type="plan",
            taxable_id=uuid4(),
        )
        assert repo.delete_by_id(applied.id) is True
        assert repo.get_by_id(applied.id) is None

    def test_delete_by_id_not_found(self, db_session):
        """Test deleting a non-existent applied tax by ID."""
        repo = AppliedTaxRepository(db_session)
        assert repo.delete_by_id(uuid4()) is False


class TestTaxSchema:
    """Tests for Tax Pydantic schemas."""

    def test_tax_create_basic(self):
        """Test TaxCreate with required fields."""
        schema = TaxCreate(
            code="TAX1",
            name="Tax 1",
            rate=Decimal("0.1000"),
        )
        assert schema.code == "TAX1"
        assert schema.applied_to_organization is False

    def test_tax_create_full(self):
        """Test TaxCreate with all fields."""
        schema = TaxCreate(
            code="TAX2",
            name="Tax 2",
            rate=Decimal("0.2000"),
            description="Full tax",
            applied_to_organization=True,
        )
        assert schema.description == "Full tax"
        assert schema.applied_to_organization is True

    def test_tax_create_code_max_length(self):
        """Test TaxCreate code max length validation."""
        with pytest.raises(ValidationError):
            TaxCreate(
                code="X" * 256,
                name="Tax",
                rate=Decimal("0.1000"),
            )

    def test_tax_create_name_max_length(self):
        """Test TaxCreate name max length validation."""
        with pytest.raises(ValidationError):
            TaxCreate(
                code="TAX",
                name="X" * 256,
                rate=Decimal("0.1000"),
            )

    def test_tax_update_partial(self):
        """Test TaxUpdate with partial fields."""
        schema = TaxUpdate(name="Updated Name")
        data = schema.model_dump(exclude_unset=True)
        assert data == {"name": "Updated Name"}

    def test_tax_update_all_fields(self):
        """Test TaxUpdate with all fields."""
        schema = TaxUpdate(
            name="Updated",
            rate=Decimal("0.3000"),
            description="Updated desc",
            applied_to_organization=True,
        )
        data = schema.model_dump(exclude_unset=True)
        assert len(data) == 4

    def test_tax_response(self, db_session, basic_tax):
        """Test TaxResponse from ORM object."""
        response = TaxResponse.model_validate(basic_tax)
        assert response.code == "VAT_20"
        assert response.rate == Decimal("0.2000")
        assert response.created_at is not None
        assert response.updated_at is not None

    def test_applied_tax_response(self, db_session, basic_tax):
        """Test AppliedTaxResponse from ORM object."""
        repo = AppliedTaxRepository(db_session)
        applied = repo.create(
            tax_id=basic_tax.id,
            taxable_type="customer",
            taxable_id=uuid4(),
            tax_rate=Decimal("0.2000"),
        )
        response = AppliedTaxResponse.model_validate(applied)
        assert response.tax_id == basic_tax.id
        assert response.taxable_type == "customer"

    def test_apply_tax_request(self):
        """Test ApplyTaxRequest schema."""
        taxable_id = uuid4()
        schema = ApplyTaxRequest(
            tax_code="VAT_20",
            taxable_type="customer",
            taxable_id=taxable_id,
        )
        assert schema.tax_code == "VAT_20"
        assert schema.taxable_id == taxable_id

    def test_apply_tax_request_type_max_length(self):
        """Test ApplyTaxRequest taxable_type max length."""
        with pytest.raises(ValidationError):
            ApplyTaxRequest(
                tax_code="TAX",
                taxable_type="X" * 51,
                taxable_id=uuid4(),
            )
