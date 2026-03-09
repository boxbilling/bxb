"""Minimal smoke tests for the public bxb repo.

Proves the app boots, core CRUD works, and endpoints respond correctly.
Full test suite with 100% coverage is maintained in bxb-internal.
"""

from decimal import Decimal

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.billable_metric import AggregationType, BillableMetric


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def billable_metric(db_session):
    """Create a billable metric required for event ingestion."""
    metric = BillableMetric(
        code="api_calls",
        name="API Calls",
        aggregation_type=AggregationType.COUNT.value,
    )
    db_session.add(metric)
    db_session.commit()
    db_session.refresh(metric)
    return metric


def test_app_starts():
    """The FastAPI app object can be imported and is a FastAPI instance."""
    assert isinstance(app, FastAPI)


def test_health_endpoint(client: TestClient):
    """GET / returns 200 with app info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "version" in data


def test_create_customer(client: TestClient):
    """POST /v1/customers/ creates a customer."""
    response = client.post(
        "/v1/customers/",
        json={"external_id": "smoke-cust-001", "name": "Smoke Test Customer"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["external_id"] == "smoke-cust-001"
    assert data["name"] == "Smoke Test Customer"
    assert "id" in data


def test_list_customers(client: TestClient):
    """GET /v1/customers/ returns a list."""
    # Create a customer first
    client.post(
        "/v1/customers/",
        json={"external_id": "smoke-cust-list", "name": "List Customer"},
    )
    response = client.get("/v1/customers/")
    assert response.status_code == 200
    customers = response.json()
    assert isinstance(customers, list)
    assert len(customers) >= 1


def test_create_plan(client: TestClient):
    """POST /v1/plans/ creates a plan."""
    response = client.post(
        "/v1/plans/",
        json={"code": "smoke_plan", "name": "Smoke Plan", "interval": "monthly"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "smoke_plan"
    assert data["name"] == "Smoke Plan"
    assert data["interval"] == "monthly"
    assert "id" in data


def test_create_subscription(client: TestClient):
    """POST /v1/subscriptions/ creates a subscription linking customer + plan."""
    customer = client.post(
        "/v1/customers/",
        json={"external_id": "smoke-sub-cust", "name": "Sub Customer"},
    ).json()
    plan = client.post(
        "/v1/plans/",
        json={"code": "smoke_sub_plan", "name": "Sub Plan", "interval": "monthly"},
    ).json()

    response = client.post(
        "/v1/subscriptions/",
        json={
            "external_id": "smoke-sub-001",
            "customer_id": customer["id"],
            "plan_id": plan["id"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["external_id"] == "smoke-sub-001"
    assert data["customer_id"] == customer["id"]
    assert data["plan_id"] == plan["id"]
    assert data["status"] in ("pending", "active")


def test_ingest_event(client: TestClient, billable_metric):
    """POST /v1/events/ ingests an event."""
    response = client.post(
        "/v1/events/",
        json={
            "transaction_id": "smoke-tx-001",
            "external_customer_id": "smoke-cust-001",
            "code": "api_calls",
            "timestamp": "2026-01-15T10:00:00Z",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["transaction_id"] == "smoke-tx-001"
    assert data["code"] == "api_calls"
    assert "id" in data


def test_create_invoice(client: TestClient):
    """POST /v1/invoices/one_off creates a one-off invoice."""
    customer = client.post(
        "/v1/customers/",
        json={"external_id": "smoke-inv-cust", "name": "Invoice Customer"},
    ).json()

    response = client.post(
        "/v1/invoices/one_off",
        json={
            "customer_id": customer["id"],
            "currency": "USD",
            "line_items": [
                {
                    "description": "Smoke test fee",
                    "quantity": "1",
                    "unit_price": "49.99",
                    "amount": "49.99",
                }
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "draft"
    assert data["customer_id"] == customer["id"]
    assert Decimal(data["subtotal_cents"]) == Decimal("49.99")


def test_delete_organization(client: TestClient):
    """DELETE /v1/organizations/{id} hard-deletes an org and its children."""
    from app.core.config import settings

    # Ensure admin secret is configured for this test
    original_secret = settings.BXB_ADMIN_SECRET
    test_secret = "smoke-test-admin-secret-that-is-at-least-32-chars-long"
    settings.BXB_ADMIN_SECRET = test_secret

    admin_headers = {"X-Admin-Secret": test_secret}

    try:
        # Step 1: Create a new organization
        org_resp = client.post(
            "/v1/organizations/",
            headers=admin_headers,
            json={"name": "Delete Test Org"},
        )
        assert org_resp.status_code == 201
        org_data = org_resp.json()
        org_id = org_data["id"]
        raw_key = org_data["api_key"]["raw_key"]

        bearer_headers = {"Authorization": f"Bearer {raw_key}"}

        # Step 2: Create a customer under that org
        cust_resp = client.post(
            "/v1/customers/",
            headers=bearer_headers,
            json={"external_id": "del-test-cust", "name": "Delete Test Customer"},
        )
        assert cust_resp.status_code == 201

        # Step 3: Create a plan under that org
        plan_resp = client.post(
            "/v1/plans/",
            headers=bearer_headers,
            json={"code": "del_test_plan", "name": "Delete Test Plan", "interval": "monthly"},
        )
        assert plan_resp.status_code == 201

        # Step 4: Delete the organization
        del_resp = client.delete(f"/v1/organizations/{org_id}", headers=admin_headers)
        assert del_resp.status_code == 204

        # Step 5: Verify the org is gone
        list_resp = client.get("/v1/organizations/", headers=admin_headers)
        assert list_resp.status_code == 200
        org_ids = [o["id"] for o in list_resp.json()]
        assert org_id not in org_ids

        # Step 6: Verify re-deleting returns 404
        del2_resp = client.delete(f"/v1/organizations/{org_id}", headers=admin_headers)
        assert del2_resp.status_code == 404
    finally:
        settings.BXB_ADMIN_SECRET = original_secret
