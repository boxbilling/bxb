"""Tests for Dashboard API endpoints."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import SubscriptionStatus
from app.repositories.customer_repository import CustomerRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.customer import CustomerCreate
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
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
def seeded_data(db_session):
    """Seed database with customers, subscriptions, invoices, and payments."""
    customer_repo = CustomerRepository(db_session)
    plan_repo = PlanRepository(db_session)
    sub_repo = SubscriptionRepository(db_session)

    # Create customers
    c1 = customer_repo.create(
        CustomerCreate(external_id="dash_cust_1", name="Acme Corp"), DEFAULT_ORG_ID
    )
    c2 = customer_repo.create(
        CustomerCreate(external_id="dash_cust_2", name="TechStart Inc"), DEFAULT_ORG_ID
    )

    # Create plan
    plan = plan_repo.create(
        PlanCreate(code="dash_plan", name="Dashboard Plan", interval="monthly"),
        DEFAULT_ORG_ID,
    )

    # Create subscriptions - one active, one pending
    sub1 = sub_repo.create(
        SubscriptionCreate(external_id="dash_sub_1", customer_id=c1.id, plan_id=plan.id),
        DEFAULT_ORG_ID,
    )
    sub1.status = SubscriptionStatus.ACTIVE.value
    db_session.commit()

    sub2 = sub_repo.create(
        SubscriptionCreate(external_id="dash_sub_2", customer_id=c2.id, plan_id=plan.id),
        DEFAULT_ORG_ID,
    )

    # Create invoices
    now = datetime.now(UTC)
    inv1 = Invoice(
        organization_id=DEFAULT_ORG_ID,
        invoice_number="DASH-INV-001",
        customer_id=c1.id,
        subscription_id=sub1.id,
        status=InvoiceStatus.PAID.value,
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("8.00"),
        total=Decimal("108.00"),
        currency="USD",
        issued_at=now - timedelta(days=5),
        line_items=[],
    )
    inv2 = Invoice(
        organization_id=DEFAULT_ORG_ID,
        invoice_number="DASH-INV-002",
        customer_id=c2.id,
        subscription_id=sub2.id,
        status=InvoiceStatus.FINALIZED.value,
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        subtotal=Decimal("50.00"),
        tax_amount=Decimal("4.00"),
        total=Decimal("54.00"),
        currency="USD",
        issued_at=now - timedelta(days=2),
        line_items=[],
    )
    db_session.add_all([inv1, inv2])
    db_session.commit()

    # Create a payment
    payment = Payment(
        organization_id=DEFAULT_ORG_ID,
        invoice_id=inv1.id,
        customer_id=c1.id,
        amount=Decimal("108.00"),
        currency="USD",
        status=PaymentStatus.SUCCEEDED.value,
        provider="stripe",
    )
    db_session.add(payment)
    db_session.commit()

    return {
        "customers": [c1, c2],
        "plan": plan,
        "subscriptions": [sub1, sub2],
        "invoices": [inv1, inv2],
        "payments": [payment],
    }


class TestDashboardStats:
    def test_stats_empty_db(self, client: TestClient):
        response = client.get("/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_customers"] == 0
        assert data["active_subscriptions"] == 0
        assert data["monthly_recurring_revenue"] == 0.0
        assert data["total_invoiced"] == 0.0
        assert data["currency"] == "USD"

    def test_stats_with_data(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_customers"] == 2
        assert data["active_subscriptions"] == 1
        # Both invoices are recent (within 30 days) and finalized/paid
        assert data["monthly_recurring_revenue"] == 162.0  # 108 + 54
        assert data["total_invoiced"] == 162.0
        assert data["currency"] == "USD"

    def test_stats_mrr_excludes_old_invoices(self, client: TestClient, db_session, seeded_data):
        """MRR should only include invoices from the last 30 days."""
        old_invoice = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="DASH-INV-OLD",
            customer_id=seeded_data["customers"][0].id,
            subscription_id=seeded_data["subscriptions"][0].id,
            status=InvoiceStatus.PAID.value,
            billing_period_start=datetime.now(UTC) - timedelta(days=90),
            billing_period_end=datetime.now(UTC) - timedelta(days=60),
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("200.00"),
            currency="USD",
            issued_at=datetime.now(UTC) - timedelta(days=60),
            line_items=[],
        )
        db_session.add(old_invoice)
        db_session.commit()

        response = client.get("/dashboard/stats")
        data = response.json()
        # MRR should still be 162 (old invoice excluded)
        assert data["monthly_recurring_revenue"] == 162.0
        # total_invoiced includes all invoices
        assert data["total_invoiced"] == 362.0

    def test_stats_excludes_draft_invoices_from_mrr(self, client: TestClient, db_session, seeded_data):
        """MRR should only count finalized and paid invoices."""
        draft_invoice = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="DASH-INV-DRAFT",
            customer_id=seeded_data["customers"][0].id,
            subscription_id=seeded_data["subscriptions"][0].id,
            status=InvoiceStatus.DRAFT.value,
            billing_period_start=datetime.now(UTC) - timedelta(days=30),
            billing_period_end=datetime.now(UTC),
            subtotal=Decimal("300.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("300.00"),
            currency="USD",
            issued_at=datetime.now(UTC),
            line_items=[],
        )
        db_session.add(draft_invoice)
        db_session.commit()

        response = client.get("/dashboard/stats")
        data = response.json()
        # MRR should still be 162 (draft excluded)
        assert data["monthly_recurring_revenue"] == 162.0


class TestDashboardActivity:
    def test_activity_empty_db(self, client: TestClient):
        response = client.get("/dashboard/activity")
        assert response.status_code == 200
        assert response.json() == []

    def test_activity_with_data(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/activity")
        assert response.status_code == 200
        data = response.json()
        # 2 customers + 2 subscriptions + 2 invoices + 1 payment = 7 activities
        assert len(data) == 7

        # Verify all activity types are present
        types = {a["type"] for a in data}
        assert types == {"customer_created", "subscription_created", "invoice_finalized", "payment_received"}

        # Verify sorted by timestamp descending
        timestamps = [a["timestamp"] for a in data]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_activity_has_correct_fields(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/activity")
        data = response.json()
        for item in data:
            assert "id" in item
            assert "type" in item
            assert "description" in item
            assert "timestamp" in item

    def test_activity_limit_to_10(self, client: TestClient, db_session):
        """Activity should return at most 10 items even when many exist."""
        customer_repo = CustomerRepository(db_session)
        plan_repo = PlanRepository(db_session)
        sub_repo = SubscriptionRepository(db_session)

        plan = plan_repo.create(
            PlanCreate(code="limit_plan", name="Limit Plan", interval="monthly"),
            DEFAULT_ORG_ID,
        )

        # Create enough entities across types to exceed 10
        for i in range(6):
            c = customer_repo.create(
                CustomerCreate(external_id=f"many_cust_{i}", name=f"Customer {i}"),
                DEFAULT_ORG_ID,
            )
            sub_repo.create(
                SubscriptionCreate(
                    external_id=f"many_sub_{i}",
                    customer_id=c.id,
                    plan_id=plan.id,
                ),
                DEFAULT_ORG_ID,
            )

        response = client.get("/dashboard/activity")
        data = response.json()
        # 5 customers (capped per type) + 5 subscriptions (capped per type) = 10
        assert len(data) == 10
