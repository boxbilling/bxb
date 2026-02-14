"""Tests for rate limiting on event ingestion.

Verifies that the sliding-window rate limiter correctly allows requests
under the limit and rejects requests that exceed the limit. Also tests
batch event ingestion rate limiting and limiter reset behavior.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.rate_limiter import RateLimiter
from app.main import app
from app.models.billable_metric import AggregationType
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.schemas.billable_metric import BillableMetricCreate
from tests.conftest import DEFAULT_ORG_ID


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
    repo = BillableMetricRepository(db_session)
    return repo.create(
        BillableMetricCreate(
            code="rl_api_calls",
            name="RL API Calls",
            aggregation_type=AggregationType.COUNT,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Ensure rate limiter is clean before and after every test."""
    from app.routers.events import event_rate_limiter

    event_rate_limiter.reset()
    yield
    event_rate_limiter.reset()


def _event_payload(tx_id: str, code: str = "rl_api_calls") -> dict:
    return {
        "transaction_id": tx_id,
        "external_customer_id": "rl_cust",
        "code": code,
        "timestamp": "2026-01-20T12:00:00Z",
    }


class TestRateLimiterUnit:
    """Unit tests for the RateLimiter class itself."""

    def test_allows_under_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is True

    def test_rejects_over_limit(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is False

    def test_separate_keys_have_separate_limits(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed("key_a") is True
        assert limiter.is_allowed("key_b") is True
        # key_a is now exhausted
        assert limiter.is_allowed("key_a") is False
        # key_b is also exhausted
        assert limiter.is_allowed("key_b") is False

    def test_reset_clears_all_state(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is False
        limiter.reset()
        assert limiter.is_allowed("key1") is True

    def test_allows_after_window_expires(self):
        """Requests outside the sliding window are pruned."""
        import time
        from unittest.mock import patch

        limiter = RateLimiter(max_requests=1, window_seconds=1)
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is False

        # Advance time past the window
        future = time.monotonic() + 2
        with patch("app.core.rate_limiter.time.monotonic", return_value=future):
            assert limiter.is_allowed("key1") is True


class TestEventRateLimitSingle:
    """Integration tests: rate limiting on single event ingestion."""

    def test_allows_under_limit(self, client: TestClient, billable_metric):
        from app.routers.events import event_rate_limiter

        event_rate_limiter.max_requests = 3
        for i in range(3):
            resp = client.post("/v1/events/", json=_event_payload(f"rl-single-{i}"))
            assert resp.status_code == 201, f"Request {i} should succeed"

    def test_rejects_over_limit(self, client: TestClient, billable_metric):
        from app.routers.events import event_rate_limiter

        event_rate_limiter.max_requests = 2
        # First two should succeed
        resp1 = client.post("/v1/events/", json=_event_payload("rl-over-1"))
        assert resp1.status_code == 201
        resp2 = client.post("/v1/events/", json=_event_payload("rl-over-2"))
        assert resp2.status_code == 201

        # Third should be rate limited
        resp3 = client.post("/v1/events/", json=_event_payload("rl-over-3"))
        assert resp3.status_code == 429
        assert "Rate limit exceeded" in resp3.json()["detail"]

    def test_429_response_body(self, client: TestClient, billable_metric):
        from app.routers.events import event_rate_limiter

        event_rate_limiter.max_requests = 1
        client.post("/v1/events/", json=_event_payload("rl-body-1"))
        resp = client.post("/v1/events/", json=_event_payload("rl-body-2"))
        assert resp.status_code == 429
        body = resp.json()
        assert "detail" in body
        assert "Rate limit exceeded" in body["detail"]


class TestEventRateLimitBatch:
    """Integration tests: rate limiting on batch event ingestion."""

    def test_batch_allowed_under_limit(self, client: TestClient, billable_metric):
        from app.routers.events import event_rate_limiter

        event_rate_limiter.max_requests = 5
        resp = client.post(
            "/v1/events/batch",
            json={
                "events": [
                    _event_payload(f"rl-batch-ok-{i}")
                    for i in range(3)
                ]
            },
        )
        assert resp.status_code == 201

    def test_batch_rejected_over_limit(self, client: TestClient, billable_metric):
        from app.routers.events import event_rate_limiter

        event_rate_limiter.max_requests = 1
        # Exhaust the limit with a single event
        resp1 = client.post("/v1/events/", json=_event_payload("rl-batch-exhaust"))
        assert resp1.status_code == 201

        # Batch should be rejected
        resp2 = client.post(
            "/v1/events/batch",
            json={
                "events": [
                    _event_payload(f"rl-batch-fail-{i}")
                    for i in range(2)
                ]
            },
        )
        assert resp2.status_code == 429

    def test_list_events_not_rate_limited(self, client: TestClient, billable_metric):
        """GET /v1/events/ should NOT be rate limited, only POST is."""
        from app.routers.events import event_rate_limiter

        event_rate_limiter.max_requests = 1
        # Exhaust the POST limit
        client.post("/v1/events/", json=_event_payload("rl-get-exhaust"))

        # GET should still work
        resp = client.get("/v1/events/")
        assert resp.status_code == 200
