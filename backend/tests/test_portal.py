"""Tests for portal-scoped customer self-service API endpoints."""

import time
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.wallet import Wallet
from tests.conftest import DEFAULT_ORG_ID


def _make_portal_token(
    customer_id: uuid.UUID,
    organization_id: uuid.UUID = DEFAULT_ORG_ID,
    expired: bool = False,
) -> str:
    """Generate a portal JWT token for testing."""
    payload = {
        "customer_id": str(customer_id),
        "organization_id": str(organization_id),
        "type": "portal",
        "exp": time.time() + (-3600 if expired else 3600),
    }
    return jwt.encode(payload, settings.PORTAL_JWT_SECRET, algorithm="HS256")


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
def customer(db_session):
    c = Customer(
        external_id=f"portal_ep_{uuid.uuid4()}",
        name="Portal Endpoint Customer",
        email="portal-ep@example.com",
        organization_id=DEFAULT_ORG_ID,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def other_customer(db_session):
    c = Customer(
        external_id=f"other_cust_{uuid.uuid4()}",
        name="Other Customer",
        email="other@example.com",
        organization_id=DEFAULT_ORG_ID,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def invoice(db_session, customer):
    inv = Invoice(
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:8]}",
        customer_id=customer.id,
        organization_id=DEFAULT_ORG_ID,
        status=InvoiceStatus.FINALIZED.value,
        billing_period_start=datetime(2025, 1, 1),
        billing_period_end=datetime(2025, 1, 31),
        subtotal=100,
        total=100,
        line_items=[],
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


@pytest.fixture
def draft_invoice(db_session, customer):
    inv = Invoice(
        invoice_number=f"INV-DRAFT-{uuid.uuid4().hex[:8]}",
        customer_id=customer.id,
        organization_id=DEFAULT_ORG_ID,
        status=InvoiceStatus.DRAFT.value,
        billing_period_start=datetime(2025, 2, 1),
        billing_period_end=datetime(2025, 2, 28),
        subtotal=50,
        total=50,
        line_items=[],
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


@pytest.fixture
def other_customer_invoice(db_session, other_customer):
    inv = Invoice(
        invoice_number=f"INV-OTHER-{uuid.uuid4().hex[:8]}",
        customer_id=other_customer.id,
        organization_id=DEFAULT_ORG_ID,
        status=InvoiceStatus.FINALIZED.value,
        billing_period_start=datetime(2025, 1, 1),
        billing_period_end=datetime(2025, 1, 31),
        subtotal=200,
        total=200,
        line_items=[],
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


@pytest.fixture
def payment(db_session, customer, invoice):
    p = Payment(
        invoice_id=invoice.id,
        customer_id=customer.id,
        organization_id=DEFAULT_ORG_ID,
        amount=100,
        currency="USD",
        status=PaymentStatus.SUCCEEDED.value,
        provider="stripe",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def wallet(db_session, customer):
    w = Wallet(
        customer_id=customer.id,
        organization_id=DEFAULT_ORG_ID,
        name="Main Wallet",
        code=f"main_{uuid.uuid4().hex[:8]}",
        balance_cents=5000,
        credits_balance=50,
        rate_amount=1,
        currency="USD",
        priority=1,
    )
    db_session.add(w)
    db_session.commit()
    db_session.refresh(w)
    return w


class TestPortalCustomerEndpoint:
    """Tests for GET /portal/customer."""

    def test_get_customer_profile(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/customer?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(customer.id)
        assert data["name"] == "Portal Endpoint Customer"
        assert data["email"] == "portal-ep@example.com"

    def test_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.get(f"/portal/customer?token={token}")
        assert response.status_code == 401
        assert response.json()["detail"] == "Portal token has expired"

    def test_invalid_token_returns_401(self, client: TestClient):
        response = client.get("/portal/customer?token=invalid-garbage")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid portal token"

    def test_missing_token_returns_422(self, client: TestClient):
        response = client.get("/portal/customer")
        assert response.status_code == 422

    def test_customer_not_found_returns_404(self, client: TestClient):
        token = _make_portal_token(uuid.uuid4())
        response = client.get(f"/portal/customer?token={token}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"


class TestPortalInvoicesEndpoint:
    """Tests for GET /portal/invoices."""

    def test_list_invoices(self, client: TestClient, customer, invoice):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/invoices?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(invoice.id)
        assert data[0]["customer_id"] == str(customer.id)

    def test_list_invoices_empty(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/invoices?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_invoices_does_not_include_other_customers(
        self, client: TestClient, customer, invoice, other_customer, other_customer_invoice
    ):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/invoices?token={token}")
        assert response.status_code == 200
        data = response.json()
        ids = [d["id"] for d in data]
        assert str(invoice.id) in ids
        assert str(other_customer_invoice.id) not in ids

    def test_list_invoices_pagination(self, client: TestClient, customer, invoice):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/invoices?token={token}&skip=0&limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.get(f"/portal/invoices?token={token}")
        assert response.status_code == 401


class TestPortalInvoiceDetailEndpoint:
    """Tests for GET /portal/invoices/{id}."""

    def test_get_invoice_detail(self, client: TestClient, customer, invoice):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/invoices/{invoice.id}?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(invoice.id)
        assert data["invoice_number"] == invoice.invoice_number

    def test_invoice_not_found(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/invoices/{uuid.uuid4()}?token={token}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Invoice not found"

    def test_other_customers_invoice_returns_404(
        self, client: TestClient, customer, other_customer, other_customer_invoice
    ):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/invoices/{other_customer_invoice.id}?token={token}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Invoice not found"


class TestPortalInvoicePdfEndpoint:
    """Tests for GET /portal/invoices/{id}/download_pdf."""

    def test_download_pdf(self, client: TestClient, customer, invoice):
        token = _make_portal_token(customer.id)
        with patch(
            "app.routers.portal.PdfService.generate_invoice_pdf",
            return_value=b"%PDF-test",
        ):
            response = client.get(f"/portal/invoices/{invoice.id}/download_pdf?token={token}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "Content-Disposition" in response.headers

    def test_invoice_not_found(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/invoices/{uuid.uuid4()}/download_pdf?token={token}")
        assert response.status_code == 404

    def test_draft_invoice_returns_400(self, client: TestClient, customer, draft_invoice):
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/invoices/{draft_invoice.id}/download_pdf?token={token}"
        )
        assert response.status_code == 400
        assert "finalized or paid" in response.json()["detail"]

    def test_other_customers_invoice_returns_404(
        self, client: TestClient, customer, other_customer, other_customer_invoice
    ):
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/invoices/{other_customer_invoice.id}/download_pdf?token={token}"
        )
        assert response.status_code == 404


class TestPortalPaymentsEndpoint:
    """Tests for GET /portal/payments."""

    def test_list_payments(self, client: TestClient, customer, payment):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/payments?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(payment.id)
        assert data[0]["customer_id"] == str(customer.id)

    def test_list_payments_empty(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/payments?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    def test_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.get(f"/portal/payments?token={token}")
        assert response.status_code == 401


class TestPortalWalletEndpoint:
    """Tests for GET /portal/wallet."""

    def test_get_wallet(self, client: TestClient, customer, wallet):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/wallet?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(wallet.id)
        assert data[0]["name"] == "Main Wallet"

    def test_wallet_empty(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/wallet?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    def test_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.get(f"/portal/wallet?token={token}")
        assert response.status_code == 401


class TestPortalCurrentUsageEndpoint:
    """Tests for GET /portal/current_usage."""

    @pytest.fixture
    def plan(self, db_session):
        p = Plan(
            code=f"plan_{uuid.uuid4().hex[:8]}",
            name="Test Plan",
            interval="monthly",
            amount_cents=1000,
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        return p

    @pytest.fixture
    def subscription(self, db_session, customer, plan):

        s = Subscription(
            external_id=f"sub_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            plan_id=plan.id,
            status="active",
            organization_id=DEFAULT_ORG_ID,
            started_at=datetime(2025, 1, 1, tzinfo=UTC),
            subscription_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
        return s

    def test_current_usage_success(self, client: TestClient, customer, subscription):
        token = _make_portal_token(customer.id)
        mock_response = {
            "from_datetime": "2025-01-01T00:00:00",
            "to_datetime": "2025-01-31T00:00:00",
            "amount_cents": "0",
            "currency": "USD",
            "charges": [],
        }
        with patch(
            "app.routers.portal.UsageQueryService.get_current_usage",
            return_value=mock_response,
        ):
            response = client.get(
                f"/portal/current_usage?token={token}&subscription_id={subscription.id}"
            )
        assert response.status_code == 200

    def test_subscription_not_found(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/current_usage?token={token}&subscription_id={uuid.uuid4()}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_subscription_belongs_to_other_customer(
        self, client: TestClient, customer, other_customer, db_session
    ):
        """Subscription belonging to another customer should return 404."""
        plan = Plan(
            code=f"plan2_{uuid.uuid4().hex[:8]}",
            name="Plan 2",
            interval="monthly",
            amount_cents=500,
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)


        other_sub = Subscription(
            external_id=f"sub2_{uuid.uuid4().hex[:8]}",
            customer_id=other_customer.id,
            plan_id=plan.id,
            status="active",
            organization_id=DEFAULT_ORG_ID,
            started_at=datetime(2025, 1, 1, tzinfo=UTC),
            subscription_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        db_session.add(other_sub)
        db_session.commit()
        db_session.refresh(other_sub)

        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/current_usage?token={token}&subscription_id={other_sub.id}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.get(
            f"/portal/current_usage?token={token}&subscription_id={uuid.uuid4()}"
        )
        assert response.status_code == 401

    def test_missing_subscription_id_returns_422(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/current_usage?token={token}")
        assert response.status_code == 422


class TestPortalBrandingEndpoint:
    """Tests for GET /portal/branding."""

    def test_get_branding_defaults(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/branding?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Default Test Organization"
        assert data["logo_url"] is None
        assert data["accent_color"] is None
        assert data["welcome_message"] is None

    def test_get_branding_with_custom_values(self, client: TestClient, customer, db_session):
        org = db_session.query(Organization).filter(Organization.id == DEFAULT_ORG_ID).first()
        org.logo_url = "https://example.com/logo.png"
        org.portal_accent_color = "#ff6600"
        org.portal_welcome_message = "Welcome to Acme Billing!"
        db_session.commit()

        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/branding?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Default Test Organization"
        assert data["logo_url"] == "https://example.com/logo.png"
        assert data["accent_color"] == "#ff6600"
        assert data["welcome_message"] == "Welcome to Acme Billing!"

    def test_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.get(f"/portal/branding?token={token}")
        assert response.status_code == 401

    def test_org_not_found_returns_404(self, client: TestClient):
        other_org_id = uuid.UUID("00000000-0000-0000-0000-000000000099")
        token = _make_portal_token(uuid.uuid4(), organization_id=other_org_id)
        response = client.get(f"/portal/branding?token={token}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Organization not found"


class TestPortalProfileUpdateEndpoint:
    """Tests for PATCH /portal/profile."""

    def test_update_name(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.patch(
            f"/portal/profile?token={token}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["email"] == "portal-ep@example.com"
        assert data["timezone"] == "UTC"

    def test_update_email(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.patch(
            f"/portal/profile?token={token}",
            json={"email": "new-email@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new-email@example.com"
        assert data["name"] == "Portal Endpoint Customer"

    def test_update_timezone(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.patch(
            f"/portal/profile?token={token}",
            json={"timezone": "America/New_York"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["timezone"] == "America/New_York"

    def test_update_all_fields(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.patch(
            f"/portal/profile?token={token}",
            json={
                "name": "Full Update",
                "email": "full@example.com",
                "timezone": "Europe/London",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Full Update"
        assert data["email"] == "full@example.com"
        assert data["timezone"] == "Europe/London"

    def test_update_empty_body(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.patch(
            f"/portal/profile?token={token}",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Portal Endpoint Customer"

    def test_update_email_to_null(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.patch(
            f"/portal/profile?token={token}",
            json={"email": None},
        )
        assert response.status_code == 200
        assert response.json()["email"] is None

    def test_invalid_email_returns_422(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.patch(
            f"/portal/profile?token={token}",
            json={"email": "not-an-email"},
        )
        assert response.status_code == 422

    def test_empty_name_returns_422(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.patch(
            f"/portal/profile?token={token}",
            json={"name": ""},
        )
        assert response.status_code == 422

    def test_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.patch(
            f"/portal/profile?token={token}",
            json={"name": "Should Fail"},
        )
        assert response.status_code == 401

    def test_customer_not_found_returns_404(self, client: TestClient):
        token = _make_portal_token(uuid.uuid4())
        response = client.patch(
            f"/portal/profile?token={token}",
            json={"name": "Ghost"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"


class TestPortalCrossCutting:
    """Cross-cutting tests for portal auth and scoping."""

    def test_all_endpoints_reject_expired_token(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        endpoints = [
            "/portal/customer",
            "/portal/branding",
            "/portal/invoices",
            f"/portal/invoices/{uuid.uuid4()}",
            f"/portal/invoices/{uuid.uuid4()}/download_pdf",
            "/portal/payments",
            "/portal/wallet",
        ]
        for endpoint in endpoints:
            response = client.get(f"{endpoint}?token={token}")
            assert response.status_code == 401, f"Expected 401 for {endpoint}"

    def test_all_endpoints_reject_invalid_token(self, client: TestClient):
        token = "invalid-jwt"
        endpoints = [
            "/portal/customer",
            "/portal/branding",
            "/portal/invoices",
            f"/portal/invoices/{uuid.uuid4()}",
            f"/portal/invoices/{uuid.uuid4()}/download_pdf",
            "/portal/payments",
            "/portal/wallet",
        ]
        for endpoint in endpoints:
            response = client.get(f"{endpoint}?token={token}")
            assert response.status_code == 401, f"Expected 401 for {endpoint}"
