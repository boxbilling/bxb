"""PaymentMethod model, schema, and repository tests."""

import uuid

import pytest

from app.core.database import get_db
from app.models.customer import Customer
from app.models.shared import generate_uuid
from app.models.organization import Organization
from app.models.payment_method import PaymentMethod
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.schemas.payment_method import (
    PaymentMethodCreate,
    PaymentMethodResponse,
    PaymentMethodUpdate,
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


@pytest.fixture
def customer(db_session):
    """Create a customer for testing."""
    c = Customer(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        external_id="cust-test-pm-001",
        name="Test Customer",
        email="test@example.com",
        currency="USD",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def second_customer(db_session):
    """Create a second customer for testing."""
    c = Customer(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        external_id="cust-test-pm-002",
        name="Second Customer",
        email="second@example.com",
        currency="USD",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


class TestPaymentMethodModel:
    def test_payment_method_defaults(self, db_session, customer):
        """Test PaymentMethod model default values."""
        pm = PaymentMethod(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_abc123",
            type="card",
        )
        db_session.add(pm)
        db_session.commit()
        db_session.refresh(pm)

        assert pm.id is not None
        assert pm.organization_id == DEFAULT_ORG_ID
        assert pm.customer_id == customer.id
        assert pm.provider == "stripe"
        assert pm.provider_payment_method_id == "pm_abc123"
        assert pm.type == "card"
        assert pm.is_default is False
        assert pm.details == {}
        assert pm.created_at is not None
        assert pm.updated_at is not None

    def test_payment_method_with_all_fields(self, db_session, customer):
        """Test PaymentMethod with all fields set."""
        details = {"last4": "4242", "brand": "visa", "exp_month": 12, "exp_year": 2027}
        pm = PaymentMethod(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_full123",
            type="card",
            is_default=True,
            details=details,
        )
        db_session.add(pm)
        db_session.commit()
        db_session.refresh(pm)

        assert pm.is_default is True
        assert pm.details["last4"] == "4242"
        assert pm.details["brand"] == "visa"
        assert pm.details["exp_month"] == 12
        assert pm.details["exp_year"] == 2027

    def test_payment_method_customer_id_stored(self, db_session, customer):
        """Test that customer_id is correctly persisted."""
        pm = PaymentMethod(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_custid",
            type="card",
        )
        db_session.add(pm)
        db_session.commit()
        db_session.refresh(pm)

        assert pm.customer_id == customer.id

    def test_payment_method_multiple_for_same_customer(self, db_session, customer):
        """Test that a customer can have multiple payment methods."""
        pm1 = PaymentMethod(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_multi_1",
            type="card",
        )
        pm2 = PaymentMethod(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_multi_2",
            type="bank_account",
        )
        db_session.add(pm1)
        db_session.add(pm2)
        db_session.commit()

        results = (
            db_session.query(PaymentMethod)
            .filter(PaymentMethod.customer_id == customer.id)
            .all()
        )
        assert len(results) == 2


class TestPaymentMethodRepository:
    def test_create(self, db_session, customer):
        """Test creating a payment method."""
        repo = PaymentMethodRepository(db_session)
        data = PaymentMethodCreate(
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_create",
            type="card",
            details={"last4": "1234"},
        )
        pm = repo.create(data, DEFAULT_ORG_ID)

        assert pm.id is not None
        assert pm.organization_id == DEFAULT_ORG_ID
        assert pm.customer_id == customer.id
        assert pm.provider == "stripe"
        assert pm.provider_payment_method_id == "pm_create"
        assert pm.type == "card"
        assert pm.is_default is False
        assert pm.details == {"last4": "1234"}

    def test_create_with_default(self, db_session, customer):
        """Test creating a payment method with is_default=True."""
        repo = PaymentMethodRepository(db_session)
        data = PaymentMethodCreate(
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_default",
            type="card",
            is_default=True,
        )
        pm = repo.create(data, DEFAULT_ORG_ID)

        assert pm.is_default is True

    def test_get_by_id(self, db_session, customer):
        """Test getting a payment method by ID."""
        repo = PaymentMethodRepository(db_session)
        data = PaymentMethodCreate(
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_getid",
            type="card",
        )
        created = repo.create(data, DEFAULT_ORG_ID)

        found = repo.get_by_id(created.id, DEFAULT_ORG_ID)
        assert found is not None
        assert found.id == created.id

    def test_get_by_id_without_org(self, db_session, customer):
        """Test getting a payment method by ID without org filter."""
        repo = PaymentMethodRepository(db_session)
        data = PaymentMethodCreate(
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_noorg",
            type="card",
        )
        created = repo.create(data, DEFAULT_ORG_ID)

        found = repo.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id

    def test_get_by_id_wrong_org(self, db_session, customer, second_org):
        """Test that payment methods are scoped by organization."""
        repo = PaymentMethodRepository(db_session)
        data = PaymentMethodCreate(
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_wrongorg",
            type="card",
        )
        created = repo.create(data, DEFAULT_ORG_ID)

        result = repo.get_by_id(created.id, second_org.id)
        assert result is None

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent payment method."""
        repo = PaymentMethodRepository(db_session)
        result = repo.get_by_id(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is None

    def test_get_all(self, db_session, customer):
        """Test listing all payment methods for an organization."""
        repo = PaymentMethodRepository(db_session)
        for i in range(3):
            repo.create(
                PaymentMethodCreate(
                    customer_id=customer.id,
                    provider="stripe",
                    provider_payment_method_id=f"pm_all_{i}",
                    type="card",
                ),
                DEFAULT_ORG_ID,
            )

        methods = repo.get_all(DEFAULT_ORG_ID)
        assert len(methods) == 3

    def test_get_all_filter_by_customer(self, db_session, customer, second_customer):
        """Test listing payment methods filtered by customer_id."""
        repo = PaymentMethodRepository(db_session)
        repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_cust1",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )
        repo.create(
            PaymentMethodCreate(
                customer_id=second_customer.id,
                provider="stripe",
                provider_payment_method_id="pm_cust2",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )

        methods = repo.get_all(DEFAULT_ORG_ID, customer_id=customer.id)
        assert len(methods) == 1
        assert methods[0].customer_id == customer.id

    def test_get_all_pagination(self, db_session, customer):
        """Test pagination of payment method listing."""
        repo = PaymentMethodRepository(db_session)
        for i in range(5):
            repo.create(
                PaymentMethodCreate(
                    customer_id=customer.id,
                    provider="stripe",
                    provider_payment_method_id=f"pm_page_{i}",
                    type="card",
                ),
                DEFAULT_ORG_ID,
            )

        page = repo.get_all(DEFAULT_ORG_ID, skip=1, limit=2)
        assert len(page) == 2

    def test_get_all_empty(self, db_session, second_org):
        """Test listing payment methods for an org with none."""
        repo = PaymentMethodRepository(db_session)
        methods = repo.get_all(second_org.id)
        assert methods == []

    def test_get_by_customer_id(self, db_session, customer, second_customer):
        """Test getting payment methods by customer ID."""
        repo = PaymentMethodRepository(db_session)
        repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_bycust_1",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )
        repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_bycust_2",
                type="bank_account",
            ),
            DEFAULT_ORG_ID,
        )
        repo.create(
            PaymentMethodCreate(
                customer_id=second_customer.id,
                provider="stripe",
                provider_payment_method_id="pm_bycust_3",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )

        methods = repo.get_by_customer_id(customer.id, DEFAULT_ORG_ID)
        assert len(methods) == 2
        assert all(m.customer_id == customer.id for m in methods)

    def test_get_by_customer_id_empty(self, db_session, customer):
        """Test getting payment methods for customer with none."""
        repo = PaymentMethodRepository(db_session)
        methods = repo.get_by_customer_id(customer.id, DEFAULT_ORG_ID)
        assert methods == []

    def test_get_default(self, db_session, customer):
        """Test getting the default payment method for a customer."""
        repo = PaymentMethodRepository(db_session)
        repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_nondefault",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )
        repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_thedefault",
                type="card",
                is_default=True,
            ),
            DEFAULT_ORG_ID,
        )

        default = repo.get_default(customer.id, DEFAULT_ORG_ID)
        assert default is not None
        assert default.provider_payment_method_id == "pm_thedefault"
        assert default.is_default is True

    def test_get_default_none(self, db_session, customer):
        """Test getting default when no default exists."""
        repo = PaymentMethodRepository(db_session)
        repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_nodef",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )

        default = repo.get_default(customer.id, DEFAULT_ORG_ID)
        assert default is None

    def test_set_default(self, db_session, customer):
        """Test setting a payment method as default."""
        repo = PaymentMethodRepository(db_session)
        pm1 = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_sd_1",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )
        pm2 = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_sd_2",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )

        result = repo.set_default(pm1.id)
        assert result is not None
        assert result.is_default is True

        # Verify pm2 is not default
        db_session.refresh(pm2)
        assert pm2.is_default is False

    def test_set_default_unsets_previous(self, db_session, customer):
        """Test that setting a new default unsets the previous one."""
        repo = PaymentMethodRepository(db_session)
        pm1 = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_unset_1",
                type="card",
                is_default=True,
            ),
            DEFAULT_ORG_ID,
        )
        pm2 = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_unset_2",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )

        assert pm1.is_default is True
        assert pm2.is_default is False

        repo.set_default(pm2.id)

        db_session.refresh(pm1)
        db_session.refresh(pm2)
        assert pm1.is_default is False
        assert pm2.is_default is True

    def test_set_default_not_found(self, db_session):
        """Test setting default for non-existent payment method."""
        repo = PaymentMethodRepository(db_session)
        result = repo.set_default(uuid.uuid4())
        assert result is None

    def test_set_default_does_not_affect_other_customers(self, db_session, customer, second_customer):
        """Test that set_default only affects the same customer."""
        repo = PaymentMethodRepository(db_session)
        pm_cust1 = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_iso_1",
                type="card",
                is_default=True,
            ),
            DEFAULT_ORG_ID,
        )
        pm_cust2 = repo.create(
            PaymentMethodCreate(
                customer_id=second_customer.id,
                provider="stripe",
                provider_payment_method_id="pm_iso_2",
                type="card",
                is_default=True,
            ),
            DEFAULT_ORG_ID,
        )

        # Set a new default for customer 1
        pm_cust1_new = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_iso_3",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )
        repo.set_default(pm_cust1_new.id)

        db_session.refresh(pm_cust1)
        db_session.refresh(pm_cust2)
        db_session.refresh(pm_cust1_new)

        assert pm_cust1.is_default is False
        assert pm_cust1_new.is_default is True
        assert pm_cust2.is_default is True  # Unaffected

    def test_update(self, db_session, customer):
        """Test updating a payment method."""
        repo = PaymentMethodRepository(db_session)
        pm = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_upd",
                type="card",
                details={"last4": "1111"},
            ),
            DEFAULT_ORG_ID,
        )

        updated = repo.update(
            pm.id,
            PaymentMethodUpdate(details={"last4": "2222", "brand": "mastercard"}),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.details == {"last4": "2222", "brand": "mastercard"}

    def test_update_partial(self, db_session, customer):
        """Test partial update only changes specified fields."""
        repo = PaymentMethodRepository(db_session)
        pm = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_partial",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )

        updated = repo.update(
            pm.id,
            PaymentMethodUpdate(type="bank_account"),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.type == "bank_account"
        assert updated.provider == "stripe"  # Unchanged

    def test_update_not_found(self, db_session):
        """Test updating a non-existent payment method."""
        repo = PaymentMethodRepository(db_session)
        result = repo.update(
            uuid.uuid4(),
            PaymentMethodUpdate(type="card"),
            DEFAULT_ORG_ID,
        )
        assert result is None

    def test_update_wrong_org(self, db_session, customer, second_org):
        """Test updating a payment method from wrong org."""
        repo = PaymentMethodRepository(db_session)
        pm = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_worg",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )

        result = repo.update(pm.id, PaymentMethodUpdate(type="bank_account"), second_org.id)
        assert result is None

    def test_delete(self, db_session, customer):
        """Test deleting a payment method."""
        repo = PaymentMethodRepository(db_session)
        pm = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_del",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )

        result = repo.delete(pm.id, DEFAULT_ORG_ID)
        assert result is True

        found = repo.get_by_id(pm.id, DEFAULT_ORG_ID)
        assert found is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent payment method."""
        repo = PaymentMethodRepository(db_session)
        result = repo.delete(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is False

    def test_delete_wrong_org(self, db_session, customer, second_org):
        """Test deleting a payment method from wrong org."""
        repo = PaymentMethodRepository(db_session)
        pm = repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_delworg",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )

        result = repo.delete(pm.id, second_org.id)
        assert result is False

        # Verify it still exists
        found = repo.get_by_id(pm.id, DEFAULT_ORG_ID)
        assert found is not None


class TestPaymentMethodSchemas:
    def test_create_schema(self):
        """Test PaymentMethodCreate schema validation."""
        schema = PaymentMethodCreate(
            customer_id=uuid.uuid4(),
            provider="stripe",
            provider_payment_method_id="pm_test",
            type="card",
        )
        assert schema.is_default is False
        assert schema.details == {}

    def test_create_schema_with_all_fields(self):
        """Test PaymentMethodCreate with all fields."""
        cid = uuid.uuid4()
        schema = PaymentMethodCreate(
            customer_id=cid,
            provider="gocardless",
            provider_payment_method_id="ba_test",
            type="direct_debit",
            is_default=True,
            details={"last4": "5678"},
        )
        assert schema.customer_id == cid
        assert schema.provider == "gocardless"
        assert schema.is_default is True
        assert schema.details == {"last4": "5678"}

    def test_update_schema_partial(self):
        """Test PaymentMethodUpdate with partial fields."""
        schema = PaymentMethodUpdate(type="bank_account")
        dumped = schema.model_dump(exclude_unset=True)
        assert dumped == {"type": "bank_account"}

    def test_update_schema_empty(self):
        """Test PaymentMethodUpdate with no fields set."""
        schema = PaymentMethodUpdate()
        dumped = schema.model_dump(exclude_unset=True)
        assert dumped == {}

    def test_response_schema_from_model(self, db_session, customer):
        """Test PaymentMethodResponse from ORM model."""
        pm = PaymentMethod(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_resp",
            type="card",
            is_default=False,
            details={"last4": "9999"},
        )
        db_session.add(pm)
        db_session.commit()
        db_session.refresh(pm)

        response = PaymentMethodResponse.model_validate(pm)
        assert response.id == pm.id
        assert response.organization_id == DEFAULT_ORG_ID
        assert response.customer_id == customer.id
        assert response.provider == "stripe"
        assert response.provider_payment_method_id == "pm_resp"
        assert response.type == "card"
        assert response.is_default is False
        assert response.details == {"last4": "9999"}
        assert response.created_at is not None
        assert response.updated_at is not None
