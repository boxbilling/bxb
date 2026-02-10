"""Event API tests for bxb."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine, get_db
from app.main import app
from app.models.event import Event
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.event_repository import EventRepository
from app.schemas.billable_metric import BillableMetricCreate
from app.schemas.event import EventCreate


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
    return repo.create(data)


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
    return repo.create(data)


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
        repo.create(data)

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
        repo.create(data)

        assert repo.transaction_id_exists("exists-tx-001") is True
        assert repo.transaction_id_exists("not-exists") is False

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
        event, is_new = repo.create_or_get_existing(data)

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
        event1, is_new1 = repo.create_or_get_existing(data)
        event2, is_new2 = repo.create_or_get_existing(data)

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
        repo.create(data1)

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
        events, ingested, duplicates = repo.create_batch(batch_data)

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
            repo.create(data)

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
        events, ingested, duplicates = repo.create_batch(batch_data)

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
            repo.create(data)

        # Filter by customer
        cust1_events = repo.get_all(external_customer_id="cust-001")
        assert len(cust1_events) == 2

        # Filter by code
        api_events = repo.get_all(code="api_calls")
        assert len(api_events) == 2

        # Filter by customer and code
        cust1_api = repo.get_all(external_customer_id="cust-001", code="api_calls")
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
            repo.create(data)

        # Filter from t2
        from_t2 = repo.get_all(from_timestamp=t2)
        assert len(from_t2) == 2

        # Filter to t2
        to_t2 = repo.get_all(to_timestamp=t2)
        assert len(to_t2) == 2

        # Filter between t1 and t2
        between = repo.get_all(from_timestamp=t1, to_timestamp=t2)
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
        event = repo.create(data)
        event_id = event.id

        assert repo.delete(event_id) is True
        assert repo.get_by_id(event_id) is None

    def test_delete_event_not_found(self, db_session):
        """Test deleting non-existent event."""
        repo = EventRepository(db_session)
        fake_id = uuid.uuid4()
        assert repo.delete(fake_id) is False


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
