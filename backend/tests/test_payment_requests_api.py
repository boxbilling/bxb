"""Tests for PaymentRequest API router endpoints."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models.customer import Customer
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
