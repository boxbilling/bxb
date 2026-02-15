"""BillingEntity model, schema, and repository tests."""

import uuid

import pytest

from app.core.database import get_db
from app.models.billing_entity import BillingEntity
from app.models.customer import Customer, generate_uuid
from app.models.organization import Organization
from app.repositories.billing_entity_repository import BillingEntityRepository
from app.schemas.billing_entity import (
    BillingEntityCreate,
    BillingEntityResponse,
    BillingEntityUpdate,
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
def second_org(db_session):
    """Create a second organization for testing."""
    org = Organization(
        id=uuid.uuid4(),
        name="Second Test Organization",
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


class TestBillingEntityModel:
    def test_defaults(self, db_session):
        """Test BillingEntity model default values."""
        entity = BillingEntity(
            id=generate_uuid(),
            organization_id=DEFAULT_ORG_ID,
            code="entity-001",
            name="Main Entity",
        )
        db_session.add(entity)
        db_session.commit()
        db_session.refresh(entity)

        assert entity.id is not None
        assert entity.organization_id == DEFAULT_ORG_ID
        assert entity.code == "entity-001"
        assert entity.name == "Main Entity"
        assert entity.legal_name is None
        assert entity.address_line1 is None
        assert entity.address_line2 is None
        assert entity.city is None
        assert entity.state is None
        assert entity.country is None
        assert entity.zip_code is None
        assert entity.tax_id is None
        assert entity.email is None
        assert entity.currency == "USD"
        assert entity.timezone == "UTC"
        assert entity.document_locale == "en"
        assert entity.invoice_prefix is None
        assert entity.next_invoice_number == 1
        assert entity.is_default is False
        assert entity.created_at is not None
        assert entity.updated_at is not None

    def test_all_fields(self, db_session):
        """Test BillingEntity with all fields set."""
        entity = BillingEntity(
            id=generate_uuid(),
            organization_id=DEFAULT_ORG_ID,
            code="full-entity",
            name="Full Entity",
            legal_name="Full Entity LLC",
            address_line1="123 Main St",
            address_line2="Suite 100",
            city="New York",
            state="NY",
            country="US",
            zip_code="10001",
            tax_id="US12345678",
            email="billing@full.com",
            currency="EUR",
            timezone="Europe/Berlin",
            document_locale="de",
            invoice_prefix="FE",
            next_invoice_number=42,
            is_default=True,
        )
        db_session.add(entity)
        db_session.commit()
        db_session.refresh(entity)

        assert entity.legal_name == "Full Entity LLC"
        assert entity.address_line1 == "123 Main St"
        assert entity.address_line2 == "Suite 100"
        assert entity.city == "New York"
        assert entity.state == "NY"
        assert entity.country == "US"
        assert entity.zip_code == "10001"
        assert entity.tax_id == "US12345678"
        assert entity.email == "billing@full.com"
        assert entity.currency == "EUR"
        assert entity.timezone == "Europe/Berlin"
        assert entity.document_locale == "de"
        assert entity.invoice_prefix == "FE"
        assert entity.next_invoice_number == 42
        assert entity.is_default is True

    def test_customer_billing_entity_fk(self, db_session):
        """Test that Customer can reference a billing entity."""
        entity = BillingEntity(
            id=generate_uuid(),
            organization_id=DEFAULT_ORG_ID,
            code="cust-be",
            name="Customer BE",
        )
        db_session.add(entity)
        db_session.commit()
        db_session.refresh(entity)

        customer = Customer(
            id=generate_uuid(),
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-with-be",
            name="Test Customer",
            billing_entity_id=entity.id,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        assert customer.billing_entity_id == entity.id

    def test_customer_billing_entity_nullable(self, db_session):
        """Test that Customer.billing_entity_id is nullable."""
        customer = Customer(
            id=generate_uuid(),
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-no-be",
            name="Test Customer No BE",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        assert customer.billing_entity_id is None


class TestBillingEntityRepository:
    def test_create(self, db_session):
        """Test creating a billing entity."""
        repo = BillingEntityRepository(db_session)
        data = BillingEntityCreate(
            code="be-create",
            name="Create Entity",
        )
        entity = repo.create(data, DEFAULT_ORG_ID)

        assert entity.id is not None
        assert entity.organization_id == DEFAULT_ORG_ID
        assert entity.code == "be-create"
        assert entity.name == "Create Entity"
        assert entity.currency == "USD"
        assert entity.timezone == "UTC"
        assert entity.is_default is False

    def test_create_with_all_fields(self, db_session):
        """Test creating a billing entity with all fields."""
        repo = BillingEntityRepository(db_session)
        data = BillingEntityCreate(
            code="be-full",
            name="Full Entity",
            legal_name="Full Entity Inc.",
            address_line1="456 Oak Ave",
            address_line2="Floor 3",
            city="San Francisco",
            state="CA",
            country="US",
            zip_code="94105",
            tax_id="USTAX999",
            email="full@entity.com",
            currency="GBP",
            timezone="Europe/London",
            document_locale="en-GB",
            invoice_prefix="FUL",
            next_invoice_number=100,
            is_default=True,
        )
        entity = repo.create(data, DEFAULT_ORG_ID)

        assert entity.legal_name == "Full Entity Inc."
        assert entity.address_line1 == "456 Oak Ave"
        assert entity.currency == "GBP"
        assert entity.invoice_prefix == "FUL"
        assert entity.next_invoice_number == 100
        assert entity.is_default is True

    def test_get_by_id(self, db_session):
        """Test getting a billing entity by ID."""
        repo = BillingEntityRepository(db_session)
        data = BillingEntityCreate(code="be-getid", name="Get ID")
        created = repo.create(data, DEFAULT_ORG_ID)

        found = repo.get_by_id(created.id, DEFAULT_ORG_ID)
        assert found is not None
        assert found.id == created.id

    def test_get_by_id_without_org(self, db_session):
        """Test getting a billing entity by ID without org filter."""
        repo = BillingEntityRepository(db_session)
        data = BillingEntityCreate(code="be-noorg", name="No Org")
        created = repo.create(data, DEFAULT_ORG_ID)

        found = repo.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id

    def test_get_by_id_wrong_org(self, db_session, second_org):
        """Test that billing entities are scoped by organization."""
        repo = BillingEntityRepository(db_session)
        data = BillingEntityCreate(code="be-wrongorg", name="Wrong Org")
        created = repo.create(data, DEFAULT_ORG_ID)

        result = repo.get_by_id(created.id, second_org.id)
        assert result is None

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent billing entity."""
        repo = BillingEntityRepository(db_session)
        result = repo.get_by_id(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is None

    def test_get_by_code(self, db_session):
        """Test getting a billing entity by code."""
        repo = BillingEntityRepository(db_session)
        data = BillingEntityCreate(code="be-bycode", name="By Code")
        repo.create(data, DEFAULT_ORG_ID)

        found = repo.get_by_code("be-bycode", DEFAULT_ORG_ID)
        assert found is not None
        assert found.code == "be-bycode"

    def test_get_by_code_not_found(self, db_session):
        """Test getting a non-existent billing entity by code."""
        repo = BillingEntityRepository(db_session)
        result = repo.get_by_code("nonexistent", DEFAULT_ORG_ID)
        assert result is None

    def test_get_by_code_wrong_org(self, db_session, second_org):
        """Test that get_by_code is scoped by organization."""
        repo = BillingEntityRepository(db_session)
        data = BillingEntityCreate(code="be-codescope", name="Code Scope")
        repo.create(data, DEFAULT_ORG_ID)

        result = repo.get_by_code("be-codescope", second_org.id)
        assert result is None

    def test_get_default(self, db_session):
        """Test getting the default billing entity."""
        repo = BillingEntityRepository(db_session)
        repo.create(
            BillingEntityCreate(
                code="be-nondefault", name="Non Default"
            ),
            DEFAULT_ORG_ID,
        )
        repo.create(
            BillingEntityCreate(
                code="be-default",
                name="Default Entity",
                is_default=True,
            ),
            DEFAULT_ORG_ID,
        )

        default = repo.get_default(DEFAULT_ORG_ID)
        assert default is not None
        assert default.code == "be-default"
        assert default.is_default is True

    def test_get_default_none(self, db_session):
        """Test getting default when no default exists."""
        repo = BillingEntityRepository(db_session)
        repo.create(
            BillingEntityCreate(code="be-nodef", name="No Default"),
            DEFAULT_ORG_ID,
        )

        default = repo.get_default(DEFAULT_ORG_ID)
        assert default is None

    def test_get_all(self, db_session):
        """Test listing all billing entities for an organization."""
        repo = BillingEntityRepository(db_session)
        for i in range(3):
            repo.create(
                BillingEntityCreate(
                    code=f"be-all-{i}", name=f"Entity {i}"
                ),
                DEFAULT_ORG_ID,
            )

        entities = repo.get_all(DEFAULT_ORG_ID)
        assert len(entities) == 3

    def test_get_all_pagination(self, db_session):
        """Test pagination of billing entity listing."""
        repo = BillingEntityRepository(db_session)
        for i in range(5):
            repo.create(
                BillingEntityCreate(
                    code=f"be-page-{i}", name=f"Page Entity {i}"
                ),
                DEFAULT_ORG_ID,
            )

        page = repo.get_all(DEFAULT_ORG_ID, skip=1, limit=2)
        assert len(page) == 2

    def test_get_all_empty(self, db_session, second_org):
        """Test listing billing entities for an org with none."""
        repo = BillingEntityRepository(db_session)
        entities = repo.get_all(second_org.id)
        assert entities == []

    def test_count(self, db_session):
        """Test counting billing entities."""
        repo = BillingEntityRepository(db_session)
        for i in range(3):
            repo.create(
                BillingEntityCreate(
                    code=f"be-cnt-{i}", name=f"Count {i}"
                ),
                DEFAULT_ORG_ID,
            )

        assert repo.count(DEFAULT_ORG_ID) == 3

    def test_count_empty(self, db_session, second_org):
        """Test counting billing entities when none exist."""
        repo = BillingEntityRepository(db_session)
        assert repo.count(second_org.id) == 0

    def test_update(self, db_session):
        """Test updating a billing entity."""
        repo = BillingEntityRepository(db_session)
        entity = repo.create(
            BillingEntityCreate(code="be-upd", name="Update Me"),
            DEFAULT_ORG_ID,
        )

        updated = repo.update(
            entity.id,
            BillingEntityUpdate(name="Updated Name", currency="EUR"),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.currency == "EUR"
        assert updated.code == "be-upd"  # unchanged

    def test_update_partial(self, db_session):
        """Test partial update only changes specified fields."""
        repo = BillingEntityRepository(db_session)
        entity = repo.create(
            BillingEntityCreate(
                code="be-partial", name="Partial", currency="USD"
            ),
            DEFAULT_ORG_ID,
        )

        updated = repo.update(
            entity.id,
            BillingEntityUpdate(name="New Name"),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.name == "New Name"
        assert updated.currency == "USD"  # unchanged

    def test_update_not_found(self, db_session):
        """Test updating a non-existent billing entity."""
        repo = BillingEntityRepository(db_session)
        result = repo.update(
            uuid.uuid4(),
            BillingEntityUpdate(name="Nope"),
            DEFAULT_ORG_ID,
        )
        assert result is None

    def test_update_wrong_org(self, db_session, second_org):
        """Test updating a billing entity from wrong org."""
        repo = BillingEntityRepository(db_session)
        entity = repo.create(
            BillingEntityCreate(code="be-updworg", name="Wrong Org Upd"),
            DEFAULT_ORG_ID,
        )

        result = repo.update(
            entity.id,
            BillingEntityUpdate(name="Hacked"),
            second_org.id,
        )
        assert result is None

    def test_delete(self, db_session):
        """Test deleting a billing entity."""
        repo = BillingEntityRepository(db_session)
        entity = repo.create(
            BillingEntityCreate(code="be-del", name="Delete Me"),
            DEFAULT_ORG_ID,
        )

        result = repo.delete(entity.id, DEFAULT_ORG_ID)
        assert result is True

        found = repo.get_by_id(entity.id, DEFAULT_ORG_ID)
        assert found is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent billing entity."""
        repo = BillingEntityRepository(db_session)
        result = repo.delete(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is False

    def test_delete_wrong_org(self, db_session, second_org):
        """Test deleting a billing entity from wrong org."""
        repo = BillingEntityRepository(db_session)
        entity = repo.create(
            BillingEntityCreate(code="be-delworg", name="Del Wrong Org"),
            DEFAULT_ORG_ID,
        )

        result = repo.delete(entity.id, second_org.id)
        assert result is False

        found = repo.get_by_id(entity.id, DEFAULT_ORG_ID)
        assert found is not None

    def test_code_exists(self, db_session):
        """Test checking if a code exists."""
        repo = BillingEntityRepository(db_session)
        repo.create(
            BillingEntityCreate(code="be-exists", name="Exists"),
            DEFAULT_ORG_ID,
        )

        assert repo.code_exists("be-exists", DEFAULT_ORG_ID) is True
        assert repo.code_exists("be-nope", DEFAULT_ORG_ID) is False

    def test_code_exists_different_org(self, db_session, second_org):
        """Test code_exists is scoped by organization."""
        repo = BillingEntityRepository(db_session)
        repo.create(
            BillingEntityCreate(code="be-orgscope", name="Org Scope"),
            DEFAULT_ORG_ID,
        )

        assert repo.code_exists("be-orgscope", DEFAULT_ORG_ID) is True
        assert repo.code_exists("be-orgscope", second_org.id) is False


class TestBillingEntitySchemas:
    def test_create_schema_defaults(self):
        """Test BillingEntityCreate schema default values."""
        schema = BillingEntityCreate(code="test", name="Test")
        assert schema.currency == "USD"
        assert schema.timezone == "UTC"
        assert schema.document_locale == "en"
        assert schema.next_invoice_number == 1
        assert schema.is_default is False
        assert schema.legal_name is None
        assert schema.invoice_prefix is None

    def test_create_schema_with_all_fields(self):
        """Test BillingEntityCreate with all fields."""
        schema = BillingEntityCreate(
            code="full",
            name="Full",
            legal_name="Full LLC",
            address_line1="123 St",
            address_line2="Apt 1",
            city="LA",
            state="CA",
            country="US",
            zip_code="90001",
            tax_id="TAX123",
            email="test@test.com",
            currency="EUR",
            timezone="Europe/Berlin",
            document_locale="de",
            invoice_prefix="PRE",
            next_invoice_number=50,
            is_default=True,
        )
        assert schema.code == "full"
        assert schema.legal_name == "Full LLC"
        assert schema.country == "US"
        assert schema.is_default is True

    def test_update_schema_partial(self):
        """Test BillingEntityUpdate with partial fields."""
        schema = BillingEntityUpdate(name="New Name")
        dumped = schema.model_dump(exclude_unset=True)
        assert dumped == {"name": "New Name"}

    def test_update_schema_empty(self):
        """Test BillingEntityUpdate with no fields set."""
        schema = BillingEntityUpdate()
        dumped = schema.model_dump(exclude_unset=True)
        assert dumped == {}

    def test_response_schema_from_model(self, db_session):
        """Test BillingEntityResponse from ORM model."""
        entity = BillingEntity(
            id=generate_uuid(),
            organization_id=DEFAULT_ORG_ID,
            code="resp-test",
            name="Response Test",
        )
        db_session.add(entity)
        db_session.commit()
        db_session.refresh(entity)

        response = BillingEntityResponse.model_validate(entity)
        assert response.id == entity.id
        assert response.code == "resp-test"
        assert response.name == "Response Test"
        assert response.currency == "USD"
        assert response.timezone == "UTC"
        assert response.document_locale == "en"
        assert response.is_default is False
        assert response.created_at is not None
        assert response.updated_at is not None
