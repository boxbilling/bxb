"""Organization model, schema, and repository tests."""

import uuid

import pytest

from app.core.database import get_db
from app.models.organization import Organization, generate_uuid
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.organization import OrganizationCreate, OrganizationResponse, OrganizationUpdate
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


class TestOrganizationModel:
    def test_generate_uuid(self):
        """Test that generate_uuid returns a valid UUID."""
        result = generate_uuid()
        assert isinstance(result, uuid.UUID)

    def test_organization_defaults(self, db_session):
        """Test Organization model default values."""
        org = Organization(
            id=uuid.uuid4(),
            name="Test Org",
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        assert org.id is not None
        assert org.name == "Test Org"
        assert org.default_currency == "USD"
        assert org.timezone == "UTC"
        assert org.hmac_key is None
        assert org.document_number_prefix is None
        assert org.invoice_grace_period == 0
        assert org.net_payment_term == 30
        assert org.logo_url is None
        assert org.email is None
        assert org.legal_name is None
        assert org.address_line1 is None
        assert org.address_line2 is None
        assert org.city is None
        assert org.state is None
        assert org.zipcode is None
        assert org.country is None
        assert org.created_at is not None
        assert org.updated_at is not None

    def test_organization_with_all_fields(self, db_session):
        """Test Organization with all fields set."""
        org = Organization(
            id=uuid.uuid4(),
            name="Full Org",
            default_currency="EUR",
            timezone="Europe/London",
            hmac_key="secret123",
            document_number_prefix="INV-",
            invoice_grace_period=5,
            net_payment_term=45,
            logo_url="https://example.com/logo.png",
            email="billing@example.com",
            legal_name="Full Org Inc.",
            address_line1="123 Main St",
            address_line2="Suite 100",
            city="London",
            state="Greater London",
            zipcode="EC1A 1BB",
            country="GB",
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        assert org.default_currency == "EUR"
        assert org.timezone == "Europe/London"
        assert org.hmac_key == "secret123"
        assert org.document_number_prefix == "INV-"
        assert org.invoice_grace_period == 5
        assert org.net_payment_term == 45
        assert org.logo_url == "https://example.com/logo.png"
        assert org.email == "billing@example.com"
        assert org.legal_name == "Full Org Inc."
        assert org.address_line1 == "123 Main St"
        assert org.address_line2 == "Suite 100"
        assert org.city == "London"
        assert org.state == "Greater London"
        assert org.zipcode == "EC1A 1BB"
        assert org.country == "GB"

    def test_default_organization_exists(self, db_session):
        """Test that the default test organization is seeded."""
        org = db_session.query(Organization).filter(Organization.id == DEFAULT_ORG_ID).first()
        assert org is not None
        assert org.name == "Default Test Organization"


class TestOrganizationRepository:
    def test_create_organization(self, db_session):
        """Test creating an organization."""
        repo = OrganizationRepository(db_session)
        data = OrganizationCreate(name="New Org")
        org = repo.create(data)

        assert org.id is not None
        assert org.name == "New Org"
        assert org.default_currency == "USD"

    def test_get_by_id(self, db_session):
        """Test getting an organization by ID."""
        repo = OrganizationRepository(db_session)
        data = OrganizationCreate(name="Get Org")
        created = repo.create(data)

        found = repo.get_by_id(created.id)
        assert found is not None
        assert found.name == "Get Org"

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent organization."""
        repo = OrganizationRepository(db_session)
        result = repo.get_by_id(uuid.uuid4())
        assert result is None

    def test_get_all(self, db_session):
        """Test listing all organizations."""
        repo = OrganizationRepository(db_session)
        # Default org is already seeded
        orgs = repo.get_all()
        assert len(orgs) >= 1

        repo.create(OrganizationCreate(name="Org A"))
        repo.create(OrganizationCreate(name="Org B"))
        orgs = repo.get_all()
        assert len(orgs) >= 3

    def test_get_all_pagination(self, db_session):
        """Test pagination of organization listing."""
        repo = OrganizationRepository(db_session)
        repo.create(OrganizationCreate(name="Org P1"))
        repo.create(OrganizationCreate(name="Org P2"))
        repo.create(OrganizationCreate(name="Org P3"))

        page = repo.get_all(skip=1, limit=2)
        assert len(page) == 2

    def test_update_organization(self, db_session):
        """Test updating an organization."""
        repo = OrganizationRepository(db_session)
        created = repo.create(OrganizationCreate(name="Update Org"))

        updated = repo.update(
            created.id,
            OrganizationUpdate(name="Updated Org", default_currency="EUR"),
        )
        assert updated is not None
        assert updated.name == "Updated Org"
        assert updated.default_currency == "EUR"

    def test_update_organization_partial(self, db_session):
        """Test partial update of an organization."""
        repo = OrganizationRepository(db_session)
        created = repo.create(OrganizationCreate(name="Partial Org", default_currency="GBP"))

        updated = repo.update(created.id, OrganizationUpdate(name="Renamed Org"))
        assert updated is not None
        assert updated.name == "Renamed Org"
        assert updated.default_currency == "GBP"  # unchanged

    def test_update_organization_not_found(self, db_session):
        """Test updating a non-existent organization."""
        repo = OrganizationRepository(db_session)
        result = repo.update(uuid.uuid4(), OrganizationUpdate(name="Ghost"))
        assert result is None

    def test_delete_organization(self, db_session):
        """Test deleting an organization."""
        repo = OrganizationRepository(db_session)
        created = repo.create(OrganizationCreate(name="Delete Org"))

        assert repo.delete(created.id) is True
        assert repo.get_by_id(created.id) is None

    def test_delete_organization_not_found(self, db_session):
        """Test deleting a non-existent organization."""
        repo = OrganizationRepository(db_session)
        assert repo.delete(uuid.uuid4()) is False


class TestOrganizationSchemas:
    def test_create_schema_minimal(self):
        """Test OrganizationCreate with minimal fields."""
        schema = OrganizationCreate(name="Min Org")
        assert schema.name == "Min Org"
        assert schema.default_currency == "USD"
        assert schema.timezone == "UTC"
        assert schema.invoice_grace_period == 0
        assert schema.net_payment_term == 30

    def test_create_schema_all_fields(self):
        """Test OrganizationCreate with all fields."""
        schema = OrganizationCreate(
            name="Full Org",
            default_currency="EUR",
            timezone="Europe/London",
            hmac_key="secret",
            document_number_prefix="INV-",
            invoice_grace_period=5,
            net_payment_term=45,
            logo_url="https://example.com/logo.png",
            email="test@example.com",
            legal_name="Full Org Inc.",
            address_line1="123 Main St",
            address_line2="Suite 100",
            city="London",
            state="Greater London",
            zipcode="EC1A 1BB",
            country="GB",
        )
        assert schema.default_currency == "EUR"
        assert schema.hmac_key == "secret"
        assert schema.city == "London"

    def test_update_schema_partial(self):
        """Test OrganizationUpdate with partial fields."""
        schema = OrganizationUpdate(name="New Name")
        dump = schema.model_dump(exclude_unset=True)
        assert dump == {"name": "New Name"}

    def test_update_schema_all_fields(self):
        """Test OrganizationUpdate with all fields."""
        schema = OrganizationUpdate(
            name="Updated",
            default_currency="JPY",
            timezone="Asia/Tokyo",
            hmac_key="new_key",
            document_number_prefix="ORD-",
            invoice_grace_period=10,
            net_payment_term=60,
            logo_url="https://example.com/new.png",
            email="new@example.com",
            legal_name="New Inc.",
            address_line1="456 Oak Ave",
            address_line2=None,
            city="Tokyo",
            state="Kanto",
            zipcode="100-0001",
            country="JP",
        )
        assert schema.default_currency == "JPY"

    def test_response_schema_from_model(self, db_session):
        """Test OrganizationResponse from ORM model."""
        org = Organization(
            id=uuid.uuid4(),
            name="Response Org",
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        response = OrganizationResponse.model_validate(org)
        assert response.name == "Response Org"
        assert response.default_currency == "USD"
        assert response.created_at is not None
        assert response.updated_at is not None

    def test_response_schema_all_fields(self, db_session):
        """Test OrganizationResponse with all fields populated."""
        org = Organization(
            id=uuid.uuid4(),
            name="Full Response Org",
            default_currency="CAD",
            timezone="America/Toronto",
            hmac_key="hmac123",
            document_number_prefix="CN-",
            invoice_grace_period=3,
            net_payment_term=15,
            logo_url="https://example.com/ca.png",
            email="ca@example.com",
            legal_name="Canadian Corp.",
            address_line1="789 Maple Dr",
            address_line2="Floor 2",
            city="Toronto",
            state="Ontario",
            zipcode="M5V 2H1",
            country="CA",
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        response = OrganizationResponse.model_validate(org)
        assert response.default_currency == "CAD"
        assert response.hmac_key == "hmac123"
        assert response.legal_name == "Canadian Corp."
        assert response.city == "Toronto"
