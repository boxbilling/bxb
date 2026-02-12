"""Billable Metric API tests for bxb."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.billable_metric import AggregationType, BillableMetric
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.schemas.billable_metric import BillableMetricCreate


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
        assert metric.created_at is not None
        assert metric.updated_at is not None


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
        repo.create(data)

        metric = repo.get_by_code("storage_gb")
        assert metric is not None
        assert metric.code == "storage_gb"

        not_found = repo.get_by_code("nonexistent")
        assert not_found is None

    def test_code_exists(self, db_session):
        """Test checking if code exists."""
        repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="exists_test",
            name="Exists Test",
            aggregation_type=AggregationType.COUNT,
        )
        repo.create(data)

        assert repo.code_exists("exists_test") is True
        assert repo.code_exists("not_exists") is False


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
