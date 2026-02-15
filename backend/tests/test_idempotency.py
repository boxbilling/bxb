"""Tests for idempotency model, repository, core dependency, and endpoint integration."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.idempotency import (
    IdempotencyResult,
    check_idempotency,
    record_idempotency_response,
)
from app.main import app
from app.models.idempotency_record import IdempotencyRecord
from app.repositories.idempotency_repository import IdempotencyRepository
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def db_session():
    """Create a database session for direct testing."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def repo(db_session: Session) -> IdempotencyRepository:
    return IdempotencyRepository(db_session)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestIdempotencyRecordModel:
    def test_create_record(self, db_session: Session) -> None:
        record = IdempotencyRecord(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="key-1",
            request_method="POST",
            request_path="/v1/customers",
        )
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)

        assert record.id is not None
        assert record.organization_id == DEFAULT_ORG_ID
        assert record.idempotency_key == "key-1"
        assert record.request_method == "POST"
        assert record.request_path == "/v1/customers"
        assert record.response_status is None
        assert record.response_body is None
        assert record.created_at is not None

    def test_unique_constraint(self, db_session: Session) -> None:
        record1 = IdempotencyRecord(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="dup-key",
            request_method="POST",
            request_path="/v1/customers",
        )
        db_session.add(record1)
        db_session.commit()

        record2 = IdempotencyRecord(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="dup-key",
            request_method="POST",
            request_path="/v1/customers",
        )
        db_session.add(record2)
        with pytest.raises(Exception):  # noqa: B017
            db_session.commit()
        db_session.rollback()


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestIdempotencyRepository:
    def test_create_and_get_by_key(self, repo: IdempotencyRepository) -> None:
        record = repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="repo-key-1",
            request_method="POST",
            request_path="/v1/subscriptions",
        )
        assert record.id is not None
        assert record.idempotency_key == "repo-key-1"

        fetched = repo.get_by_key(DEFAULT_ORG_ID, "repo-key-1")
        assert fetched is not None
        assert fetched.id == record.id

    def test_get_by_key_not_found(self, repo: IdempotencyRepository) -> None:
        result = repo.get_by_key(DEFAULT_ORG_ID, "nonexistent")
        assert result is None

    def test_different_orgs_dont_collide(self, repo: IdempotencyRepository) -> None:
        org_a = DEFAULT_ORG_ID
        org_b = uuid4()

        # Seed org_b in the organizations table
        from app.models.organization import Organization

        org = Organization(id=org_b, name="Org B")
        repo.db.add(org)
        repo.db.commit()

        repo.create(
            organization_id=org_a,
            idempotency_key="shared-key",
            request_method="POST",
            request_path="/v1/customers",
            response_status=201,
            response_body={"id": "aaa"},
        )
        repo.create(
            organization_id=org_b,
            idempotency_key="shared-key",
            request_method="POST",
            request_path="/v1/customers",
            response_status=201,
            response_body={"id": "bbb"},
        )

        record_a = repo.get_by_key(org_a, "shared-key")
        record_b = repo.get_by_key(org_b, "shared-key")
        assert record_a is not None
        assert record_b is not None
        assert record_a.response_body == {"id": "aaa"}
        assert record_b.response_body == {"id": "bbb"}

    def test_update_response(self, repo: IdempotencyRepository) -> None:
        record = repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="update-key",
            request_method="POST",
            request_path="/v1/invoices",
        )
        assert record.response_status is None

        repo.update_response(record, 201, {"id": "inv-1"})

        fetched = repo.get_by_key(DEFAULT_ORG_ID, "update-key")
        assert fetched is not None
        assert fetched.response_status == 201
        assert fetched.response_body == {"id": "inv-1"}

    def test_delete_expired(self, db_session: Session, repo: IdempotencyRepository) -> None:
        # Create a record and backdate it
        record = repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="old-key",
            request_method="POST",
            request_path="/v1/events",
            response_status=200,
            response_body={},
        )
        old_time = datetime.now(UTC) - timedelta(hours=25)
        record.created_at = old_time  # type: ignore[assignment]
        db_session.commit()

        # Create a fresh record
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="new-key",
            request_method="POST",
            request_path="/v1/events",
            response_status=200,
            response_body={},
        )

        deleted = repo.delete_expired(max_age_hours=24)
        assert deleted == 1

        assert repo.get_by_key(DEFAULT_ORG_ID, "old-key") is None
        assert repo.get_by_key(DEFAULT_ORG_ID, "new-key") is not None

    def test_delete_expired_none(self, repo: IdempotencyRepository) -> None:
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="fresh-key",
            request_method="POST",
            request_path="/v1/customers",
            response_status=201,
            response_body={},
        )
        deleted = repo.delete_expired(max_age_hours=24)
        assert deleted == 0


# ---------------------------------------------------------------------------
# Core dependency tests
# ---------------------------------------------------------------------------


def _make_request(headers: dict[str, str] | None = None, method: str = "POST", path: str = "/v1/customers") -> Request:
    """Build a minimal ASGI Request for testing."""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    request = Request(scope)
    return request


class TestCheckIdempotency:
    def test_no_header_returns_none(self, db_session: Session) -> None:
        request = _make_request()
        result = check_idempotency(request, db_session, DEFAULT_ORG_ID)
        assert result is None

    def test_new_key_returns_idempotency_result(self, db_session: Session) -> None:
        request = _make_request(headers={"Idempotency-Key": "new-dep-key"})
        result = check_idempotency(request, db_session, DEFAULT_ORG_ID)

        assert isinstance(result, IdempotencyResult)
        assert result.key == "new-dep-key"
        assert result.method == "POST"
        assert result.path == "/v1/customers"

        # Verify a record was created in the database
        repo = IdempotencyRepository(db_session)
        record = repo.get_by_key(DEFAULT_ORG_ID, "new-dep-key")
        assert record is not None
        assert record.response_status is None

    def test_existing_completed_key_returns_cached_response(
        self, db_session: Session, repo: IdempotencyRepository
    ) -> None:
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="cached-key",
            request_method="POST",
            request_path="/v1/customers",
            response_status=201,
            response_body={"id": "cust-123", "name": "Test"},
        )

        request = _make_request(headers={"Idempotency-Key": "cached-key"})
        result = check_idempotency(request, db_session, DEFAULT_ORG_ID)

        from fastapi.responses import JSONResponse

        assert isinstance(result, JSONResponse)
        assert result.status_code == 201
        assert result.headers.get("Idempotency-Replayed") == "true"

    def test_existing_pending_key_returns_idempotency_result(
        self, db_session: Session, repo: IdempotencyRepository
    ) -> None:
        # Record exists but response not yet stored (concurrent request)
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="pending-key",
            request_method="POST",
            request_path="/v1/customers",
        )

        request = _make_request(headers={"Idempotency-Key": "pending-key"})
        result = check_idempotency(request, db_session, DEFAULT_ORG_ID)

        assert isinstance(result, IdempotencyResult)
        assert result.key == "pending-key"


class TestRecordIdempotencyResponse:
    def test_records_response(self, db_session: Session, repo: IdempotencyRepository) -> None:
        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="record-key",
            request_method="POST",
            request_path="/v1/customers",
        )

        record_idempotency_response(
            db_session, DEFAULT_ORG_ID, "record-key", 201, {"id": "cust-456"}
        )

        record = repo.get_by_key(DEFAULT_ORG_ID, "record-key")
        assert record is not None
        assert record.response_status == 201
        assert record.response_body == {"id": "cust-456"}

    def test_no_record_does_nothing(self, db_session: Session) -> None:
        # Should not raise even if no record exists
        record_idempotency_response(
            db_session, DEFAULT_ORG_ID, "missing-key", 201, {"id": "x"}
        )


# ---------------------------------------------------------------------------
# Endpoint integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


class TestCustomerIdempotencyIntegration:
    def test_create_customer_same_key_returns_cached_response(self, client: TestClient) -> None:
        key = f"cust-idem-{uuid4()}"
        payload = {"external_id": f"ext-{uuid4()}", "name": "Idempotent Corp"}

        resp1 = client.post("/v1/customers/", json=payload, headers={"Idempotency-Key": key})
        assert resp1.status_code == 201
        data1 = resp1.json()

        resp2 = client.post("/v1/customers/", json=payload, headers={"Idempotency-Key": key})
        assert resp2.status_code == 201
        assert resp2.headers.get("Idempotency-Replayed") == "true"
        data2 = resp2.json()
        assert data2["id"] == data1["id"]
        assert data2["external_id"] == data1["external_id"]

    def test_create_customer_different_key_creates_new(self, client: TestClient) -> None:
        key1 = f"cust-diff-{uuid4()}"
        key2 = f"cust-diff-{uuid4()}"

        resp1 = client.post(
            "/v1/customers/",
            json={"external_id": f"ext-{uuid4()}", "name": "First"},
            headers={"Idempotency-Key": key1},
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/v1/customers/",
            json={"external_id": f"ext-{uuid4()}", "name": "Second"},
            headers={"Idempotency-Key": key2},
        )
        assert resp2.status_code == 201
        assert resp2.json()["id"] != resp1.json()["id"]

    def test_create_customer_no_key_works_normally(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/customers/",
            json={"external_id": f"ext-{uuid4()}", "name": "No Key"},
        )
        assert resp.status_code == 201
        assert resp.headers.get("Idempotency-Replayed") is None


class TestSubscriptionIdempotencyIntegration:
    @pytest.fixture(autouse=True)
    def _create_customer_and_plan(self, db_session: Session) -> None:
        from app.models.customer import Customer
        from app.models.plan import Plan, PlanInterval

        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="idem-sub-cust",
            name="Sub Idempotency Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        self._customer_id = str(customer.id)

        plan = Plan(
            organization_id=DEFAULT_ORG_ID,
            code="idem-test-plan",
            name="Idempotency Test Plan",
            interval=PlanInterval.MONTHLY.value,
            amount_cents=1000,
            currency="USD",
        )
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)
        self._plan_id = str(plan.id)

    def test_create_subscription_same_key_returns_cached(self, client: TestClient) -> None:
        key = f"sub-idem-{uuid4()}"
        payload = {
            "external_id": f"sub-{uuid4()}",
            "customer_id": self._customer_id,
            "plan_id": self._plan_id,
        }
        resp1 = client.post("/v1/subscriptions/", json=payload, headers={"Idempotency-Key": key})
        assert resp1.status_code == 201

        resp2 = client.post("/v1/subscriptions/", json=payload, headers={"Idempotency-Key": key})
        assert resp2.status_code == 201
        assert resp2.headers.get("Idempotency-Replayed") == "true"
        assert resp2.json()["id"] == resp1.json()["id"]


class TestInvoiceFinalizeIdempotencyIntegration:
    @pytest.fixture(autouse=True)
    def _create_invoice(self, db_session: Session) -> None:
        from app.models.customer import Customer
        from app.models.invoice import Invoice

        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="idem-inv-cust",
            name="Invoice Idempotency Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        invoice = Invoice(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            invoice_number="IDEM-INV-001",
            status="draft",
            invoice_type="subscription",
            billing_period_start=datetime(2026, 1, 1),
            billing_period_end=datetime(2026, 2, 1),
            subtotal=1000,
            tax_amount=0,
            total=1000,
            currency="USD",
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)
        self._invoice_id = str(invoice.id)

    def test_finalize_invoice_same_key_returns_cached(self, client: TestClient) -> None:
        key = f"inv-idem-{uuid4()}"
        resp1 = client.post(
            f"/v1/invoices/{self._invoice_id}/finalize",
            headers={"Idempotency-Key": key},
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            f"/v1/invoices/{self._invoice_id}/finalize",
            headers={"Idempotency-Key": key},
        )
        assert resp2.status_code == 200
        assert resp2.headers.get("Idempotency-Replayed") == "true"
        assert resp2.json()["id"] == resp1.json()["id"]


class TestCheckoutIdempotencyIntegration:
    @pytest.fixture(autouse=True)
    def _create_finalized_invoice(self, db_session: Session) -> None:
        from app.models.customer import Customer
        from app.models.invoice import Invoice

        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="idem-pay-cust",
            name="Payment Idempotency Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        invoice = Invoice(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            invoice_number="IDEM-PAY-001",
            status="finalized",
            invoice_type="subscription",
            billing_period_start=datetime(2026, 1, 1),
            billing_period_end=datetime(2026, 2, 1),
            subtotal=1000,
            tax_amount=0,
            total=1000,
            currency="USD",
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)
        self._invoice_id = str(invoice.id)

    def test_checkout_same_key_returns_cached(self, client: TestClient) -> None:
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_session.provider_checkout_id = "chk_123"
        mock_session.checkout_url = "https://pay.example.com/chk_123"
        mock_session.expires_at = None
        mock_provider = MagicMock()
        mock_provider.create_checkout_session.return_value = mock_session

        key = f"pay-idem-{uuid4()}"
        payload = {
            "invoice_id": self._invoice_id,
            "provider": "stripe",
            "success_url": "https://example.com/ok",
            "cancel_url": "https://example.com/cancel",
        }
        with patch("app.routers.payments.get_payment_provider", return_value=mock_provider):
            resp1 = client.post(
                "/v1/payments/checkout", json=payload, headers={"Idempotency-Key": key}
            )
        assert resp1.status_code == 200

        resp2 = client.post(
            "/v1/payments/checkout", json=payload, headers={"Idempotency-Key": key}
        )
        assert resp2.status_code == 200
        assert resp2.headers.get("Idempotency-Replayed") == "true"
        assert resp2.json()["payment_id"] == resp1.json()["payment_id"]


class TestEventIdempotencyIntegration:
    @pytest.fixture(autouse=True)
    def _create_metric(self, db_session: Session) -> None:
        from app.models.billable_metric import AggregationType, BillableMetric

        metric = BillableMetric(
            organization_id=DEFAULT_ORG_ID,
            code="idem_test_calls",
            name="Idempotency Test Calls",
            aggregation_type=AggregationType.COUNT.value,
        )
        db_session.add(metric)
        db_session.commit()

    def test_create_event_same_key_returns_cached(self, client: TestClient) -> None:
        key = f"evt-idem-{uuid4()}"
        payload = {
            "transaction_id": f"tx-{uuid4()}",
            "external_customer_id": "cust-001",
            "code": "idem_test_calls",
            "timestamp": "2026-01-15T10:30:00Z",
        }
        resp1 = client.post("/v1/events/", json=payload, headers={"Idempotency-Key": key})
        assert resp1.status_code == 201

        resp2 = client.post("/v1/events/", json=payload, headers={"Idempotency-Key": key})
        assert resp2.status_code == 201
        assert resp2.headers.get("Idempotency-Replayed") == "true"
        assert resp2.json()["id"] == resp1.json()["id"]


class TestCleanupIdempotencyRecordsTask:
    @pytest.mark.asyncio
    async def test_cleanup_deletes_old_records(self, db_session: Session) -> None:
        from unittest.mock import patch

        from app.worker import cleanup_idempotency_records_task

        repo = IdempotencyRepository(db_session)
        record = repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="cleanup-old",
            request_method="POST",
            request_path="/v1/customers",
            response_status=201,
            response_body={"id": "test"},
        )
        record.created_at = datetime.now(UTC) - timedelta(hours=25)  # type: ignore[assignment]
        db_session.commit()

        repo.create(
            organization_id=DEFAULT_ORG_ID,
            idempotency_key="cleanup-new",
            request_method="POST",
            request_path="/v1/customers",
            response_status=201,
            response_body={"id": "test2"},
        )

        with patch("app.worker.SessionLocal", return_value=db_session):
            result = await cleanup_idempotency_records_task({})
        assert result == 1

        assert repo.get_by_key(DEFAULT_ORG_ID, "cleanup-old") is None
        assert repo.get_by_key(DEFAULT_ORG_ID, "cleanup-new") is not None

    @pytest.mark.asyncio
    async def test_cleanup_nothing_to_delete(self, db_session: Session) -> None:
        from unittest.mock import patch

        from app.worker import cleanup_idempotency_records_task

        with patch("app.worker.SessionLocal", return_value=db_session):
            result = await cleanup_idempotency_records_task({})
        assert result == 0

    def test_worker_settings_includes_cleanup_function(self) -> None:
        from app.worker import WorkerSettings

        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "cleanup_idempotency_records_task" in func_names

    def test_worker_settings_includes_cleanup_cron(self) -> None:
        from app.worker import WorkerSettings

        cron_func_names = [job.coroutine.__name__ for job in WorkerSettings.cron_jobs]
        assert "cleanup_idempotency_records_task" in cron_func_names

    def test_cleanup_cron_runs_daily_at_midnight(self) -> None:
        from app.worker import WorkerSettings

        job = None
        for j in WorkerSettings.cron_jobs:
            if j.coroutine.__name__ == "cleanup_idempotency_records_task":
                job = j
                break
        assert job is not None
        assert job.hour == 0
        assert job.minute == 0
