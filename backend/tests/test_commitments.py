"""Tests for Commitment model, repository, and schema."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import get_db
from app.models.commitment import Commitment
from app.repositories.commitment_repository import CommitmentRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.commitment import CommitmentCreate, CommitmentUpdate
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
