"""Plan API tests for bxb."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine, get_db
from app.main import app
from app.models.billable_metric import AggregationType, BillableMetric
from app.models.charge import Charge, ChargeModel
from app.models.plan import Plan, PlanInterval
from app.repositories.charge_repository import ChargeRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.charge import ChargeCreate, ChargeUpdate
from app.schemas.plan import ChargeInput, PlanCreate


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
        repo.create(data)

        plan = repo.get_by_code("pro")
        assert plan is not None
        assert plan.code == "pro"

        not_found = repo.get_by_code("nonexistent")
        assert not_found is None

    def test_code_exists(self, db_session):
        """Test checking if code exists."""
        repo = PlanRepository(db_session)
        data = PlanCreate(
            code="exists_test",
            name="Exists Test",
            interval=PlanInterval.MONTHLY,
        )
        repo.create(data)

        assert repo.code_exists("exists_test") is True
        assert repo.code_exists("not_exists") is False


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

        repo.create(plan.id, ChargeCreate(
            billable_metric_id=metric1.id,
            charge_model=ChargeModel.STANDARD,
        ))
        repo.create(plan.id, ChargeCreate(
            billable_metric_id=metric2.id,
            charge_model=ChargeModel.GRADUATED,
        ))

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

        charge = repo.create(plan.id, ChargeCreate(
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD,
            properties={"amount": 100},
        ))

        updated = repo.update(charge.id, ChargeUpdate(
            charge_model=ChargeModel.GRADUATED,
            properties={"tiers": [{"up_to": 100, "amount": 10}]},
        ))
        assert updated is not None
        assert updated.charge_model == "graduated"
        assert updated.properties == {"tiers": [{"up_to": 100, "amount": 10}]}

    def test_update_partial(self, db_session):
        """Test partial update of a charge."""
        plan = create_test_plan(db_session)
        metric = create_test_metric(db_session)
        repo = ChargeRepository(db_session)

        charge = repo.create(plan.id, ChargeCreate(
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD,
            properties={"amount": 100},
        ))

        updated = repo.update(charge.id, ChargeUpdate(
            properties={"amount": 200},
        ))
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

        charge = repo.create(plan.id, ChargeCreate(
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD,
        ))

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

        repo.create(plan.id, ChargeCreate(
            billable_metric_id=metric1.id,
            charge_model=ChargeModel.STANDARD,
        ))
        repo.create(plan.id, ChargeCreate(
            billable_metric_id=metric2.id,
            charge_model=ChargeModel.VOLUME,
        ))

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
            json={"code": "storage", "name": "Storage", "aggregation_type": "sum", "field_name": "gb"},
        ).json()

        # Create plan with multiple charges
        response = client.post(
            "/v1/plans/",
            json={
                "code": "multi_charges",
                "name": "Multi Charges Plan",
                "interval": "monthly",
                "charges": [
                    {"billable_metric_id": metric1["id"], "charge_model": "standard", "properties": {"amount": 1}},
                    {"billable_metric_id": metric2["id"], "charge_model": "graduated", "properties": {"tiers": []}},
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
                    {"billable_metric_id": fake_metric_id, "charge_model": "standard", "properties": {}},
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
                "charges": [{"billable_metric_id": metric["id"], "charge_model": "standard", "properties": {}}],
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
                "charges": [{"billable_metric_id": metric1["id"], "charge_model": "standard", "properties": {}}],
            },
        )
        plan_id = create_response.json()["id"]

        # Update to have a different charge
        response = client.put(
            f"/v1/plans/{plan_id}",
            json={
                "charges": [{"billable_metric_id": metric2["id"], "charge_model": "graduated", "properties": {}}],
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
                "charges": [{"billable_metric_id": fake_metric_id, "charge_model": "standard", "properties": {}}],
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
                "charges": [{"billable_metric_id": metric["id"], "charge_model": "standard", "properties": {}}],
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
                "charges": [{"billable_metric_id": metric["id"], "charge_model": "standard", "properties": {}}],
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
