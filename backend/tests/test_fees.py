"""Tests for Fee API endpoints."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.fee import FeePaymentStatus, FeeType
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.customer import CustomerCreate
from app.schemas.fee import FeeCreate, FeeUpdate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
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
def customer(db_session):
    """Create a test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"fee_test_cust_{uuid4()}",
            name="Fee Test Customer",
            email="fee@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"fee_test_plan_{uuid4()}",
            name="Fee Test Plan",
            interval="monthly",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def subscription(db_session, customer, plan):
    """Create a test subscription."""
    repo = SubscriptionRepository(db_session)
    return repo.create(
        SubscriptionCreate(
            external_id=f"fee_test_sub_{uuid4()}",
            customer_id=customer.id,
            plan_id=plan.id,
        ),
        DEFAULT_ORG_ID,
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
def fee(db_session, customer, invoice):
    """Create a test fee."""
    repo = FeeRepository(db_session)
    return repo.create(
        FeeCreate(
            customer_id=customer.id,
            invoice_id=invoice.id,
            fee_type=FeeType.CHARGE,
            amount_cents=Decimal("10000"),
            total_amount_cents=Decimal("10000"),
            units=Decimal("100"),
            events_count=50,
            unit_amount_cents=Decimal("100"),
            description="API calls charge",
            metric_code="api_calls",
        )
    )


class TestFeeRepository:
    """Tests for FeeRepository CRUD and query methods."""

    def test_create_fee(self, db_session, customer, invoice):
        repo = FeeRepository(db_session)
        fee = repo.create(
            FeeCreate(
                customer_id=customer.id,
                invoice_id=invoice.id,
                fee_type=FeeType.CHARGE,
                amount_cents=Decimal("5000"),
                total_amount_cents=Decimal("5000"),
                units=Decimal("10"),
                events_count=10,
                unit_amount_cents=Decimal("500"),
                description="Test charge",
                metric_code="test_metric",
            )
        )
        assert fee.id is not None
        assert fee.customer_id == customer.id
        assert fee.invoice_id == invoice.id
        assert fee.fee_type == FeeType.CHARGE.value
        assert fee.amount_cents == Decimal("5000")
        assert fee.payment_status == FeePaymentStatus.PENDING.value

    def test_create_fee_minimal(self, db_session, customer):
        """Test creating a fee with only required fields."""
        repo = FeeRepository(db_session)
        fee = repo.create(FeeCreate(customer_id=customer.id))
        assert fee.id is not None
        assert fee.customer_id == customer.id
        assert fee.invoice_id is None
        assert fee.fee_type == FeeType.CHARGE.value
        assert fee.amount_cents == Decimal("0")

    def test_create_bulk(self, db_session, customer, invoice):
        repo = FeeRepository(db_session)
        fees_data = [
            FeeCreate(
                customer_id=customer.id,
                invoice_id=invoice.id,
                fee_type=FeeType.CHARGE,
                amount_cents=Decimal("1000"),
                total_amount_cents=Decimal("1000"),
                description=f"Charge {i}",
            )
            for i in range(3)
        ]
        fees = repo.create_bulk(fees_data)
        assert len(fees) == 3
        for f in fees:
            assert f.id is not None
            assert f.customer_id == customer.id

    def test_get_by_id(self, db_session, fee):
        repo = FeeRepository(db_session)
        fetched = repo.get_by_id(fee.id)
        assert fetched is not None
        assert fetched.id == fee.id

    def test_get_by_id_not_found(self, db_session):
        repo = FeeRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_invoice_id(self, db_session, fee, invoice):
        repo = FeeRepository(db_session)
        fees = repo.get_by_invoice_id(invoice.id)
        assert len(fees) == 1
        assert fees[0].id == fee.id

    def test_get_by_customer_id(self, db_session, fee, customer):
        repo = FeeRepository(db_session)
        fees = repo.get_by_customer_id(customer.id)
        assert len(fees) == 1
        assert fees[0].id == fee.id

    def test_get_by_subscription_id(self, db_session, customer, invoice, subscription):
        repo = FeeRepository(db_session)
        fee = repo.create(
            FeeCreate(
                customer_id=customer.id,
                invoice_id=invoice.id,
                subscription_id=subscription.id,
                fee_type=FeeType.SUBSCRIPTION,
                amount_cents=Decimal("2999"),
                total_amount_cents=Decimal("2999"),
            )
        )
        fees = repo.get_by_subscription_id(subscription.id)
        assert len(fees) == 1
        assert fees[0].id == fee.id

    def test_get_all_with_filters(self, db_session, customer, invoice):
        repo = FeeRepository(db_session)

        # Create fees with different types
        repo.create(
            FeeCreate(
                customer_id=customer.id,
                invoice_id=invoice.id,
                fee_type=FeeType.CHARGE,
                amount_cents=Decimal("1000"),
                total_amount_cents=Decimal("1000"),
            )
        )
        repo.create(
            FeeCreate(
                customer_id=customer.id,
                invoice_id=invoice.id,
                fee_type=FeeType.SUBSCRIPTION,
                amount_cents=Decimal("2000"),
                total_amount_cents=Decimal("2000"),
            )
        )

        # Test fee_type filter
        charges = repo.get_all(fee_type=FeeType.CHARGE)
        assert len(charges) == 1

        subs = repo.get_all(fee_type=FeeType.SUBSCRIPTION)
        assert len(subs) == 1

        # Test all
        all_fees = repo.get_all()
        assert len(all_fees) == 2

    def test_get_all_with_subscription_filter(self, db_session, customer, invoice, subscription):
        repo = FeeRepository(db_session)
        fee = repo.create(
            FeeCreate(
                customer_id=customer.id,
                invoice_id=invoice.id,
                subscription_id=subscription.id,
                fee_type=FeeType.CHARGE,
                amount_cents=Decimal("1000"),
                total_amount_cents=Decimal("1000"),
            )
        )
        # Filter by subscription_id
        results = repo.get_all(subscription_id=subscription.id)
        assert len(results) == 1
        assert results[0].id == fee.id

        # No match
        results = repo.get_all(subscription_id=uuid4())
        assert len(results) == 0

    def test_get_all_with_charge_filter(self, db_session, customer, invoice):
        repo = FeeRepository(db_session)

        # Create a charge to use as FK
        from app.models.billable_metric import BillableMetric
        from app.models.charge import Charge, ChargeModel
        from app.repositories.plan_repository import PlanRepository
        from app.schemas.plan import PlanCreate

        plan_repo = PlanRepository(db_session)
        plan = plan_repo.create(PlanCreate(code=f"fee_charge_plan_{uuid4()}", name="Test", interval="monthly"), DEFAULT_ORG_ID)

        metric = BillableMetric(code=f"fee_test_metric_{uuid4()}", name="Test Metric", aggregation_type="count")
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        fee = repo.create(
            FeeCreate(
                customer_id=customer.id,
                invoice_id=invoice.id,
                charge_id=charge.id,
                fee_type=FeeType.CHARGE,
                amount_cents=Decimal("500"),
                total_amount_cents=Decimal("500"),
            )
        )
        # Filter by charge_id
        results = repo.get_all(charge_id=charge.id)
        assert len(results) == 1
        assert results[0].id == fee.id

        # No match
        results = repo.get_all(charge_id=uuid4())
        assert len(results) == 0

    def test_get_all_pagination(self, db_session, customer):
        repo = FeeRepository(db_session)
        for i in range(5):
            repo.create(
                FeeCreate(
                    customer_id=customer.id,
                    amount_cents=Decimal(str(i * 1000)),
                    total_amount_cents=Decimal(str(i * 1000)),
                )
            )

        fees = repo.get_all(skip=2, limit=2)
        assert len(fees) == 2

    def test_update_fee(self, db_session, fee):
        repo = FeeRepository(db_session)
        updated = repo.update(
            fee.id,
            FeeUpdate(
                payment_status=FeePaymentStatus.SUCCEEDED,
                description="Updated description",
            ),
        )
        assert updated is not None
        assert updated.payment_status == FeePaymentStatus.SUCCEEDED.value
        assert updated.description == "Updated description"

    def test_update_fee_not_found(self, db_session):
        repo = FeeRepository(db_session)
        assert repo.update(uuid4(), FeeUpdate(description="nope")) is None

    def test_delete_fee(self, db_session, fee):
        repo = FeeRepository(db_session)
        assert repo.delete(fee.id) is True
        assert repo.get_by_id(fee.id) is None

    def test_delete_fee_not_found(self, db_session):
        repo = FeeRepository(db_session)
        assert repo.delete(uuid4()) is False

    def test_mark_succeeded(self, db_session, fee):
        repo = FeeRepository(db_session)
        updated = repo.mark_succeeded(fee.id)
        assert updated is not None
        assert updated.payment_status == FeePaymentStatus.SUCCEEDED.value

    def test_mark_succeeded_not_found(self, db_session):
        repo = FeeRepository(db_session)
        assert repo.mark_succeeded(uuid4()) is None

    def test_mark_failed(self, db_session, fee):
        repo = FeeRepository(db_session)
        updated = repo.mark_failed(fee.id)
        assert updated is not None
        assert updated.payment_status == FeePaymentStatus.FAILED.value

    def test_mark_failed_not_found(self, db_session):
        repo = FeeRepository(db_session)
        assert repo.mark_failed(uuid4()) is None

    def test_payment_status_filter(self, db_session, customer):
        repo = FeeRepository(db_session)
        fee1 = repo.create(FeeCreate(customer_id=customer.id))
        fee2 = repo.create(FeeCreate(customer_id=customer.id))
        repo.mark_succeeded(fee1.id)

        pending = repo.get_all(payment_status=FeePaymentStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].id == fee2.id

        succeeded = repo.get_all(payment_status=FeePaymentStatus.SUCCEEDED)
        assert len(succeeded) == 1
        assert succeeded[0].id == fee1.id


class TestFeesAPI:
    """Tests for Fee API endpoints."""

    def test_list_fees_empty(self, client):
        response = client.get("/v1/fees/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_fees(self, client, db_session, fee):
        response = client.get("/v1/fees/")
        assert response.status_code == 200
        fees = response.json()
        assert len(fees) == 1
        assert fees[0]["id"] == str(fee.id)
        assert fees[0]["fee_type"] == "charge"
        assert fees[0]["payment_status"] == "pending"

    def test_list_fees_with_invoice_filter(self, client, db_session, fee, invoice):
        response = client.get(f"/v1/fees/?invoice_id={invoice.id}")
        assert response.status_code == 200
        fees = response.json()
        assert len(fees) == 1
        assert fees[0]["invoice_id"] == str(invoice.id)

    def test_list_fees_with_customer_filter(self, client, db_session, fee, customer):
        response = client.get(f"/v1/fees/?customer_id={customer.id}")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_fees_with_fee_type_filter(self, client, db_session, fee):
        response = client.get("/v1/fees/?fee_type=charge")
        assert response.status_code == 200
        assert len(response.json()) == 1

        response = client.get("/v1/fees/?fee_type=subscription")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_list_fees_with_payment_status_filter(self, client, db_session, fee):
        response = client.get("/v1/fees/?payment_status=pending")
        assert response.status_code == 200
        assert len(response.json()) == 1

        response = client.get("/v1/fees/?payment_status=succeeded")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_list_fees_with_no_match_filter(self, client, db_session, fee):
        response = client.get(f"/v1/fees/?customer_id={uuid4()}")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_list_fees_pagination(self, client, db_session, customer):
        repo = FeeRepository(db_session)
        for _ in range(5):
            repo.create(FeeCreate(customer_id=customer.id))

        response = client.get("/v1/fees/?skip=2&limit=2")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_fee(self, client, db_session, fee):
        response = client.get(f"/v1/fees/{fee.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(fee.id)
        assert data["fee_type"] == "charge"
        assert data["description"] == "API calls charge"
        assert data["metric_code"] == "api_calls"
        assert data["payment_status"] == "pending"
        assert data["events_count"] == 50

    def test_get_fee_not_found(self, client):
        response = client.get(f"/v1/fees/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Fee not found"

    def test_update_fee_payment_status(self, client, db_session, fee):
        response = client.put(
            f"/v1/fees/{fee.id}",
            json={"payment_status": "succeeded"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["payment_status"] == "succeeded"

    def test_update_fee_description(self, client, db_session, fee):
        response = client.put(
            f"/v1/fees/{fee.id}",
            json={"description": "Updated charge description"},
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Updated charge description"

    def test_update_fee_taxes(self, client, db_session, fee):
        response = client.put(
            f"/v1/fees/{fee.id}",
            json={
                "taxes_amount_cents": "1500",
                "total_amount_cents": "11500",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["taxes_amount_cents"]) == Decimal("1500")
        assert Decimal(data["total_amount_cents"]) == Decimal("11500")

    def test_update_fee_not_found(self, client):
        response = client.put(
            f"/v1/fees/{uuid4()}",
            json={"payment_status": "succeeded"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Fee not found"

    def test_fee_response_format(self, client, db_session, fee):
        """Verify the full response schema."""
        response = client.get(f"/v1/fees/{fee.id}")
        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields are present
        expected_fields = {
            "id", "invoice_id", "charge_id", "subscription_id", "customer_id",
            "fee_type", "amount_cents", "taxes_amount_cents", "total_amount_cents",
            "units", "events_count", "unit_amount_cents", "payment_status",
            "description", "metric_code", "properties", "created_at", "updated_at",
        }
        assert set(data.keys()) == expected_fields

    def test_list_fees_multiple_filters(self, client, db_session, customer, invoice):
        """Test combining multiple filters."""
        repo = FeeRepository(db_session)
        repo.create(
            FeeCreate(
                customer_id=customer.id,
                invoice_id=invoice.id,
                fee_type=FeeType.CHARGE,
                amount_cents=Decimal("1000"),
                total_amount_cents=Decimal("1000"),
            )
        )
        repo.create(
            FeeCreate(
                customer_id=customer.id,
                invoice_id=invoice.id,
                fee_type=FeeType.SUBSCRIPTION,
                amount_cents=Decimal("2000"),
                total_amount_cents=Decimal("2000"),
            )
        )

        # Filter by both customer and fee_type
        response = client.get(
            f"/v1/fees/?customer_id={customer.id}&fee_type=charge"
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["fee_type"] == "charge"
