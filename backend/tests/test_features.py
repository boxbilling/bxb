"""Feature model, repository, and API endpoint tests."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.models.customer import generate_uuid
from app.models.entitlement import Entitlement
from app.models.feature import Feature, FeatureType
from app.models.plan import Plan, PlanInterval
from app.repositories.feature_repository import FeatureRepository
from app.schemas.feature import FeatureCreate, FeatureUpdate
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def client():
    """Create test client."""
    from app.main import app

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


def _create_feature(
    db_session,
    code: str = "feat-test",
    name: str = "Test Feature",
    feature_type: str = FeatureType.BOOLEAN.value,
    **kwargs,
) -> Feature:
    """Helper to create a feature directly in the DB."""
    feature = Feature(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        code=code,
        name=name,
        feature_type=feature_type,
        **kwargs,
    )
    db_session.add(feature)
    db_session.commit()
    db_session.refresh(feature)
    return feature


def _create_plan(db_session, code: str = "plan-test") -> Plan:
    """Helper to create a plan directly in the DB."""
    plan = Plan(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        code=code,
        name=f"Plan {code}",
        interval=PlanInterval.MONTHLY.value,
        amount_cents=1000,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


class TestFeatureRepository:
    """Tests for FeatureRepository."""

    def test_create(self, db_session):
        repo = FeatureRepository(db_session)
        data = FeatureCreate(
            code="repo-create",
            name="Repo Feature",
            feature_type=FeatureType.BOOLEAN,
        )
        feature = repo.create(data, DEFAULT_ORG_ID)
        assert feature.code == "repo-create"
        assert feature.name == "Repo Feature"
        assert feature.feature_type == "boolean"
        assert feature.organization_id == DEFAULT_ORG_ID

    def test_get_all(self, db_session):
        repo = FeatureRepository(db_session)
        _create_feature(db_session, code="all-1", name="F1")
        _create_feature(db_session, code="all-2", name="F2")
        features = repo.get_all(DEFAULT_ORG_ID)
        assert len(features) == 2

    def test_get_all_pagination(self, db_session):
        repo = FeatureRepository(db_session)
        for i in range(5):
            _create_feature(db_session, code=f"page-{i}", name=f"F{i}")
        features = repo.get_all(DEFAULT_ORG_ID, skip=1, limit=2)
        assert len(features) == 2

    def test_count(self, db_session):
        repo = FeatureRepository(db_session)
        _create_feature(db_session, code="cnt-1", name="F1")
        _create_feature(db_session, code="cnt-2", name="F2")
        assert repo.count(DEFAULT_ORG_ID) == 2

    def test_get_by_id(self, db_session):
        repo = FeatureRepository(db_session)
        feature = _create_feature(db_session, code="get-id", name="By ID")
        result = repo.get_by_id(feature.id, DEFAULT_ORG_ID)
        assert result is not None
        assert result.code == "get-id"

    def test_get_by_id_not_found(self, db_session):
        repo = FeatureRepository(db_session)
        result = repo.get_by_id(generate_uuid(), DEFAULT_ORG_ID)
        assert result is None

    def test_get_by_id_no_org_filter(self, db_session):
        repo = FeatureRepository(db_session)
        feature = _create_feature(db_session, code="no-org", name="No Org")
        result = repo.get_by_id(feature.id)
        assert result is not None
        assert result.code == "no-org"

    def test_get_by_code(self, db_session):
        repo = FeatureRepository(db_session)
        _create_feature(db_session, code="by-code", name="By Code")
        result = repo.get_by_code("by-code", DEFAULT_ORG_ID)
        assert result is not None
        assert result.name == "By Code"

    def test_get_by_code_not_found(self, db_session):
        repo = FeatureRepository(db_session)
        result = repo.get_by_code("nonexistent", DEFAULT_ORG_ID)
        assert result is None

    def test_update(self, db_session):
        repo = FeatureRepository(db_session)
        feature = _create_feature(db_session, code="upd", name="Original")
        data = FeatureUpdate(name="Updated")
        result = repo.update(feature.id, data, DEFAULT_ORG_ID)
        assert result is not None
        assert result.name == "Updated"
        assert result.code == "upd"

    def test_update_not_found(self, db_session):
        repo = FeatureRepository(db_session)
        data = FeatureUpdate(name="Nope")
        result = repo.update(generate_uuid(), data, DEFAULT_ORG_ID)
        assert result is None

    def test_delete(self, db_session):
        repo = FeatureRepository(db_session)
        feature = _create_feature(db_session, code="del", name="Delete Me")
        assert repo.delete(feature.id, DEFAULT_ORG_ID) is True
        assert repo.get_by_id(feature.id, DEFAULT_ORG_ID) is None

    def test_delete_not_found(self, db_session):
        repo = FeatureRepository(db_session)
        assert repo.delete(generate_uuid(), DEFAULT_ORG_ID) is False

    def test_code_exists(self, db_session):
        repo = FeatureRepository(db_session)
        _create_feature(db_session, code="exists", name="Exists")
        assert repo.code_exists("exists", DEFAULT_ORG_ID) is True
        assert repo.code_exists("nope", DEFAULT_ORG_ID) is False

    def test_create_with_description(self, db_session):
        repo = FeatureRepository(db_session)
        data = FeatureCreate(
            code="desc-feat",
            name="Feature With Desc",
            description="A detailed description",
            feature_type=FeatureType.QUANTITY,
        )
        feature = repo.create(data, DEFAULT_ORG_ID)
        assert feature.description == "A detailed description"
        assert feature.feature_type == "quantity"

    def test_create_custom_type(self, db_session):
        repo = FeatureRepository(db_session)
        data = FeatureCreate(
            code="custom-feat",
            name="Custom Feature",
            feature_type=FeatureType.CUSTOM,
        )
        feature = repo.create(data, DEFAULT_ORG_ID)
        assert feature.feature_type == "custom"


class TestFeaturesAPI:
    """Tests for feature CRUD endpoints."""

    def test_create_feature(self, client):
        """Test creating a feature via POST."""
        resp = client.post(
            "/v1/features/",
            json={
                "code": "api-create",
                "name": "API Created",
                "feature_type": "boolean",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == "api-create"
        assert data["name"] == "API Created"
        assert data["feature_type"] == "boolean"
        assert data["description"] is None
        assert data["id"] is not None

    def test_create_feature_with_description(self, client):
        """Test creating a feature with all fields."""
        resp = client.post(
            "/v1/features/",
            json={
                "code": "api-full",
                "name": "Full Feature",
                "description": "A detailed description",
                "feature_type": "quantity",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "A detailed description"
        assert data["feature_type"] == "quantity"

    def test_create_feature_duplicate_code(self, client):
        """Test creating a feature with duplicate code returns 409."""
        client.post(
            "/v1/features/",
            json={"code": "dup-code", "name": "First", "feature_type": "boolean"},
        )
        resp = client.post(
            "/v1/features/",
            json={"code": "dup-code", "name": "Second", "feature_type": "boolean"},
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_create_feature_validation_error(self, client):
        """Test creating a feature with invalid data returns 422."""
        resp = client.post(
            "/v1/features/",
            json={"code": "", "name": "", "feature_type": "boolean"},
        )
        assert resp.status_code == 422

    def test_list_features(self, client, db_session):
        """Test listing features."""
        for i in range(3):
            _create_feature(db_session, code=f"list-{i}", name=f"Feature {i}")

        resp = client.get("/v1/features/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert resp.headers["X-Total-Count"] == "3"

    def test_list_features_pagination(self, client, db_session):
        """Test listing features with pagination."""
        for i in range(5):
            _create_feature(db_session, code=f"page-{i}", name=f"Feature {i}")

        resp = client.get("/v1/features/?skip=1&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_features_empty(self, client):
        """Test listing features when none exist."""
        resp = client.get("/v1/features/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_feature_by_code(self, client, db_session):
        """Test getting a feature by code."""
        _create_feature(db_session, code="get-code", name="Get By Code")

        resp = client.get("/v1/features/get-code")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "get-code"
        assert data["name"] == "Get By Code"

    def test_get_feature_not_found(self, client):
        """Test getting a non-existent feature returns 404."""
        resp = client.get("/v1/features/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_update_feature(self, client, db_session):
        """Test updating a feature via PATCH."""
        _create_feature(db_session, code="upd-code", name="Original Name")

        resp = client.patch(
            "/v1/features/upd-code",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["code"] == "upd-code"

    def test_update_feature_description(self, client, db_session):
        """Test updating a feature description."""
        _create_feature(
            db_session, code="upd-desc", name="Desc Feature", description="Old desc"
        )

        resp = client.patch(
            "/v1/features/upd-desc",
            json={"description": "New desc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "New desc"
        assert data["name"] == "Desc Feature"

    def test_update_feature_not_found(self, client):
        """Test updating a non-existent feature returns 404."""
        resp = client.patch(
            "/v1/features/nonexistent",
            json={"name": "Nope"},
        )
        assert resp.status_code == 404

    def test_delete_feature(self, client, db_session):
        """Test deleting a feature."""
        _create_feature(db_session, code="del-code", name="Delete Me")

        resp = client.delete("/v1/features/del-code")
        assert resp.status_code == 204

        # Verify it was deleted
        resp = client.get("/v1/features/del-code")
        assert resp.status_code == 404

    def test_delete_feature_not_found(self, client):
        """Test deleting a non-existent feature returns 404."""
        resp = client.delete("/v1/features/nonexistent")
        assert resp.status_code == 404

    def test_delete_feature_with_entitlements(self, client, db_session):
        """Test deleting a feature with entitlements returns 400."""
        feature = _create_feature(
            db_session, code="del-ent", name="Has Entitlements"
        )
        plan = _create_plan(db_session, code="del-ent-plan")
        entitlement = Entitlement(
            id=generate_uuid(),
            organization_id=DEFAULT_ORG_ID,
            plan_id=plan.id,
            feature_id=feature.id,
            value="true",
        )
        db_session.add(entitlement)
        db_session.commit()

        resp = client.delete("/v1/features/del-ent")
        assert resp.status_code == 400
        assert "existing entitlements" in resp.json()["detail"]

    def test_create_idempotency(self, client):
        """Test idempotent creation with Idempotency-Key header."""
        key = str(uuid.uuid4())
        headers = {"Idempotency-Key": key}
        resp1 = client.post(
            "/v1/features/",
            json={"code": "idempotent", "name": "Idempotent", "feature_type": "boolean"},
            headers=headers,
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/v1/features/",
            json={"code": "idempotent", "name": "Idempotent", "feature_type": "boolean"},
            headers=headers,
        )
        assert resp2.status_code == 201
        assert resp1.json()["id"] == resp2.json()["id"]
