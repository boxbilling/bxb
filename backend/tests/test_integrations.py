"""Tests for Integration framework: models, repositories, schemas, mappings, and API."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.integration import (
    Integration,
    IntegrationProviderType,
    IntegrationStatus,
    IntegrationType,
)
from app.models.integration_customer import IntegrationCustomer
from app.models.integration_mapping import IntegrationMapping
from app.repositories.customer_repository import CustomerRepository
from app.repositories.integration_customer_repository import IntegrationCustomerRepository
from app.repositories.integration_mapping_repository import IntegrationMappingRepository
from app.repositories.integration_repository import IntegrationRepository
from app.schemas.customer import CustomerCreate
from app.schemas.integration import IntegrationCreate, IntegrationResponse, IntegrationUpdate
from app.schemas.integration_customer import (
    IntegrationCustomerCreate,
    IntegrationCustomerResponse,
    IntegrationCustomerUpdate,
)
from app.schemas.integration_mapping import (
    IntegrationMappingCreate,
    IntegrationMappingResponse,
    IntegrationMappingUpdate,
)
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
def integration(db_session):
    """Create a test integration."""
    repo = IntegrationRepository(db_session)
    return repo.create(
        IntegrationCreate(
            integration_type="payment_provider",
            provider_type="stripe",
            settings={"api_key": "sk_test_123"},
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def customer(db_session):
    """Create a test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"int_test_cust_{uuid4()}",
            name="Integration Test Customer",
        ),
        DEFAULT_ORG_ID,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Enum Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationEnums:
    """Tests for integration-related enums."""

    def test_integration_type_values(self):
        assert IntegrationType.PAYMENT_PROVIDER == "payment_provider"
        assert IntegrationType.ACCOUNTING == "accounting"
        assert IntegrationType.CRM == "crm"
        assert IntegrationType.TAX == "tax"

    def test_integration_provider_type_values(self):
        assert IntegrationProviderType.STRIPE == "stripe"
        assert IntegrationProviderType.GOCARDLESS == "gocardless"
        assert IntegrationProviderType.ADYEN == "adyen"
        assert IntegrationProviderType.NETSUITE == "netsuite"
        assert IntegrationProviderType.XERO == "xero"
        assert IntegrationProviderType.HUBSPOT == "hubspot"
        assert IntegrationProviderType.SALESFORCE == "salesforce"
        assert IntegrationProviderType.ANROK == "anrok"
        assert IntegrationProviderType.AVALARA == "avalara"

    def test_integration_status_values(self):
        assert IntegrationStatus.ACTIVE == "active"
        assert IntegrationStatus.INACTIVE == "inactive"
        assert IntegrationStatus.ERROR == "error"


# ─────────────────────────────────────────────────────────────────────────────
# Integration Model Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationModel:
    """Tests for the Integration model."""

    def test_integration_table_name(self):
        assert Integration.__tablename__ == "integrations"

    def test_integration_creation(self, db_session):
        integration = Integration(
            organization_id=DEFAULT_ORG_ID,
            integration_type="payment_provider",
            provider_type="stripe",
            settings={"api_key": "sk_test_123"},
        )
        db_session.add(integration)
        db_session.commit()
        db_session.refresh(integration)

        assert integration.id is not None
        assert integration.organization_id == DEFAULT_ORG_ID
        assert integration.integration_type == "payment_provider"
        assert integration.provider_type == "stripe"
        assert integration.status == "active"
        assert integration.settings == {"api_key": "sk_test_123"}
        assert integration.last_sync_at is None
        assert integration.error_details is None
        assert integration.created_at is not None
        assert integration.updated_at is not None

    def test_integration_creation_with_defaults(self, db_session):
        integration = Integration(
            organization_id=DEFAULT_ORG_ID,
            integration_type="accounting",
            provider_type="netsuite",
            settings={},
        )
        db_session.add(integration)
        db_session.commit()
        db_session.refresh(integration)

        assert integration.status == "active"
        assert integration.settings == {}


# ─────────────────────────────────────────────────────────────────────────────
# IntegrationMapping Model Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationMappingModel:
    """Tests for the IntegrationMapping model."""

    def test_mapping_table_name(self):
        assert IntegrationMapping.__tablename__ == "integration_mappings"

    def test_mapping_creation(self, db_session, integration):
        resource_id = uuid4()
        mapping = IntegrationMapping(
            integration_id=integration.id,
            mappable_type="customer",
            mappable_id=resource_id,
            external_id="ext_cus_123",
            external_data={"name": "Test"},
        )
        db_session.add(mapping)
        db_session.commit()
        db_session.refresh(mapping)

        assert mapping.id is not None
        assert mapping.integration_id == integration.id
        assert mapping.mappable_type == "customer"
        assert mapping.mappable_id == resource_id
        assert mapping.external_id == "ext_cus_123"
        assert mapping.external_data == {"name": "Test"}
        assert mapping.last_synced_at is None
        assert mapping.created_at is not None
        assert mapping.updated_at is not None


# ─────────────────────────────────────────────────────────────────────────────
# IntegrationCustomer Model Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationCustomerModel:
    """Tests for the IntegrationCustomer model."""

    def test_integration_customer_table_name(self):
        assert IntegrationCustomer.__tablename__ == "integration_customers"

    def test_integration_customer_creation(self, db_session, integration, customer):
        ic = IntegrationCustomer(
            integration_id=integration.id,
            customer_id=customer.id,
            external_customer_id="ext_cus_456",
            settings={"auto_sync": True},
        )
        db_session.add(ic)
        db_session.commit()
        db_session.refresh(ic)

        assert ic.id is not None
        assert ic.integration_id == integration.id
        assert ic.customer_id == customer.id
        assert ic.external_customer_id == "ext_cus_456"
        assert ic.settings == {"auto_sync": True}
        assert ic.created_at is not None
        assert ic.updated_at is not None


# ─────────────────────────────────────────────────────────────────────────────
# Integration Repository Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationRepository:
    """Tests for IntegrationRepository CRUD and query methods."""

    def test_create_integration(self, db_session):
        repo = IntegrationRepository(db_session)
        integration = repo.create(
            IntegrationCreate(
                integration_type="payment_provider",
                provider_type="adyen",
                settings={"merchant_account": "test"},
            ),
            DEFAULT_ORG_ID,
        )
        assert integration.id is not None
        assert integration.integration_type == "payment_provider"
        assert integration.provider_type == "adyen"
        assert integration.status == "active"
        assert integration.settings == {"merchant_account": "test"}

    def test_create_integration_minimal(self, db_session):
        repo = IntegrationRepository(db_session)
        integration = repo.create(
            IntegrationCreate(
                integration_type="crm",
                provider_type="hubspot",
            ),
            DEFAULT_ORG_ID,
        )
        assert integration.id is not None
        assert integration.settings == {}
        assert integration.status == "active"

    def test_get_by_id(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        fetched = repo.get_by_id(integration.id)
        assert fetched is not None
        assert fetched.id == integration.id
        assert fetched.provider_type == "stripe"

    def test_get_by_id_with_organization(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        fetched = repo.get_by_id(integration.id, DEFAULT_ORG_ID)
        assert fetched is not None
        assert fetched.id == integration.id

    def test_get_by_id_wrong_organization(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        fetched = repo.get_by_id(integration.id, uuid4())
        assert fetched is None

    def test_get_by_id_not_found(self, db_session):
        repo = IntegrationRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_provider(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        fetched = repo.get_by_provider(DEFAULT_ORG_ID, "stripe")
        assert fetched is not None
        assert fetched.id == integration.id

    def test_get_by_provider_not_found(self, db_session):
        repo = IntegrationRepository(db_session)
        fetched = repo.get_by_provider(DEFAULT_ORG_ID, "nonexistent")
        assert fetched is None

    def test_get_all(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        integrations = repo.get_all(DEFAULT_ORG_ID)
        assert len(integrations) == 1
        assert integrations[0].id == integration.id

    def test_get_all_empty(self, db_session):
        repo = IntegrationRepository(db_session)
        # Use a random org id that has no integrations
        integrations = repo.get_all(uuid4())
        assert len(integrations) == 0

    def test_get_all_pagination(self, db_session):
        repo = IntegrationRepository(db_session)
        providers = ["stripe", "adyen", "gocardless", "netsuite", "xero"]
        for p in providers:
            repo.create(
                IntegrationCreate(
                    integration_type="payment_provider",
                    provider_type=p,
                ),
                DEFAULT_ORG_ID,
            )
        integrations = repo.get_all(DEFAULT_ORG_ID, skip=2, limit=2)
        assert len(integrations) == 2

    def test_update_integration(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        updated = repo.update(
            integration.id,
            IntegrationUpdate(
                status="inactive",
                settings={"api_key": "sk_live_456"},
            ),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.status == "inactive"
        assert updated.settings == {"api_key": "sk_live_456"}

    def test_update_integration_partial(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        updated = repo.update(
            integration.id,
            IntegrationUpdate(status="error"),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.status == "error"
        assert updated.settings == {"api_key": "sk_test_123"}

    def test_update_integration_error_details(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        updated = repo.update(
            integration.id,
            IntegrationUpdate(
                status="error",
                error_details={"code": "auth_failed", "message": "Invalid API key"},
            ),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.error_details == {"code": "auth_failed", "message": "Invalid API key"}

    def test_update_integration_not_found(self, db_session):
        repo = IntegrationRepository(db_session)
        result = repo.update(uuid4(), IntegrationUpdate(status="inactive"), DEFAULT_ORG_ID)
        assert result is None

    def test_update_integration_wrong_organization(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        result = repo.update(integration.id, IntegrationUpdate(status="inactive"), uuid4())
        assert result is None

    def test_delete_integration(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        assert repo.delete(integration.id, DEFAULT_ORG_ID) is True
        assert repo.get_by_id(integration.id) is None

    def test_delete_integration_not_found(self, db_session):
        repo = IntegrationRepository(db_session)
        assert repo.delete(uuid4(), DEFAULT_ORG_ID) is False

    def test_delete_integration_wrong_organization(self, db_session, integration):
        repo = IntegrationRepository(db_session)
        assert repo.delete(integration.id, uuid4()) is False
        assert repo.get_by_id(integration.id) is not None


# ─────────────────────────────────────────────────────────────────────────────
# IntegrationMapping Repository Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationMappingRepository:
    """Tests for IntegrationMappingRepository CRUD and query methods."""

    def test_create_mapping(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        resource_id = uuid4()
        mapping = repo.create(
            IntegrationMappingCreate(
                integration_id=integration.id,
                mappable_type="customer",
                mappable_id=resource_id,
                external_id="ext_cus_123",
                external_data={"name": "Test Customer"},
            ),
        )
        assert mapping.id is not None
        assert mapping.integration_id == integration.id
        assert mapping.mappable_type == "customer"
        assert mapping.mappable_id == resource_id
        assert mapping.external_id == "ext_cus_123"
        assert mapping.external_data == {"name": "Test Customer"}

    def test_create_mapping_minimal(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        mapping = repo.create(
            IntegrationMappingCreate(
                integration_id=integration.id,
                mappable_type="invoice",
                mappable_id=uuid4(),
                external_id="inv_ext_1",
            ),
        )
        assert mapping.id is not None
        assert mapping.external_data is None

    def test_get_by_id(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        mapping = repo.create(
            IntegrationMappingCreate(
                integration_id=integration.id,
                mappable_type="customer",
                mappable_id=uuid4(),
                external_id="ext_1",
            ),
        )
        fetched = repo.get_by_id(mapping.id)
        assert fetched is not None
        assert fetched.id == mapping.id

    def test_get_by_id_not_found(self, db_session):
        repo = IntegrationMappingRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_mappable(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        resource_id = uuid4()
        repo.create(
            IntegrationMappingCreate(
                integration_id=integration.id,
                mappable_type="customer",
                mappable_id=resource_id,
                external_id="ext_map_1",
            ),
        )
        fetched = repo.get_by_mappable(integration.id, "customer", resource_id)
        assert fetched is not None
        assert fetched.external_id == "ext_map_1"

    def test_get_by_mappable_not_found(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        fetched = repo.get_by_mappable(integration.id, "customer", uuid4())
        assert fetched is None

    def test_get_by_external_id(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        repo.create(
            IntegrationMappingCreate(
                integration_id=integration.id,
                mappable_type="customer",
                mappable_id=uuid4(),
                external_id="shared_ext_id",
            ),
        )
        repo.create(
            IntegrationMappingCreate(
                integration_id=integration.id,
                mappable_type="invoice",
                mappable_id=uuid4(),
                external_id="shared_ext_id",
            ),
        )
        results = repo.get_by_external_id(integration.id, "shared_ext_id")
        assert len(results) == 2

    def test_get_by_external_id_not_found(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        results = repo.get_by_external_id(integration.id, "nonexistent")
        assert len(results) == 0

    def test_get_all(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        for i in range(3):
            repo.create(
                IntegrationMappingCreate(
                    integration_id=integration.id,
                    mappable_type="customer",
                    mappable_id=uuid4(),
                    external_id=f"ext_{i}",
                ),
            )
        mappings = repo.get_all(integration.id)
        assert len(mappings) == 3

    def test_get_all_pagination(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        for i in range(5):
            repo.create(
                IntegrationMappingCreate(
                    integration_id=integration.id,
                    mappable_type="customer",
                    mappable_id=uuid4(),
                    external_id=f"ext_page_{i}",
                ),
            )
        mappings = repo.get_all(integration.id, skip=2, limit=2)
        assert len(mappings) == 2

    def test_get_all_empty(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        # Use a random integration id that has no mappings
        mappings = repo.get_all(uuid4())
        assert len(mappings) == 0

    def test_update_mapping(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        mapping = repo.create(
            IntegrationMappingCreate(
                integration_id=integration.id,
                mappable_type="customer",
                mappable_id=uuid4(),
                external_id="old_ext",
            ),
        )
        updated = repo.update(
            mapping.id,
            IntegrationMappingUpdate(
                external_id="new_ext",
                external_data={"updated": True},
            ),
        )
        assert updated is not None
        assert updated.external_id == "new_ext"
        assert updated.external_data == {"updated": True}

    def test_update_mapping_partial(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        mapping = repo.create(
            IntegrationMappingCreate(
                integration_id=integration.id,
                mappable_type="customer",
                mappable_id=uuid4(),
                external_id="keep_me",
                external_data={"original": True},
            ),
        )
        updated = repo.update(
            mapping.id,
            IntegrationMappingUpdate(external_data={"changed": True}),
        )
        assert updated is not None
        assert updated.external_id == "keep_me"
        assert updated.external_data == {"changed": True}

    def test_update_mapping_not_found(self, db_session):
        repo = IntegrationMappingRepository(db_session)
        result = repo.update(uuid4(), IntegrationMappingUpdate(external_id="x"))
        assert result is None

    def test_delete_mapping(self, db_session, integration):
        repo = IntegrationMappingRepository(db_session)
        mapping = repo.create(
            IntegrationMappingCreate(
                integration_id=integration.id,
                mappable_type="customer",
                mappable_id=uuid4(),
                external_id="del_me",
            ),
        )
        assert repo.delete(mapping.id) is True
        assert repo.get_by_id(mapping.id) is None

    def test_delete_mapping_not_found(self, db_session):
        repo = IntegrationMappingRepository(db_session)
        assert repo.delete(uuid4()) is False


# ─────────────────────────────────────────────────────────────────────────────
# IntegrationCustomer Repository Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationCustomerRepository:
    """Tests for IntegrationCustomerRepository CRUD and query methods."""

    def test_create_integration_customer(self, db_session, integration, customer):
        repo = IntegrationCustomerRepository(db_session)
        ic = repo.create(
            IntegrationCustomerCreate(
                integration_id=integration.id,
                customer_id=customer.id,
                external_customer_id="stripe_cus_123",
                settings={"auto_sync": True},
            ),
        )
        assert ic.id is not None
        assert ic.integration_id == integration.id
        assert ic.customer_id == customer.id
        assert ic.external_customer_id == "stripe_cus_123"
        assert ic.settings == {"auto_sync": True}

    def test_create_integration_customer_minimal(self, db_session, integration, customer):
        repo = IntegrationCustomerRepository(db_session)
        ic = repo.create(
            IntegrationCustomerCreate(
                integration_id=integration.id,
                customer_id=customer.id,
                external_customer_id="stripe_cus_456",
            ),
        )
        assert ic.id is not None
        assert ic.settings is None

    def test_get_by_id(self, db_session, integration, customer):
        repo = IntegrationCustomerRepository(db_session)
        ic = repo.create(
            IntegrationCustomerCreate(
                integration_id=integration.id,
                customer_id=customer.id,
                external_customer_id="stripe_cus_789",
            ),
        )
        fetched = repo.get_by_id(ic.id)
        assert fetched is not None
        assert fetched.id == ic.id

    def test_get_by_id_not_found(self, db_session):
        repo = IntegrationCustomerRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_customer(self, db_session, integration, customer):
        repo = IntegrationCustomerRepository(db_session)
        repo.create(
            IntegrationCustomerCreate(
                integration_id=integration.id,
                customer_id=customer.id,
                external_customer_id="ext_cus_by_customer",
            ),
        )
        fetched = repo.get_by_customer(integration.id, customer.id)
        assert fetched is not None
        assert fetched.external_customer_id == "ext_cus_by_customer"

    def test_get_by_customer_not_found(self, db_session, integration):
        repo = IntegrationCustomerRepository(db_session)
        fetched = repo.get_by_customer(integration.id, uuid4())
        assert fetched is None

    def test_get_by_external_customer_id(self, db_session, integration, customer):
        repo = IntegrationCustomerRepository(db_session)
        repo.create(
            IntegrationCustomerCreate(
                integration_id=integration.id,
                customer_id=customer.id,
                external_customer_id="ext_lookup_id",
            ),
        )
        fetched = repo.get_by_external_customer_id(integration.id, "ext_lookup_id")
        assert fetched is not None
        assert fetched.customer_id == customer.id

    def test_get_by_external_customer_id_not_found(self, db_session, integration):
        repo = IntegrationCustomerRepository(db_session)
        fetched = repo.get_by_external_customer_id(integration.id, "nonexistent")
        assert fetched is None

    def test_get_all(self, db_session, integration):
        repo = IntegrationCustomerRepository(db_session)
        customer_repo = CustomerRepository(db_session)
        for i in range(3):
            cust = customer_repo.create(
                CustomerCreate(
                    external_id=f"ic_all_cust_{uuid4()}",
                    name=f"Customer {i}",
                ),
                DEFAULT_ORG_ID,
            )
            repo.create(
                IntegrationCustomerCreate(
                    integration_id=integration.id,
                    customer_id=cust.id,
                    external_customer_id=f"ext_all_{i}",
                ),
            )
        results = repo.get_all(integration.id)
        assert len(results) == 3

    def test_get_all_pagination(self, db_session, integration):
        repo = IntegrationCustomerRepository(db_session)
        customer_repo = CustomerRepository(db_session)
        for i in range(5):
            cust = customer_repo.create(
                CustomerCreate(
                    external_id=f"ic_page_cust_{uuid4()}",
                    name=f"Customer {i}",
                ),
                DEFAULT_ORG_ID,
            )
            repo.create(
                IntegrationCustomerCreate(
                    integration_id=integration.id,
                    customer_id=cust.id,
                    external_customer_id=f"ext_page_{i}",
                ),
            )
        results = repo.get_all(integration.id, skip=2, limit=2)
        assert len(results) == 2

    def test_get_all_empty(self, db_session):
        repo = IntegrationCustomerRepository(db_session)
        results = repo.get_all(uuid4())
        assert len(results) == 0

    def test_update_integration_customer(self, db_session, integration, customer):
        repo = IntegrationCustomerRepository(db_session)
        ic = repo.create(
            IntegrationCustomerCreate(
                integration_id=integration.id,
                customer_id=customer.id,
                external_customer_id="old_ext",
            ),
        )
        updated = repo.update(
            ic.id,
            IntegrationCustomerUpdate(
                external_customer_id="new_ext",
                settings={"updated": True},
            ),
        )
        assert updated is not None
        assert updated.external_customer_id == "new_ext"
        assert updated.settings == {"updated": True}

    def test_update_integration_customer_partial(self, db_session, integration, customer):
        repo = IntegrationCustomerRepository(db_session)
        ic = repo.create(
            IntegrationCustomerCreate(
                integration_id=integration.id,
                customer_id=customer.id,
                external_customer_id="keep_ext",
                settings={"original": True},
            ),
        )
        updated = repo.update(
            ic.id,
            IntegrationCustomerUpdate(settings={"changed": True}),
        )
        assert updated is not None
        assert updated.external_customer_id == "keep_ext"
        assert updated.settings == {"changed": True}

    def test_update_integration_customer_not_found(self, db_session):
        repo = IntegrationCustomerRepository(db_session)
        result = repo.update(uuid4(), IntegrationCustomerUpdate(external_customer_id="x"))
        assert result is None

    def test_delete_integration_customer(self, db_session, integration, customer):
        repo = IntegrationCustomerRepository(db_session)
        ic = repo.create(
            IntegrationCustomerCreate(
                integration_id=integration.id,
                customer_id=customer.id,
                external_customer_id="del_me",
            ),
        )
        assert repo.delete(ic.id) is True
        assert repo.get_by_id(ic.id) is None

    def test_delete_integration_customer_not_found(self, db_session):
        repo = IntegrationCustomerRepository(db_session)
        assert repo.delete(uuid4()) is False


# ─────────────────────────────────────────────────────────────────────────────
# Schema Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationSchemas:
    """Tests for Pydantic integration schemas."""

    def test_create_defaults(self):
        schema = IntegrationCreate(
            integration_type="payment_provider",
            provider_type="stripe",
        )
        assert schema.status == "active"
        assert schema.settings == {}

    def test_create_all_fields(self):
        schema = IntegrationCreate(
            integration_type="accounting",
            provider_type="netsuite",
            status="inactive",
            settings={"account_id": "123"},
        )
        assert schema.integration_type == "accounting"
        assert schema.provider_type == "netsuite"
        assert schema.status == "inactive"
        assert schema.settings == {"account_id": "123"}

    def test_update_all_optional(self):
        schema = IntegrationUpdate()
        assert schema.status is None
        assert schema.settings is None
        assert schema.error_details is None

    def test_response_from_model(self, db_session, integration):
        response = IntegrationResponse.model_validate(integration)
        assert response.id == integration.id
        assert response.organization_id == DEFAULT_ORG_ID
        assert response.integration_type == "payment_provider"
        assert response.provider_type == "stripe"
        assert response.status == "active"
        assert response.settings == {"api_key": "sk_test_123"}


class TestIntegrationMappingSchemas:
    """Tests for Pydantic integration mapping schemas."""

    def test_create_all_fields(self):
        iid = uuid4()
        mid = uuid4()
        schema = IntegrationMappingCreate(
            integration_id=iid,
            mappable_type="customer",
            mappable_id=mid,
            external_id="ext_123",
            external_data={"key": "value"},
        )
        assert schema.integration_id == iid
        assert schema.mappable_type == "customer"
        assert schema.mappable_id == mid
        assert schema.external_id == "ext_123"
        assert schema.external_data == {"key": "value"}

    def test_create_minimal(self):
        schema = IntegrationMappingCreate(
            integration_id=uuid4(),
            mappable_type="invoice",
            mappable_id=uuid4(),
            external_id="inv_1",
        )
        assert schema.external_data is None

    def test_update_all_optional(self):
        schema = IntegrationMappingUpdate()
        assert schema.external_id is None
        assert schema.external_data is None
        assert schema.last_synced_at is None

    def test_response_from_model(self, db_session, integration):
        mapping_repo = IntegrationMappingRepository(db_session)
        mapping = mapping_repo.create(
            IntegrationMappingCreate(
                integration_id=integration.id,
                mappable_type="customer",
                mappable_id=uuid4(),
                external_id="ext_resp",
            ),
        )
        response = IntegrationMappingResponse.model_validate(mapping)
        assert response.id == mapping.id
        assert response.integration_id == integration.id
        assert response.mappable_type == "customer"
        assert response.external_id == "ext_resp"


class TestIntegrationCustomerSchemas:
    """Tests for Pydantic integration customer schemas."""

    def test_create_all_fields(self):
        iid = uuid4()
        cid = uuid4()
        schema = IntegrationCustomerCreate(
            integration_id=iid,
            customer_id=cid,
            external_customer_id="stripe_cus_1",
            settings={"sync": True},
        )
        assert schema.integration_id == iid
        assert schema.customer_id == cid
        assert schema.external_customer_id == "stripe_cus_1"
        assert schema.settings == {"sync": True}

    def test_create_minimal(self):
        schema = IntegrationCustomerCreate(
            integration_id=uuid4(),
            customer_id=uuid4(),
            external_customer_id="ext_1",
        )
        assert schema.settings is None

    def test_update_all_optional(self):
        schema = IntegrationCustomerUpdate()
        assert schema.external_customer_id is None
        assert schema.settings is None

    def test_response_from_model(self, db_session, integration, customer):
        ic_repo = IntegrationCustomerRepository(db_session)
        ic = ic_repo.create(
            IntegrationCustomerCreate(
                integration_id=integration.id,
                customer_id=customer.id,
                external_customer_id="resp_ext",
            ),
        )
        response = IntegrationCustomerResponse.model_validate(ic)
        assert response.id == ic.id
        assert response.integration_id == integration.id
        assert response.customer_id == customer.id
        assert response.external_customer_id == "resp_ext"


# ─────────────────────────────────────────────────────────────────────────────
# Integration API Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationAPI:
    """Tests for integration API endpoints."""

    def test_create_integration(self, client):
        """Test POST /v1/integrations."""
        response = client.post(
            "/v1/integrations/",
            json={
                "integration_type": "accounting",
                "provider_type": "netsuite",
                "settings": {"account_id": "123"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["integration_type"] == "accounting"
        assert data["provider_type"] == "netsuite"
        assert data["status"] == "active"
        assert data["settings"] == {"account_id": "123"}
        assert data["id"] is not None
        assert data["organization_id"] is not None

    def test_create_integration_minimal(self, client):
        """Test POST /v1/integrations with minimal fields."""
        response = client.post(
            "/v1/integrations/",
            json={
                "integration_type": "crm",
                "provider_type": "hubspot",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["integration_type"] == "crm"
        assert data["provider_type"] == "hubspot"
        assert data["settings"] == {}

    def test_create_integration_duplicate_provider(self, client):
        """Test POST /v1/integrations with duplicate provider returns 409."""
        payload = {
            "integration_type": "accounting",
            "provider_type": "xero",
        }
        response1 = client.post("/v1/integrations/", json=payload)
        assert response1.status_code == 201

        response2 = client.post("/v1/integrations/", json=payload)
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"]

    def test_create_integration_invalid_data(self, client):
        """Test POST /v1/integrations with missing required fields."""
        response = client.post(
            "/v1/integrations/",
            json={"integration_type": "accounting"},
        )
        assert response.status_code == 422

    def test_list_integrations(self, client, db_session):
        """Test GET /v1/integrations."""
        repo = IntegrationRepository(db_session)
        repo.create(
            IntegrationCreate(integration_type="accounting", provider_type="netsuite"),
            DEFAULT_ORG_ID,
        )
        repo.create(
            IntegrationCreate(integration_type="crm", provider_type="hubspot"),
            DEFAULT_ORG_ID,
        )

        response = client.get("/v1/integrations/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_integrations_empty(self, client):
        """Test GET /v1/integrations when empty."""
        response = client.get("/v1/integrations/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_integrations_pagination(self, client, db_session):
        """Test GET /v1/integrations with pagination."""
        repo = IntegrationRepository(db_session)
        providers = ["netsuite", "xero", "hubspot", "salesforce", "anrok"]
        for p in providers:
            repo.create(
                IntegrationCreate(integration_type="accounting", provider_type=p),
                DEFAULT_ORG_ID,
            )

        response = client.get("/v1/integrations/?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_integration(self, client, db_session):
        """Test GET /v1/integrations/{id}."""
        repo = IntegrationRepository(db_session)
        integration = repo.create(
            IntegrationCreate(
                integration_type="accounting",
                provider_type="netsuite",
                settings={"key": "val"},
            ),
            DEFAULT_ORG_ID,
        )

        response = client.get(f"/v1/integrations/{integration.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["provider_type"] == "netsuite"
        assert data["settings"] == {"key": "val"}

    def test_get_integration_not_found(self, client):
        """Test GET /v1/integrations/{id} for non-existent integration."""
        response = client.get(f"/v1/integrations/{uuid4()}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_integration(self, client, db_session):
        """Test PUT /v1/integrations/{id}."""
        repo = IntegrationRepository(db_session)
        integration = repo.create(
            IntegrationCreate(
                integration_type="accounting",
                provider_type="netsuite",
                settings={"old_key": "old_val"},
            ),
            DEFAULT_ORG_ID,
        )

        response = client.put(
            f"/v1/integrations/{integration.id}",
            json={
                "status": "inactive",
                "settings": {"new_key": "new_val"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "inactive"
        assert data["settings"] == {"new_key": "new_val"}

    def test_update_integration_partial(self, client, db_session):
        """Test PUT /v1/integrations/{id} with partial update."""
        repo = IntegrationRepository(db_session)
        integration = repo.create(
            IntegrationCreate(
                integration_type="crm",
                provider_type="hubspot",
                settings={"api_key": "abc"},
            ),
            DEFAULT_ORG_ID,
        )

        response = client.put(
            f"/v1/integrations/{integration.id}",
            json={"status": "error"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["settings"] == {"api_key": "abc"}

    def test_update_integration_not_found(self, client):
        """Test PUT /v1/integrations/{id} for non-existent integration."""
        response = client.put(
            f"/v1/integrations/{uuid4()}",
            json={"status": "inactive"},
        )
        assert response.status_code == 404

    def test_delete_integration(self, client, db_session):
        """Test DELETE /v1/integrations/{id}."""
        repo = IntegrationRepository(db_session)
        integration = repo.create(
            IntegrationCreate(
                integration_type="accounting",
                provider_type="netsuite",
            ),
            DEFAULT_ORG_ID,
        )

        response = client.delete(f"/v1/integrations/{integration.id}")
        assert response.status_code == 204

        # Verify it's gone
        assert repo.get_by_id(integration.id) is None

    def test_delete_integration_not_found(self, client):
        """Test DELETE /v1/integrations/{id} for non-existent integration."""
        response = client.delete(f"/v1/integrations/{uuid4()}")
        assert response.status_code == 404

    def test_test_connection(self, client, db_session):
        """Test POST /v1/integrations/{id}/test with a supported adapter."""
        repo = IntegrationRepository(db_session)
        integration = repo.create(
            IntegrationCreate(
                integration_type="accounting",
                provider_type="netsuite",
                settings={"account_id": "test123"},
            ),
            DEFAULT_ORG_ID,
        )

        response = client.post(f"/v1/integrations/{integration.id}/test")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["error"] is None

    def test_test_connection_not_found(self, client):
        """Test POST /v1/integrations/{id}/test for non-existent integration."""
        response = client.post(f"/v1/integrations/{uuid4()}/test")
        assert response.status_code == 404

    def test_test_connection_unsupported_adapter(self, client, db_session):
        """Test POST /v1/integrations/{id}/test with unsupported provider returns 422."""
        repo = IntegrationRepository(db_session)
        integration = repo.create(
            IntegrationCreate(
                integration_type="payment_provider",
                provider_type="stripe",
            ),
            DEFAULT_ORG_ID,
        )

        response = client.post(f"/v1/integrations/{integration.id}/test")
        assert response.status_code == 422
        assert "No adapter registered" in response.json()["detail"]
