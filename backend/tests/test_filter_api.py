"""Tests for filter API endpoints (billable metric filters and charge filters via plans)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.charge_filter import ChargeFilter
from app.models.charge_filter_value import ChargeFilterValue


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


def create_metric(client: TestClient, code: str = "api_calls") -> dict:
    """Helper to create a billable metric via API."""
    response = client.post(
        "/v1/billable_metrics/",
        json={
            "code": code,
            "name": f"Metric {code}",
            "aggregation_type": "count",
        },
    )
    assert response.status_code == 201
    return response.json()


class TestBillableMetricFilterAPI:
    def test_create_filter(self, client: TestClient):
        """Test creating a filter on a billable metric."""
        metric = create_metric(client, "filter_create")

        response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={
                "key": "region",
                "values": ["us-east", "eu-west", "ap-south"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "region"
        assert data["values"] == ["us-east", "eu-west", "ap-south"]
        assert "id" in data
        assert "billable_metric_id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_filter_default_values(self, client: TestClient):
        """Test creating a filter with default empty values."""
        metric = create_metric(client, "filter_defaults")

        response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "tier"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "tier"
        assert data["values"] == []

    def test_create_filter_metric_not_found(self, client: TestClient):
        """Test creating a filter on a non-existent metric."""
        response = client.post(
            "/v1/billable_metrics/nonexistent_code/filters",
            json={"key": "region", "values": ["us-east"]},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Billable metric not found"

    def test_create_filter_empty_key_rejected(self, client: TestClient):
        """Test creating a filter with empty key is rejected."""
        metric = create_metric(client, "filter_empty_key")

        response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "", "values": ["us-east"]},
        )
        assert response.status_code == 422

    def test_create_filter_duplicate_key(self, client: TestClient):
        """Test creating a duplicate filter key on the same metric raises IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        metric = create_metric(client, "filter_dup_key")

        # Create first filter
        response1 = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east"]},
        )
        assert response1.status_code == 201

        # Create second filter with same key - IntegrityError from unique constraint
        with pytest.raises(IntegrityError):
            client.post(
                f"/v1/billable_metrics/{metric['code']}/filters",
                json={"key": "region", "values": ["eu-west"]},
            )

    def test_list_filters(self, client: TestClient):
        """Test listing filters for a metric."""
        metric = create_metric(client, "filter_list")

        # Create filters
        client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east", "eu-west"]},
        )
        client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "tier", "values": ["free", "pro"]},
        )

        response = client.get(f"/v1/billable_metrics/{metric['code']}/filters")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        keys = {f["key"] for f in data}
        assert keys == {"region", "tier"}

    def test_list_filters_empty(self, client: TestClient):
        """Test listing filters when none exist."""
        metric = create_metric(client, "filter_empty_list")

        response = client.get(
            f"/v1/billable_metrics/{metric['code']}/filters"
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_filters_metric_not_found(self, client: TestClient):
        """Test listing filters for a non-existent metric."""
        response = client.get(
            "/v1/billable_metrics/nonexistent_code/filters"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Billable metric not found"

    def test_delete_filter(self, client: TestClient):
        """Test deleting a filter."""
        metric = create_metric(client, "filter_delete")

        # Create filter
        create_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east"]},
        )
        filter_id = create_response.json()["id"]

        # Delete filter
        response = client.delete(
            f"/v1/billable_metrics/{metric['code']}/filters/{filter_id}"
        )
        assert response.status_code == 204

        # Verify it's gone
        list_response = client.get(
            f"/v1/billable_metrics/{metric['code']}/filters"
        )
        assert list_response.json() == []

    def test_delete_filter_not_found(self, client: TestClient):
        """Test deleting a non-existent filter."""
        metric = create_metric(client, "filter_del_404")

        fake_id = str(uuid.uuid4())
        response = client.delete(
            f"/v1/billable_metrics/{metric['code']}/filters/{fake_id}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Filter not found"

    def test_delete_filter_metric_not_found(self, client: TestClient):
        """Test deleting a filter on a non-existent metric."""
        fake_id = str(uuid.uuid4())
        response = client.delete(
            f"/v1/billable_metrics/nonexistent_code/filters/{fake_id}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Billable metric not found"

    def test_delete_filter_invalid_uuid(self, client: TestClient):
        """Test deleting a filter with an invalid UUID."""
        metric = create_metric(client, "filter_bad_uuid")

        response = client.delete(
            f"/v1/billable_metrics/{metric['code']}/filters/not-a-uuid"
        )
        assert response.status_code == 422

    def test_multiple_metrics_with_filters(self, client: TestClient):
        """Test filters are scoped to their metric."""
        metric1 = create_metric(client, "filter_scope_1")
        metric2 = create_metric(client, "filter_scope_2")

        client.post(
            f"/v1/billable_metrics/{metric1['code']}/filters",
            json={"key": "region", "values": ["us-east"]},
        )
        client.post(
            f"/v1/billable_metrics/{metric2['code']}/filters",
            json={"key": "tier", "values": ["free"]},
        )

        response1 = client.get(
            f"/v1/billable_metrics/{metric1['code']}/filters"
        )
        response2 = client.get(
            f"/v1/billable_metrics/{metric2['code']}/filters"
        )

        assert len(response1.json()) == 1
        assert response1.json()[0]["key"] == "region"
        assert len(response2.json()) == 1
        assert response2.json()[0]["key"] == "tier"


class TestPlanChargeFilterAPI:
    def test_create_plan_with_charge_filters(self, client: TestClient):
        """Test creating a plan with charge filters."""
        # Create metric and filter
        metric = create_metric(client, "pcf_create")
        filter_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east", "eu-west"]},
        )
        filter_id = filter_response.json()["id"]

        # Create plan with charge that has filters
        response = client.post(
            "/v1/plans/",
            json={
                "code": "plan_with_filters",
                "name": "Plan with Filters",
                "interval": "monthly",
                "amount_cents": 1000,
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "10"},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                                "values": ["us-east"],
                                "properties": {"amount": "20"},
                                "invoice_display_name": "US East",
                            }
                        ],
                    }
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["charges"]) == 1

    def test_create_plan_with_charge_filters_stored(
        self, client: TestClient, db_session
    ):
        """Test that charge filters are correctly stored in the DB."""
        metric = create_metric(client, "pcf_stored")
        filter_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east", "eu-west"]},
        )
        filter_id = filter_response.json()["id"]

        plan_response = client.post(
            "/v1/plans/",
            json={
                "code": "pcf_stored_plan",
                "name": "Stored Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "10"},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                                "values": ["us-east"],
                                "properties": {"amount": "25"},
                                "invoice_display_name": "US East Region",
                            }
                        ],
                    }
                ],
            },
        )
        assert plan_response.status_code == 201
        charge_id = plan_response.json()["charges"][0]["id"]

        # Verify charge filters in DB
        charge_filters = (
            db_session.query(ChargeFilter)
            .filter(ChargeFilter.charge_id == charge_id)
            .all()
        )
        assert len(charge_filters) == 1
        assert charge_filters[0].properties == {"amount": "25"}
        assert charge_filters[0].invoice_display_name == "US East Region"

        # Verify charge filter values in DB
        filter_values = (
            db_session.query(ChargeFilterValue)
            .filter(
                ChargeFilterValue.charge_filter_id == charge_filters[0].id
            )
            .all()
        )
        assert len(filter_values) == 1
        assert filter_values[0].value == "us-east"
        assert str(filter_values[0].billable_metric_filter_id) == filter_id

    def test_create_plan_with_multiple_filter_values(
        self, client: TestClient, db_session
    ):
        """Test creating a plan with multiple values per filter.

        Each value creates a separate ChargeFilter+ChargeFilterValue pair
        due to the unique constraint on (charge_filter_id, billable_metric_filter_id).
        """
        metric = create_metric(client, "pcf_multi_val")
        filter_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={
                "key": "region",
                "values": ["us-east", "eu-west", "ap-south"],
            },
        )
        filter_id = filter_response.json()["id"]

        plan_response = client.post(
            "/v1/plans/",
            json={
                "code": "pcf_multi_val_plan",
                "name": "Multi Val Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "10"},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                                "values": ["us-east", "eu-west"],
                                "properties": {"amount": "15"},
                            }
                        ],
                    }
                ],
            },
        )
        assert plan_response.status_code == 201
        charge_id = plan_response.json()["charges"][0]["id"]

        # Each value creates a separate ChargeFilter
        charge_filters = (
            db_session.query(ChargeFilter)
            .filter(ChargeFilter.charge_id == charge_id)
            .all()
        )
        assert len(charge_filters) == 2

        # Collect all filter values across all charge filters
        all_values = set()
        for cf in charge_filters:
            assert cf.properties == {"amount": "15"}
            filter_values = (
                db_session.query(ChargeFilterValue)
                .filter(ChargeFilterValue.charge_filter_id == cf.id)
                .all()
            )
            assert len(filter_values) == 1
            all_values.add(filter_values[0].value)
        assert all_values == {"us-east", "eu-west"}

    def test_create_plan_with_multiple_charge_filters(
        self, client: TestClient, db_session
    ):
        """Test creating a plan with multiple filters on one charge."""
        metric = create_metric(client, "pcf_multi_filter")
        f1 = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east", "eu-west"]},
        ).json()
        f2 = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "tier", "values": ["free", "pro"]},
        ).json()

        plan_response = client.post(
            "/v1/plans/",
            json={
                "code": "pcf_multi_filter_plan",
                "name": "Multi Filter Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "10"},
                        "filters": [
                            {
                                "billable_metric_filter_id": f1["id"],
                                "values": ["us-east"],
                                "properties": {"amount": "20"},
                                "invoice_display_name": "US East",
                            },
                            {
                                "billable_metric_filter_id": f2["id"],
                                "values": ["pro"],
                                "properties": {"amount": "30"},
                                "invoice_display_name": "Pro Tier",
                            },
                        ],
                    }
                ],
            },
        )
        assert plan_response.status_code == 201
        charge_id = plan_response.json()["charges"][0]["id"]

        charge_filters = (
            db_session.query(ChargeFilter)
            .filter(ChargeFilter.charge_id == charge_id)
            .all()
        )
        assert len(charge_filters) == 2

    def test_create_plan_without_filters(self, client: TestClient):
        """Test that plans without filters still work fine."""
        metric = create_metric(client, "pcf_no_filters")

        response = client.post(
            "/v1/plans/",
            json={
                "code": "no_filter_plan",
                "name": "No Filter Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "10"},
                    }
                ],
            },
        )
        assert response.status_code == 201
        assert len(response.json()["charges"]) == 1

    def test_create_plan_invalid_filter_id(self, client: TestClient):
        """Test creating a plan with non-existent filter ID."""
        metric = create_metric(client, "pcf_bad_filter")
        fake_filter_id = str(uuid.uuid4())

        response = client.post(
            "/v1/plans/",
            json={
                "code": "bad_filter_plan",
                "name": "Bad Filter Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                        "filters": [
                            {
                                "billable_metric_filter_id": fake_filter_id,
                                "values": ["us-east"],
                                "properties": {"amount": "20"},
                            }
                        ],
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert "Billable metric filter" in response.json()["detail"]
        assert "not found" in response.json()["detail"]

    def test_create_plan_invalid_filter_value(self, client: TestClient):
        """Test creating a plan with value not in allowed values."""
        metric = create_metric(client, "pcf_bad_val")
        filter_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east", "eu-west"]},
        )
        filter_id = filter_response.json()["id"]

        response = client.post(
            "/v1/plans/",
            json={
                "code": "bad_val_plan",
                "name": "Bad Value Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                                "values": ["invalid-region"],
                                "properties": {"amount": "20"},
                            }
                        ],
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]
        assert "invalid-region" in response.json()["detail"]

    def test_create_plan_filter_value_validation_skipped_empty(
        self, client: TestClient
    ):
        """Test that value validation is skipped when filter has empty values list."""
        metric = create_metric(client, "pcf_empty_vals")
        filter_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "custom_dim"},  # No values = any value allowed
        )
        filter_id = filter_response.json()["id"]

        response = client.post(
            "/v1/plans/",
            json={
                "code": "empty_val_plan",
                "name": "Empty Val Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                                "values": ["any-value-is-ok"],
                                "properties": {"amount": "20"},
                            }
                        ],
                    }
                ],
            },
        )
        assert response.status_code == 201

    def test_update_plan_with_charge_filters(
        self, client: TestClient, db_session
    ):
        """Test updating a plan to add charge filters."""
        metric = create_metric(client, "pcf_update")
        filter_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east", "eu-west"]},
        )
        filter_id = filter_response.json()["id"]

        # Create plan without filters
        plan_response = client.post(
            "/v1/plans/",
            json={
                "code": "pcf_update_plan",
                "name": "Update Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "10"},
                    }
                ],
            },
        )
        plan_id = plan_response.json()["id"]

        # Update plan to add filters
        update_response = client.put(
            f"/v1/plans/{plan_id}",
            json={
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "10"},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                                "values": ["us-east"],
                                "properties": {"amount": "25"},
                                "invoice_display_name": "US East",
                            }
                        ],
                    }
                ],
            },
        )
        assert update_response.status_code == 200

        # Verify filters in DB
        charge_id = update_response.json()["charges"][0]["id"]
        charge_filters = (
            db_session.query(ChargeFilter)
            .filter(ChargeFilter.charge_id == charge_id)
            .all()
        )
        assert len(charge_filters) == 1
        assert charge_filters[0].properties == {"amount": "25"}

    def test_update_plan_replaces_charge_filters(
        self, client: TestClient, db_session
    ):
        """Test that updating charges replaces old charge filters."""
        metric = create_metric(client, "pcf_replace")
        filter_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east", "eu-west"]},
        )
        filter_id = filter_response.json()["id"]

        # Create plan with filters
        plan_response = client.post(
            "/v1/plans/",
            json={
                "code": "pcf_replace_plan",
                "name": "Replace Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "10"},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                                "values": ["us-east"],
                                "properties": {"amount": "20"},
                            }
                        ],
                    }
                ],
            },
        )
        plan_id = plan_response.json()["id"]
        old_charge_id = plan_response.json()["charges"][0]["id"]

        # Update plan with different filters
        update_response = client.put(
            f"/v1/plans/{plan_id}",
            json={
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {"amount": "10"},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                                "values": ["eu-west"],
                                "properties": {"amount": "30"},
                                "invoice_display_name": "EU West",
                            }
                        ],
                    }
                ],
            },
        )
        assert update_response.status_code == 200

        # Verify old filters are gone
        old_filters = (
            db_session.query(ChargeFilter)
            .filter(ChargeFilter.charge_id == old_charge_id)
            .all()
        )
        assert len(old_filters) == 0

        # Verify new filters exist
        new_charge_id = update_response.json()["charges"][0]["id"]
        new_filters = (
            db_session.query(ChargeFilter)
            .filter(ChargeFilter.charge_id == new_charge_id)
            .all()
        )
        assert len(new_filters) == 1
        assert new_filters[0].properties == {"amount": "30"}
        assert new_filters[0].invoice_display_name == "EU West"

    def test_update_plan_invalid_filter_id(self, client: TestClient):
        """Test updating a plan with non-existent filter ID."""
        metric = create_metric(client, "pcf_upd_bad_filter")
        fake_filter_id = str(uuid.uuid4())

        plan_response = client.post(
            "/v1/plans/",
            json={
                "code": "pcf_upd_bad_plan",
                "name": "Update Bad Plan",
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
        plan_id = plan_response.json()["id"]

        response = client.put(
            f"/v1/plans/{plan_id}",
            json={
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                        "filters": [
                            {
                                "billable_metric_filter_id": fake_filter_id,
                                "values": ["us-east"],
                                "properties": {},
                            }
                        ],
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    def test_update_plan_invalid_filter_value(self, client: TestClient):
        """Test updating a plan with invalid filter value."""
        metric = create_metric(client, "pcf_upd_bad_val")
        filter_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east", "eu-west"]},
        )
        filter_id = filter_response.json()["id"]

        plan_response = client.post(
            "/v1/plans/",
            json={
                "code": "pcf_upd_bad_val_plan",
                "name": "Update Bad Val Plan",
                "interval": "monthly",
            },
        )
        plan_id = plan_response.json()["id"]

        response = client.put(
            f"/v1/plans/{plan_id}",
            json={
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                                "values": ["bad-region"],
                                "properties": {},
                            }
                        ],
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]

    def test_delete_plan_removes_plan(self, client: TestClient):
        """Test that deleting a plan with charge filters succeeds."""
        metric = create_metric(client, "pcf_cascade")
        filter_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region", "values": ["us-east"]},
        )
        filter_id = filter_response.json()["id"]

        plan_response = client.post(
            "/v1/plans/",
            json={
                "code": "pcf_cascade_plan",
                "name": "Cascade Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                                "values": ["us-east"],
                                "properties": {"amount": "20"},
                            }
                        ],
                    }
                ],
            },
        )
        plan_id = plan_response.json()["id"]

        # Delete plan
        response = client.delete(f"/v1/plans/{plan_id}")
        assert response.status_code == 204

        # Verify plan is gone
        get_response = client.get(f"/v1/plans/{plan_id}")
        assert get_response.status_code == 404


class TestChargeFilterInputSchema:
    def test_charge_filter_input_defaults(self, client: TestClient):
        """Test ChargeFilterInput schema defaults."""
        metric = create_metric(client, "cfi_defaults")
        filter_response = client.post(
            f"/v1/billable_metrics/{metric['code']}/filters",
            json={"key": "region"},
        )
        filter_id = filter_response.json()["id"]

        response = client.post(
            "/v1/plans/",
            json={
                "code": "cfi_defaults_plan",
                "name": "CFI Defaults Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                        "filters": [
                            {
                                "billable_metric_filter_id": filter_id,
                            }
                        ],
                    }
                ],
            },
        )
        assert response.status_code == 201

    def test_charge_input_empty_filters_list(self, client: TestClient):
        """Test that empty filters list is fine."""
        metric = create_metric(client, "cfi_empty_list")

        response = client.post(
            "/v1/plans/",
            json={
                "code": "cfi_empty_plan",
                "name": "Empty Filters Plan",
                "interval": "monthly",
                "charges": [
                    {
                        "billable_metric_id": metric["id"],
                        "charge_model": "standard",
                        "properties": {},
                        "filters": [],
                    }
                ],
            },
        )
        assert response.status_code == 201
