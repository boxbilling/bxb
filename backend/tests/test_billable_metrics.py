"""Billable Metric API tests for bxb."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.billable_metric import AggregationType, BillableMetric
from app.models.charge import Charge
from app.models.plan import Plan
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.schemas.billable_metric import BillableMetricCreate, BillableMetricStats
from tests.conftest import DEFAULT_ORG_ID


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


class TestAggregationType:
    def test_count(self):
        """Test COUNT aggregation type."""
        assert AggregationType.COUNT == "count"
        assert AggregationType.COUNT.value == "count"

    def test_sum(self):
        """Test SUM aggregation type."""
        assert AggregationType.SUM == "sum"
        assert AggregationType.SUM.value == "sum"

    def test_max(self):
        """Test MAX aggregation type."""
        assert AggregationType.MAX == "max"
        assert AggregationType.MAX.value == "max"

    def test_unique_count(self):
        """Test UNIQUE_COUNT aggregation type."""
        assert AggregationType.UNIQUE_COUNT == "unique_count"
        assert AggregationType.UNIQUE_COUNT.value == "unique_count"

    def test_weighted_sum(self):
        """Test WEIGHTED_SUM aggregation type."""
        assert AggregationType.WEIGHTED_SUM == "weighted_sum"
        assert AggregationType.WEIGHTED_SUM.value == "weighted_sum"

    def test_latest(self):
        """Test LATEST aggregation type."""
        assert AggregationType.LATEST == "latest"
        assert AggregationType.LATEST.value == "latest"

    def test_custom(self):
        """Test CUSTOM aggregation type."""
        assert AggregationType.CUSTOM == "custom"
        assert AggregationType.CUSTOM.value == "custom"


class TestBillableMetricModel:
    def test_billable_metric_defaults(self, db_session):
        """Test BillableMetric model default values."""
        metric = BillableMetric(
            code="api_calls",
            name="API Calls",
            aggregation_type=AggregationType.COUNT.value,
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        assert metric.id is not None
        assert metric.code == "api_calls"
        assert metric.name == "API Calls"
        assert metric.aggregation_type == "count"
        assert metric.description is None
        assert metric.field_name is None
        assert metric.recurring is False
        assert metric.rounding_function is None
        assert metric.rounding_precision is None
        assert metric.expression is None
        assert metric.created_at is not None
        assert metric.updated_at is not None

    def test_billable_metric_with_advanced_fields(self, db_session):
        """Test BillableMetric model with advanced aggregation fields."""
        metric = BillableMetric(
            code="weighted_usage",
            name="Weighted Usage",
            aggregation_type=AggregationType.WEIGHTED_SUM.value,
            field_name="cpu_usage",
            recurring=False,
            rounding_function="ceil",
            rounding_precision=2,
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        assert metric.rounding_function == "ceil"
        assert metric.rounding_precision == 2
        assert metric.recurring is False

    def test_billable_metric_with_expression(self, db_session):
        """Test BillableMetric model with custom expression."""
        metric = BillableMetric(
            code="custom_metric",
            name="Custom Metric",
            aggregation_type=AggregationType.CUSTOM.value,
            expression="sum(amount * quantity)",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        assert metric.expression == "sum(amount * quantity)"

    def test_billable_metric_recurring(self, db_session):
        """Test BillableMetric model with recurring flag."""
        metric = BillableMetric(
            code="recurring_count",
            name="Recurring Count",
            aggregation_type=AggregationType.COUNT.value,
            recurring=True,
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        assert metric.recurring is True


class TestBillableMetricRepository:
    def test_get_by_code(self, db_session):
        """Test getting metric by code."""
        repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="storage_gb",
            name="Storage GB",
            aggregation_type=AggregationType.SUM,
            field_name="gb_used",
        )
        repo.create(data, DEFAULT_ORG_ID)

        metric = repo.get_by_code("storage_gb", DEFAULT_ORG_ID)
        assert metric is not None
        assert metric.code == "storage_gb"

        not_found = repo.get_by_code("nonexistent", DEFAULT_ORG_ID)
        assert not_found is None

    def test_code_exists(self, db_session):
        """Test checking if code exists."""
        repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="exists_test",
            name="Exists Test",
            aggregation_type=AggregationType.COUNT,
        )
        repo.create(data, DEFAULT_ORG_ID)

        assert repo.code_exists("exists_test", DEFAULT_ORG_ID) is True
        assert repo.code_exists("not_exists", DEFAULT_ORG_ID) is False

    def test_create_with_advanced_fields(self, db_session):
        """Test creating metric with advanced fields via repository."""
        repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="adv_repo",
            name="Advanced Repo",
            aggregation_type=AggregationType.MAX,
            field_name="value",
            recurring=True,
            rounding_function="round",
            rounding_precision=3,
        )
        metric = repo.create(data, DEFAULT_ORG_ID)

        assert metric.recurring is True
        assert metric.rounding_function == "round"
        assert metric.rounding_precision == 3
        assert metric.expression is None

    def test_create_with_expression(self, db_session):
        """Test creating metric with expression via repository."""
        repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="custom_repo",
            name="Custom Repo",
            aggregation_type=AggregationType.CUSTOM,
            expression="sum(amount)",
        )
        metric = repo.create(data, DEFAULT_ORG_ID)

        assert metric.expression == "sum(amount)"


class TestBillableMetricRepositoryCountsByAggregationType:
    def test_counts_empty(self, db_session):
        """Test aggregation type counts with no metrics."""
        repo = BillableMetricRepository(db_session)
        result = repo.counts_by_aggregation_type(DEFAULT_ORG_ID)
        assert result == {}

    def test_counts_single_type(self, db_session):
        """Test aggregation type counts with one type."""
        repo = BillableMetricRepository(db_session)
        for i in range(3):
            repo.create(
                BillableMetricCreate(
                    code=f"cnt_{i}", name=f"Cnt {i}", aggregation_type=AggregationType.COUNT
                ),
                DEFAULT_ORG_ID,
            )
        result = repo.counts_by_aggregation_type(DEFAULT_ORG_ID)
        assert result == {"count": 3}

    def test_counts_multiple_types(self, db_session):
        """Test aggregation type counts with multiple types."""
        repo = BillableMetricRepository(db_session)
        repo.create(
            BillableMetricCreate(code="c1", name="C1", aggregation_type=AggregationType.COUNT),
            DEFAULT_ORG_ID,
        )
        repo.create(
            BillableMetricCreate(code="s1", name="S1", aggregation_type=AggregationType.SUM, field_name="v"),
            DEFAULT_ORG_ID,
        )
        repo.create(
            BillableMetricCreate(code="s2", name="S2", aggregation_type=AggregationType.SUM, field_name="v"),
            DEFAULT_ORG_ID,
        )
        repo.create(
            BillableMetricCreate(code="m1", name="M1", aggregation_type=AggregationType.MAX, field_name="v"),
            DEFAULT_ORG_ID,
        )
        result = repo.counts_by_aggregation_type(DEFAULT_ORG_ID)
        assert result == {"count": 1, "sum": 2, "max": 1}


class TestBillableMetricStatsSchema:
    def test_stats_schema(self):
        """Test BillableMetricStats schema construction."""
        stats = BillableMetricStats(total=5, by_aggregation_type={"count": 3, "sum": 2})
        assert stats.total == 5
        assert stats.by_aggregation_type == {"count": 3, "sum": 2}

    def test_stats_schema_empty(self):
        """Test BillableMetricStats schema with empty breakdown."""
        stats = BillableMetricStats(total=0, by_aggregation_type={})
        assert stats.total == 0
        assert stats.by_aggregation_type == {}


class TestBillableMetricSchemaValidation:
    def test_field_name_required_for_sum(self, client: TestClient):
        """Test field_name is required for SUM aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "sum_test",
                "name": "Sum Test",
                "aggregation_type": "sum",
            },
        )
        assert response.status_code == 422
        # field_name is required for SUM

    def test_field_name_required_for_max(self, client: TestClient):
        """Test field_name is required for MAX aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "max_test",
                "name": "Max Test",
                "aggregation_type": "max",
            },
        )
        assert response.status_code == 422

    def test_field_name_required_for_unique_count(self, client: TestClient):
        """Test field_name is required for UNIQUE_COUNT aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "unique_test",
                "name": "Unique Test",
                "aggregation_type": "unique_count",
            },
        )
        assert response.status_code == 422

    def test_field_name_not_required_for_count(self, client: TestClient):
        """Test field_name is not required for COUNT aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "count_test",
                "name": "Count Test",
                "aggregation_type": "count",
            },
        )
        assert response.status_code == 201

    def test_field_name_required_for_weighted_sum(self, client: TestClient):
        """Test field_name is required for WEIGHTED_SUM aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "ws_test",
                "name": "Weighted Sum Test",
                "aggregation_type": "weighted_sum",
            },
        )
        assert response.status_code == 422

    def test_field_name_required_for_latest(self, client: TestClient):
        """Test field_name is required for LATEST aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "latest_test",
                "name": "Latest Test",
                "aggregation_type": "latest",
            },
        )
        assert response.status_code == 422

    def test_expression_required_for_custom(self, client: TestClient):
        """Test expression is required for CUSTOM aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "custom_test",
                "name": "Custom Test",
                "aggregation_type": "custom",
            },
        )
        assert response.status_code == 422

    def test_recurring_invalid_for_sum(self, client: TestClient):
        """Test recurring is not allowed for SUM aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "rec_sum_test",
                "name": "Recurring Sum Test",
                "aggregation_type": "sum",
                "field_name": "amount",
                "recurring": True,
            },
        )
        assert response.status_code == 422

    def test_recurring_valid_for_count(self, client: TestClient):
        """Test recurring is allowed for COUNT aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "rec_count_test",
                "name": "Recurring Count Test",
                "aggregation_type": "count",
                "recurring": True,
            },
        )
        assert response.status_code == 201
        assert response.json()["recurring"] is True

    def test_recurring_valid_for_max(self, client: TestClient):
        """Test recurring is allowed for MAX aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "rec_max_test",
                "name": "Recurring Max Test",
                "aggregation_type": "max",
                "field_name": "val",
                "recurring": True,
            },
        )
        assert response.status_code == 201
        assert response.json()["recurring"] is True

    def test_recurring_valid_for_latest(self, client: TestClient):
        """Test recurring is allowed for LATEST aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "rec_latest_test",
                "name": "Recurring Latest Test",
                "aggregation_type": "latest",
                "field_name": "val",
                "recurring": True,
            },
        )
        assert response.status_code == 201
        assert response.json()["recurring"] is True

    def test_recurring_invalid_for_unique_count(self, client: TestClient):
        """Test recurring is not allowed for UNIQUE_COUNT aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "rec_uc_test",
                "name": "Recurring UC Test",
                "aggregation_type": "unique_count",
                "field_name": "user_id",
                "recurring": True,
            },
        )
        assert response.status_code == 422

    def test_recurring_invalid_for_weighted_sum(self, client: TestClient):
        """Test recurring is not allowed for WEIGHTED_SUM aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "rec_ws_test",
                "name": "Recurring WS Test",
                "aggregation_type": "weighted_sum",
                "field_name": "cpu",
                "recurring": True,
            },
        )
        assert response.status_code == 422

    def test_recurring_invalid_for_custom(self, client: TestClient):
        """Test recurring is not allowed for CUSTOM aggregation."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "rec_custom_test",
                "name": "Recurring Custom Test",
                "aggregation_type": "custom",
                "expression": "sum(x)",
                "recurring": True,
            },
        )
        assert response.status_code == 422

    def test_rounding_precision_requires_function(self, client: TestClient):
        """Test rounding_precision requires rounding_function."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "rp_test",
                "name": "RP Test",
                "aggregation_type": "count",
                "rounding_precision": 2,
            },
        )
        assert response.status_code == 422

    def test_rounding_function_valid_values(self):
        """Test rounding_function only accepts valid values."""
        # Valid: round
        data = BillableMetricCreate(
            code="rf_round",
            name="RF Round",
            aggregation_type=AggregationType.COUNT,
            rounding_function="round",
        )
        assert data.rounding_function == "round"

        # Valid: ceil
        data = BillableMetricCreate(
            code="rf_ceil",
            name="RF Ceil",
            aggregation_type=AggregationType.COUNT,
            rounding_function="ceil",
        )
        assert data.rounding_function == "ceil"

        # Valid: floor
        data = BillableMetricCreate(
            code="rf_floor",
            name="RF Floor",
            aggregation_type=AggregationType.COUNT,
            rounding_function="floor",
        )
        assert data.rounding_function == "floor"

    def test_rounding_function_invalid_value(self):
        """Test rounding_function rejects invalid values."""
        with pytest.raises(ValueError):
            BillableMetricCreate(
                code="rf_invalid",
                name="RF Invalid",
                aggregation_type=AggregationType.COUNT,
                rounding_function="truncate",
            )

    def test_rounding_precision_bounds(self):
        """Test rounding_precision rejects out-of-bounds values."""
        with pytest.raises(ValueError):
            BillableMetricCreate(
                code="rp_neg",
                name="RP Neg",
                aggregation_type=AggregationType.COUNT,
                rounding_function="round",
                rounding_precision=-1,
            )

        with pytest.raises(ValueError):
            BillableMetricCreate(
                code="rp_high",
                name="RP High",
                aggregation_type=AggregationType.COUNT,
                rounding_function="round",
                rounding_precision=16,
            )


class TestBillableMetricsAPI:
    def test_list_billable_metrics_empty(self, client: TestClient):
        """Test listing metrics when none exist."""
        response = client.get("/v1/billable_metrics/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_billable_metric_count(self, client: TestClient):
        """Test creating a COUNT metric."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "api_requests",
                "name": "API Requests",
                "description": "Number of API requests",
                "aggregation_type": "count",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "api_requests"
        assert data["name"] == "API Requests"
        assert data["description"] == "Number of API requests"
        assert data["aggregation_type"] == "count"
        assert data["field_name"] is None
        assert data["recurring"] is False
        assert data["rounding_function"] is None
        assert data["rounding_precision"] is None
        assert data["expression"] is None
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_billable_metric_sum(self, client: TestClient):
        """Test creating a SUM metric."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "data_transfer",
                "name": "Data Transfer",
                "aggregation_type": "sum",
                "field_name": "bytes_transferred",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "data_transfer"
        assert data["aggregation_type"] == "sum"
        assert data["field_name"] == "bytes_transferred"

    def test_create_billable_metric_max(self, client: TestClient):
        """Test creating a MAX metric."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "peak_users",
                "name": "Peak Concurrent Users",
                "aggregation_type": "max",
                "field_name": "concurrent_users",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["aggregation_type"] == "max"
        assert data["field_name"] == "concurrent_users"

    def test_create_billable_metric_unique_count(self, client: TestClient):
        """Test creating a UNIQUE_COUNT metric."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "unique_visitors",
                "name": "Unique Visitors",
                "aggregation_type": "unique_count",
                "field_name": "visitor_id",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["aggregation_type"] == "unique_count"
        assert data["field_name"] == "visitor_id"

    def test_create_billable_metric_weighted_sum(self, client: TestClient):
        """Test creating a WEIGHTED_SUM metric."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "cpu_weighted",
                "name": "CPU Weighted Usage",
                "aggregation_type": "weighted_sum",
                "field_name": "cpu_percent",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["aggregation_type"] == "weighted_sum"
        assert data["field_name"] == "cpu_percent"

    def test_create_billable_metric_latest(self, client: TestClient):
        """Test creating a LATEST metric."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "current_seats",
                "name": "Current Seats",
                "aggregation_type": "latest",
                "field_name": "seat_count",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["aggregation_type"] == "latest"
        assert data["field_name"] == "seat_count"

    def test_create_billable_metric_custom(self, client: TestClient):
        """Test creating a CUSTOM metric."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "custom_agg",
                "name": "Custom Aggregation",
                "aggregation_type": "custom",
                "expression": "sum(amount * quantity)",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["aggregation_type"] == "custom"
        assert data["expression"] == "sum(amount * quantity)"

    def test_create_billable_metric_with_rounding(self, client: TestClient):
        """Test creating a metric with rounding configuration."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "rounded_metric",
                "name": "Rounded Metric",
                "aggregation_type": "sum",
                "field_name": "amount",
                "rounding_function": "ceil",
                "rounding_precision": 2,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["rounding_function"] == "ceil"
        assert data["rounding_precision"] == 2

    def test_create_billable_metric_rounding_function_no_precision(self, client: TestClient):
        """Test creating a metric with rounding_function but no precision."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "rf_no_prec",
                "name": "RF No Precision",
                "aggregation_type": "count",
                "rounding_function": "floor",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["rounding_function"] == "floor"
        assert data["rounding_precision"] is None

    def test_create_billable_metric_duplicate_code(self, client: TestClient):
        """Test creating a metric with duplicate code."""
        client.post(
            "/v1/billable_metrics/",
            json={
                "code": "dup_code",
                "name": "First Metric",
                "aggregation_type": "count",
            },
        )
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "dup_code",
                "name": "Second Metric",
                "aggregation_type": "count",
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Billable metric with this code already exists"

    def test_create_billable_metric_invalid_aggregation_type(self, client: TestClient):
        """Test creating a metric with invalid aggregation_type."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "invalid_agg",
                "name": "Invalid Aggregation",
                "aggregation_type": "invalid",
            },
        )
        assert response.status_code == 422

    def test_create_billable_metric_empty_code(self, client: TestClient):
        """Test creating a metric with empty code."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "",
                "name": "Empty Code",
                "aggregation_type": "count",
            },
        )
        assert response.status_code == 422

    def test_create_billable_metric_empty_name(self, client: TestClient):
        """Test creating a metric with empty name."""
        response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "empty_name",
                "name": "",
                "aggregation_type": "count",
            },
        )
        assert response.status_code == 422

    def test_get_billable_metric(self, client: TestClient):
        """Test getting a metric by ID."""
        create_response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "get_test",
                "name": "Get Test",
                "aggregation_type": "count",
            },
        )
        metric_id = create_response.json()["id"]

        response = client.get(f"/v1/billable_metrics/{metric_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == metric_id
        assert data["code"] == "get_test"

    def test_get_billable_metric_not_found(self, client: TestClient):
        """Test getting a non-existent metric."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/billable_metrics/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Billable metric not found"

    def test_get_billable_metric_invalid_uuid(self, client: TestClient):
        """Test getting a metric with invalid UUID."""
        response = client.get("/v1/billable_metrics/not-a-uuid")
        assert response.status_code == 422

    def test_update_billable_metric(self, client: TestClient):
        """Test updating a metric."""
        create_response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "upd_test",
                "name": "Original Name",
                "aggregation_type": "count",
            },
        )
        metric_id = create_response.json()["id"]

        response = client.put(
            f"/v1/billable_metrics/{metric_id}",
            json={"name": "Updated Name", "description": "New description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New description"
        assert data["code"] == "upd_test"  # Unchanged

    def test_update_billable_metric_advanced_fields(self, client: TestClient):
        """Test updating a metric's advanced fields."""
        create_response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "upd_adv",
                "name": "Update Advanced",
                "aggregation_type": "count",
            },
        )
        metric_id = create_response.json()["id"]

        response = client.put(
            f"/v1/billable_metrics/{metric_id}",
            json={
                "rounding_function": "round",
                "rounding_precision": 5,
                "recurring": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rounding_function"] == "round"
        assert data["rounding_precision"] == 5
        assert data["recurring"] is True

    def test_update_billable_metric_partial(self, client: TestClient):
        """Test partial update of a metric."""
        create_response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "partial_upd",
                "name": "Partial Update",
                "description": "Original description",
                "aggregation_type": "sum",
                "field_name": "value",
            },
        )
        metric_id = create_response.json()["id"]

        # Only update description
        response = client.put(
            f"/v1/billable_metrics/{metric_id}",
            json={"description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Partial Update"  # Unchanged
        assert data["description"] == "Updated description"  # Updated
        assert data["field_name"] == "value"  # Unchanged

    def test_update_billable_metric_not_found(self, client: TestClient):
        """Test updating a non-existent metric."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/v1/billable_metrics/{fake_id}",
            json={"name": "Ghost"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Billable metric not found"

    def test_delete_billable_metric(self, client: TestClient):
        """Test deleting a metric."""
        create_response = client.post(
            "/v1/billable_metrics/",
            json={
                "code": "del_test",
                "name": "Delete Me",
                "aggregation_type": "count",
            },
        )
        metric_id = create_response.json()["id"]

        response = client.delete(f"/v1/billable_metrics/{metric_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/v1/billable_metrics/{metric_id}")
        assert get_response.status_code == 404

    def test_delete_billable_metric_not_found(self, client: TestClient):
        """Test deleting a non-existent metric."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/v1/billable_metrics/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Billable metric not found"

    def test_list_billable_metrics_pagination(self, client: TestClient):
        """Test listing metrics with pagination."""
        # Create multiple metrics
        for i in range(5):
            client.post(
                "/v1/billable_metrics/",
                json={
                    "code": f"page_{i}",
                    "name": f"Metric {i}",
                    "aggregation_type": "count",
                },
            )

        # Test pagination
        response = client.get("/v1/billable_metrics/?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_billable_metrics_default_pagination(self, client: TestClient):
        """Test listing metrics with default pagination."""
        client.post(
            "/v1/billable_metrics/",
            json={
                "code": "default_test",
                "name": "Default Test",
                "aggregation_type": "count",
            },
        )

        response = client.get("/v1/billable_metrics/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestBillableMetricsStatsAPI:
    def test_stats_empty(self, client: TestClient):
        """Test stats with no metrics."""
        response = client.get("/v1/billable_metrics/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["by_aggregation_type"] == {}

    def test_stats_with_metrics(self, client: TestClient):
        """Test stats with multiple metrics of different types."""
        client.post(
            "/v1/billable_metrics/",
            json={"code": "stat_c1", "name": "Count 1", "aggregation_type": "count"},
        )
        client.post(
            "/v1/billable_metrics/",
            json={"code": "stat_c2", "name": "Count 2", "aggregation_type": "count"},
        )
        client.post(
            "/v1/billable_metrics/",
            json={
                "code": "stat_s1",
                "name": "Sum 1",
                "aggregation_type": "sum",
                "field_name": "amount",
            },
        )
        client.post(
            "/v1/billable_metrics/",
            json={
                "code": "stat_m1",
                "name": "Max 1",
                "aggregation_type": "max",
                "field_name": "val",
            },
        )

        response = client.get("/v1/billable_metrics/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert data["by_aggregation_type"]["count"] == 2
        assert data["by_aggregation_type"]["sum"] == 1
        assert data["by_aggregation_type"]["max"] == 1

    def test_stats_single_type(self, client: TestClient):
        """Test stats when all metrics are the same type."""
        for i in range(3):
            client.post(
                "/v1/billable_metrics/",
                json={
                    "code": f"stat_only_{i}",
                    "name": f"Only {i}",
                    "aggregation_type": "count",
                },
            )

        response = client.get("/v1/billable_metrics/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["by_aggregation_type"] == {"count": 3}


class TestBillableMetricRepositoryPlanCounts:
    def test_plan_counts_empty(self, db_session):
        """Test plan counts with no metrics or charges."""
        repo = BillableMetricRepository(db_session)
        result = repo.plan_counts(DEFAULT_ORG_ID)
        assert result == {}

    def test_plan_counts_no_charges(self, db_session):
        """Test plan counts when metrics exist but no charges reference them."""
        repo = BillableMetricRepository(db_session)
        repo.create(
            BillableMetricCreate(code="unused", name="Unused", aggregation_type=AggregationType.COUNT),
            DEFAULT_ORG_ID,
        )
        result = repo.plan_counts(DEFAULT_ORG_ID)
        assert result == {}

    def test_plan_counts_single_plan(self, db_session):
        """Test plan counts when one plan uses one metric."""
        repo = BillableMetricRepository(db_session)
        metric = repo.create(
            BillableMetricCreate(code="api_calls", name="API Calls", aggregation_type=AggregationType.COUNT),
            DEFAULT_ORG_ID,
        )
        plan = Plan(code="basic", name="Basic", interval="monthly", organization_id=DEFAULT_ORG_ID)
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)

        charge = Charge(
            organization_id=DEFAULT_ORG_ID,
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model="standard",
        )
        db_session.add(charge)
        db_session.commit()

        result = repo.plan_counts(DEFAULT_ORG_ID)
        assert result == {str(metric.id): 1}

    def test_plan_counts_multiple_plans(self, db_session):
        """Test plan counts when multiple plans use the same metric."""
        repo = BillableMetricRepository(db_session)
        metric = repo.create(
            BillableMetricCreate(code="storage", name="Storage", aggregation_type=AggregationType.SUM, field_name="gb"),
            DEFAULT_ORG_ID,
        )
        for i in range(3):
            plan = Plan(code=f"plan_{i}", name=f"Plan {i}", interval="monthly", organization_id=DEFAULT_ORG_ID)
            db_session.add(plan)
            db_session.commit()
            db_session.refresh(plan)
            charge = Charge(
                organization_id=DEFAULT_ORG_ID,
                plan_id=plan.id,
                billable_metric_id=metric.id,
                charge_model="standard",
            )
            db_session.add(charge)
        db_session.commit()

        result = repo.plan_counts(DEFAULT_ORG_ID)
        assert result == {str(metric.id): 3}

    def test_plan_counts_multiple_charges_same_plan(self, db_session):
        """Test that multiple charges from the same plan count as 1 plan."""
        repo = BillableMetricRepository(db_session)
        metric = repo.create(
            BillableMetricCreate(code="events", name="Events", aggregation_type=AggregationType.COUNT),
            DEFAULT_ORG_ID,
        )
        plan = Plan(code="pro", name="Pro", interval="monthly", organization_id=DEFAULT_ORG_ID)
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)

        # Two charges in the same plan using the same metric
        for _ in range(2):
            charge = Charge(
                organization_id=DEFAULT_ORG_ID,
                plan_id=plan.id,
                billable_metric_id=metric.id,
                charge_model="standard",
            )
            db_session.add(charge)
        db_session.commit()

        result = repo.plan_counts(DEFAULT_ORG_ID)
        assert result == {str(metric.id): 1}


class TestBillableMetricPlanCountsAPI:
    def test_plan_counts_empty(self, client: TestClient):
        """Test plan counts API with no data."""
        response = client.get("/v1/billable_metrics/plan_counts")
        assert response.status_code == 200
        assert response.json() == {}

    def test_plan_counts_with_data(self, client: TestClient, db_session):
        """Test plan counts API with metrics referenced by plans."""
        # Create metric via API
        metric_resp = client.post(
            "/v1/billable_metrics/",
            json={"code": "pc_metric", "name": "PC Metric", "aggregation_type": "count"},
        )
        metric_id = metric_resp.json()["id"]

        # Create plan and charge directly in DB
        plan = Plan(code="pc_plan", name="PC Plan", interval="monthly", organization_id=DEFAULT_ORG_ID)
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)

        charge = Charge(
            organization_id=DEFAULT_ORG_ID,
            plan_id=plan.id,
            billable_metric_id=uuid.UUID(metric_id),
            charge_model="standard",
        )
        db_session.add(charge)
        db_session.commit()

        response = client.get("/v1/billable_metrics/plan_counts")
        assert response.status_code == 200
        data = response.json()
        assert data[metric_id] == 1

    def test_plan_counts_multiple_metrics(self, client: TestClient, db_session):
        """Test plan counts API with multiple metrics."""
        m1_resp = client.post(
            "/v1/billable_metrics/",
            json={"code": "pc_m1", "name": "M1", "aggregation_type": "count"},
        )
        m2_resp = client.post(
            "/v1/billable_metrics/",
            json={"code": "pc_m2", "name": "M2", "aggregation_type": "sum", "field_name": "val"},
        )
        m1_id = m1_resp.json()["id"]
        m2_id = m2_resp.json()["id"]

        plan1 = Plan(code="pc_p1", name="P1", interval="monthly", organization_id=DEFAULT_ORG_ID)
        plan2 = Plan(code="pc_p2", name="P2", interval="monthly", organization_id=DEFAULT_ORG_ID)
        db_session.add_all([plan1, plan2])
        db_session.commit()
        db_session.refresh(plan1)
        db_session.refresh(plan2)

        # m1 used in both plans, m2 used in only plan1
        db_session.add_all([
            Charge(organization_id=DEFAULT_ORG_ID, plan_id=plan1.id, billable_metric_id=uuid.UUID(m1_id), charge_model="standard"),
            Charge(organization_id=DEFAULT_ORG_ID, plan_id=plan2.id, billable_metric_id=uuid.UUID(m1_id), charge_model="standard"),
            Charge(organization_id=DEFAULT_ORG_ID, plan_id=plan1.id, billable_metric_id=uuid.UUID(m2_id), charge_model="volume"),
        ])
        db_session.commit()

        response = client.get("/v1/billable_metrics/plan_counts")
        assert response.status_code == 200
        data = response.json()
        assert data[m1_id] == 2
        assert data[m2_id] == 1
