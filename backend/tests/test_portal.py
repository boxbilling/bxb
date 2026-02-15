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
from app.models.add_on import AddOn
from app.models.applied_add_on import AppliedAddOn
from app.models.coupon import Coupon
from app.models.customer import Customer
from app.models.entitlement import Entitlement
from app.models.feature import Feature
from app.models.invoice import Invoice, InvoiceStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentStatus
from app.models.payment_method import PaymentMethod
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


class TestPortalPaymentMethodsEndpoint:
    """Tests for portal payment method management endpoints."""

    @pytest.fixture
    def payment_method(self, db_session, customer):
        pm = PaymentMethod(
            customer_id=customer.id,
            organization_id=DEFAULT_ORG_ID,
            provider="stripe",
            provider_payment_method_id=f"pm_{uuid.uuid4().hex[:12]}",
            type="card",
            is_default=True,
            details={"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2026},
        )
        db_session.add(pm)
        db_session.commit()
        db_session.refresh(pm)
        return pm

    @pytest.fixture
    def second_payment_method(self, db_session, customer):
        pm = PaymentMethod(
            customer_id=customer.id,
            organization_id=DEFAULT_ORG_ID,
            provider="stripe",
            provider_payment_method_id=f"pm_{uuid.uuid4().hex[:12]}",
            type="card",
            is_default=False,
            details={"brand": "mastercard", "last4": "5555", "exp_month": 6, "exp_year": 2027},
        )
        db_session.add(pm)
        db_session.commit()
        db_session.refresh(pm)
        return pm

    @pytest.fixture
    def other_customer_pm(self, db_session, other_customer):
        pm = PaymentMethod(
            customer_id=other_customer.id,
            organization_id=DEFAULT_ORG_ID,
            provider="stripe",
            provider_payment_method_id=f"pm_{uuid.uuid4().hex[:12]}",
            type="card",
            is_default=True,
            details={"brand": "amex", "last4": "0001"},
        )
        db_session.add(pm)
        db_session.commit()
        db_session.refresh(pm)
        return pm

    # --- GET /portal/payment_methods ---

    def test_list_payment_methods(self, client: TestClient, customer, payment_method):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/payment_methods?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(payment_method.id)
        assert data[0]["is_default"] is True
        assert data[0]["details"]["brand"] == "visa"

    def test_list_payment_methods_empty(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/payment_methods?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_excludes_other_customers(
        self, client: TestClient, customer, payment_method, other_customer, other_customer_pm
    ):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/payment_methods?token={token}")
        assert response.status_code == 200
        ids = [d["id"] for d in response.json()]
        assert str(payment_method.id) in ids
        assert str(other_customer_pm.id) not in ids

    def test_list_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.get(f"/portal/payment_methods?token={token}")
        assert response.status_code == 401

    # --- POST /portal/payment_methods ---

    def test_add_payment_method(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/payment_methods?token={token}",
            json={
                "customer_id": str(customer.id),
                "provider": "stripe",
                "provider_payment_method_id": "pm_new_123",
                "type": "card",
                "is_default": False,
                "details": {"brand": "visa", "last4": "1234"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "stripe"
        assert data["type"] == "card"
        assert data["is_default"] is False
        assert data["details"]["last4"] == "1234"

    def test_add_payment_method_as_default(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/payment_methods?token={token}",
            json={
                "customer_id": str(customer.id),
                "provider": "adyen",
                "provider_payment_method_id": "pm_adyen_001",
                "type": "bank_account",
                "is_default": True,
                "details": {},
            },
        )
        assert response.status_code == 201
        assert response.json()["is_default"] is True

    def test_add_for_other_customer_returns_403(
        self, client: TestClient, customer, other_customer
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/payment_methods?token={token}",
            json={
                "customer_id": str(other_customer.id),
                "provider": "stripe",
                "provider_payment_method_id": "pm_bad",
                "type": "card",
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Cannot add payment method for another customer"

    def test_add_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.post(
            f"/portal/payment_methods?token={token}",
            json={
                "customer_id": str(customer.id),
                "provider": "stripe",
                "provider_payment_method_id": "pm_fail",
                "type": "card",
            },
        )
        assert response.status_code == 401

    # --- DELETE /portal/payment_methods/{id} ---

    def test_delete_payment_method(
        self, client: TestClient, customer, payment_method, second_payment_method
    ):
        token = _make_portal_token(customer.id)
        response = client.delete(
            f"/portal/payment_methods/{second_payment_method.id}?token={token}"
        )
        assert response.status_code == 204

    def test_delete_default_returns_400(self, client: TestClient, customer, payment_method):
        token = _make_portal_token(customer.id)
        response = client.delete(
            f"/portal/payment_methods/{payment_method.id}?token={token}"
        )
        assert response.status_code == 400
        assert "default" in response.json()["detail"].lower()

    def test_delete_not_found(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.delete(
            f"/portal/payment_methods/{uuid.uuid4()}?token={token}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Payment method not found"

    def test_delete_other_customers_pm_returns_404(
        self, client: TestClient, customer, other_customer, other_customer_pm
    ):
        token = _make_portal_token(customer.id)
        response = client.delete(
            f"/portal/payment_methods/{other_customer_pm.id}?token={token}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Payment method not found"

    def test_delete_expired_token_returns_401(self, client: TestClient, customer, payment_method):
        token = _make_portal_token(customer.id, expired=True)
        response = client.delete(
            f"/portal/payment_methods/{payment_method.id}?token={token}"
        )
        assert response.status_code == 401

    # --- POST /portal/payment_methods/{id}/set_default ---

    def test_set_default(
        self, client: TestClient, customer, payment_method, second_payment_method
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/payment_methods/{second_payment_method.id}/set_default?token={token}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(second_payment_method.id)
        assert data["is_default"] is True

        # Verify old default was unset
        list_resp = client.get(f"/portal/payment_methods?token={token}")
        methods = list_resp.json()
        defaults = [m for m in methods if m["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["id"] == str(second_payment_method.id)

    def test_set_default_not_found(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/payment_methods/{uuid.uuid4()}/set_default?token={token}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Payment method not found"

    def test_set_default_other_customers_pm_returns_404(
        self, client: TestClient, customer, other_customer, other_customer_pm
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/payment_methods/{other_customer_pm.id}/set_default?token={token}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Payment method not found"

    def test_set_default_expired_token_returns_401(
        self, client: TestClient, customer, payment_method
    ):
        token = _make_portal_token(customer.id, expired=True)
        response = client.post(
            f"/portal/payment_methods/{payment_method.id}/set_default?token={token}"
        )
        assert response.status_code == 401


class TestPortalSubscriptionsEndpoint:
    """Tests for portal subscription management endpoints."""

    @pytest.fixture
    def plan(self, db_session):
        p = Plan(
            code=f"plan_{uuid.uuid4().hex[:8]}",
            name="Basic Plan",
            interval="monthly",
            amount_cents=2000,
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        return p

    @pytest.fixture
    def premium_plan(self, db_session):
        p = Plan(
            code=f"premium_{uuid.uuid4().hex[:8]}",
            name="Premium Plan",
            description="Premium features",
            interval="monthly",
            amount_cents=5000,
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        return p

    @pytest.fixture
    def budget_plan(self, db_session):
        p = Plan(
            code=f"budget_{uuid.uuid4().hex[:8]}",
            name="Budget Plan",
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

    # ---- GET /portal/subscriptions ----

    def test_list_subscriptions(self, client: TestClient, customer, subscription, plan):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/subscriptions?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(subscription.id)
        assert data[0]["status"] == "active"
        assert data[0]["plan"]["name"] == "Basic Plan"
        assert data[0]["plan"]["amount_cents"] == 2000

    def test_list_subscriptions_empty(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/subscriptions?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_subscriptions_excludes_other_customer(
        self, client: TestClient, customer, other_customer, db_session, plan
    ):
        other_sub = Subscription(
            external_id=f"other_sub_{uuid.uuid4().hex[:8]}",
            customer_id=other_customer.id,
            plan_id=plan.id,
            status="active",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(other_sub)
        db_session.commit()

        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/subscriptions?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.get(f"/portal/subscriptions?token={token}")
        assert response.status_code == 401

    # ---- GET /portal/subscriptions/{id} ----

    def test_get_subscription_detail(self, client: TestClient, customer, subscription, plan):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/subscriptions/{subscription.id}?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(subscription.id)
        assert data["plan"]["name"] == "Basic Plan"
        assert data["pending_downgrade_plan"] is None

    def test_get_subscription_not_found(self, client: TestClient, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/subscriptions/{uuid.uuid4()}?token={token}")
        assert response.status_code == 404

    def test_get_other_customers_subscription_returns_404(
        self, client: TestClient, customer, other_customer, db_session, plan
    ):
        other_sub = Subscription(
            external_id=f"other_sub_{uuid.uuid4().hex[:8]}",
            customer_id=other_customer.id,
            plan_id=plan.id,
            status="active",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(other_sub)
        db_session.commit()
        db_session.refresh(other_sub)

        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/subscriptions/{other_sub.id}?token={token}")
        assert response.status_code == 404

    # ---- GET /portal/plans ----

    def test_list_plans(self, client: TestClient, customer, plan, premium_plan):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/plans?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        names = [p["name"] for p in data]
        assert "Basic Plan" in names
        assert "Premium Plan" in names

    def test_list_plans_expired_token_returns_401(self, client: TestClient, customer):
        token = _make_portal_token(customer.id, expired=True)
        response = client.get(f"/portal/plans?token={token}")
        assert response.status_code == 401

    # ---- POST /portal/subscriptions/{id}/change_plan_preview ----

    def test_change_plan_preview(
        self, client: TestClient, customer, subscription, plan, premium_plan
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{subscription.id}/change_plan_preview?token={token}",
            json={"new_plan_id": str(premium_plan.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["current_plan"]["name"] == "Basic Plan"
        assert data["new_plan"]["name"] == "Premium Plan"
        assert "proration" in data
        assert data["proration"]["total_days"] == 30

    def test_change_plan_preview_same_plan_returns_400(
        self, client: TestClient, customer, subscription, plan
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{subscription.id}/change_plan_preview?token={token}",
            json={"new_plan_id": str(plan.id)},
        )
        assert response.status_code == 400
        assert "different" in response.json()["detail"]

    def test_change_plan_preview_plan_not_found(
        self, client: TestClient, customer, subscription
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{subscription.id}/change_plan_preview?token={token}",
            json={"new_plan_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_change_plan_preview_subscription_not_found(
        self, client: TestClient, customer, premium_plan
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{uuid.uuid4()}/change_plan_preview?token={token}",
            json={"new_plan_id": str(premium_plan.id)},
        )
        assert response.status_code == 404

    def test_change_plan_preview_other_customers_sub(
        self, client: TestClient, customer, other_customer, db_session, plan, premium_plan
    ):
        other_sub = Subscription(
            external_id=f"other_{uuid.uuid4().hex[:8]}",
            customer_id=other_customer.id,
            plan_id=plan.id,
            status="active",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(other_sub)
        db_session.commit()
        db_session.refresh(other_sub)

        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{other_sub.id}/change_plan_preview?token={token}",
            json={"new_plan_id": str(premium_plan.id)},
        )
        assert response.status_code == 404

    def test_change_plan_preview_expired_token(
        self, client: TestClient, customer, subscription, premium_plan
    ):
        token = _make_portal_token(customer.id, expired=True)
        response = client.post(
            f"/portal/subscriptions/{subscription.id}/change_plan_preview?token={token}",
            json={"new_plan_id": str(premium_plan.id)},
        )
        assert response.status_code == 401

    # ---- POST /portal/subscriptions/{id}/change_plan ----

    def test_change_plan_upgrade(
        self, client: TestClient, customer, subscription, plan, premium_plan
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{subscription.id}/change_plan?token={token}",
            json={"new_plan_id": str(premium_plan.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == str(premium_plan.id)

    def test_change_plan_downgrade(
        self, client: TestClient, customer, subscription, plan, budget_plan
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{subscription.id}/change_plan?token={token}",
            json={"new_plan_id": str(budget_plan.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == str(budget_plan.id)

    def test_change_plan_same_plan_returns_400(
        self, client: TestClient, customer, subscription, plan
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{subscription.id}/change_plan?token={token}",
            json={"new_plan_id": str(plan.id)},
        )
        assert response.status_code == 400
        assert "different" in response.json()["detail"]

    def test_change_plan_inactive_subscription_returns_400(
        self, client: TestClient, customer, db_session, plan, premium_plan
    ):
        s = Subscription(
            external_id=f"canceled_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            plan_id=plan.id,
            status="canceled",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)

        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{s.id}/change_plan?token={token}",
            json={"new_plan_id": str(premium_plan.id)},
        )
        assert response.status_code == 400
        assert "active" in response.json()["detail"]

    def test_change_plan_not_found_plan(
        self, client: TestClient, customer, subscription
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{subscription.id}/change_plan?token={token}",
            json={"new_plan_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_change_plan_subscription_not_found(
        self, client: TestClient, customer, premium_plan
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{uuid.uuid4()}/change_plan?token={token}",
            json={"new_plan_id": str(premium_plan.id)},
        )
        assert response.status_code == 404

    def test_change_plan_other_customers_sub(
        self, client: TestClient, customer, other_customer, db_session, plan, premium_plan
    ):
        other_sub = Subscription(
            external_id=f"other_{uuid.uuid4().hex[:8]}",
            customer_id=other_customer.id,
            plan_id=plan.id,
            status="active",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(other_sub)
        db_session.commit()
        db_session.refresh(other_sub)

        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/subscriptions/{other_sub.id}/change_plan?token={token}",
            json={"new_plan_id": str(premium_plan.id)},
        )
        assert response.status_code == 404

    def test_change_plan_expired_token(
        self, client: TestClient, customer, subscription, premium_plan
    ):
        token = _make_portal_token(customer.id, expired=True)
        response = client.post(
            f"/portal/subscriptions/{subscription.id}/change_plan?token={token}",
            json={"new_plan_id": str(premium_plan.id)},
        )
        assert response.status_code == 401

    # ---- Pending downgrade display ----

    def test_subscription_with_pending_downgrade(
        self, client: TestClient, customer, db_session, plan, budget_plan
    ):
        s = Subscription(
            external_id=f"dg_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            plan_id=plan.id,
            status="active",
            organization_id=DEFAULT_ORG_ID,
            started_at=datetime(2025, 1, 1, tzinfo=UTC),
            downgraded_at=datetime(2025, 6, 1, tzinfo=UTC),
            previous_plan_id=budget_plan.id,
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)

        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/subscriptions/{s.id}?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert data["pending_downgrade_plan"] is not None
        assert data["pending_downgrade_plan"]["name"] == "Budget Plan"


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
            "/portal/payment_methods",
            "/portal/subscriptions",
            "/portal/plans",
            "/portal/add_ons",
            "/portal/add_ons/purchased",
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
            "/portal/payment_methods",
            "/portal/subscriptions",
            "/portal/plans",
            "/portal/add_ons",
            "/portal/add_ons/purchased",
        ]
        for endpoint in endpoints:
            response = client.get(f"{endpoint}?token={token}")
            assert response.status_code == 401, f"Expected 401 for {endpoint}"


class TestPortalAddOns:
    """Tests for portal add-on endpoints."""

    @pytest.fixture
    def add_on(self, db_session):
        a = AddOn(
            code=f"addon_{uuid.uuid4().hex[:8]}",
            name="Premium Support",
            description="24/7 premium support access",
            amount_cents=4999,
            amount_currency="USD",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(a)
        db_session.commit()
        db_session.refresh(a)
        return a

    @pytest.fixture
    def add_on_2(self, db_session):
        a = AddOn(
            code=f"addon2_{uuid.uuid4().hex[:8]}",
            name="Extra Storage",
            description="Additional 100GB storage",
            amount_cents=1999,
            amount_currency="USD",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(a)
        db_session.commit()
        db_session.refresh(a)
        return a

    @pytest.fixture
    def other_org_add_on(self, db_session):
        other_org_id = uuid.UUID("00000000-0000-0000-0000-000000000099")
        org = Organization(id=other_org_id, name="Other Org Portal Addon")
        db_session.merge(org)
        db_session.commit()
        a = AddOn(
            code=f"other_addon_{uuid.uuid4().hex[:8]}",
            name="Other Org Add-on",
            amount_cents=999,
            amount_currency="EUR",
            organization_id=other_org_id,
        )
        db_session.add(a)
        db_session.commit()
        db_session.refresh(a)
        return a

    @pytest.fixture
    def applied_add_on(self, db_session, customer, add_on):
        applied = AppliedAddOn(
            add_on_id=add_on.id,
            customer_id=customer.id,
            amount_cents=4999,
            amount_currency="USD",
        )
        db_session.add(applied)
        db_session.commit()
        db_session.refresh(applied)
        return applied

    def test_list_available_add_ons(self, client, customer, add_on, add_on_2):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/add_ons?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        codes = {a["code"] for a in data}
        assert add_on.code in codes
        assert add_on_2.code in codes
        # Verify response shape
        item = next(a for a in data if a["code"] == add_on.code)
        assert item["name"] == "Premium Support"
        assert item["description"] == "24/7 premium support access"
        assert float(item["amount_cents"]) == 4999.0
        assert item["amount_currency"] == "USD"

    def test_list_available_add_ons_empty(self, client, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/add_ons?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_available_add_ons_excludes_other_org(
        self, client, customer, add_on, other_org_add_on
    ):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/add_ons?token={token}")
        assert response.status_code == 200
        data = response.json()
        codes = {a["code"] for a in data}
        assert add_on.code in codes
        assert other_org_add_on.code not in codes

    def test_list_purchased_add_ons(self, client, customer, add_on, applied_add_on):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/add_ons/purchased?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["add_on_name"] == "Premium Support"
        assert data[0]["add_on_code"] == add_on.code
        assert float(data[0]["amount_cents"]) == 4999.0
        assert data[0]["amount_currency"] == "USD"

    def test_list_purchased_add_ons_empty(self, client, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/add_ons/purchased?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_purchased_excludes_other_customer(
        self, client, customer, other_customer, add_on, db_session
    ):
        # Apply add-on to other customer only
        applied = AppliedAddOn(
            add_on_id=add_on.id,
            customer_id=other_customer.id,
            amount_cents=4999,
            amount_currency="USD",
        )
        db_session.add(applied)
        db_session.commit()
        # Our customer should see nothing
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/add_ons/purchased?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    def test_purchase_add_on_success(self, client, customer, add_on):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/add_ons/{add_on.id}/purchase?token={token}"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["add_on_name"] == "Premium Support"
        assert float(data["amount_cents"]) == 4999.0
        assert data["amount_currency"] == "USD"
        assert "applied_add_on_id" in data
        assert "invoice_id" in data

    def test_purchase_add_on_creates_invoice(self, client, customer, add_on, db_session):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/add_ons/{add_on.id}/purchase?token={token}"
        )
        assert response.status_code == 201
        data = response.json()
        # Verify invoice was created
        invoice = db_session.query(Invoice).filter(
            Invoice.id == uuid.UUID(data["invoice_id"])
        ).first()
        assert invoice is not None
        assert str(invoice.customer_id) == str(customer.id)

    def test_purchase_add_on_not_found(self, client, customer):
        token = _make_portal_token(customer.id)
        fake_id = uuid.uuid4()
        response = client.post(
            f"/portal/add_ons/{fake_id}/purchase?token={token}"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Add-on not found"

    def test_purchase_add_on_other_org_not_found(
        self, client, customer, other_org_add_on
    ):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/add_ons/{other_org_add_on.id}/purchase?token={token}"
        )
        assert response.status_code == 404

    def test_purchase_add_on_appears_in_purchased(self, client, customer, add_on):
        token = _make_portal_token(customer.id)
        # Purchase
        response = client.post(
            f"/portal/add_ons/{add_on.id}/purchase?token={token}"
        )
        assert response.status_code == 201
        # Verify it shows up in purchased list
        response = client.get(f"/portal/add_ons/purchased?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["add_on_name"] == "Premium Support"

    def test_purchase_add_on_service_error(self, client, customer, add_on):
        token = _make_portal_token(customer.id)
        with patch(
            "app.routers.portal.AddOnService.apply_add_on",
            side_effect=ValueError("Service error"),
        ):
            response = client.post(
                f"/portal/add_ons/{add_on.id}/purchase?token={token}"
            )
        assert response.status_code == 400
        assert response.json()["detail"] == "Service error"

    def test_purchase_add_on_invalid_uuid(self, client, customer):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/add_ons/not-a-uuid/purchase?token={token}"
        )
        assert response.status_code == 422


class TestPortalCoupons:
    """Tests for portal coupon endpoints."""

    @pytest.fixture
    def coupon_fixed(self, db_session):
        c = Coupon(
            code=f"SAVE10_{uuid.uuid4().hex[:8]}",
            name="Save $10",
            description="$10 off your next billing period",
            coupon_type="fixed_amount",
            amount_cents=1000,
            amount_currency="USD",
            frequency="once",
            reusable=True,
            expiration="no_expiration",
            status="active",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    @pytest.fixture
    def coupon_percentage(self, db_session):
        c = Coupon(
            code=f"PCT20_{uuid.uuid4().hex[:8]}",
            name="20% Off",
            description="20% off for 3 billing periods",
            coupon_type="percentage",
            percentage_rate=20,
            frequency="recurring",
            frequency_duration=3,
            reusable=True,
            expiration="no_expiration",
            status="active",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    @pytest.fixture
    def terminated_coupon(self, db_session):
        c = Coupon(
            code=f"DEAD_{uuid.uuid4().hex[:8]}",
            name="Terminated Coupon",
            coupon_type="fixed_amount",
            amount_cents=500,
            amount_currency="USD",
            frequency="once",
            reusable=True,
            expiration="no_expiration",
            status="terminated",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    @pytest.fixture
    def non_reusable_coupon(self, db_session):
        c = Coupon(
            code=f"ONCE_{uuid.uuid4().hex[:8]}",
            name="One-time Only",
            coupon_type="fixed_amount",
            amount_cents=500,
            amount_currency="USD",
            frequency="once",
            reusable=False,
            expiration="no_expiration",
            status="active",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    @pytest.fixture
    def expired_coupon(self, db_session):
        c = Coupon(
            code=f"EXP_{uuid.uuid4().hex[:8]}",
            name="Expired Coupon",
            coupon_type="fixed_amount",
            amount_cents=500,
            amount_currency="USD",
            frequency="once",
            reusable=True,
            expiration="time_limit",
            expiration_at=datetime(2020, 1, 1, tzinfo=UTC),
            status="active",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    @pytest.fixture
    def applied_coupon(self, db_session, customer, coupon_fixed):
        from app.models.applied_coupon import AppliedCoupon

        ac = AppliedCoupon(
            coupon_id=coupon_fixed.id,
            customer_id=customer.id,
            amount_cents=1000,
            amount_currency="USD",
            frequency="once",
            status="active",
        )
        db_session.add(ac)
        db_session.commit()
        db_session.refresh(ac)
        return ac

    # ── List active coupons ──

    def test_list_coupons_empty(self, client, customer):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/coupons?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_coupons_with_applied(self, client, customer, coupon_fixed, applied_coupon):
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/coupons?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        item = data[0]
        assert item["coupon_code"] == coupon_fixed.code
        assert item["coupon_name"] == "Save $10"
        assert item["coupon_type"] == "fixed_amount"
        assert float(item["amount_cents"]) == 1000.0
        assert item["amount_currency"] == "USD"
        assert item["frequency"] == "once"
        assert item["status"] == "active"

    def test_list_coupons_excludes_other_customer(
        self, client, customer, other_customer, coupon_fixed, db_session
    ):
        from app.models.applied_coupon import AppliedCoupon

        # Apply coupon to other customer only
        ac = AppliedCoupon(
            coupon_id=coupon_fixed.id,
            customer_id=other_customer.id,
            amount_cents=1000,
            amount_currency="USD",
            frequency="once",
            status="active",
        )
        db_session.add(ac)
        db_session.commit()
        # Our customer should see nothing
        token = _make_portal_token(customer.id)
        response = client.get(f"/portal/coupons?token={token}")
        assert response.status_code == 200
        assert response.json() == []

    # ── Redeem coupon ──

    def test_redeem_coupon_fixed(self, client, customer, coupon_fixed):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/coupons/redeem?token={token}",
            json={"coupon_code": coupon_fixed.code},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["coupon_code"] == coupon_fixed.code
        assert data["coupon_name"] == "Save $10"
        assert data["coupon_type"] == "fixed_amount"
        assert float(data["amount_cents"]) == 1000.0
        assert data["amount_currency"] == "USD"
        assert data["frequency"] == "once"
        assert data["status"] == "active"

    def test_redeem_coupon_percentage(self, client, customer, coupon_percentage):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/coupons/redeem?token={token}",
            json={"coupon_code": coupon_percentage.code},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["coupon_code"] == coupon_percentage.code
        assert data["coupon_name"] == "20% Off"
        assert data["coupon_type"] == "percentage"
        assert float(data["percentage_rate"]) == 20.0
        assert data["frequency"] == "recurring"
        assert data["frequency_duration"] == 3
        assert data["frequency_duration_remaining"] == 3

    def test_redeem_coupon_appears_in_list(self, client, customer, coupon_fixed):
        token = _make_portal_token(customer.id)
        # Redeem first
        response = client.post(
            f"/portal/coupons/redeem?token={token}",
            json={"coupon_code": coupon_fixed.code},
        )
        assert response.status_code == 201
        # Verify it shows up in the list
        response = client.get(f"/portal/coupons?token={token}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["coupon_name"] == "Save $10"

    def test_redeem_coupon_not_found(self, client, customer):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/coupons/redeem?token={token}",
            json={"coupon_code": "NONEXISTENT_CODE"},
        )
        assert response.status_code == 404

    def test_redeem_terminated_coupon(self, client, customer, terminated_coupon):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/coupons/redeem?token={token}",
            json={"coupon_code": terminated_coupon.code},
        )
        assert response.status_code == 400
        assert "not active" in response.json()["detail"].lower()

    def test_redeem_expired_coupon(self, client, customer, expired_coupon):
        token = _make_portal_token(customer.id)
        response = client.post(
            f"/portal/coupons/redeem?token={token}",
            json={"coupon_code": expired_coupon.code},
        )
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()

    def test_redeem_non_reusable_twice(self, client, customer, non_reusable_coupon):
        token = _make_portal_token(customer.id)
        # First application should succeed
        response = client.post(
            f"/portal/coupons/redeem?token={token}",
            json={"coupon_code": non_reusable_coupon.code},
        )
        assert response.status_code == 201
        # Second application should fail
        response = client.post(
            f"/portal/coupons/redeem?token={token}",
            json={"coupon_code": non_reusable_coupon.code},
        )
        assert response.status_code == 400
        assert "already applied" in response.json()["detail"].lower()

    def test_redeem_coupon_invalid_token(self, client, customer, coupon_fixed):
        response = client.post(
            "/portal/coupons/redeem?token=invalid_token",
            json={"coupon_code": coupon_fixed.code},
        )
        assert response.status_code == 401


class TestPortalDashboardSummaryEndpoint:
    """Tests for GET /portal/dashboard_summary."""

    @pytest.fixture
    def plan(self, db_session):
        p = Plan(
            code=f"plan_{uuid.uuid4().hex[:8]}",
            name="Pro Plan",
            interval="monthly",
            amount_cents=2000,
            currency="USD",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        return p

    @pytest.fixture
    def active_subscription(self, db_session, customer, plan):
        s = Subscription(
            external_id=f"sub_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            plan_id=plan.id,
            status="active",
            organization_id=DEFAULT_ORG_ID,
            started_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
        return s

    @pytest.fixture
    def pending_subscription(self, db_session, customer, plan):
        s = Subscription(
            external_id=f"sub_pending_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            plan_id=plan.id,
            status="pending",
            organization_id=DEFAULT_ORG_ID,
            started_at=datetime(2030, 6, 1, tzinfo=UTC),
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
        return s

    @pytest.fixture
    def finalized_invoice(self, db_session, customer):
        inv = Invoice(
            invoice_number=f"INV-FIN-{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            organization_id=DEFAULT_ORG_ID,
            status=InvoiceStatus.FINALIZED.value,
            billing_period_start=datetime(2025, 1, 1),
            billing_period_end=datetime(2025, 1, 31),
            subtotal=500,
            total=500,
            line_items=[],
        )
        db_session.add(inv)
        db_session.commit()
        db_session.refresh(inv)
        return inv

    @pytest.fixture
    def feature_boolean(self, db_session):
        f = Feature(
            code="sso",
            name="Single Sign-On",
            feature_type="boolean",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)
        return f

    @pytest.fixture
    def feature_quantity(self, db_session):
        f = Feature(
            code="api_calls",
            name="API Calls",
            feature_type="quantity",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)
        return f

    @pytest.fixture
    def entitlement_boolean(self, db_session, plan, feature_boolean):
        e = Entitlement(
            plan_id=plan.id,
            feature_id=feature_boolean.id,
            value="true",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(e)
        db_session.commit()
        db_session.refresh(e)
        return e

    @pytest.fixture
    def entitlement_quantity(self, db_session, plan, feature_quantity):
        e = Entitlement(
            plan_id=plan.id,
            feature_id=feature_quantity.id,
            value="1000",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(e)
        db_session.commit()
        db_session.refresh(e)
        return e

    def test_empty_dashboard(self, client: TestClient, customer):
        """No subscriptions, invoices, or wallets — all sections empty."""
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["next_billing"] == []
        assert data["upcoming_charges"] == []
        assert data["usage_progress"] == []
        qa = data["quick_actions"]
        assert qa["outstanding_invoice_count"] == 0
        assert qa["outstanding_amount_cents"] == 0
        assert qa["has_wallet"] is False
        assert qa["has_active_subscription"] is False

    def test_next_billing_active_subscription(
        self, client: TestClient, customer, active_subscription, plan
    ):
        """Active subscription returns next billing info."""
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["next_billing"]) == 1
        nb = data["next_billing"][0]
        assert nb["subscription_id"] == str(active_subscription.id)
        assert nb["plan_name"] == "Pro Plan"
        assert nb["plan_interval"] == "monthly"
        assert nb["amount_cents"] == 2000
        assert nb["currency"] == "USD"
        assert nb["days_until_next_billing"] >= 0

    def test_next_billing_pending_future_subscription(
        self, client: TestClient, customer, pending_subscription, plan
    ):
        """Pending subscription with future start date."""
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["next_billing"]) == 1
        nb = data["next_billing"][0]
        assert nb["subscription_id"] == str(pending_subscription.id)
        # Future start date — days_until should be > 0
        assert nb["days_until_next_billing"] > 0

    def test_upcoming_charges_with_usage(
        self, client: TestClient, customer, active_subscription, plan
    ):
        """Upcoming charges include base amount + mocked usage."""
        token = _make_portal_token(customer.id)

        from decimal import Decimal

        from app.schemas.usage import (
            BillableMetricUsage,
            ChargeUsage,
            CurrentUsageResponse,
        )

        mock_usage = CurrentUsageResponse(
            from_datetime=datetime(2025, 1, 1, tzinfo=UTC),
            to_datetime=datetime(2025, 1, 31, tzinfo=UTC),
            amount_cents=Decimal("300"),
            currency="USD",
            charges=[
                ChargeUsage(
                    billable_metric=BillableMetricUsage(
                        code="api_calls",
                        name="API Calls",
                        aggregation_type="count",
                    ),
                    units=Decimal("150"),
                    amount_cents=Decimal("300"),
                    charge_model="standard",
                    filters={},
                ),
            ],
        )

        with patch(
            "app.routers.portal.UsageQueryService.get_current_usage",
            return_value=mock_usage,
        ):
            response = client.get(
                f"/portal/dashboard_summary?token={token}"
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data["upcoming_charges"]) == 1
        uc = data["upcoming_charges"][0]
        assert uc["base_amount_cents"] == 2000
        assert uc["usage_amount_cents"] == 300
        assert uc["total_estimated_cents"] == 2300

    def test_upcoming_charges_usage_failure_defaults_zero(
        self, client: TestClient, customer, active_subscription, plan
    ):
        """Usage query failure defaults usage_amount_cents to 0."""
        token = _make_portal_token(customer.id)
        with patch(
            "app.routers.portal.UsageQueryService.get_current_usage",
            side_effect=Exception("Usage service down"),
        ):
            response = client.get(
                f"/portal/dashboard_summary?token={token}"
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data["upcoming_charges"]) == 1
        uc = data["upcoming_charges"][0]
        assert uc["usage_amount_cents"] == 0
        assert uc["total_estimated_cents"] == 2000

    def test_usage_progress_boolean_feature(
        self,
        client: TestClient,
        customer,
        active_subscription,
        plan,
        feature_boolean,
        entitlement_boolean,
    ):
        """Boolean feature entitlement appears in usage_progress."""
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 200
        data = response.json()
        booleans = [
            p for p in data["usage_progress"]
            if p["feature_type"] == "boolean"
        ]
        assert len(booleans) == 1
        assert booleans[0]["feature_name"] == "Single Sign-On"
        assert booleans[0]["entitlement_value"] == "true"
        assert booleans[0]["current_usage"] is None
        assert booleans[0]["usage_percentage"] is None

    def test_usage_progress_quantity_feature(
        self,
        client: TestClient,
        customer,
        active_subscription,
        plan,
        feature_quantity,
        entitlement_quantity,
    ):
        """Quantity feature with matching usage shows progress %."""
        token = _make_portal_token(customer.id)

        from decimal import Decimal

        from app.schemas.usage import (
            BillableMetricUsage,
            ChargeUsage,
            CurrentUsageResponse,
        )

        mock_usage = CurrentUsageResponse(
            from_datetime=datetime(2025, 1, 1, tzinfo=UTC),
            to_datetime=datetime(2025, 1, 31, tzinfo=UTC),
            amount_cents=Decimal("0"),
            currency="USD",
            charges=[
                ChargeUsage(
                    billable_metric=BillableMetricUsage(
                        code="api_calls",
                        name="API Calls",
                        aggregation_type="count",
                    ),
                    units=Decimal("750"),
                    amount_cents=Decimal("0"),
                    charge_model="standard",
                    filters={},
                ),
            ],
        )

        with patch(
            "app.routers.portal.UsageQueryService.get_current_usage",
            return_value=mock_usage,
        ):
            response = client.get(
                f"/portal/dashboard_summary?token={token}"
            )
        assert response.status_code == 200
        data = response.json()
        quantities = [
            p for p in data["usage_progress"]
            if p["feature_type"] == "quantity"
        ]
        assert len(quantities) == 1
        assert quantities[0]["feature_name"] == "API Calls"
        assert quantities[0]["entitlement_value"] == "1000"
        assert float(quantities[0]["current_usage"]) == 750.0
        assert quantities[0]["usage_percentage"] == 75.0

    def test_quick_actions_with_outstanding_invoice(
        self, client: TestClient, customer, finalized_invoice
    ):
        """Quick actions show outstanding invoice count and amount."""
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 200
        qa = response.json()["quick_actions"]
        assert qa["outstanding_invoice_count"] == 1
        assert qa["outstanding_amount_cents"] == 500

    def test_quick_actions_with_wallet(
        self, client: TestClient, customer, wallet
    ):
        """Quick actions show wallet info."""
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 200
        qa = response.json()["quick_actions"]
        assert qa["has_wallet"] is True
        assert qa["wallet_balance_cents"] == 5000

    def test_quick_actions_has_active_subscription(
        self, client: TestClient, customer, active_subscription
    ):
        """Quick actions reflect active subscription presence."""
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 200
        qa = response.json()["quick_actions"]
        assert qa["has_active_subscription"] is True

    def test_invalid_token(self, client: TestClient):
        """Invalid token returns 401."""
        response = client.get(
            "/portal/dashboard_summary?token=invalid"
        )
        assert response.status_code == 401

    def test_customer_not_found(self, client: TestClient):
        """Non-existent customer returns 404."""
        token = _make_portal_token(uuid.uuid4())
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 404

    def test_terminated_subscription_excluded(
        self, client: TestClient, customer, plan, db_session
    ):
        """Terminated subscriptions don't appear in billing/charges."""
        s = Subscription(
            external_id=f"sub_term_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            plan_id=plan.id,
            status="terminated",
            organization_id=DEFAULT_ORG_ID,
            started_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        db_session.add(s)
        db_session.commit()
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["next_billing"] == []
        assert data["upcoming_charges"] == []
        assert data["quick_actions"]["has_active_subscription"] is False

    def test_usage_progress_quantity_usage_failure(
        self,
        client: TestClient,
        customer,
        active_subscription,
        plan,
        feature_quantity,
        entitlement_quantity,
    ):
        """Usage query failure for quantity feature defaults to None."""
        token = _make_portal_token(customer.id)
        with patch(
            "app.routers.portal.UsageQueryService.get_current_usage",
            side_effect=Exception("Service down"),
        ):
            response = client.get(
                f"/portal/dashboard_summary?token={token}"
            )
        assert response.status_code == 200
        quantities = [
            p for p in response.json()["usage_progress"]
            if p["feature_type"] == "quantity"
        ]
        assert len(quantities) == 1
        # Usage query failed, so current_usage and percentage are None
        assert quantities[0]["current_usage"] is None
        assert quantities[0]["usage_percentage"] is None

    def test_duplicate_feature_across_subscriptions_deduped(
        self,
        client: TestClient,
        customer,
        plan,
        feature_boolean,
        entitlement_boolean,
        db_session,
    ):
        """Same feature on two subscriptions appears only once."""
        # Create two active subs with the same plan
        s1 = Subscription(
            external_id=f"sub_dup1_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            plan_id=plan.id,
            status="active",
            organization_id=DEFAULT_ORG_ID,
            started_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        s2 = Subscription(
            external_id=f"sub_dup2_{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            plan_id=plan.id,
            status="active",
            organization_id=DEFAULT_ORG_ID,
            started_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        db_session.add_all([s1, s2])
        db_session.commit()

        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 200
        # Feature should appear only once despite two subs
        booleans = [
            p for p in response.json()["usage_progress"]
            if p["feature_code"] == "sso"
        ]
        assert len(booleans) == 1

    def test_quantity_entitlement_zero_limit(
        self,
        client: TestClient,
        customer,
        active_subscription,
        plan,
        feature_quantity,
        db_session,
    ):
        """Quantity entitlement with value=0 skips usage calc."""
        e = Entitlement(
            plan_id=plan.id,
            feature_id=feature_quantity.id,
            value="0",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(e)
        db_session.commit()
        token = _make_portal_token(customer.id)
        response = client.get(
            f"/portal/dashboard_summary?token={token}"
        )
        assert response.status_code == 200
        quantities = [
            p for p in response.json()["usage_progress"]
            if p["feature_type"] == "quantity"
        ]
        assert len(quantities) == 1
        # Zero limit means no usage calculation attempted
        assert quantities[0]["current_usage"] is None
        assert quantities[0]["usage_percentage"] is None
