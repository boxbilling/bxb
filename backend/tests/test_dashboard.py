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
        assert data["total_wallet_credits"] == 0.0
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
        assert data["total_wallet_credits"] == 0.0
        assert data["currency"] == "USD"

    def test_stats_wallet_credits(self, client: TestClient, db_session, seeded_data):
        """Wallet credits across active wallets appear in stats."""
        from app.models.wallet import Wallet

        w1 = Wallet(
            organization_id=DEFAULT_ORG_ID,
            customer_id=seeded_data["customers"][0].id,
            name="Main Wallet",
            code="main_w",
            status="active",
            credits_balance=Decimal("50.00"),
            currency="USD",
        )
        w2 = Wallet(
            organization_id=DEFAULT_ORG_ID,
            customer_id=seeded_data["customers"][1].id,
            name="Second Wallet",
            code="second_w",
            status="active",
            credits_balance=Decimal("30.00"),
            currency="USD",
        )
        w3 = Wallet(
            organization_id=DEFAULT_ORG_ID,
            customer_id=seeded_data["customers"][0].id,
            name="Terminated",
            code="term_w",
            status="terminated",
            credits_balance=Decimal("100.00"),
            currency="USD",
        )
        db_session.add_all([w1, w2, w3])
        db_session.commit()

        response = client.get("/dashboard/stats")
        data = response.json()
        # Only active wallets: 50 + 30 = 80
        assert data["total_wallet_credits"] == 80.0

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

    def test_stats_excludes_draft_invoices_from_mrr(
        self, client: TestClient, db_session, seeded_data
    ):
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


class TestDashboardRevenue:
    def test_revenue_empty_db(self, client: TestClient):
        response = client.get("/dashboard/revenue")
        assert response.status_code == 200
        data = response.json()
        assert data["mrr"] == 0.0
        assert data["total_revenue_this_month"] == 0.0
        assert data["outstanding_invoices"] == 0.0
        assert data["overdue_amount"] == 0.0
        assert data["currency"] == "USD"
        assert isinstance(data["monthly_trend"], list)

    def test_revenue_with_data(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/revenue")
        assert response.status_code == 200
        data = response.json()
        # MRR = 108 + 54 = 162 (both invoices recent and finalized/paid)
        assert data["mrr"] == 162.0
        assert data["total_revenue_this_month"] == 162.0
        # inv2 is finalized (not paid) = 54 outstanding
        assert data["outstanding_invoices"] == 54.0
        assert data["currency"] == "USD"

    def test_revenue_overdue(self, client: TestClient, db_session, seeded_data):
        """Overdue amount only includes finalized invoices past due_date."""
        seeded_data["invoices"][1].due_date = datetime.now(UTC) - timedelta(days=1)
        db_session.commit()

        response = client.get("/dashboard/revenue")
        data = response.json()
        assert data["overdue_amount"] == 54.0

    def test_revenue_no_overdue_when_no_due_date(self, client: TestClient, seeded_data):
        """Invoices without due_date are not counted as overdue."""
        response = client.get("/dashboard/revenue")
        data = response.json()
        assert data["overdue_amount"] == 0.0

    def test_revenue_monthly_trend_has_entries(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/revenue")
        data = response.json()
        assert len(data["monthly_trend"]) > 0
        for entry in data["monthly_trend"]:
            assert "month" in entry
            assert "revenue" in entry


class TestDashboardCustomers:
    def test_customers_empty_db(self, client: TestClient):
        response = client.get("/dashboard/customers")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["new_this_month"] == 0
        assert data["churned_this_month"] == 0

    def test_customers_with_data(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/customers")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["new_this_month"] == 2
        assert data["churned_this_month"] == 0

    def test_customers_churn(self, client: TestClient, db_session, seeded_data):
        """A customer with a canceled subscription counts as churned."""
        sub = seeded_data["subscriptions"][0]
        sub.status = "canceled"
        sub.canceled_at = datetime.now(UTC)
        db_session.commit()

        response = client.get("/dashboard/customers")
        data = response.json()
        assert data["churned_this_month"] == 1


class TestDashboardSubscriptions:
    def test_subscriptions_empty_db(self, client: TestClient):
        response = client.get("/dashboard/subscriptions")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] == 0
        assert data["new_this_month"] == 0
        assert data["canceled_this_month"] == 0
        assert data["by_plan"] == []

    def test_subscriptions_with_data(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/subscriptions")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] == 1
        assert data["new_this_month"] == 2
        assert data["canceled_this_month"] == 0

    def test_subscriptions_by_plan(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/subscriptions")
        data = response.json()
        assert len(data["by_plan"]) == 1
        assert data["by_plan"][0]["plan_name"] == "Dashboard Plan"
        assert data["by_plan"][0]["count"] == 1

    def test_subscriptions_canceled(self, client: TestClient, db_session, seeded_data):
        sub = seeded_data["subscriptions"][0]
        sub.status = "canceled"
        sub.canceled_at = datetime.now(UTC)
        db_session.commit()

        response = client.get("/dashboard/subscriptions")
        data = response.json()
        assert data["canceled_this_month"] == 1
        assert data["by_plan"] == []


class TestDashboardUsage:
    def test_usage_empty_db(self, client: TestClient):
        response = client.get("/dashboard/usage")
        assert response.status_code == 200
        data = response.json()
        assert data["top_metrics"] == []

    def test_usage_with_events(self, client: TestClient, db_session):
        """Events matching billable metrics appear in top usage."""
        from app.models.billable_metric import BillableMetric
        from app.models.event import Event

        metric = BillableMetric(
            organization_id=DEFAULT_ORG_ID,
            code="api_calls",
            name="API Calls",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.flush()

        now = datetime.now(UTC)
        for i in range(3):
            db_session.add(
                Event(
                    organization_id=DEFAULT_ORG_ID,
                    transaction_id=f"usage_evt_{i}",
                    external_customer_id="cust_1",
                    code="api_calls",
                    timestamp=now - timedelta(hours=i),
                    properties={},
                )
            )
        db_session.commit()

        response = client.get("/dashboard/usage")
        data = response.json()
        assert len(data["top_metrics"]) == 1
        assert data["top_metrics"][0]["metric_name"] == "API Calls"
        assert data["top_metrics"][0]["metric_code"] == "api_calls"
        assert data["top_metrics"][0]["event_count"] == 3

    def test_usage_excludes_old_events(self, client: TestClient, db_session):
        """Events older than 30 days should not be counted."""
        from app.models.billable_metric import BillableMetric
        from app.models.event import Event

        metric = BillableMetric(
            organization_id=DEFAULT_ORG_ID,
            code="old_metric",
            name="Old Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.flush()

        db_session.add(
            Event(
                organization_id=DEFAULT_ORG_ID,
                transaction_id="old_evt_1",
                external_customer_id="cust_1",
                code="old_metric",
                timestamp=datetime.now(UTC) - timedelta(days=60),
                properties={},
            )
        )
        db_session.commit()

        response = client.get("/dashboard/usage")
        data = response.json()
        assert data["top_metrics"] == []

    def test_usage_top_5_limit(self, client: TestClient, db_session):
        """Only top 5 metrics by volume are returned."""
        from app.models.billable_metric import BillableMetric
        from app.models.event import Event

        now = datetime.now(UTC)
        for i in range(7):
            metric = BillableMetric(
                organization_id=DEFAULT_ORG_ID,
                code=f"metric_{i}",
                name=f"Metric {i}",
                aggregation_type="count",
            )
            db_session.add(metric)
            db_session.flush()
            for j in range(i + 1):
                db_session.add(
                    Event(
                        organization_id=DEFAULT_ORG_ID,
                        transaction_id=f"limit_evt_{i}_{j}",
                        external_customer_id="cust_1",
                        code=f"metric_{i}",
                        timestamp=now - timedelta(hours=j),
                        properties={},
                    )
                )
        db_session.commit()

        response = client.get("/dashboard/usage")
        data = response.json()
        assert len(data["top_metrics"]) == 5
        counts = [m["event_count"] for m in data["top_metrics"]]
        assert counts == sorted(counts, reverse=True)


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
        assert types == {
            "customer_created",
            "subscription_created",
            "invoice_finalized",
            "payment_received",
        }

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
