"""Entitlement model, repository, API endpoint, and service tests."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.models.customer import Customer, generate_uuid
from app.models.entitlement import Entitlement
from app.models.feature import Feature, FeatureType
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription
from app.repositories.entitlement_repository import EntitlementRepository
from app.schemas.entitlement import EntitlementCreate, EntitlementUpdate
from app.services.entitlement_service import EntitlementService
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


def _create_customer(db_session, external_id: str = "cust-test") -> Customer:
    """Helper to create a customer directly in the DB."""
    customer = Customer(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        external_id=external_id,
        name=f"Customer {external_id}",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


def _create_subscription(
    db_session, customer_id, plan_id, external_id: str = "sub-test"
) -> Subscription:
    """Helper to create a subscription directly in the DB."""
    subscription = Subscription(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        external_id=external_id,
        customer_id=customer_id,
        plan_id=plan_id,
        status="active",
    )
    db_session.add(subscription)
    db_session.commit()
    db_session.refresh(subscription)
    return subscription


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


class TestEntitlementsAPI:
    """Tests for entitlement CRUD endpoints."""

    def test_create_entitlement(self, client, db_session):
        """Test creating an entitlement via POST."""
        plan = _create_plan(db_session, code="api-plan")
        feature = _create_feature(db_session, code="api-feat")
        resp = client.post(
            "/v1/entitlements/",
            json={
                "plan_id": str(plan.id),
                "feature_id": str(feature.id),
                "value": "true",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["plan_id"] == str(plan.id)
        assert data["feature_id"] == str(feature.id)
        assert data["value"] == "true"
        assert data["id"] is not None

    def test_create_entitlement_invalid_plan(self, client, db_session):
        """Test creating an entitlement with invalid plan returns 400."""
        feature = _create_feature(db_session, code="inv-plan-feat")
        resp = client.post(
            "/v1/entitlements/",
            json={
                "plan_id": str(generate_uuid()),
                "feature_id": str(feature.id),
                "value": "true",
            },
        )
        assert resp.status_code == 400
        assert "Plan" in resp.json()["detail"]

    def test_create_entitlement_invalid_feature(self, client, db_session):
        """Test creating an entitlement with invalid feature returns 400."""
        plan = _create_plan(db_session, code="inv-feat-plan")
        resp = client.post(
            "/v1/entitlements/",
            json={
                "plan_id": str(plan.id),
                "feature_id": str(generate_uuid()),
                "value": "true",
            },
        )
        assert resp.status_code == 400
        assert "Feature" in resp.json()["detail"]

    def test_create_entitlement_duplicate(self, client, db_session):
        """Test creating a duplicate plan+feature entitlement returns 409."""
        plan = _create_plan(db_session, code="dup-plan")
        feature = _create_feature(db_session, code="dup-feat")
        _create_entitlement(db_session, plan.id, feature.id)

        resp = client.post(
            "/v1/entitlements/",
            json={
                "plan_id": str(plan.id),
                "feature_id": str(feature.id),
                "value": "false",
            },
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_create_entitlement_different_feature_same_plan(self, client, db_session):
        """Test creating entitlement for different feature on same plan succeeds."""
        plan = _create_plan(db_session, code="diff-feat-plan")
        f1 = _create_feature(db_session, code="diff-f1")
        f2 = _create_feature(db_session, code="diff-f2")
        _create_entitlement(db_session, plan.id, f1.id)

        resp = client.post(
            "/v1/entitlements/",
            json={
                "plan_id": str(plan.id),
                "feature_id": str(f2.id),
                "value": "100",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["feature_id"] == str(f2.id)

    def test_create_entitlement_validation_error(self, client, db_session):
        """Test creating an entitlement with invalid data returns 422."""
        plan = _create_plan(db_session, code="val-plan")
        feature = _create_feature(db_session, code="val-feat")
        resp = client.post(
            "/v1/entitlements/",
            json={
                "plan_id": str(plan.id),
                "feature_id": str(feature.id),
                "value": "",
            },
        )
        assert resp.status_code == 422

    def test_list_entitlements(self, client, db_session):
        """Test listing entitlements."""
        plan = _create_plan(db_session, code="list-plan")
        for i in range(3):
            feat = _create_feature(db_session, code=f"list-f{i}")
            _create_entitlement(db_session, plan.id, feat.id)

        resp = client.get("/v1/entitlements/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert resp.headers["X-Total-Count"] == "3"

    def test_list_entitlements_filter_by_plan(self, client, db_session):
        """Test listing entitlements filtered by plan_id."""
        plan1 = _create_plan(db_session, code="filt-p1")
        plan2 = _create_plan(db_session, code="filt-p2")
        f1 = _create_feature(db_session, code="filt-f1")
        f2 = _create_feature(db_session, code="filt-f2")
        _create_entitlement(db_session, plan1.id, f1.id)
        _create_entitlement(db_session, plan2.id, f2.id)

        resp = client.get(f"/v1/entitlements/?plan_id={plan1.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["plan_id"] == str(plan1.id)
        assert resp.headers["X-Total-Count"] == "1"

    def test_list_entitlements_pagination(self, client, db_session):
        """Test listing entitlements with pagination."""
        plan = _create_plan(db_session, code="page-plan2")
        for i in range(5):
            feat = _create_feature(db_session, code=f"page2-f{i}")
            _create_entitlement(db_session, plan.id, feat.id)

        resp = client.get("/v1/entitlements/?skip=1&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_entitlements_empty(self, client):
        """Test listing entitlements when none exist."""
        resp = client.get("/v1/entitlements/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_update_entitlement(self, client, db_session):
        """Test updating an entitlement via PATCH."""
        plan = _create_plan(db_session, code="upd-api-plan")
        feature = _create_feature(db_session, code="upd-api-feat")
        ent = _create_entitlement(db_session, plan.id, feature.id, value="true")

        resp = client.patch(
            f"/v1/entitlements/{ent.id}",
            json={"value": "false"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == "false"

    def test_update_entitlement_not_found(self, client):
        """Test updating a non-existent entitlement returns 404."""
        resp = client.patch(
            f"/v1/entitlements/{generate_uuid()}",
            json={"value": "nope"},
        )
        assert resp.status_code == 404

    def test_delete_entitlement(self, client, db_session):
        """Test deleting an entitlement."""
        plan = _create_plan(db_session, code="del-api-plan")
        feature = _create_feature(db_session, code="del-api-feat")
        ent = _create_entitlement(db_session, plan.id, feature.id)

        resp = client.delete(f"/v1/entitlements/{ent.id}")
        assert resp.status_code == 204

    def test_delete_entitlement_not_found(self, client):
        """Test deleting a non-existent entitlement returns 404."""
        resp = client.delete(f"/v1/entitlements/{generate_uuid()}")
        assert resp.status_code == 404

    def test_create_idempotency(self, client, db_session):
        """Test idempotent creation with Idempotency-Key header."""
        plan = _create_plan(db_session, code="idem-plan")
        feature = _create_feature(db_session, code="idem-feat")
        key = str(uuid.uuid4())
        headers = {"Idempotency-Key": key}
        resp1 = client.post(
            "/v1/entitlements/",
            json={
                "plan_id": str(plan.id),
                "feature_id": str(feature.id),
                "value": "true",
            },
            headers=headers,
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/v1/entitlements/",
            json={
                "plan_id": str(plan.id),
                "feature_id": str(feature.id),
                "value": "true",
            },
            headers=headers,
        )
        assert resp2.status_code == 201
        assert resp1.json()["id"] == resp2.json()["id"]


class TestSubscriptionEntitlements:
    """Tests for GET /v1/subscriptions/{external_id}/entitlements."""

    def test_get_subscription_entitlements(self, client, db_session):
        """Test getting entitlements for a subscription."""
        plan = _create_plan(db_session, code="sub-ent-plan")
        customer = _create_customer(db_session, external_id="sub-ent-cust")
        subscription = _create_subscription(
            db_session, customer.id, plan.id, external_id="sub-ent-1"
        )
        f1 = _create_feature(db_session, code="sub-ent-f1")
        f2 = _create_feature(db_session, code="sub-ent-f2")
        _create_entitlement(db_session, plan.id, f1.id, value="true")
        _create_entitlement(db_session, plan.id, f2.id, value="100")

        resp = client.get(
            f"/v1/subscriptions/{subscription.external_id}/entitlements"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_get_subscription_entitlements_empty(self, client, db_session):
        """Test getting entitlements when plan has none."""
        plan = _create_plan(db_session, code="sub-empty-plan")
        customer = _create_customer(db_session, external_id="sub-empty-cust")
        _create_subscription(
            db_session, customer.id, plan.id, external_id="sub-empty-1"
        )

        resp = client.get("/v1/subscriptions/sub-empty-1/entitlements")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_subscription_entitlements_not_found(self, client):
        """Test getting entitlements for non-existent subscription returns 404."""
        resp = client.get("/v1/subscriptions/nonexistent-sub/entitlements")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


class TestEntitlementService:
    """Tests for EntitlementService.check_entitlement."""

    def test_check_entitlement_has_access(self, db_session):
        """Test checking an entitlement the subscription has access to."""
        plan = _create_plan(db_session, code="svc-plan")
        feature = _create_feature(db_session, code="svc-feat")
        _create_entitlement(db_session, plan.id, feature.id, value="true")
        customer = _create_customer(db_session, external_id="svc-cust")
        subscription = _create_subscription(
            db_session, customer.id, plan.id, external_id="svc-sub"
        )

        service = EntitlementService(db_session)
        result = service.check_entitlement(subscription.id, "svc-feat")
        assert result.feature_code == "svc-feat"
        assert result.has_access is True
        assert result.value == "true"

    def test_check_entitlement_no_access(self, db_session):
        """Test checking an entitlement the subscription does not have."""
        plan = _create_plan(db_session, code="svc-no-plan")
        _create_feature(db_session, code="svc-no-feat")
        customer = _create_customer(db_session, external_id="svc-no-cust")
        subscription = _create_subscription(
            db_session, customer.id, plan.id, external_id="svc-no-sub"
        )
        # Feature exists but no entitlement for this plan

        service = EntitlementService(db_session)
        result = service.check_entitlement(subscription.id, "svc-no-feat")
        assert result.feature_code == "svc-no-feat"
        assert result.has_access is False
        assert result.value is None

    def test_check_entitlement_subscription_not_found(self, db_session):
        """Test check_entitlement raises for nonexistent subscription."""
        service = EntitlementService(db_session)
        with pytest.raises(ValueError, match="Subscription"):
            service.check_entitlement(generate_uuid(), "any-feat")

    def test_check_entitlement_feature_not_found(self, db_session):
        """Test check_entitlement raises for nonexistent feature."""
        plan = _create_plan(db_session, code="svc-nf-plan")
        customer = _create_customer(db_session, external_id="svc-nf-cust")
        subscription = _create_subscription(
            db_session, customer.id, plan.id, external_id="svc-nf-sub"
        )

        service = EntitlementService(db_session)
        with pytest.raises(ValueError, match="Feature"):
            service.check_entitlement(subscription.id, "nonexistent-feature")

    def test_check_entitlement_quantity_value(self, db_session):
        """Test checking an entitlement with a quantity value."""
        plan = _create_plan(db_session, code="svc-qty-plan")
        feature = _create_feature(
            db_session, code="svc-qty-feat", feature_type=FeatureType.QUANTITY.value
        )
        _create_entitlement(db_session, plan.id, feature.id, value="50")
        customer = _create_customer(db_session, external_id="svc-qty-cust")
        subscription = _create_subscription(
            db_session, customer.id, plan.id, external_id="svc-qty-sub"
        )

        service = EntitlementService(db_session)
        result = service.check_entitlement(subscription.id, "svc-qty-feat")
        assert result.has_access is True
        assert result.value == "50"

    def test_check_entitlement_multiple_entitlements(self, db_session):
        """Test checking when plan has multiple entitlements."""
        plan = _create_plan(db_session, code="svc-multi-plan")
        f1 = _create_feature(db_session, code="svc-multi-f1")
        f2 = _create_feature(db_session, code="svc-multi-f2")
        _create_entitlement(db_session, plan.id, f1.id, value="true")
        _create_entitlement(db_session, plan.id, f2.id, value="200")
        customer = _create_customer(db_session, external_id="svc-multi-cust")
        subscription = _create_subscription(
            db_session, customer.id, plan.id, external_id="svc-multi-sub"
        )

        service = EntitlementService(db_session)
        result = service.check_entitlement(subscription.id, "svc-multi-f2")
        assert result.has_access is True
        assert result.value == "200"


class TestCopyEntitlementsAPI:
    """Tests for the copy entitlements endpoint."""

    def test_copy_entitlements_success(self, client, db_session):
        """Test copying entitlements from one plan to another."""
        source_plan = _create_plan(db_session, code="copy-src")
        target_plan = _create_plan(db_session, code="copy-tgt")
        f1 = _create_feature(db_session, code="copy-f1")
        f2 = _create_feature(db_session, code="copy-f2")
        _create_entitlement(db_session, source_plan.id, f1.id, value="true")
        _create_entitlement(db_session, source_plan.id, f2.id, value="100")

        resp = client.post(
            "/v1/entitlements/copy",
            json={
                "source_plan_id": str(source_plan.id),
                "target_plan_id": str(target_plan.id),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 2
        values = {d["value"] for d in data}
        assert values == {"true", "100"}

    def test_copy_entitlements_skips_existing(self, client, db_session):
        """Test copy skips features that already exist on the target plan."""
        source_plan = _create_plan(db_session, code="copy-skip-src")
        target_plan = _create_plan(db_session, code="copy-skip-tgt")
        f1 = _create_feature(db_session, code="copy-skip-f1")
        f2 = _create_feature(db_session, code="copy-skip-f2")
        _create_entitlement(db_session, source_plan.id, f1.id, value="true")
        _create_entitlement(db_session, source_plan.id, f2.id, value="50")
        # Target already has f1
        _create_entitlement(db_session, target_plan.id, f1.id, value="false")

        resp = client.post(
            "/v1/entitlements/copy",
            json={
                "source_plan_id": str(source_plan.id),
                "target_plan_id": str(target_plan.id),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 1
        assert data[0]["value"] == "50"

    def test_copy_entitlements_empty_source(self, client, db_session):
        """Test copy with no entitlements on source plan returns empty list."""
        source_plan = _create_plan(db_session, code="copy-empty-src")
        target_plan = _create_plan(db_session, code="copy-empty-tgt")

        resp = client.post(
            "/v1/entitlements/copy",
            json={
                "source_plan_id": str(source_plan.id),
                "target_plan_id": str(target_plan.id),
            },
        )
        assert resp.status_code == 201
        assert resp.json() == []

    def test_copy_entitlements_same_plan(self, client, db_session):
        """Test copy to same plan returns 400."""
        plan = _create_plan(db_session, code="copy-same")

        resp = client.post(
            "/v1/entitlements/copy",
            json={
                "source_plan_id": str(plan.id),
                "target_plan_id": str(plan.id),
            },
        )
        assert resp.status_code == 400
        assert "different" in resp.json()["detail"]

    def test_copy_entitlements_source_not_found(self, client, db_session):
        """Test copy with invalid source plan returns 400."""
        target_plan = _create_plan(db_session, code="copy-notfound-tgt")

        resp = client.post(
            "/v1/entitlements/copy",
            json={
                "source_plan_id": str(generate_uuid()),
                "target_plan_id": str(target_plan.id),
            },
        )
        assert resp.status_code == 400
        assert "Source plan" in resp.json()["detail"]

    def test_copy_entitlements_target_not_found(self, client, db_session):
        """Test copy with invalid target plan returns 400."""
        source_plan = _create_plan(db_session, code="copy-notfound-src")

        resp = client.post(
            "/v1/entitlements/copy",
            json={
                "source_plan_id": str(source_plan.id),
                "target_plan_id": str(generate_uuid()),
            },
        )
        assert resp.status_code == 400
        assert "Target plan" in resp.json()["detail"]
