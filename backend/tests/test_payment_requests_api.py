"""Tests for PaymentRequest API router endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.customer import Customer, generate_uuid
from app.models.invoice import Invoice
from app.models.payment_request import PaymentRequest
from app.repositories.payment_request_repository import PaymentRequestRepository
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def db_session():
    """Get a database session."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def customer(db_session: Session) -> Customer:
    """Create a test customer."""
    c = Customer(
        organization_id=DEFAULT_ORG_ID,
        external_id="cust-api-pr-001",
        name="API PR Test Customer",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def invoices(db_session: Session, customer: Customer) -> list[Invoice]:
    """Create test finalized invoices."""
    invs = []
    for i in range(3):
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number=f"INV-API-PR-{i:04d}",
            customer_id=customer.id,
            status="finalized",
            billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
            billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
            subtotal=Decimal("100"),
            tax_amount=Decimal("0"),
            total=Decimal("100"),
            currency="USD",
        )
        db_session.add(inv)
        invs.append(inv)
    db_session.commit()
    for inv in invs:
        db_session.refresh(inv)
    return invs


@pytest.fixture
def payment_request(
    db_session: Session,
    customer: Customer,
    invoices: list[Invoice],
) -> PaymentRequest:
    """Create a test payment request."""
    repo = PaymentRequestRepository(db_session)
    return repo.create(
        organization_id=DEFAULT_ORG_ID,
        customer_id=customer.id,
        amount_cents=Decimal("300"),
        amount_currency="USD",
        invoice_ids=[inv.id for inv in invoices],
    )


class TestCreatePaymentRequest:
    def test_create_payment_request(
        self,
        client: TestClient,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        """Test creating a manual payment request."""
        response = client.post(
            "/v1/payment_requests/",
            json={
                "customer_id": str(customer.id),
                "invoice_ids": [str(inv.id) for inv in invoices[:2]],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["customer_id"] == str(customer.id)
        assert data["organization_id"] == str(DEFAULT_ORG_ID)
        assert data["payment_status"] == "pending"
        assert data["payment_attempts"] == 0
        assert data["ready_for_payment_processing"] is True
        assert data["amount_currency"] == "USD"
        assert len(data["invoices"]) == 2
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_payment_request_customer_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test creating a payment request with non-existent customer."""
        response = client.post(
            "/v1/payment_requests/",
            json={
                "customer_id": str(uuid.uuid4()),
                "invoice_ids": [str(uuid.uuid4())],
            },
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    def test_create_payment_request_invoice_not_found(
        self,
        client: TestClient,
        customer: Customer,
    ) -> None:
        """Test creating a payment request with non-existent invoice."""
        response = client.post(
            "/v1/payment_requests/",
            json={
                "customer_id": str(customer.id),
                "invoice_ids": [str(uuid.uuid4())],
            },
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    def test_create_payment_request_validation_error(
        self,
        client: TestClient,
    ) -> None:
        """Test creating a payment request with empty invoice_ids returns 422."""
        response = client.post(
            "/v1/payment_requests/",
            json={
                "customer_id": str(uuid.uuid4()),
                "invoice_ids": [],
            },
        )
        assert response.status_code == 422


class TestListPaymentRequests:
    def test_list_payment_requests_empty(self, client: TestClient) -> None:
        """Test listing payment requests when none exist."""
        response = client.get("/v1/payment_requests/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_payment_requests(
        self,
        client: TestClient,
        payment_request: PaymentRequest,
    ) -> None:
        """Test listing payment requests."""
        response = client.get("/v1/payment_requests/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(payment_request.id)
        assert len(data[0]["invoices"]) == 3

    def test_list_payment_requests_filter_customer(
        self,
        client: TestClient,
        customer: Customer,
        payment_request: PaymentRequest,
    ) -> None:
        """Test listing payment requests filtered by customer_id."""
        response = client.get(
            f"/v1/payment_requests/?customer_id={customer.id}",
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

        # No results for a different customer
        response = client.get(
            f"/v1/payment_requests/?customer_id={uuid.uuid4()}",
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_payment_requests_filter_status(
        self,
        client: TestClient,
        payment_request: PaymentRequest,
    ) -> None:
        """Test listing payment requests filtered by status."""
        response = client.get("/v1/payment_requests/?payment_status=pending")
        assert response.status_code == 200
        assert len(response.json()) == 1

        response = client.get("/v1/payment_requests/?payment_status=succeeded")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_payment_requests_pagination(
        self,
        client: TestClient,
        db_session: Session,
        customer: Customer,
        invoices: list[Invoice],
    ) -> None:
        """Test listing payment requests with pagination."""
        repo = PaymentRequestRepository(db_session)
        for i, inv in enumerate(invoices):
            repo.create(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                amount_cents=Decimal(str((i + 1) * 100)),
                amount_currency="USD",
                invoice_ids=[inv.id],
            )

        response = client.get("/v1/payment_requests/?skip=1&limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestGetPaymentRequest:
    def test_get_payment_request(
        self,
        client: TestClient,
        payment_request: PaymentRequest,
        customer: Customer,
    ) -> None:
        """Test getting a payment request by ID."""
        response = client.get(f"/v1/payment_requests/{payment_request.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(payment_request.id)
        assert data["customer_id"] == str(customer.id)
        assert data["payment_status"] == "pending"
        assert len(data["invoices"]) == 3

    def test_get_payment_request_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent payment request returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/payment_requests/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Payment request not found"


class TestBatchCreatePaymentRequests:
    """Tests for POST /v1/payment_requests/batch."""

    def test_batch_create_no_overdue(self, client: TestClient) -> None:
        """Test batch creation with no overdue invoices."""
        response = client.post("/v1/payment_requests/batch")
        assert response.status_code == 201
        data = response.json()
        assert data["total_customers"] == 0
        assert data["created"] == 0
        assert data["failed"] == 0
        assert data["results"] == []

    def test_batch_create_with_overdue_invoices(
        self,
        client: TestClient,
        db_session: Session,
        customer: Customer,
    ) -> None:
        """Test batch creation with overdue finalized invoices."""
        # Create overdue invoices (due date in the past)
        past = datetime(2025, 6, 1, tzinfo=UTC)
        for i in range(2):
            inv = Invoice(
                organization_id=DEFAULT_ORG_ID,
                invoice_number=f"INV-BATCH-{i:04d}",
                customer_id=customer.id,
                status="finalized",
                billing_period_start=datetime(2025, 5, 1, tzinfo=UTC),
                billing_period_end=datetime(2025, 5, 31, tzinfo=UTC),
                subtotal=Decimal("150"),
                tax_amount=Decimal("0"),
                total=Decimal("150"),
                currency="USD",
                due_date=past,
            )
            db_session.add(inv)
        db_session.commit()

        response = client.post("/v1/payment_requests/batch")
        assert response.status_code == 201
        data = response.json()
        assert data["total_customers"] == 1
        assert data["created"] == 1
        assert data["failed"] == 0
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["customer_id"] == str(customer.id)
        assert result["customer_name"] == customer.name
        assert result["invoice_count"] == 2
        assert result["status"] == "created"
        assert result["payment_request_id"] is not None

    def test_batch_create_excludes_non_overdue(
        self,
        client: TestClient,
        db_session: Session,
        customer: Customer,
    ) -> None:
        """Test batch creation excludes invoices with future due dates."""
        future = datetime.now(UTC) + timedelta(days=30)
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="INV-BATCH-FUTURE-001",
            customer_id=customer.id,
            status="finalized",
            billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
            billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
            subtotal=Decimal("100"),
            tax_amount=Decimal("0"),
            total=Decimal("100"),
            currency="USD",
            due_date=future,
        )
        db_session.add(inv)
        db_session.commit()

        response = client.post("/v1/payment_requests/batch")
        assert response.status_code == 201
        data = response.json()
        assert data["total_customers"] == 0
        assert data["created"] == 0

    def test_batch_create_excludes_no_due_date(
        self,
        client: TestClient,
        db_session: Session,
        customer: Customer,
    ) -> None:
        """Test batch creation excludes invoices without a due date."""
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="INV-BATCH-NODUE-001",
            customer_id=customer.id,
            status="finalized",
            billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
            billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
            subtotal=Decimal("100"),
            tax_amount=Decimal("0"),
            total=Decimal("100"),
            currency="USD",
            due_date=None,
        )
        db_session.add(inv)
        db_session.commit()

        response = client.post("/v1/payment_requests/batch")
        assert response.status_code == 201
        assert response.json()["total_customers"] == 0

    def test_batch_create_multiple_customers(
        self,
        client: TestClient,
        db_session: Session,
        customer: Customer,
    ) -> None:
        """Test batch creation groups by customer."""
        # Create a second customer
        c2 = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-batch-002",
            name="Batch Customer 2",
        )
        db_session.add(c2)
        db_session.commit()
        db_session.refresh(c2)

        past = datetime(2025, 6, 1, tzinfo=UTC)
        for cust in [customer, c2]:
            inv = Invoice(
                organization_id=DEFAULT_ORG_ID,
                invoice_number=f"INV-BATCH-MULTI-{cust.external_id}",
                customer_id=cust.id,
                status="finalized",
                billing_period_start=datetime(2025, 5, 1, tzinfo=UTC),
                billing_period_end=datetime(2025, 5, 31, tzinfo=UTC),
                subtotal=Decimal("200"),
                tax_amount=Decimal("0"),
                total=Decimal("200"),
                currency="USD",
                due_date=past,
            )
            db_session.add(inv)
        db_session.commit()

        response = client.post("/v1/payment_requests/batch")
        assert response.status_code == 201
        data = response.json()
        assert data["total_customers"] == 2
        assert data["created"] == 2

    def test_batch_create_excludes_draft_invoices(
        self,
        client: TestClient,
        db_session: Session,
        customer: Customer,
    ) -> None:
        """Test batch creation excludes draft invoices (only finalized)."""
        past = datetime(2025, 6, 1, tzinfo=UTC)
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="INV-BATCH-DRAFT-001",
            customer_id=customer.id,
            status="draft",
            billing_period_start=datetime(2025, 5, 1, tzinfo=UTC),
            billing_period_end=datetime(2025, 5, 31, tzinfo=UTC),
            subtotal=Decimal("100"),
            tax_amount=Decimal("0"),
            total=Decimal("100"),
            currency="USD",
            due_date=past,
        )
        db_session.add(inv)
        db_session.commit()

        response = client.post("/v1/payment_requests/batch")
        assert response.status_code == 201
        assert response.json()["total_customers"] == 0


class TestGetPaymentAttemptHistory:
    """Tests for GET /v1/payment_requests/{id}/attempts."""

    def test_get_attempts_basic(
        self,
        client: TestClient,
        payment_request: PaymentRequest,
    ) -> None:
        """Test getting attempt history returns at least the creation entry."""
        response = client.get(
            f"/v1/payment_requests/{payment_request.id}/attempts",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["payment_request_id"] == str(payment_request.id)
        assert data["current_status"] == "pending"
        assert data["total_attempts"] == 0
        assert len(data["entries"]) >= 1
        # First entry should be "created"
        assert data["entries"][0]["action"] == "created"
        assert data["entries"][0]["new_status"] == "pending"

    def test_get_attempts_with_audit_logs(
        self,
        client: TestClient,
        db_session: Session,
        payment_request: PaymentRequest,
    ) -> None:
        """Test attempt history includes audit log entries."""
        # Add audit log entries simulating status changes
        log = AuditLog(
            id=generate_uuid(),
            organization_id=DEFAULT_ORG_ID,
            resource_type="payment_request",
            resource_id=payment_request.id,
            action="status_changed",
            changes={"old_status": "pending", "new_status": "processing"},
            actor_type="system",
        )
        db_session.add(log)

        log2 = AuditLog(
            id=generate_uuid(),
            organization_id=DEFAULT_ORG_ID,
            resource_type="payment_request",
            resource_id=payment_request.id,
            action="status_changed",
            changes={"old_status": "processing", "new_status": "failed", "attempt_number": 1},
            actor_type="system",
        )
        db_session.add(log2)
        db_session.commit()

        response = client.get(
            f"/v1/payment_requests/{payment_request.id}/attempts",
        )
        assert response.status_code == 200
        data = response.json()
        # creation + 2 audit entries
        assert len(data["entries"]) == 3
        assert data["entries"][1]["action"] == "status_changed"
        assert data["entries"][1]["old_status"] == "pending"
        assert data["entries"][1]["new_status"] == "processing"
        assert data["entries"][2]["attempt_number"] == 1
        assert data["entries"][2]["new_status"] == "failed"

    def test_get_attempts_not_found(self, client: TestClient) -> None:
        """Test getting attempts for non-existent payment request."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/payment_requests/{fake_id}/attempts")
        assert response.status_code == 404
        assert response.json()["detail"] == "Payment request not found"

    def test_get_attempts_no_audit_logs(
        self,
        client: TestClient,
        payment_request: PaymentRequest,
    ) -> None:
        """Test attempt history with no audit logs shows just the creation entry."""
        response = client.get(
            f"/v1/payment_requests/{payment_request.id}/attempts",
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["action"] == "created"
