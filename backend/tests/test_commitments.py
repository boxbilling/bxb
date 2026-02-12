"""Tests for Commitment model, repository, schema, and API endpoints."""

import uuid
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.commitment import Commitment
from app.repositories.commitment_repository import CommitmentRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.commitment import CommitmentCreate, CommitmentResponse, CommitmentUpdate
from app.schemas.plan import PlanCreate
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
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"commitment_test_plan_{uuid4()}",
            name="Commitment Test Plan",
            interval="monthly",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def commitment(db_session, plan):
    """Create a test commitment."""
    repo = CommitmentRepository(db_session)
    return repo.create(
        CommitmentCreate(
            plan_id=plan.id,
            commitment_type="minimum_commitment",
            amount_cents=Decimal("10000"),
            invoice_display_name="Minimum Monthly Commitment",
        ),
        DEFAULT_ORG_ID,
    )


class TestCommitmentModel:
    """Tests for the Commitment model."""

    def test_commitment_table_name(self):
        assert Commitment.__tablename__ == "commitments"

    def test_commitment_creation(self, db_session, plan):
        commitment = Commitment(
            plan_id=plan.id,
            commitment_type="minimum_commitment",
            amount_cents=Decimal("5000"),
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(commitment)
        db_session.commit()
        db_session.refresh(commitment)

        assert commitment.id is not None
        assert commitment.plan_id == plan.id
        assert commitment.commitment_type == "minimum_commitment"
        assert commitment.amount_cents == Decimal("5000")
        assert commitment.invoice_display_name is None
        assert commitment.created_at is not None
        assert commitment.updated_at is not None


class TestCommitmentRepository:
    """Tests for CommitmentRepository CRUD and query methods."""

    def test_create_commitment(self, db_session, plan):
        repo = CommitmentRepository(db_session)
        commitment = repo.create(
            CommitmentCreate(
                plan_id=plan.id,
                commitment_type="minimum_commitment",
                amount_cents=Decimal("10000"),
                invoice_display_name="Min Commitment",
            ),
            DEFAULT_ORG_ID,
        )
        assert commitment.id is not None
        assert commitment.plan_id == plan.id
        assert commitment.commitment_type == "minimum_commitment"
        assert commitment.amount_cents == Decimal("10000")
        assert commitment.invoice_display_name == "Min Commitment"

    def test_create_commitment_minimal(self, db_session, plan):
        """Test creating a commitment with only required fields."""
        repo = CommitmentRepository(db_session)
        commitment = repo.create(
            CommitmentCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
            ),
            DEFAULT_ORG_ID,
        )
        assert commitment.id is not None
        assert commitment.commitment_type == "minimum_commitment"
        assert commitment.invoice_display_name is None

    def test_get_by_id(self, db_session, commitment):
        repo = CommitmentRepository(db_session)
        fetched = repo.get_by_id(commitment.id)
        assert fetched is not None
        assert fetched.id == commitment.id
        assert fetched.amount_cents == Decimal("10000")

    def test_get_by_id_with_organization(self, db_session, commitment):
        repo = CommitmentRepository(db_session)
        fetched = repo.get_by_id(commitment.id, DEFAULT_ORG_ID)
        assert fetched is not None
        assert fetched.id == commitment.id

    def test_get_by_id_wrong_organization(self, db_session, commitment):
        repo = CommitmentRepository(db_session)
        fetched = repo.get_by_id(commitment.id, uuid4())
        assert fetched is None

    def test_get_by_id_not_found(self, db_session):
        repo = CommitmentRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_plan_id(self, db_session, plan, commitment):
        repo = CommitmentRepository(db_session)
        commitments = repo.get_by_plan_id(plan.id)
        assert len(commitments) == 1
        assert commitments[0].id == commitment.id

    def test_get_by_plan_id_multiple(self, db_session, plan):
        repo = CommitmentRepository(db_session)
        repo.create(
            CommitmentCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
            ),
            DEFAULT_ORG_ID,
        )
        repo.create(
            CommitmentCreate(
                plan_id=plan.id,
                amount_cents=Decimal("10000"),
            ),
            DEFAULT_ORG_ID,
        )
        commitments = repo.get_by_plan_id(plan.id)
        assert len(commitments) == 2

    def test_get_by_plan_id_empty(self, db_session):
        repo = CommitmentRepository(db_session)
        commitments = repo.get_by_plan_id(uuid4())
        assert len(commitments) == 0

    def test_get_all(self, db_session, commitment):
        repo = CommitmentRepository(db_session)
        commitments = repo.get_all(DEFAULT_ORG_ID)
        assert len(commitments) == 1
        assert commitments[0].id == commitment.id

    def test_get_all_pagination(self, db_session, plan):
        repo = CommitmentRepository(db_session)
        for i in range(5):
            repo.create(
                CommitmentCreate(
                    plan_id=plan.id,
                    amount_cents=Decimal(str((i + 1) * 1000)),
                ),
                DEFAULT_ORG_ID,
            )
        commitments = repo.get_all(DEFAULT_ORG_ID, skip=2, limit=2)
        assert len(commitments) == 2

    def test_update_commitment(self, db_session, commitment):
        repo = CommitmentRepository(db_session)
        updated = repo.update(
            commitment.id,
            CommitmentUpdate(
                amount_cents=Decimal("20000"),
                invoice_display_name="Updated Commitment",
            ),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.amount_cents == Decimal("20000")
        assert updated.invoice_display_name == "Updated Commitment"

    def test_update_commitment_partial(self, db_session, commitment):
        repo = CommitmentRepository(db_session)
        updated = repo.update(
            commitment.id,
            CommitmentUpdate(amount_cents=Decimal("15000")),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.amount_cents == Decimal("15000")
        assert updated.invoice_display_name == "Minimum Monthly Commitment"

    def test_update_commitment_not_found(self, db_session):
        repo = CommitmentRepository(db_session)
        result = repo.update(
            uuid4(),
            CommitmentUpdate(amount_cents=Decimal("1000")),
            DEFAULT_ORG_ID,
        )
        assert result is None

    def test_update_commitment_wrong_organization(self, db_session, commitment):
        repo = CommitmentRepository(db_session)
        result = repo.update(
            commitment.id,
            CommitmentUpdate(amount_cents=Decimal("1000")),
            uuid4(),
        )
        assert result is None

    def test_delete_commitment(self, db_session, commitment):
        repo = CommitmentRepository(db_session)
        assert repo.delete(commitment.id, DEFAULT_ORG_ID) is True
        assert repo.get_by_id(commitment.id) is None

    def test_delete_commitment_not_found(self, db_session):
        repo = CommitmentRepository(db_session)
        assert repo.delete(uuid4(), DEFAULT_ORG_ID) is False

    def test_delete_commitment_wrong_organization(self, db_session, commitment):
        repo = CommitmentRepository(db_session)
        assert repo.delete(commitment.id, uuid4()) is False
        # Verify commitment still exists
        assert repo.get_by_id(commitment.id) is not None


# ─────────────────────────────────────────────────────────────────────────────
# Schema Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCommitmentSchemas:
    """Tests for Pydantic commitment schemas."""

    def test_create_defaults(self):
        """Test CommitmentCreate default values."""
        schema = CommitmentCreate(
            plan_id=uuid4(),
            amount_cents=Decimal("5000"),
        )
        assert schema.commitment_type == "minimum_commitment"
        assert schema.invoice_display_name is None

    def test_create_all_fields(self):
        """Test CommitmentCreate with all fields."""
        pid = uuid4()
        schema = CommitmentCreate(
            plan_id=pid,
            commitment_type="minimum_commitment",
            amount_cents=Decimal("10000"),
            invoice_display_name="Custom Name",
        )
        assert schema.plan_id == pid
        assert schema.amount_cents == Decimal("10000")
        assert schema.invoice_display_name == "Custom Name"

    def test_update_all_optional(self):
        """Test CommitmentUpdate has all optional fields."""
        schema = CommitmentUpdate()
        assert schema.commitment_type is None
        assert schema.amount_cents is None
        assert schema.invoice_display_name is None

    def test_response_from_model(self, db_session, commitment):
        """Test CommitmentResponse from ORM model."""
        response = CommitmentResponse.model_validate(commitment)
        assert response.id == commitment.id
        assert response.plan_id == commitment.plan_id
        assert response.commitment_type == "minimum_commitment"
        assert response.amount_cents == Decimal("10000")
        assert response.invoice_display_name == "Minimum Monthly Commitment"


# ─────────────────────────────────────────────────────────────────────────────
# API Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestCommitmentsAPI:
    """Tests for the commitments API endpoints."""

    def _create_plan(self, client: TestClient, code: str | None = None) -> dict:
        """Helper to create a plan via API."""
        plan_code = code or f"cmt_plan_{uuid4()}"
        response = client.post(
            "/v1/plans/",
            json={
                "code": plan_code,
                "name": "Commitment API Test Plan",
                "interval": "monthly",
            },
        )
        assert response.status_code == 201
        return response.json()

    def test_create_commitment(self, client: TestClient):
        """Test creating a commitment on a plan."""
        plan = self._create_plan(client, "cmt_create_test")
        response = client.post(
            f"/v1/plans/{plan['code']}/commitments",
            json={
                "amount_cents": 10000,
                "commitment_type": "minimum_commitment",
                "invoice_display_name": "Minimum Monthly Commitment",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["plan_id"] == plan["id"]
        assert float(data["amount_cents"]) == 10000.0
        assert data["commitment_type"] == "minimum_commitment"
        assert data["invoice_display_name"] == "Minimum Monthly Commitment"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_commitment_minimal(self, client: TestClient):
        """Test creating a commitment with minimal fields."""
        plan = self._create_plan(client, "cmt_create_minimal")
        response = client.post(
            f"/v1/plans/{plan['code']}/commitments",
            json={"amount_cents": 5000},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["commitment_type"] == "minimum_commitment"
        assert data["invoice_display_name"] is None

    def test_create_commitment_plan_not_found(self, client: TestClient):
        """Test creating a commitment on a non-existent plan."""
        response = client.post(
            "/v1/plans/nonexistent_plan/commitments",
            json={"amount_cents": 5000},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_create_commitment_invalid_amount(self, client: TestClient):
        """Test creating a commitment with negative amount."""
        plan = self._create_plan(client, "cmt_invalid_amount")
        response = client.post(
            f"/v1/plans/{plan['code']}/commitments",
            json={"amount_cents": -100},
        )
        assert response.status_code == 422

    def test_list_commitments_empty(self, client: TestClient):
        """Test listing commitments for a plan with none."""
        plan = self._create_plan(client, "cmt_list_empty")
        response = client.get(f"/v1/plans/{plan['code']}/commitments")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_commitments(self, client: TestClient):
        """Test listing commitments for a plan."""
        plan = self._create_plan(client, "cmt_list_test")
        client.post(
            f"/v1/plans/{plan['code']}/commitments",
            json={"amount_cents": 5000},
        )
        client.post(
            f"/v1/plans/{plan['code']}/commitments",
            json={"amount_cents": 10000},
        )
        response = client.get(f"/v1/plans/{plan['code']}/commitments")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_commitments_plan_not_found(self, client: TestClient):
        """Test listing commitments for a non-existent plan."""
        response = client.get("/v1/plans/nonexistent_plan/commitments")
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_update_commitment(self, client: TestClient):
        """Test updating a commitment."""
        plan = self._create_plan(client, "cmt_update_test")
        create_resp = client.post(
            f"/v1/plans/{plan['code']}/commitments",
            json={"amount_cents": 5000, "invoice_display_name": "Original"},
        )
        commitment_id = create_resp.json()["id"]

        response = client.put(
            f"/v1/commitments/{commitment_id}",
            json={"amount_cents": 20000, "invoice_display_name": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["amount_cents"]) == 20000.0
        assert data["invoice_display_name"] == "Updated"

    def test_update_commitment_partial(self, client: TestClient):
        """Test partial update of a commitment."""
        plan = self._create_plan(client, "cmt_partial_upd")
        create_resp = client.post(
            f"/v1/plans/{plan['code']}/commitments",
            json={"amount_cents": 5000, "invoice_display_name": "Keep Me"},
        )
        commitment_id = create_resp.json()["id"]

        response = client.put(
            f"/v1/commitments/{commitment_id}",
            json={"amount_cents": 8000},
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["amount_cents"]) == 8000.0
        assert data["invoice_display_name"] == "Keep Me"

    def test_update_commitment_not_found(self, client: TestClient):
        """Test updating a non-existent commitment."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/v1/commitments/{fake_id}",
            json={"amount_cents": 1000},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Commitment not found"

    def test_update_commitment_invalid_uuid(self, client: TestClient):
        """Test updating a commitment with invalid UUID."""
        response = client.put(
            "/v1/commitments/not-a-uuid",
            json={"amount_cents": 1000},
        )
        assert response.status_code == 422

    def test_delete_commitment(self, client: TestClient):
        """Test deleting a commitment."""
        plan = self._create_plan(client, "cmt_delete_test")
        create_resp = client.post(
            f"/v1/plans/{plan['code']}/commitments",
            json={"amount_cents": 5000},
        )
        commitment_id = create_resp.json()["id"]

        response = client.delete(f"/v1/commitments/{commitment_id}")
        assert response.status_code == 204

        # Verify it's gone
        list_resp = client.get(f"/v1/plans/{plan['code']}/commitments")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 0

    def test_delete_commitment_not_found(self, client: TestClient):
        """Test deleting a non-existent commitment."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/v1/commitments/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Commitment not found"

    def test_delete_commitment_invalid_uuid(self, client: TestClient):
        """Test deleting a commitment with invalid UUID."""
        response = client.delete("/v1/commitments/not-a-uuid")
        assert response.status_code == 422
