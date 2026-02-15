"""Entitlement model and repository tests."""

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.models.customer import generate_uuid
from app.models.entitlement import Entitlement
from app.models.feature import Feature, FeatureType
from app.models.plan import Plan, PlanInterval
from app.repositories.entitlement_repository import EntitlementRepository
from app.schemas.entitlement import EntitlementCreate, EntitlementUpdate
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


def _create_feature(
    db_session,
    code: str = "feat-test",
    feature_type: str = FeatureType.BOOLEAN.value,
) -> Feature:
    """Helper to create a feature directly in the DB."""
    feature = Feature(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        code=code,
        name=f"Feature {code}",
        feature_type=feature_type,
    )
    db_session.add(feature)
    db_session.commit()
    db_session.refresh(feature)
    return feature


def _create_entitlement(
    db_session,
    plan_id,
    feature_id,
    value: str = "true",
) -> Entitlement:
    """Helper to create an entitlement directly in the DB."""
    entitlement = Entitlement(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        plan_id=plan_id,
        feature_id=feature_id,
        value=value,
    )
    db_session.add(entitlement)
    db_session.commit()
    db_session.refresh(entitlement)
    return entitlement


class TestEntitlementRepository:
    """Tests for EntitlementRepository."""

    def test_create(self, db_session):
        repo = EntitlementRepository(db_session)
        plan = _create_plan(db_session, code="ent-plan-1")
        feature = _create_feature(db_session, code="ent-feat-1")
        data = EntitlementCreate(
            plan_id=plan.id,
            feature_id=feature.id,
            value="true",
        )
        entitlement = repo.create(data, DEFAULT_ORG_ID)
        assert entitlement.plan_id == plan.id
        assert entitlement.feature_id == feature.id
        assert entitlement.value == "true"

    def test_get_all(self, db_session):
        repo = EntitlementRepository(db_session)
        plan = _create_plan(db_session, code="all-plan")
        f1 = _create_feature(db_session, code="all-f1")
        f2 = _create_feature(db_session, code="all-f2")
        _create_entitlement(db_session, plan.id, f1.id)
        _create_entitlement(db_session, plan.id, f2.id)
        entitlements = repo.get_all(DEFAULT_ORG_ID)
        assert len(entitlements) == 2

    def test_get_all_pagination(self, db_session):
        repo = EntitlementRepository(db_session)
        plan = _create_plan(db_session, code="page-plan")
        for i in range(5):
            feat = _create_feature(db_session, code=f"page-f{i}")
            _create_entitlement(db_session, plan.id, feat.id)
        entitlements = repo.get_all(DEFAULT_ORG_ID, skip=1, limit=2)
        assert len(entitlements) == 2

    def test_count(self, db_session):
        repo = EntitlementRepository(db_session)
        plan = _create_plan(db_session, code="cnt-plan")
        f1 = _create_feature(db_session, code="cnt-f1")
        f2 = _create_feature(db_session, code="cnt-f2")
        _create_entitlement(db_session, plan.id, f1.id)
        _create_entitlement(db_session, plan.id, f2.id)
        assert repo.count(DEFAULT_ORG_ID) == 2

    def test_count_with_plan_filter(self, db_session):
        repo = EntitlementRepository(db_session)
        plan1 = _create_plan(db_session, code="cnt-p1")
        plan2 = _create_plan(db_session, code="cnt-p2")
        f1 = _create_feature(db_session, code="cnt-pf1")
        f2 = _create_feature(db_session, code="cnt-pf2")
        _create_entitlement(db_session, plan1.id, f1.id)
        _create_entitlement(db_session, plan2.id, f2.id)
        assert repo.count(DEFAULT_ORG_ID, plan_id=plan1.id) == 1

    def test_get_by_id(self, db_session):
        repo = EntitlementRepository(db_session)
        plan = _create_plan(db_session, code="get-plan")
        feature = _create_feature(db_session, code="get-feat")
        ent = _create_entitlement(db_session, plan.id, feature.id)
        result = repo.get_by_id(ent.id, DEFAULT_ORG_ID)
        assert result is not None
        assert result.value == "true"

    def test_get_by_id_not_found(self, db_session):
        repo = EntitlementRepository(db_session)
        result = repo.get_by_id(generate_uuid(), DEFAULT_ORG_ID)
        assert result is None

    def test_get_by_id_no_org_filter(self, db_session):
        repo = EntitlementRepository(db_session)
        plan = _create_plan(db_session, code="norg-plan")
        feature = _create_feature(db_session, code="norg-feat")
        ent = _create_entitlement(db_session, plan.id, feature.id)
        result = repo.get_by_id(ent.id)
        assert result is not None

    def test_get_by_plan_id(self, db_session):
        repo = EntitlementRepository(db_session)
        plan = _create_plan(db_session, code="byplan")
        f1 = _create_feature(db_session, code="byplan-f1")
        f2 = _create_feature(db_session, code="byplan-f2")
        _create_entitlement(db_session, plan.id, f1.id)
        _create_entitlement(db_session, plan.id, f2.id)
        entitlements = repo.get_by_plan_id(plan.id, DEFAULT_ORG_ID)
        assert len(entitlements) == 2

    def test_get_by_feature_id(self, db_session):
        repo = EntitlementRepository(db_session)
        plan1 = _create_plan(db_session, code="byfeat-p1")
        plan2 = _create_plan(db_session, code="byfeat-p2")
        feature = _create_feature(db_session, code="byfeat-f")
        _create_entitlement(db_session, plan1.id, feature.id)
        _create_entitlement(db_session, plan2.id, feature.id)
        entitlements = repo.get_by_feature_id(feature.id, DEFAULT_ORG_ID)
        assert len(entitlements) == 2

    def test_update(self, db_session):
        repo = EntitlementRepository(db_session)
        plan = _create_plan(db_session, code="upd-plan")
        feature = _create_feature(db_session, code="upd-feat")
        ent = _create_entitlement(db_session, plan.id, feature.id, value="true")
        data = EntitlementUpdate(value="false")
        result = repo.update(ent.id, data, DEFAULT_ORG_ID)
        assert result is not None
        assert result.value == "false"

    def test_update_not_found(self, db_session):
        repo = EntitlementRepository(db_session)
        data = EntitlementUpdate(value="nope")
        result = repo.update(generate_uuid(), data, DEFAULT_ORG_ID)
        assert result is None

    def test_delete(self, db_session):
        repo = EntitlementRepository(db_session)
        plan = _create_plan(db_session, code="del-plan")
        feature = _create_feature(db_session, code="del-feat")
        ent = _create_entitlement(db_session, plan.id, feature.id)
        assert repo.delete(ent.id, DEFAULT_ORG_ID) is True
        assert repo.get_by_id(ent.id, DEFAULT_ORG_ID) is None

    def test_delete_not_found(self, db_session):
        repo = EntitlementRepository(db_session)
        assert repo.delete(generate_uuid(), DEFAULT_ORG_ID) is False
