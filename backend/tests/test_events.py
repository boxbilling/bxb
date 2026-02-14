"""Event API tests for bxb."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.billable_metric import BillableMetric
from app.models.charge import Charge
from app.models.customer import Customer
from app.models.event import Event
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.event_repository import EventRepository
from app.routers.events import (
    _add_hypothetical_event,
    _calculate_estimated_amount,
    _enqueue_threshold_checks,
    _get_active_subscription_ids,
)
from app.schemas.billable_metric import BillableMetricCreate
from app.schemas.event import EventCreate
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


@pytest.fixture
def billable_metric(db_session):
    """Create a billable metric for testing."""
    repo = BillableMetricRepository(db_session)
    from app.models.billable_metric import AggregationType

    data = BillableMetricCreate(
        code="api_calls",
        name="API Calls",
        aggregation_type=AggregationType.COUNT,
    )
    return repo.create(data, DEFAULT_ORG_ID)


@pytest.fixture
def billable_metric_sum(db_session):
    """Create a SUM billable metric for testing."""
    repo = BillableMetricRepository(db_session)
    from app.models.billable_metric import AggregationType

    data = BillableMetricCreate(
        code="data_transfer",
        name="Data Transfer",
        aggregation_type=AggregationType.SUM,
        field_name="bytes",
    )
    return repo.create(data, DEFAULT_ORG_ID)


class TestEventModel:
    def test_event_defaults(self, db_session, billable_metric):
        """Test Event model default values."""
        now = datetime.now(UTC)
        event = Event(
            transaction_id="tx-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=now,
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        assert event.id is not None
        assert event.transaction_id == "tx-001"
        assert event.external_customer_id == "cust-001"
        assert event.code == "api_calls"
        assert event.properties == {}
        assert event.created_at is not None

    def test_event_with_properties(self, db_session, billable_metric):
        """Test Event model with properties."""
        now = datetime.now(UTC)
        event = Event(
            transaction_id="tx-002",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=now,
            properties={"endpoint": "/api/v1/users", "method": "GET"},
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        assert event.properties == {"endpoint": "/api/v1/users", "method": "GET"}


class TestEventRepository:
    def test_get_by_transaction_id(self, db_session, billable_metric):
        """Test getting event by transaction_id."""
        repo = EventRepository(db_session)
        now = datetime.now(UTC)
        data = EventCreate(
            transaction_id="tx-find-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=now,
        )
        repo.create(data, DEFAULT_ORG_ID)

        event = repo.get_by_transaction_id("tx-find-001")
        assert event is not None
        assert event.transaction_id == "tx-find-001"

        not_found = repo.get_by_transaction_id("nonexistent")
        assert not_found is None

    def test_transaction_id_exists(self, db_session, billable_metric):
        """Test checking if transaction_id exists."""
        repo = EventRepository(db_session)
        now = datetime.now(UTC)
        data = EventCreate(
            transaction_id="exists-tx-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=now,
        )
        repo.create(data, DEFAULT_ORG_ID)

        assert repo.transaction_id_exists("exists-tx-001", DEFAULT_ORG_ID) is True
        assert repo.transaction_id_exists("not-exists", DEFAULT_ORG_ID) is False

    def test_create_or_get_existing_new(self, db_session, billable_metric):
        """Test create_or_get_existing creates new event."""
        repo = EventRepository(db_session)
        now = datetime.now(UTC)
        data = EventCreate(
            transaction_id="new-tx-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=now,
        )
        event, is_new = repo.create_or_get_existing(data, DEFAULT_ORG_ID)

        assert is_new is True
        assert event.transaction_id == "new-tx-001"

    def test_create_or_get_existing_duplicate(self, db_session, billable_metric):
        """Test create_or_get_existing returns existing event."""
        repo = EventRepository(db_session)
        now = datetime.now(UTC)
        data = EventCreate(
            transaction_id="dup-tx-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=now,
        )
        event1, is_new1 = repo.create_or_get_existing(data, DEFAULT_ORG_ID)
        event2, is_new2 = repo.create_or_get_existing(data, DEFAULT_ORG_ID)

        assert is_new1 is True
        assert is_new2 is False
        assert event1.id == event2.id

    def test_create_batch(self, db_session, billable_metric):
        """Test batch creation with mixed new and duplicate events."""
        repo = EventRepository(db_session)
        now = datetime.now(UTC)

        # Create first event
        data1 = EventCreate(
            transaction_id="batch-tx-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=now,
        )
        repo.create(data1, DEFAULT_ORG_ID)

        # Batch with 1 duplicate and 2 new
        batch_data = [
            EventCreate(
                transaction_id="batch-tx-001",  # duplicate
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=now,
            ),
            EventCreate(
                transaction_id="batch-tx-002",  # new
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=now,
            ),
            EventCreate(
                transaction_id="batch-tx-003",  # new
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=now,
            ),
        ]
        events, ingested, duplicates = repo.create_batch(batch_data, DEFAULT_ORG_ID)

        assert len(events) == 3
        assert ingested == 2
        assert duplicates == 1

    def test_create_batch_all_duplicates(self, db_session, billable_metric):
        """Test batch creation when all events are duplicates."""
        repo = EventRepository(db_session)
        now = datetime.now(UTC)

        # Create events first
        for i in range(3):
            data = EventCreate(
                transaction_id=f"all-dup-tx-{i}",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=now,
            )
            repo.create(data, DEFAULT_ORG_ID)

        # Batch with all duplicates - should not commit
        batch_data = [
            EventCreate(
                transaction_id="all-dup-tx-0",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=now,
            ),
            EventCreate(
                transaction_id="all-dup-tx-1",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=now,
            ),
            EventCreate(
                transaction_id="all-dup-tx-2",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=now,
            ),
        ]
        events, ingested, duplicates = repo.create_batch(batch_data, DEFAULT_ORG_ID)

        assert len(events) == 3
        assert ingested == 0
        assert duplicates == 3

    def test_get_all_with_filters(self, db_session, billable_metric, billable_metric_sum):
        """Test getting events with filters."""
        repo = EventRepository(db_session)
        now = datetime.now(UTC)

        # Create events for different customers and codes
        events_data = [
            EventCreate(
                transaction_id="filter-tx-001",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=now,
            ),
            EventCreate(
                transaction_id="filter-tx-002",
                external_customer_id="cust-001",
                code="data_transfer",
                timestamp=now,
            ),
            EventCreate(
                transaction_id="filter-tx-003",
                external_customer_id="cust-002",
                code="api_calls",
                timestamp=now,
            ),
        ]
        for data in events_data:
            repo.create(data, DEFAULT_ORG_ID)

        # Filter by customer
        cust1_events = repo.get_all(DEFAULT_ORG_ID, external_customer_id="cust-001")
        assert len(cust1_events) == 2

        # Filter by code
        api_events = repo.get_all(DEFAULT_ORG_ID, code="api_calls")
        assert len(api_events) == 2

        # Filter by customer and code
        cust1_api = repo.get_all(DEFAULT_ORG_ID, external_customer_id="cust-001", code="api_calls")
        assert len(cust1_api) == 1

    def test_get_all_with_timestamp_filters(self, db_session, billable_metric):
        """Test getting events with timestamp filters."""
        repo = EventRepository(db_session)

        # Create events at different times
        t1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        t3 = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC)

        for i, t in enumerate([t1, t2, t3]):
            data = EventCreate(
                transaction_id=f"time-tx-{i}",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=t,
            )
            repo.create(data, DEFAULT_ORG_ID)

        # Filter from t2
        from_t2 = repo.get_all(DEFAULT_ORG_ID, from_timestamp=t2)
        assert len(from_t2) == 2

        # Filter to t2
        to_t2 = repo.get_all(DEFAULT_ORG_ID, to_timestamp=t2)
        assert len(to_t2) == 2

        # Filter between t1 and t2
        between = repo.get_all(DEFAULT_ORG_ID, from_timestamp=t1, to_timestamp=t2)
        assert len(between) == 2

    def test_delete_event(self, db_session, billable_metric):
        """Test deleting an event."""
        repo = EventRepository(db_session)
        now = datetime.now(UTC)
        data = EventCreate(
            transaction_id="del-tx-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=now,
        )
        event = repo.create(data, DEFAULT_ORG_ID)
        event_id = event.id

        assert repo.delete(event_id, DEFAULT_ORG_ID) is True
        assert repo.get_by_id(event_id) is None

    def test_delete_event_not_found(self, db_session):
        """Test deleting non-existent event."""
        repo = EventRepository(db_session)
        fake_id = uuid.uuid4()
        assert repo.delete(fake_id, DEFAULT_ORG_ID) is False


class TestEventSchemaValidation:
    def test_timestamp_parsing_iso(self):
        """Test ISO timestamp parsing."""
        data = EventCreate(
            transaction_id="ts-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp="2026-01-15T10:30:00+00:00",
        )
        assert data.timestamp.year == 2026
        assert data.timestamp.month == 1
        assert data.timestamp.day == 15

    def test_timestamp_parsing_z_suffix(self):
        """Test timestamp parsing with Z suffix."""
        data = EventCreate(
            transaction_id="ts-002",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp="2026-01-15T10:30:00Z",
        )
        assert data.timestamp.year == 2026

    def test_timestamp_parsing_datetime(self):
        """Test timestamp parsing with datetime object."""
        now = datetime.now(UTC)
        data = EventCreate(
            transaction_id="ts-003",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=now,
        )
        assert data.timestamp == now

    def test_timestamp_parsing_invalid_string(self):
        """Test invalid string timestamp raises error."""
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            EventCreate(
                transaction_id="ts-004",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp="not-a-timestamp",
            )

    def test_timestamp_parsing_invalid_type(self):
        """Test invalid type for timestamp raises error."""
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            EventCreate(
                transaction_id="ts-005",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=12345,  # Not a string or datetime
            )


class TestEventsAPI:
    def test_list_events_empty(self, client: TestClient, billable_metric):
        """Test listing events when none exist."""
        response = client.get("/v1/events/")
        assert response.status_code == 200
        assert response.json() == []
        assert response.headers["X-Total-Count"] == "0"

    def test_create_event_minimal(self, client: TestClient, billable_metric):
        """Test creating an event with minimal data."""
        response = client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-api-001",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:30:00Z",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["transaction_id"] == "tx-api-001"
        assert data["external_customer_id"] == "cust-001"
        assert data["code"] == "api_calls"
        assert data["properties"] == {}
        assert "id" in data
        assert "created_at" in data

    def test_create_event_with_properties(self, client: TestClient, billable_metric):
        """Test creating an event with properties."""
        response = client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-api-002",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:30:00Z",
                "properties": {"endpoint": "/api/users", "status_code": 200},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["properties"] == {"endpoint": "/api/users", "status_code": 200}

    def test_create_event_idempotent(self, client: TestClient, billable_metric):
        """Test that duplicate transaction_id returns existing event."""
        # Create first event
        response1 = client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-idem-001",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:30:00Z",
            },
        )
        assert response1.status_code == 201
        id1 = response1.json()["id"]

        # Create duplicate
        response2 = client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-idem-001",
                "external_customer_id": "cust-002",  # Different customer
                "code": "api_calls",
                "timestamp": "2026-01-16T10:30:00Z",  # Different time
            },
        )
        assert response2.status_code == 201
        id2 = response2.json()["id"]

        # Should return same event
        assert id1 == id2
        assert response2.json()["external_customer_id"] == "cust-001"  # Original data

    def test_create_event_invalid_billable_metric(self, client: TestClient, billable_metric):
        """Test creating an event with non-existent billable metric code."""
        response = client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-invalid-001",
                "external_customer_id": "cust-001",
                "code": "nonexistent_metric",
                "timestamp": "2026-01-15T10:30:00Z",
            },
        )
        assert response.status_code == 422
        assert "nonexistent_metric" in response.json()["detail"]

    def test_create_event_empty_transaction_id(self, client: TestClient, billable_metric):
        """Test creating an event with empty transaction_id."""
        response = client.post(
            "/v1/events/",
            json={
                "transaction_id": "",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:30:00Z",
            },
        )
        assert response.status_code == 422

    def test_create_event_empty_external_customer_id(self, client: TestClient, billable_metric):
        """Test creating an event with empty external_customer_id."""
        response = client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-empty-cust",
                "external_customer_id": "",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:30:00Z",
            },
        )
        assert response.status_code == 422

    def test_create_event_empty_code(self, client: TestClient, billable_metric):
        """Test creating an event with empty code."""
        response = client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-empty-code",
                "external_customer_id": "cust-001",
                "code": "",
                "timestamp": "2026-01-15T10:30:00Z",
            },
        )
        assert response.status_code == 422

    def test_create_event_invalid_timestamp(self, client: TestClient, billable_metric):
        """Test creating an event with invalid timestamp."""
        response = client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-invalid-ts",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "not-a-timestamp",
            },
        )
        assert response.status_code == 422

    def test_get_event(self, client: TestClient, billable_metric):
        """Test getting an event by ID."""
        create_response = client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-get-001",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:30:00Z",
            },
        )
        event_id = create_response.json()["id"]

        response = client.get(f"/v1/events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == event_id
        assert data["transaction_id"] == "tx-get-001"

    def test_get_event_not_found(self, client: TestClient, billable_metric):
        """Test getting a non-existent event."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/events/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Event not found"

    def test_get_event_invalid_uuid(self, client: TestClient, billable_metric):
        """Test getting an event with invalid UUID."""
        response = client.get("/v1/events/not-a-uuid")
        assert response.status_code == 422

    def test_list_events_with_customer_filter(self, client: TestClient, billable_metric):
        """Test listing events filtered by customer."""
        # Create events for different customers
        for i, cust in enumerate(["cust-001", "cust-001", "cust-002"]):
            client.post(
                "/v1/events/",
                json={
                    "transaction_id": f"tx-filter-cust-{i}",
                    "external_customer_id": cust,
                    "code": "api_calls",
                    "timestamp": "2026-01-15T10:30:00Z",
                },
            )

        response = client.get("/v1/events/?external_customer_id=cust-001")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_events_with_code_filter(
        self, client: TestClient, billable_metric, billable_metric_sum
    ):
        """Test listing events filtered by code."""
        client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-filter-code-1",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:30:00Z",
            },
        )
        client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-filter-code-2",
                "external_customer_id": "cust-001",
                "code": "data_transfer",
                "timestamp": "2026-01-15T10:30:00Z",
                "properties": {"bytes": 1024},
            },
        )

        response = client.get("/v1/events/?code=api_calls")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == "api_calls"

    def test_list_events_with_timestamp_filters(self, client: TestClient, billable_metric):
        """Test listing events filtered by timestamp range."""
        client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-ts-1",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T08:00:00Z",
            },
        )
        client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-ts-2",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T12:00:00Z",
            },
        )
        client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-ts-3",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T16:00:00Z",
            },
        )

        # Filter from 10:00
        response = client.get("/v1/events/?from_timestamp=2026-01-15T10:00:00Z")
        assert response.status_code == 200
        assert len(response.json()) == 2

        # Filter to 14:00
        response = client.get("/v1/events/?to_timestamp=2026-01-15T14:00:00Z")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_events_pagination(self, client: TestClient, billable_metric):
        """Test listing events with pagination."""
        for i in range(5):
            client.post(
                "/v1/events/",
                json={
                    "transaction_id": f"tx-page-{i}",
                    "external_customer_id": "cust-001",
                    "code": "api_calls",
                    "timestamp": f"2026-01-15T{10 + i}:00:00Z",
                },
            )

        response = client.get("/v1/events/?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_batch_create_events(self, client: TestClient, billable_metric):
        """Test batch event ingestion."""
        response = client.post(
            "/v1/events/batch",
            json={
                "events": [
                    {
                        "transaction_id": "batch-001",
                        "external_customer_id": "cust-001",
                        "code": "api_calls",
                        "timestamp": "2026-01-15T10:00:00Z",
                    },
                    {
                        "transaction_id": "batch-002",
                        "external_customer_id": "cust-001",
                        "code": "api_calls",
                        "timestamp": "2026-01-15T10:01:00Z",
                    },
                    {
                        "transaction_id": "batch-003",
                        "external_customer_id": "cust-002",
                        "code": "api_calls",
                        "timestamp": "2026-01-15T10:02:00Z",
                    },
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ingested"] == 3
        assert data["duplicates"] == 0
        assert len(data["events"]) == 3

    def test_batch_create_events_with_duplicates(self, client: TestClient, billable_metric):
        """Test batch event ingestion with duplicate transaction_ids."""
        # Create one event first
        client.post(
            "/v1/events/",
            json={
                "transaction_id": "pre-batch-001",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:00:00Z",
            },
        )

        # Batch with duplicates
        response = client.post(
            "/v1/events/batch",
            json={
                "events": [
                    {
                        "transaction_id": "pre-batch-001",  # Duplicate
                        "external_customer_id": "cust-001",
                        "code": "api_calls",
                        "timestamp": "2026-01-15T10:00:00Z",
                    },
                    {
                        "transaction_id": "batch-new-001",  # New
                        "external_customer_id": "cust-001",
                        "code": "api_calls",
                        "timestamp": "2026-01-15T10:01:00Z",
                    },
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ingested"] == 1
        assert data["duplicates"] == 1
        assert len(data["events"]) == 2

    def test_batch_create_events_invalid_metric_code(self, client: TestClient, billable_metric):
        """Test batch event ingestion with invalid metric code."""
        response = client.post(
            "/v1/events/batch",
            json={
                "events": [
                    {
                        "transaction_id": "batch-invalid-001",
                        "external_customer_id": "cust-001",
                        "code": "nonexistent",
                        "timestamp": "2026-01-15T10:00:00Z",
                    },
                ]
            },
        )
        assert response.status_code == 422
        assert "nonexistent" in response.json()["detail"]

    def test_batch_create_events_empty(self, client: TestClient, billable_metric):
        """Test batch event ingestion with empty list."""
        response = client.post(
            "/v1/events/batch",
            json={"events": []},
        )
        assert response.status_code == 422

    def test_batch_create_events_over_limit(self, client: TestClient, billable_metric):
        """Test batch event ingestion with more than 100 events."""
        events = [
            {
                "transaction_id": f"batch-over-{i}",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:00:00Z",
            }
            for i in range(101)
        ]
        response = client.post(
            "/v1/events/batch",
            json={"events": events},
        )
        assert response.status_code == 422

    def test_batch_create_max_events(self, client: TestClient, billable_metric):
        """Test batch event ingestion with exactly 100 events."""
        events = [
            {
                "transaction_id": f"batch-max-{i}",
                "external_customer_id": "cust-001",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:00:00Z",
            }
            for i in range(100)
        ]
        response = client.post(
            "/v1/events/batch",
            json={"events": events},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ingested"] == 100

    def test_batch_create_multiple_codes(
        self, client: TestClient, billable_metric, billable_metric_sum
    ):
        """Test batch event ingestion with multiple metric codes."""
        response = client.post(
            "/v1/events/batch",
            json={
                "events": [
                    {
                        "transaction_id": "batch-multi-001",
                        "external_customer_id": "cust-001",
                        "code": "api_calls",
                        "timestamp": "2026-01-15T10:00:00Z",
                    },
                    {
                        "transaction_id": "batch-multi-002",
                        "external_customer_id": "cust-001",
                        "code": "data_transfer",
                        "timestamp": "2026-01-15T10:01:00Z",
                        "properties": {"bytes": 2048},
                    },
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["ingested"] == 2


def _create_customer(db, external_id: str = "cust-threshold") -> Customer:
    customer = Customer(external_id=external_id, name="Test", email="t@t.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _create_plan(db, code: str = "plan-threshold") -> Plan:
    plan = Plan(
        code=code,
        name=f"Plan {code}",
        interval=PlanInterval.MONTHLY.value,
        amount_cents=10000,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _create_active_subscription(
    db, customer: Customer, plan: Plan, external_id: str = "sub-threshold"
) -> Subscription:
    sub = Subscription(
        external_id=external_id,
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        started_at=datetime.now(UTC) - timedelta(days=5),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


class TestGetActiveSubscriptionIds:
    """Tests for _get_active_subscription_ids helper."""

    def test_returns_empty_when_customer_not_found(self, db_session):
        """Test returns empty list when customer does not exist."""
        result = _get_active_subscription_ids("nonexistent", db_session, DEFAULT_ORG_ID)
        assert result == []

    def test_returns_active_subscription_ids(self, db_session):
        """Test returns active subscription IDs for the customer."""
        customer = _create_customer(db_session, "cust-active-sub")
        plan = _create_plan(db_session, "plan-active-sub")
        sub = _create_active_subscription(db_session, customer, plan, "sub-active-test")

        result = _get_active_subscription_ids("cust-active-sub", db_session, DEFAULT_ORG_ID)
        assert result == [str(sub.id)]

    def test_excludes_non_active_subscriptions(self, db_session):
        """Test excludes canceled/terminated subscriptions."""
        customer = _create_customer(db_session, "cust-mixed-subs")
        plan = _create_plan(db_session, "plan-mixed-subs")

        active_sub = _create_active_subscription(db_session, customer, plan, "sub-active-only")

        canceled_sub = Subscription(
            external_id="sub-canceled",
            customer_id=customer.id,
            plan_id=plan.id,
            status=SubscriptionStatus.CANCELED.value,
            started_at=datetime.now(UTC) - timedelta(days=5),
        )
        db_session.add(canceled_sub)
        db_session.commit()

        result = _get_active_subscription_ids("cust-mixed-subs", db_session, DEFAULT_ORG_ID)
        assert result == [str(active_sub.id)]

    def test_returns_multiple_active_subscriptions(self, db_session):
        """Test returns multiple active subscription IDs."""
        customer = _create_customer(db_session, "cust-multi-sub")
        plan1 = _create_plan(db_session, "plan-multi-1")
        plan2 = _create_plan(db_session, "plan-multi-2")
        sub1 = _create_active_subscription(db_session, customer, plan1, "sub-multi-1")
        sub2 = _create_active_subscription(db_session, customer, plan2, "sub-multi-2")

        result = _get_active_subscription_ids("cust-multi-sub", db_session, DEFAULT_ORG_ID)
        assert set(result) == {str(sub1.id), str(sub2.id)}


class TestEnqueueThresholdChecks:
    """Tests for _enqueue_threshold_checks helper."""

    @pytest.mark.asyncio
    async def test_enqueues_for_each_subscription(self):
        """Test enqueues a task for each subscription ID."""
        sub_ids = ["sub-1", "sub-2"]
        with patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            await _enqueue_threshold_checks(sub_ids)

        assert mock_enqueue.call_count == 2
        mock_enqueue.assert_any_call("sub-1")
        mock_enqueue.assert_any_call("sub-2")

    @pytest.mark.asyncio
    async def test_continues_on_error(self):
        """Test continues processing if one enqueue fails."""
        sub_ids = ["sub-fail", "sub-ok"]
        with patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            mock_enqueue.side_effect = [Exception("Redis error"), None]
            await _enqueue_threshold_checks(sub_ids)

        assert mock_enqueue.call_count == 2


class TestEventThresholdIntegration:
    """Tests for threshold checking integration with event ingestion API."""

    def test_create_event_enqueues_threshold_check(
        self, client: TestClient, db_session, billable_metric
    ):
        """Test single event ingestion enqueues threshold checks for active subscriptions."""
        customer = _create_customer(db_session, "cust-evt-threshold")
        plan = _create_plan(db_session, "plan-evt-threshold")
        sub = _create_active_subscription(db_session, customer, plan, "sub-evt-threshold")

        with patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            response = client.post(
                "/v1/events/",
                json={
                    "transaction_id": "tx-threshold-001",
                    "external_customer_id": "cust-evt-threshold",
                    "code": "api_calls",
                    "timestamp": "2026-01-15T10:30:00Z",
                },
            )

        assert response.status_code == 201
        mock_enqueue.assert_called_once_with(str(sub.id))

    def test_create_event_no_enqueue_for_duplicate(
        self, client: TestClient, db_session, billable_metric
    ):
        """Test duplicate event does not enqueue threshold checks."""
        customer = _create_customer(db_session, "cust-evt-dup-thresh")
        plan = _create_plan(db_session, "plan-evt-dup-thresh")
        _create_active_subscription(db_session, customer, plan, "sub-evt-dup-thresh")

        # Create the first event
        client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-dup-threshold",
                "external_customer_id": "cust-evt-dup-thresh",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:30:00Z",
            },
        )

        # Send duplicate - should not enqueue
        with patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            response = client.post(
                "/v1/events/",
                json={
                    "transaction_id": "tx-dup-threshold",
                    "external_customer_id": "cust-evt-dup-thresh",
                    "code": "api_calls",
                    "timestamp": "2026-01-15T10:30:00Z",
                },
            )

        assert response.status_code == 201
        mock_enqueue.assert_not_called()

    def test_create_event_no_enqueue_without_customer(self, client: TestClient, billable_metric):
        """Test no threshold check when customer doesn't exist."""
        with patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            response = client.post(
                "/v1/events/",
                json={
                    "transaction_id": "tx-no-cust-001",
                    "external_customer_id": "nonexistent-customer",
                    "code": "api_calls",
                    "timestamp": "2026-01-15T10:30:00Z",
                },
            )

        assert response.status_code == 201
        mock_enqueue.assert_not_called()

    def test_batch_create_enqueues_threshold_checks(
        self, client: TestClient, db_session, billable_metric
    ):
        """Test batch event ingestion enqueues threshold checks."""
        customer = _create_customer(db_session, "cust-batch-thresh")
        plan = _create_plan(db_session, "plan-batch-thresh")
        sub = _create_active_subscription(db_session, customer, plan, "sub-batch-thresh")

        with patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            response = client.post(
                "/v1/events/batch",
                json={
                    "events": [
                        {
                            "transaction_id": "tx-batch-thresh-001",
                            "external_customer_id": "cust-batch-thresh",
                            "code": "api_calls",
                            "timestamp": "2026-01-15T10:00:00Z",
                        },
                        {
                            "transaction_id": "tx-batch-thresh-002",
                            "external_customer_id": "cust-batch-thresh",
                            "code": "api_calls",
                            "timestamp": "2026-01-15T10:01:00Z",
                        },
                    ]
                },
            )

        assert response.status_code == 201
        assert response.json()["ingested"] == 2
        # Should enqueue once per subscription (deduplicated)
        mock_enqueue.assert_called_once_with(str(sub.id))

    def test_batch_create_no_enqueue_all_duplicates(
        self, client: TestClient, db_session, billable_metric
    ):
        """Test batch with all duplicates does not enqueue threshold checks."""
        customer = _create_customer(db_session, "cust-batch-alldup")
        plan = _create_plan(db_session, "plan-batch-alldup")
        _create_active_subscription(db_session, customer, plan, "sub-batch-alldup")

        # Pre-create the events
        client.post(
            "/v1/events/",
            json={
                "transaction_id": "tx-batch-alldup-001",
                "external_customer_id": "cust-batch-alldup",
                "code": "api_calls",
                "timestamp": "2026-01-15T10:00:00Z",
            },
        )

        # Send batch with only duplicates
        with patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            response = client.post(
                "/v1/events/batch",
                json={
                    "events": [
                        {
                            "transaction_id": "tx-batch-alldup-001",
                            "external_customer_id": "cust-batch-alldup",
                            "code": "api_calls",
                            "timestamp": "2026-01-15T10:00:00Z",
                        },
                    ]
                },
            )

        assert response.status_code == 201
        assert response.json()["ingested"] == 0
        mock_enqueue.assert_not_called()

    def test_batch_create_multiple_customers(self, client: TestClient, db_session, billable_metric):
        """Test batch events for multiple customers enqueue for all subscriptions."""
        cust1 = _create_customer(db_session, "cust-multi-batch-1")
        cust2 = _create_customer(db_session, "cust-multi-batch-2")
        plan = _create_plan(db_session, "plan-multi-batch")
        sub1 = _create_active_subscription(db_session, cust1, plan, "sub-multi-batch-1")
        sub2 = _create_active_subscription(db_session, cust2, plan, "sub-multi-batch-2")

        with patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            response = client.post(
                "/v1/events/batch",
                json={
                    "events": [
                        {
                            "transaction_id": "tx-multi-batch-001",
                            "external_customer_id": "cust-multi-batch-1",
                            "code": "api_calls",
                            "timestamp": "2026-01-15T10:00:00Z",
                        },
                        {
                            "transaction_id": "tx-multi-batch-002",
                            "external_customer_id": "cust-multi-batch-2",
                            "code": "api_calls",
                            "timestamp": "2026-01-15T10:01:00Z",
                        },
                    ]
                },
            )

        assert response.status_code == 201
        assert mock_enqueue.call_count == 2
        enqueued_ids = {call.args[0] for call in mock_enqueue.call_args_list}
        assert enqueued_ids == {str(sub1.id), str(sub2.id)}


class TestEventRateLimit:
    """Tests for event ingestion rate limiting."""

    def test_rate_limit_exceeded(self, client: TestClient, billable_metric):
        """Test that exceeding the rate limit returns 429."""
        from app.routers.events import event_rate_limiter

        event_rate_limiter.reset()
        # Patch max_requests to 1 so the second request exceeds the limit
        original = event_rate_limiter.max_requests
        event_rate_limiter.max_requests = 1
        try:
            # First request should succeed
            resp1 = client.post(
                "/v1/events/",
                json={
                    "transaction_id": "tx-rate-1",
                    "external_customer_id": "cust-001",
                    "code": "api_calls",
                    "timestamp": "2026-01-15T10:00:00Z",
                },
            )
            assert resp1.status_code == 201

            # Second request should be rate-limited
            resp2 = client.post(
                "/v1/events/",
                json={
                    "transaction_id": "tx-rate-2",
                    "external_customer_id": "cust-001",
                    "code": "api_calls",
                    "timestamp": "2026-01-15T10:01:00Z",
                },
            )
            assert resp2.status_code == 429
            assert "Rate limit exceeded" in resp2.json()["detail"]
        finally:
            event_rate_limiter.max_requests = original
            event_rate_limiter.reset()


class TestEstimateFeesAPI:
    """Tests for POST /v1/events/estimate_fees endpoint."""

    @pytest.fixture
    def estimate_metric(self, db_session):
        """Create a COUNT billable metric for estimate_fees tests."""
        m = BillableMetric(
            code="est_api_calls",
            name="Estimated API Calls",
            aggregation_type="count",
        )
        db_session.add(m)
        db_session.commit()
        db_session.refresh(m)
        return m

    @pytest.fixture
    def estimate_sum_metric(self, db_session):
        """Create a SUM billable metric for estimate_fees tests."""
        m = BillableMetric(
            code="est_data_transfer",
            name="Data Transfer",
            aggregation_type="sum",
            field_name="bytes",
        )
        db_session.add(m)
        db_session.commit()
        db_session.refresh(m)
        return m

    @pytest.fixture
    def estimate_plan(self, db_session):
        """Create a plan for estimate_fees tests."""
        p = Plan(
            code="est_plan",
            name="Estimate Plan",
            interval=PlanInterval.MONTHLY.value,
            amount_cents=10000,
        )
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        return p

    @pytest.fixture
    def estimate_charge(self, db_session, estimate_plan, estimate_metric):
        """Create a standard charge for estimate_fees tests."""
        c = Charge(
            plan_id=estimate_plan.id,
            billable_metric_id=estimate_metric.id,
            charge_model="standard",
            properties={"unit_price": "50"},
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    @pytest.fixture
    def estimate_customer(self, db_session):
        """Create a customer for estimate_fees tests."""
        c = Customer(
            external_id="est_cust",
            name="Estimate Customer",
            email="est@example.com",
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    @pytest.fixture
    def estimate_subscription(self, db_session, estimate_customer, estimate_plan):
        """Create an active subscription for estimate_fees tests."""
        sub = Subscription(
            external_id="est_sub",
            customer_id=estimate_customer.id,
            plan_id=estimate_plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            started_at=datetime.now(UTC) - timedelta(days=30),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        return sub

    def test_estimate_fees_count_metric(
        self,
        client,
        db_session,
        estimate_metric,
        estimate_charge,
        estimate_customer,
        estimate_subscription,
    ):
        """Test fee estimation with a COUNT metric adds 1 to current usage."""
        # Create some existing events for the current billing period
        now = datetime.now(UTC)
        start = datetime(now.year, now.month, 1, tzinfo=UTC)
        for i in range(3):
            event = Event(
                transaction_id=f"est-tx-{i}",
                external_customer_id="est_cust",
                code="est_api_calls",
                timestamp=start + timedelta(hours=i),
            )
            db_session.add(event)
        db_session.commit()

        response = client.post(
            "/v1/events/estimate_fees",
            json={
                "subscription_id": str(estimate_subscription.id),
                "code": "est_api_calls",
                "properties": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        # 3 existing events + 1 hypothetical = 4 units
        assert Decimal(data["units"]) == Decimal("4")
        # 4 units * 50 cents = 200
        assert Decimal(data["amount_cents"]) == Decimal("200")
        assert data["metric_code"] == "est_api_calls"
        assert data["charge_model"] == "standard"

    def test_estimate_fees_sum_metric(
        self,
        client,
        db_session,
        estimate_sum_metric,
        estimate_plan,
        estimate_customer,
        estimate_subscription,
    ):
        """Test fee estimation with a SUM metric adds event value."""
        # Create a charge for the sum metric
        c = Charge(
            plan_id=estimate_plan.id,
            billable_metric_id=estimate_sum_metric.id,
            charge_model="standard",
            properties={"unit_price": "10"},
        )
        db_session.add(c)
        db_session.commit()

        # Create existing events
        now = datetime.now(UTC)
        start = datetime(now.year, now.month, 1, tzinfo=UTC)
        for i in range(2):
            event = Event(
                transaction_id=f"est-sum-tx-{i}",
                external_customer_id="est_cust",
                code="est_data_transfer",
                timestamp=start + timedelta(hours=i),
                properties={"bytes": 100},
            )
            db_session.add(event)
        db_session.commit()

        response = client.post(
            "/v1/events/estimate_fees",
            json={
                "subscription_id": str(estimate_subscription.id),
                "code": "est_data_transfer",
                "properties": {"bytes": 250},
            },
        )
        assert response.status_code == 200
        data = response.json()
        # 200 existing + 250 hypothetical = 450 units
        assert Decimal(data["units"]) == Decimal("450")
        # 450 * 10 = 4500
        assert Decimal(data["amount_cents"]) == Decimal("4500")

    def test_estimate_fees_subscription_not_found(self, client):
        """Test estimate_fees with non-existent subscription."""
        response = client.post(
            "/v1/events/estimate_fees",
            json={
                "subscription_id": str(uuid.uuid4()),
                "code": "api_calls",
                "properties": {},
            },
        )
        assert response.status_code == 404
        assert "Subscription not found" in response.json()["detail"]

    def test_estimate_fees_inactive_subscription(
        self,
        client,
        db_session,
        estimate_metric,
        estimate_charge,
        estimate_customer,
        estimate_plan,
    ):
        """Test estimate_fees with a non-active subscription returns 400."""
        sub = Subscription(
            external_id="est_canceled_sub",
            customer_id=estimate_customer.id,
            plan_id=estimate_plan.id,
            status=SubscriptionStatus.CANCELED.value,
            started_at=datetime.now(UTC) - timedelta(days=30),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        response = client.post(
            "/v1/events/estimate_fees",
            json={
                "subscription_id": str(sub.id),
                "code": "est_api_calls",
                "properties": {},
            },
        )
        assert response.status_code == 400
        assert "not active" in response.json()["detail"]

    def test_estimate_fees_invalid_metric_code(
        self,
        client,
        estimate_customer,
        estimate_subscription,
    ):
        """Test estimate_fees with non-existent metric code."""
        response = client.post(
            "/v1/events/estimate_fees",
            json={
                "subscription_id": str(estimate_subscription.id),
                "code": "nonexistent_metric",
                "properties": {},
            },
        )
        assert response.status_code == 422
        assert "nonexistent_metric" in response.json()["detail"]

    def test_estimate_fees_no_charge_for_metric(
        self,
        client,
        db_session,
        estimate_customer,
        estimate_subscription,
    ):
        """Test estimate_fees when no charge exists for the metric on the plan."""
        # Create a metric that has no associated charge on the plan
        m = BillableMetric(
            code="est_orphan_metric",
            name="Orphan Metric",
            aggregation_type="count",
        )
        db_session.add(m)
        db_session.commit()

        response = client.post(
            "/v1/events/estimate_fees",
            json={
                "subscription_id": str(estimate_subscription.id),
                "code": "est_orphan_metric",
                "properties": {},
            },
        )
        assert response.status_code == 404
        assert "No charge found" in response.json()["detail"]

    def test_estimate_fees_zero_existing_usage(
        self,
        client,
        db_session,
        estimate_metric,
        estimate_charge,
        estimate_customer,
        estimate_subscription,
    ):
        """Test estimate_fees with no existing events returns estimate for 1 event."""
        response = client.post(
            "/v1/events/estimate_fees",
            json={
                "subscription_id": str(estimate_subscription.id),
                "code": "est_api_calls",
                "properties": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        # 0 existing + 1 hypothetical = 1 unit
        assert Decimal(data["units"]) == Decimal("1")
        # 1 * 50 = 50
        assert Decimal(data["amount_cents"]) == Decimal("50")


class TestAddHypotheticalEvent:
    """Tests for _add_hypothetical_event helper function."""

    def test_count_aggregation(self):
        """Test COUNT adds 1 to usage."""
        result = _add_hypothetical_event(
            current_usage=Decimal("5"),
            current_count=5,
            aggregation_type="count",
            field_name=None,
            event_properties={},
        )
        assert result == Decimal("6")

    def test_sum_aggregation(self):
        """Test SUM adds event value."""
        result = _add_hypothetical_event(
            current_usage=Decimal("100"),
            current_count=3,
            aggregation_type="sum",
            field_name="bytes",
            event_properties={"bytes": 50},
        )
        assert result == Decimal("150")

    def test_max_aggregation_new_max(self):
        """Test MAX returns new max when event exceeds current."""
        result = _add_hypothetical_event(
            current_usage=Decimal("10"),
            current_count=3,
            aggregation_type="max",
            field_name="value",
            event_properties={"value": 20},
        )
        assert result == Decimal("20")

    def test_max_aggregation_same_max(self):
        """Test MAX returns current when event is lower."""
        result = _add_hypothetical_event(
            current_usage=Decimal("100"),
            current_count=3,
            aggregation_type="max",
            field_name="value",
            event_properties={"value": 50},
        )
        assert result == Decimal("100")

    def test_latest_aggregation(self):
        """Test LATEST returns event value."""
        result = _add_hypothetical_event(
            current_usage=Decimal("10"),
            current_count=3,
            aggregation_type="latest",
            field_name="value",
            event_properties={"value": 42},
        )
        assert result == Decimal("42")

    def test_unique_count_aggregation(self):
        """Test UNIQUE_COUNT conservatively adds 1."""
        result = _add_hypothetical_event(
            current_usage=Decimal("5"),
            current_count=10,
            aggregation_type="unique_count",
            field_name="user_id",
            event_properties={"user_id": "new_user"},
        )
        assert result == Decimal("6")

    def test_weighted_sum_aggregation(self):
        """Test WEIGHTED_SUM adds event value."""
        result = _add_hypothetical_event(
            current_usage=Decimal("100"),
            current_count=3,
            aggregation_type="weighted_sum",
            field_name="watts",
            event_properties={"watts": 50},
        )
        assert result == Decimal("150")

    def test_custom_aggregation(self):
        """Test CUSTOM conservatively adds 1."""
        result = _add_hypothetical_event(
            current_usage=Decimal("10"),
            current_count=3,
            aggregation_type="custom",
            field_name=None,
            event_properties={"a": 1, "b": 2},
        )
        assert result == Decimal("11")


class TestCalculateEstimatedAmount:
    """Tests for _calculate_estimated_amount helper function."""

    def test_standard_charge(self):
        """Test standard charge calculation."""
        from app.models.charge import ChargeModel
        from app.services.charge_models.factory import get_charge_calculator

        calculator = get_charge_calculator(ChargeModel.STANDARD)
        amount = _calculate_estimated_amount(
            calculator=calculator,
            charge_model=ChargeModel.STANDARD,
            usage=Decimal("10"),
            properties={"unit_price": "100"},
        )
        assert amount == Decimal("1000")

    def test_standard_charge_with_min_price(self):
        """Test standard charge respects min_price."""
        from app.models.charge import ChargeModel
        from app.services.charge_models.factory import get_charge_calculator

        calculator = get_charge_calculator(ChargeModel.STANDARD)
        amount = _calculate_estimated_amount(
            calculator=calculator,
            charge_model=ChargeModel.STANDARD,
            usage=Decimal("1"),
            properties={"unit_price": "10", "min_price": "500"},
        )
        assert amount == Decimal("500")

    def test_standard_charge_with_max_price(self):
        """Test standard charge respects max_price."""
        from app.models.charge import ChargeModel
        from app.services.charge_models.factory import get_charge_calculator

        calculator = get_charge_calculator(ChargeModel.STANDARD)
        amount = _calculate_estimated_amount(
            calculator=calculator,
            charge_model=ChargeModel.STANDARD,
            usage=Decimal("100"),
            properties={"unit_price": "100", "max_price": "5000"},
        )
        assert amount == Decimal("5000")

    def test_percentage_charge(self):
        """Test percentage charge calculation."""
        from app.models.charge import ChargeModel
        from app.services.charge_models.factory import get_charge_calculator

        calculator = get_charge_calculator(ChargeModel.PERCENTAGE)
        amount = _calculate_estimated_amount(
            calculator=calculator,
            charge_model=ChargeModel.PERCENTAGE,
            usage=Decimal("10"),
            properties={"rate": "10", "base_amount": "1000", "event_count": 1},
        )
        assert amount > Decimal("0")

    def test_graduated_percentage_charge(self):
        """Test graduated percentage charge calculation."""
        from app.models.charge import ChargeModel
        from app.services.charge_models.factory import get_charge_calculator

        calculator = get_charge_calculator(ChargeModel.GRADUATED_PERCENTAGE)
        amount = _calculate_estimated_amount(
            calculator=calculator,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE,
            usage=Decimal("10"),
            properties={
                "base_amount": "1000",
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": None, "rate": "5", "flat_amount": "0"},
                ],
            },
        )
        assert amount > Decimal("0")

    def test_dynamic_charge(self):
        """Test dynamic charge calculation."""
        from app.models.charge import ChargeModel
        from app.services.charge_models.factory import get_charge_calculator

        calculator = get_charge_calculator(ChargeModel.DYNAMIC)
        amount = _calculate_estimated_amount(
            calculator=calculator,
            charge_model=ChargeModel.DYNAMIC,
            usage=Decimal("10"),
            properties={},
        )
        assert amount == Decimal("0")


class TestEstimateFeesEdgeCases:
    """Tests for edge cases in the estimate_fees endpoint."""

    @pytest.fixture
    def edge_customer(self, db_session):
        """Create a customer for edge case tests."""
        c = Customer(
            external_id="edge_cust",
            name="Edge Customer",
            email="edge@example.com",
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    @pytest.fixture
    def edge_plan(self, db_session):
        """Create a plan for edge case tests."""
        p = Plan(
            code="edge_plan",
            name="Edge Plan",
            interval=PlanInterval.MONTHLY.value,
            amount_cents=10000,
        )
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        return p

    @pytest.fixture
    def edge_metric(self, db_session):
        """Create a metric for edge case tests."""
        m = BillableMetric(
            code="edge_metric",
            name="Edge Metric",
            aggregation_type="count",
        )
        db_session.add(m)
        db_session.commit()
        db_session.refresh(m)
        return m

    @pytest.fixture
    def edge_subscription(self, db_session, edge_customer, edge_plan):
        """Create an active subscription for edge case tests."""
        sub = Subscription(
            external_id="edge_sub",
            customer_id=edge_customer.id,
            plan_id=edge_plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            started_at=datetime.now(UTC) - timedelta(days=30),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        return sub

    def test_estimate_fees_customer_not_found(
        self, client, db_session, edge_metric, edge_plan
    ):
        """Test estimate_fees when subscription exists but customer was deleted."""
        # Create a subscription with a non-existent customer_id
        sub = Subscription(
            external_id="orphan_sub",
            customer_id=uuid.uuid4(),
            plan_id=edge_plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            started_at=datetime.now(UTC) - timedelta(days=30),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        response = client.post(
            "/v1/events/estimate_fees",
            json={
                "subscription_id": str(sub.id),
                "code": "edge_metric",
                "properties": {},
            },
        )
        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]

    def test_estimate_fees_unsupported_charge_model(
        self,
        client,
        db_session,
        edge_customer,
        edge_metric,
        edge_plan,
        edge_subscription,
    ):
        """Test estimate_fees with an unsupported charge model."""
        c = Charge(
            plan_id=edge_plan.id,
            billable_metric_id=edge_metric.id,
            charge_model="standard",
            properties={"unit_price": "100"},
        )
        db_session.add(c)
        db_session.commit()

        with patch(
            "app.routers.events.get_charge_calculator",
            return_value=None,
        ):
            response = client.post(
                "/v1/events/estimate_fees",
                json={
                    "subscription_id": str(edge_subscription.id),
                    "code": "edge_metric",
                    "properties": {},
                },
            )
        assert response.status_code == 400
        assert "Unsupported charge model" in response.json()["detail"]
