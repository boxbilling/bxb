"""Plan API tests for bxb."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine, get_db
from app.main import app
from app.models.plan import Plan, PlanInterval
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan import PlanCreate


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
