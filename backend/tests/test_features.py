"""Feature model and repository tests."""

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.models.customer import generate_uuid
from app.models.feature import Feature, FeatureType
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
