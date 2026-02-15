"""Plan API tests for bxb."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.billable_metric import AggregationType, BillableMetric
from app.models.charge import Charge, ChargeModel
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.charge_repository import ChargeRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.charge import ChargeCreate, ChargeUpdate
from app.schemas.plan import PlanCreate
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


def create_test_metric(db_session, code: str = "api_calls") -> BillableMetric:
    """Helper to create a test billable metric."""
    metric = BillableMetric(
        code=code,
        name=f"Test Metric {code}",
        aggregation_type=AggregationType.COUNT.value,
    )
    db_session.add(metric)
    db_session.commit()
    db_session.refresh(metric)
    return metric


def create_test_plan(db_session, code: str = "test_plan") -> Plan:
    """Helper to create a test plan."""
    plan = Plan(
        code=code,
        name=f"Test Plan {code}",
        interval=PlanInterval.MONTHLY.value,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


class TestPlanInterval:
    def test_weekly(self):
        """Test WEEKLY interval."""
        assert PlanInterval.WEEKLY == "weekly"
        assert PlanInterval.WEEKLY.value == "weekly"

    def test_monthly(self):
        """Test MONTHLY interval."""
        assert PlanInterval.MONTHLY == "monthly"
        assert PlanInterval.MONTHLY.value == "monthly"

    def test_quarterly(self):
        """Test QUARTERLY interval."""
        assert PlanInterval.QUARTERLY == "quarterly"
        assert PlanInterval.QUARTERLY.value == "quarterly"

    def test_yearly(self):
        """Test YEARLY interval."""
        assert PlanInterval.YEARLY == "yearly"
        assert PlanInterval.YEARLY.value == "yearly"


class TestPlanModel:
    def test_plan_defaults(self, db_session):
        """Test Plan model default values."""
        plan = Plan(
            code="basic",
            name="Basic Plan",
            interval=PlanInterval.MONTHLY.value,
        )
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)

        assert plan.id is not None
        assert plan.code == "basic"
        assert plan.name == "Basic Plan"
        assert plan.interval == "monthly"
        assert plan.description is None
        assert plan.amount_cents == 0
        assert plan.currency == "USD"
        assert plan.trial_period_days == 0
        assert plan.created_at is not None
        assert plan.updated_at is not None


class TestPlanRepository:
    def test_get_by_code(self, db_session):
        """Test getting plan by code."""
        repo = PlanRepository(db_session)
        data = PlanCreate(
            code="pro",
            name="Pro Plan",
            interval=PlanInterval.MONTHLY,
            amount_cents=4999,
        )
        repo.create(data, DEFAULT_ORG_ID)

        plan = repo.get_by_code("pro", DEFAULT_ORG_ID)
        assert plan is not None
        assert plan.code == "pro"

        not_found = repo.get_by_code("nonexistent", DEFAULT_ORG_ID)
        assert not_found is None

    def test_code_exists(self, db_session):
        """Test checking if code exists."""
        repo = PlanRepository(db_session)
        data = PlanCreate(
            code="exists_test",
            name="Exists Test",
            interval=PlanInterval.MONTHLY,
        )
        repo.create(data, DEFAULT_ORG_ID)

        assert repo.code_exists("exists_test", DEFAULT_ORG_ID) is True
        assert repo.code_exists("not_exists", DEFAULT_ORG_ID) is False


class TestPlansAPI:
    def test_list_plans_empty(self, client: TestClient):
        """Test listing plans when none exist."""
        response = client.get("/v1/plans/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_plan_monthly(self, client: TestClient):
        """Test creating a monthly plan."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "starter",
                "name": "Starter Plan",
                "description": "Perfect for small teams",
                "interval": "monthly",
                "amount_cents": 2999,
                "currency": "USD",
                "trial_period_days": 14,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "starter"
        assert data["name"] == "Starter Plan"
        assert data["description"] == "Perfect for small teams"
        assert data["interval"] == "monthly"
        assert data["amount_cents"] == 2999
        assert data["currency"] == "USD"
        assert data["trial_period_days"] == 14
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_plan_weekly(self, client: TestClient):
        """Test creating a weekly plan."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "weekly_plan",
                "name": "Weekly Plan",
                "interval": "weekly",
                "amount_cents": 999,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["interval"] == "weekly"

    def test_create_plan_quarterly(self, client: TestClient):
        """Test creating a quarterly plan."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "quarterly_plan",
                "name": "Quarterly Plan",
                "interval": "quarterly",
                "amount_cents": 7999,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["interval"] == "quarterly"

    def test_create_plan_yearly(self, client: TestClient):
        """Test creating a yearly plan."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "yearly_plan",
                "name": "Yearly Plan",
                "interval": "yearly",
                "amount_cents": 29999,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["interval"] == "yearly"

    def test_create_plan_defaults(self, client: TestClient):
        """Test creating a plan with default values."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "default_plan",
                "name": "Default Plan",
                "interval": "monthly",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["amount_cents"] == 0
        assert data["currency"] == "USD"
        assert data["trial_period_days"] == 0
        assert data["description"] is None

    def test_create_plan_duplicate_code(self, client: TestClient):
        """Test creating a plan with duplicate code."""
        client.post(
            "/v1/plans/",
            json={
                "code": "dup_code",
                "name": "First Plan",
                "interval": "monthly",
            },
        )
        response = client.post(
            "/v1/plans/",
            json={
                "code": "dup_code",
                "name": "Second Plan",
                "interval": "monthly",
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Plan with this code already exists"

    def test_create_plan_invalid_interval(self, client: TestClient):
        """Test creating a plan with invalid interval."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "invalid_interval",
                "name": "Invalid Interval",
                "interval": "biweekly",
            },
        )
        assert response.status_code == 422

    def test_create_plan_empty_code(self, client: TestClient):
        """Test creating a plan with empty code."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "",
                "name": "Empty Code",
                "interval": "monthly",
            },
        )
        assert response.status_code == 422

    def test_create_plan_empty_name(self, client: TestClient):
        """Test creating a plan with empty name."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "empty_name",
                "name": "",
                "interval": "monthly",
            },
        )
        assert response.status_code == 422

    def test_create_plan_negative_amount(self, client: TestClient):
        """Test creating a plan with negative amount_cents."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "negative_amount",
                "name": "Negative Amount",
                "interval": "monthly",
                "amount_cents": -100,
            },
        )
        assert response.status_code == 422

    def test_create_plan_negative_trial(self, client: TestClient):
        """Test creating a plan with negative trial_period_days."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "negative_trial",
                "name": "Negative Trial",
                "interval": "monthly",
                "trial_period_days": -1,
            },
        )
        assert response.status_code == 422

    def test_create_plan_invalid_currency(self, client: TestClient):
        """Test creating a plan with invalid currency."""
        response = client.post(
            "/v1/plans/",
            json={
                "code": "invalid_currency",
                "name": "Invalid Currency",
                "interval": "monthly",
                "currency": "US",  # Too short
            },
        )
        assert response.status_code == 422

    def test_get_plan(self, client: TestClient):
        """Test getting a plan by ID."""
        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "get_test",
                "name": "Get Test",
                "interval": "monthly",
            },
        )
        plan_id = create_response.json()["id"]

        response = client.get(f"/v1/plans/{plan_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == plan_id
        assert data["code"] == "get_test"

    def test_get_plan_not_found(self, client: TestClient):
        """Test getting a non-existent plan."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/plans/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_get_plan_invalid_uuid(self, client: TestClient):
        """Test getting a plan with invalid UUID."""
        response = client.get("/v1/plans/not-a-uuid")
        assert response.status_code == 422

    def test_update_plan(self, client: TestClient):
        """Test updating a plan."""
        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "upd_test",
                "name": "Original Name",
                "interval": "monthly",
                "amount_cents": 1000,
            },
        )
        plan_id = create_response.json()["id"]

        response = client.put(
            f"/v1/plans/{plan_id}",
            json={
                "name": "Updated Name",
                "description": "New description",
                "amount_cents": 2000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New description"
        assert data["amount_cents"] == 2000
        assert data["code"] == "upd_test"  # Unchanged

    def test_update_plan_partial(self, client: TestClient):
        """Test partial update of a plan."""
        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "partial_upd",
                "name": "Partial Update",
                "description": "Original description",
                "interval": "monthly",
                "amount_cents": 5000,
                "trial_period_days": 7,
            },
        )
        plan_id = create_response.json()["id"]

        # Only update description
        response = client.put(
            f"/v1/plans/{plan_id}",
            json={"description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Partial Update"  # Unchanged
        assert data["description"] == "Updated description"  # Updated
        assert data["amount_cents"] == 5000  # Unchanged
        assert data["trial_period_days"] == 7  # Unchanged

    def test_update_plan_not_found(self, client: TestClient):
        """Test updating a non-existent plan."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/v1/plans/{fake_id}",
            json={"name": "Ghost"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_delete_plan(self, client: TestClient):
        """Test deleting a plan."""
        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "del_test",
                "name": "Delete Me",
                "interval": "monthly",
            },
        )
        plan_id = create_response.json()["id"]

        response = client.delete(f"/v1/plans/{plan_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/v1/plans/{plan_id}")
        assert get_response.status_code == 404

    def test_delete_plan_not_found(self, client: TestClient):
        """Test deleting a non-existent plan."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/v1/plans/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_list_plans_pagination(self, client: TestClient):
        """Test listing plans with pagination."""
        # Create multiple plans
        for i in range(5):
            client.post(
                "/v1/plans/",
                json={
                    "code": f"page_{i}",
                    "name": f"Plan {i}",
                    "interval": "monthly",
                },
            )

        # Test pagination
        response = client.get("/v1/plans/?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_plans_default_pagination(self, client: TestClient):
        """Test listing plans with default pagination."""
        client.post(
            "/v1/plans/",
            json={
                "code": "default_test",
                "name": "Default Test",
                "interval": "monthly",
            },
        )

        response = client.get("/v1/plans/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestChargeModel:
    def test_standard(self):
        """Test STANDARD charge model."""
        assert ChargeModel.STANDARD == "standard"
        assert ChargeModel.STANDARD.value == "standard"

    def test_graduated(self):
        """Test GRADUATED charge model."""
        assert ChargeModel.GRADUATED == "graduated"
        assert ChargeModel.GRADUATED.value == "graduated"

    def test_volume(self):
        """Test VOLUME charge model."""
        assert ChargeModel.VOLUME == "volume"
        assert ChargeModel.VOLUME.value == "volume"

    def test_package(self):
        """Test PACKAGE charge model."""
        assert ChargeModel.PACKAGE == "package"
        assert ChargeModel.PACKAGE.value == "package"

    def test_percentage(self):
        """Test PERCENTAGE charge model."""
        assert ChargeModel.PERCENTAGE == "percentage"
        assert ChargeModel.PERCENTAGE.value == "percentage"


class TestChargeModelDB:
    def test_charge_defaults(self, db_session):
        """Test Charge model default values."""
        plan = create_test_plan(db_session)
        metric = create_test_metric(db_session)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        assert charge.id is not None
        assert charge.plan_id == plan.id
        assert charge.billable_metric_id == metric.id
        assert charge.charge_model == "standard"
        assert charge.properties == {}
        assert charge.created_at is not None
        assert charge.updated_at is not None


class TestChargeRepository:
    def test_get_by_id(self, db_session):
        """Test getting charge by ID."""
        plan = create_test_plan(db_session)
        metric = create_test_metric(db_session)
        repo = ChargeRepository(db_session)

        data = ChargeCreate(
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD,
            properties={"amount": 100},
        )
        charge = repo.create(plan.id, data)

        found = repo.get_by_id(charge.id)
        assert found is not None
        assert found.id == charge.id

        not_found = repo.get_by_id(uuid.uuid4())
        assert not_found is None

    def test_get_by_plan_id(self, db_session):
        """Test getting charges by plan ID."""
        plan = create_test_plan(db_session)
        metric1 = create_test_metric(db_session, "metric1")
        metric2 = create_test_metric(db_session, "metric2")
        repo = ChargeRepository(db_session)

        repo.create(
            plan.id,
            ChargeCreate(
                billable_metric_id=metric1.id,
                charge_model=ChargeModel.STANDARD,
            ),
        )
        repo.create(
            plan.id,
            ChargeCreate(
                billable_metric_id=metric2.id,
                charge_model=ChargeModel.GRADUATED,
            ),
        )

        charges = repo.get_by_plan_id(plan.id)
        assert len(charges) == 2

        empty = repo.get_by_plan_id(uuid.uuid4())
        assert len(empty) == 0

    def test_create(self, db_session):
        """Test creating a charge."""
        plan = create_test_plan(db_session)
        metric = create_test_metric(db_session)
        repo = ChargeRepository(db_session)

        data = ChargeCreate(
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD,
            properties={"amount_cents": 500},
        )
        charge = repo.create(plan.id, data)

        assert charge.id is not None
        assert charge.plan_id == plan.id
        assert charge.billable_metric_id == metric.id
        assert charge.charge_model == "standard"
        assert charge.properties == {"amount_cents": 500}

    def test_update(self, db_session):
        """Test updating a charge."""
        plan = create_test_plan(db_session)
        metric = create_test_metric(db_session)
        repo = ChargeRepository(db_session)

        charge = repo.create(
            plan.id,
            ChargeCreate(
                billable_metric_id=metric.id,
                charge_model=ChargeModel.STANDARD,
                properties={"amount": 100},
            ),
        )

        updated = repo.update(
            charge.id,
            ChargeUpdate(
                charge_model=ChargeModel.GRADUATED,
                properties={"tiers": [{"up_to": 100, "amount": 10}]},
            ),
        )
        assert updated is not None
        assert updated.charge_model == "graduated"
        assert updated.properties == {"tiers": [{"up_to": 100, "amount": 10}]}

    def test_update_partial(self, db_session):
        """Test partial update of a charge."""
        plan = create_test_plan(db_session)
        metric = create_test_metric(db_session)
        repo = ChargeRepository(db_session)

        charge = repo.create(
            plan.id,
            ChargeCreate(
                billable_metric_id=metric.id,
                charge_model=ChargeModel.STANDARD,
                properties={"amount": 100},
            ),
        )

        updated = repo.update(
            charge.id,
            ChargeUpdate(
                properties={"amount": 200},
            ),
        )
        assert updated is not None
        assert updated.charge_model == "standard"  # Unchanged
        assert updated.properties == {"amount": 200}  # Updated

    def test_update_not_found(self, db_session):
        """Test updating a non-existent charge."""
        repo = ChargeRepository(db_session)
        result = repo.update(uuid.uuid4(), ChargeUpdate(properties={"x": 1}))
        assert result is None

    def test_delete(self, db_session):
        """Test deleting a charge."""
        plan = create_test_plan(db_session)
        metric = create_test_metric(db_session)
        repo = ChargeRepository(db_session)

        charge = repo.create(
            plan.id,
            ChargeCreate(
                billable_metric_id=metric.id,
                charge_model=ChargeModel.STANDARD,
            ),
        )

        assert repo.delete(charge.id) is True
        assert repo.get_by_id(charge.id) is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent charge."""
        repo = ChargeRepository(db_session)
        assert repo.delete(uuid.uuid4()) is False

    def test_delete_by_plan_id(self, db_session):
        """Test deleting all charges for a plan."""
        plan = create_test_plan(db_session)
        metric1 = create_test_metric(db_session, "m1")
        metric2 = create_test_metric(db_session, "m2")
        repo = ChargeRepository(db_session)

        repo.create(
            plan.id,
            ChargeCreate(
                billable_metric_id=metric1.id,
                charge_model=ChargeModel.STANDARD,
            ),
        )
        repo.create(
            plan.id,
            ChargeCreate(
                billable_metric_id=metric2.id,
                charge_model=ChargeModel.VOLUME,
            ),
        )

        count = repo.delete_by_plan_id(plan.id)
        assert count == 2
        assert len(repo.get_by_plan_id(plan.id)) == 0


class TestPlansWithChargesAPI:
    def test_create_plan_with_charges(self, client: TestClient, db_session):
        """Test creating a plan with charges."""
        # First create a billable metric
        metric_response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "api_calls",
                "name": "API Calls",
                "aggregation_type": "count",
            },
        )
        metric_id = metric_response.json()["id"]

        # Create plan with charges
        response = client.post(
            "/v1/plans/",
            json={
                "code": "with_charges",
                "name": "Plan with Charges",
                "interval": "monthly",
                "amount_cents": 2999,
                "charges": [
                    {
                        "billable_metric_id": metric_id,
                        "charge_model": "standard",
                        "properties": {"amount_cents": 10},
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "with_charges"
        assert len(data["charges"]) == 1
        assert data["charges"][0]["billable_metric_id"] == metric_id
        assert data["charges"][0]["charge_model"] == "standard"
        assert data["charges"][0]["properties"] == {"amount_cents": 10}

    def test_create_plan_with_multiple_charges(self, client: TestClient):
        """Test creating a plan with multiple charges."""
        # Create billable metrics
        metric1 = client.post(
            "/v1/billable_metrics/",
            json={"code": "calls", "name": "Calls", "aggregation_type": "count"},
        ).json()
        metric2 = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "storage",
                "name": "Storage",
                "aggregation_type": "sum",
                "field_name": "gb",
            },
        ).json()

        # Create plan with multiple charges
        response = client.post(
            "/v1/plans/",
            json={
                "code": "multi_charges",
                "name": "Multi Charges Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric1["id"],
                        "charge_model": "standard",
                        "properties": {"amount": 1},
                    },
                    {
                        "billable_metric_id": metric2["id"],
                        "charge_model": "graduated",
                        "properties": {"tiers": []},
                    },
                ],
            },
        )
        assert response.status_code == 201
        assert len(response.json()["charges"]) == 2

    def test_create_plan_invalid_metric_id(self, client: TestClient):
        """Test creating a plan with non-existent billable metric."""
        fake_metric_id = str(uuid.uuid4())
        response = client.post(
            "/v1/plans/",
            json={
                "code": "bad_metric",
                "name": "Bad Metric Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": fake_metric_id,
                        "charge_model": "standard",
                        "properties": {},
                    },
                ],
            },
        )
        assert response.status_code == 400
        assert f"Billable metric {fake_metric_id} not found" in response.json()["detail"]

    def test_get_plan_with_charges(self, client: TestClient):
        """Test getting a plan returns its charges."""
        # Create metric
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "test_metric", "name": "Test", "aggregation_type": "count"},
        ).json()

        # Create plan with charge
        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "get_with_charges",
                "name": "Get With Charges",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        # Get plan
        response = client.get(f"/v1/plans/{plan_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["charges"]) == 1

    def test_update_plan_with_charges(self, client: TestClient):
        """Test updating a plan's charges."""
        # Create metrics
        metric1 = client.post(
            "/v1/billable_metrics/",
            json={"code": "upd_metric1", "name": "Update Metric 1", "aggregation_type": "count"},
        ).json()
        metric2 = client.post(
            "/v1/billable_metrics/",
            json={"code": "upd_metric2", "name": "Update Metric 2", "aggregation_type": "count"},
        ).json()

        # Create plan with one charge
        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "upd_charges",
                "name": "Update Charges",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric1["id"],
                        "charge_model": "standard",
                        "properties": {},
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        # Update to have a different charge
        response = client.put(
            f"/v1/plans/{plan_id}",
            json={
                "charges": [
                    {
                        "billable_metric_id": metric2["id"],
                        "charge_model": "graduated",
                        "properties": {},
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["charges"]) == 1
        assert data["charges"][0]["billable_metric_id"] == metric2["id"]
        assert data["charges"][0]["charge_model"] == "graduated"

    def test_update_plan_invalid_metric_id(self, client: TestClient):
        """Test updating a plan with non-existent billable metric."""
        # Create plan without charges
        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "upd_bad_metric",
                "name": "Update Bad Metric",
                "interval": "monthly",
            },
        )
        plan_id = create_response.json()["id"]

        # Try to update with invalid metric
        fake_metric_id = str(uuid.uuid4())
        response = client.put(
            f"/v1/plans/{plan_id}",
            json={
                "charges": [
                    {
                        "billable_metric_id": fake_metric_id,
                        "charge_model": "standard",
                        "properties": {},
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert f"Billable metric {fake_metric_id} not found" in response.json()["detail"]

    def test_list_plans_with_charges(self, client: TestClient):
        """Test listing plans includes their charges."""
        # Create metric
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "list_metric", "name": "List Metric", "aggregation_type": "count"},
        ).json()

        # Create plan with charge
        client.post(
            "/v1/plans/",
            json={
                "code": "list_plan",
                "name": "List Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                    }
                ],
            },
        )

        # List plans
        response = client.get("/v1/plans/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert len(data[0]["charges"]) == 1

    def test_delete_plan_deletes_charges(self, client: TestClient):
        """Test deleting a plan also deletes its charges."""
        # Create metric
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "del_metric", "name": "Delete Metric", "aggregation_type": "count"},
        ).json()

        # Create plan with charge
        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "del_plan_charges",
                "name": "Delete Plan Charges",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]
        assert len(create_response.json()["charges"]) == 1

        # Delete plan
        response = client.delete(f"/v1/plans/{plan_id}")
        assert response.status_code == 204

        # Verify plan is gone
        get_response = client.get(f"/v1/plans/{plan_id}")
        assert get_response.status_code == 404


def create_test_customer(db_session, external_id: str = "cust_1"):
    """Helper to create a test customer."""
    from app.models.customer import Customer

    customer = Customer(
        external_id=external_id,
        name=f"Customer {external_id}",
        organization_id=DEFAULT_ORG_ID,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


class TestPlanSubscriptionCountsRepository:
    def test_subscription_counts_empty(self, db_session):
        """Test subscription counts with no plans."""
        repo = PlanRepository(db_session)
        result = repo.subscription_counts(DEFAULT_ORG_ID)
        assert result == {}

    def test_subscription_counts_no_subscriptions(self, db_session):
        """Test subscription counts when plans exist but no subscriptions."""
        plan = create_test_plan(db_session, "no_subs_plan")
        repo = PlanRepository(db_session)
        result = repo.subscription_counts(DEFAULT_ORG_ID)
        # Plans without subscriptions are not included in the result
        assert str(plan.id) not in result

    def test_subscription_counts_with_subscriptions(self, db_session):
        """Test subscription counts with subscriptions."""
        plan1 = create_test_plan(db_session, "plan_sc_1")
        plan2 = create_test_plan(db_session, "plan_sc_2")
        customer = create_test_customer(db_session, "sc_cust_1")

        # Create 2 subscriptions for plan1
        for i in range(2):
            sub = Subscription(
                external_id=f"sub_sc_{i}",
                customer_id=customer.id,
                plan_id=plan1.id,
                status=SubscriptionStatus.ACTIVE.value,
                organization_id=DEFAULT_ORG_ID,
            )
            db_session.add(sub)

        # Create 1 subscription for plan2
        sub = Subscription(
            external_id="sub_sc_2",
            customer_id=customer.id,
            plan_id=plan2.id,
            status=SubscriptionStatus.ACTIVE.value,
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(sub)
        db_session.commit()

        repo = PlanRepository(db_session)
        result = repo.subscription_counts(DEFAULT_ORG_ID)
        assert result[str(plan1.id)] == 2
        assert result[str(plan2.id)] == 1

    def test_subscription_counts_different_org(self, db_session):
        """Test subscription counts are org-scoped."""
        other_org_id = uuid.UUID("00000000-0000-0000-0000-000000000099")
        plan = create_test_plan(db_session, "org_plan")
        customer = create_test_customer(db_session, "org_cust")

        sub = Subscription(
            external_id="sub_org_test",
            customer_id=customer.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(sub)
        db_session.commit()

        repo = PlanRepository(db_session)
        # Should return count for default org
        result = repo.subscription_counts(DEFAULT_ORG_ID)
        assert str(plan.id) in result

        # Should return empty for other org
        result = repo.subscription_counts(other_org_id)
        assert result == {}


class TestPlanSubscriptionCountsAPI:
    def test_subscription_counts_empty(self, client: TestClient):
        """Test subscription counts endpoint with no plans."""
        response = client.get("/v1/plans/subscription_counts")
        assert response.status_code == 200
        assert response.json() == {}

    def test_subscription_counts_with_data(self, client: TestClient, db_session):
        """Test subscription counts endpoint with data."""
        plan = create_test_plan(db_session, "api_sc_plan")
        customer = create_test_customer(db_session, "api_sc_cust")

        sub = Subscription(
            external_id="api_sub_sc",
            customer_id=customer.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(sub)
        db_session.commit()

        response = client.get("/v1/plans/subscription_counts")
        assert response.status_code == 200
        data = response.json()
        assert data[str(plan.id)] == 1


class TestPlanSimulateAPI:
    def test_simulate_no_charges(self, client: TestClient):
        """Test simulate with a plan that has no charges."""
        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_no_charges",
                "name": "Sim No Charges",
                "interval": "monthly",
                "amount_cents": 5000,
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 100},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == plan_id
        assert data["base_amount_cents"] == 5000
        assert data["charges"] == []
        assert data["total_amount_cents"] == 5000
        assert data["currency"] == "USD"

    def test_simulate_standard_charge(self, client: TestClient):
        """Test simulate with a standard charge."""
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_std_metric", "name": "Sim Std", "aggregation_type": "count"},
        ).json()

        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_standard",
                "name": "Sim Standard",
                "interval": "monthly",
                "amount_cents": 2000,
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "0.50"},
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 100},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["base_amount_cents"] == 2000
        assert len(data["charges"]) == 1
        assert data["charges"][0]["charge_model"] == "standard"
        assert data["charges"][0]["units"] == 100
        # 100 units * $0.50 = $50.00 = 5000 cents
        assert data["charges"][0]["amount_cents"] == 5000
        assert data["total_amount_cents"] == 2000 + 5000

    def test_simulate_graduated_charge(self, client: TestClient):
        """Test simulate with a graduated charge."""
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_grad_metric", "name": "Sim Grad", "aggregation_type": "count"},
        ).json()

        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_graduated",
                "name": "Sim Graduated",
                "interval": "monthly",
                "amount_cents": 1000,
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "graduated",
                        "properties": {
                            "graduated_ranges": [
                                {"from_value": 0, "to_value": 10, "per_unit_amount": "1.00", "flat_amount": "0"},
                                {"from_value": 10, "to_value": None, "per_unit_amount": "0.50", "flat_amount": "0"},
                            ]
                        },
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 20},
        )
        assert response.status_code == 200
        data = response.json()
        # First 11 units at $1.00 = $11.00, next 9 at $0.50 = $4.50 => $15.50 = 1550 cents
        assert data["charges"][0]["amount_cents"] == 1550
        assert data["total_amount_cents"] == 1000 + 1550

    def test_simulate_volume_charge(self, client: TestClient):
        """Test simulate with a volume charge."""
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_vol_metric", "name": "Sim Vol", "aggregation_type": "count"},
        ).json()

        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_volume",
                "name": "Sim Volume",
                "interval": "monthly",
                "amount_cents": 0,
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "volume",
                        "properties": {
                            "volume_ranges": [
                                {"from_value": 0, "to_value": 100, "per_unit_amount": "1.00", "flat_amount": "0"},
                                {"from_value": 100, "to_value": None, "per_unit_amount": "0.50", "flat_amount": "0"},
                            ]
                        },
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 50},
        )
        assert response.status_code == 200
        data = response.json()
        # 50 units at $1.00 = $50.00 = 5000 cents
        assert data["charges"][0]["amount_cents"] == 5000

    def test_simulate_package_charge(self, client: TestClient):
        """Test simulate with a package charge."""
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_pkg_metric", "name": "Sim Pkg", "aggregation_type": "count"},
        ).json()

        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_package",
                "name": "Sim Package",
                "interval": "monthly",
                "amount_cents": 0,
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "package",
                        "properties": {"amount": "10", "package_size": "25", "free_units": "0"},
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 60},
        )
        assert response.status_code == 200
        data = response.json()
        # ceil(60 / 25) = 3 packages * $10 = $30 = 3000 cents
        assert data["charges"][0]["amount_cents"] == 3000

    def test_simulate_percentage_charge(self, client: TestClient):
        """Test simulate with a percentage charge."""
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_pct_metric", "name": "Sim Pct", "aggregation_type": "sum", "field_name": "amount"},
        ).json()

        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_percentage",
                "name": "Sim Percentage",
                "interval": "monthly",
                "amount_cents": 0,
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "percentage",
                        "properties": {"rate": "2.5"},
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 1000},
        )
        assert response.status_code == 200
        data = response.json()
        # 2.5% of 1000 = 25 => 2500 cents
        assert data["charges"][0]["amount_cents"] == 2500

    def test_simulate_plan_not_found(self, client: TestClient):
        """Test simulate with a non-existent plan."""
        fake_id = str(uuid.uuid4())
        response = client.post(
            f"/v1/plans/{fake_id}/simulate",
            json={"units": 100},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_simulate_zero_units(self, client: TestClient):
        """Test simulate with zero units."""
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_zero_metric", "name": "Sim Zero", "aggregation_type": "count"},
        ).json()

        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_zero",
                "name": "Sim Zero",
                "interval": "monthly",
                "amount_cents": 3000,
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "1.00"},
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["charges"][0]["amount_cents"] == 0
        assert data["total_amount_cents"] == 3000

    def test_simulate_multiple_charges(self, client: TestClient):
        """Test simulate with multiple charges on one plan."""
        metric1 = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_multi1", "name": "Sim Multi 1", "aggregation_type": "count"},
        ).json()
        metric2 = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_multi2", "name": "Sim Multi 2", "aggregation_type": "count"},
        ).json()

        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_multi",
                "name": "Sim Multi",
                "interval": "monthly",
                "amount_cents": 1000,
                "charges": [
                    {
                        "billable_metric_id": metric1["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "0.10"},
                    },
                    {
                        "billable_metric_id": metric2["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "0.20"},
                    },
                ],
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 100},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["charges"]) == 2
        # 100 * $0.10 = $10 = 1000 cents
        assert data["charges"][0]["amount_cents"] == 1000
        # 100 * $0.20 = $20 = 2000 cents
        assert data["charges"][1]["amount_cents"] == 2000
        assert data["total_amount_cents"] == 1000 + 1000 + 2000

    def test_simulate_graduated_percentage_charge(self, client: TestClient):
        """Test simulate with a graduated percentage charge."""
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_gp_metric", "name": "Sim GP", "aggregation_type": "sum", "field_name": "amount"},
        ).json()

        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_grad_pct",
                "name": "Sim Graduated Percentage",
                "interval": "monthly",
                "amount_cents": 0,
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "graduated_percentage",
                        "properties": {
                            "graduated_percentage_ranges": [
                                {"from_value": 0, "to_value": 100, "rate": "5", "flat_amount": "0"},
                                {"from_value": 100, "to_value": None, "rate": "2", "flat_amount": "0"},
                            ]
                        },
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 200},
        )
        assert response.status_code == 200
        data = response.json()
        # First 100 at 5% = $5, next 100 at 2% = $2 => $7 = 700 cents
        assert data["charges"][0]["amount_cents"] == 700

    def test_simulate_custom_charge(self, client: TestClient):
        """Test simulate with a custom charge."""
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_custom_metric", "name": "Sim Custom", "aggregation_type": "count"},
        ).json()

        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_custom",
                "name": "Sim Custom",
                "interval": "monthly",
                "amount_cents": 0,
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "custom",
                        "properties": {"custom_amount": "25.00"},
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 999},
        )
        assert response.status_code == 200
        data = response.json()
        # Custom amount is always $25.00 = 2500 cents
        assert data["charges"][0]["amount_cents"] == 2500

    def test_simulate_dynamic_charge(self, client: TestClient):
        """Test simulate with a dynamic charge returns zero (not event-based)."""
        metric = client.post(
            "/v1/billable_metrics/",
            json={"code": "sim_dyn_metric", "name": "Sim Dyn", "aggregation_type": "count"},
        ).json()

        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_dynamic",
                "name": "Sim Dynamic",
                "interval": "monthly",
                "amount_cents": 0,
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "dynamic",
                        "properties": {},
                    }
                ],
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": 100},
        )
        assert response.status_code == 200
        data = response.json()
        # Dynamic charges are event-based, simulation returns 0
        assert data["charges"][0]["amount_cents"] == 0

    def test_simulate_negative_units_rejected(self, client: TestClient):
        """Test simulate rejects negative units."""
        create_response = client.post(
            "/v1/plans/",
            json={
                "code": "sim_neg",
                "name": "Sim Neg",
                "interval": "monthly",
            },
        )
        plan_id = create_response.json()["id"]

        response = client.post(
            f"/v1/plans/{plan_id}/simulate",
            json={"units": -10},
        )
        assert response.status_code == 422
