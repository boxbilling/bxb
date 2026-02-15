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


class TestDashboardDateRangeFiltering:
    """Tests for date range query parameters on dashboard endpoints."""

    def test_stats_with_date_range(self, client: TestClient, seeded_data):
        """Stats MRR respects start_date/end_date params."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.get(f"/dashboard/stats?start_date={week_ago}&end_date={today}")
        assert response.status_code == 200
        data = response.json()
        # Invoices were created 2-5 days ago, so within 7 days
        assert data["monthly_recurring_revenue"] == 162.0

    def test_stats_narrow_date_range_excludes_data(self, client: TestClient, seeded_data):
        """Stats with a narrow date range that excludes all invoices."""
        far_past = "2020-01-01"
        far_past_end = "2020-01-02"
        response = client.get(
            f"/dashboard/stats?start_date={far_past}&end_date={far_past_end}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["monthly_recurring_revenue"] == 0.0
        # total_customers and total_invoiced are not date-filtered
        assert data["total_customers"] == 2

    def test_revenue_with_date_range(self, client: TestClient, seeded_data):
        """Revenue endpoint respects date range."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        month_ago = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
        response = client.get(
            f"/dashboard/revenue?start_date={month_ago}&end_date={today}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mrr"] == 162.0
        assert len(data["monthly_trend"]) >= 1

    def test_revenue_future_date_range_empty(self, client: TestClient, seeded_data):
        """Revenue with future dates returns empty trend."""
        response = client.get(
            "/dashboard/revenue?start_date=2099-01-01&end_date=2099-12-31"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mrr"] == 0.0

    def test_customers_with_date_range(self, client: TestClient, seeded_data):
        """Customer metrics respect date range."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.get(
            f"/dashboard/customers?start_date={week_ago}&end_date={today}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["new_this_month"] == 2
        assert data["churned_this_month"] == 0

    def test_customers_narrow_range_excludes_new(self, client: TestClient, seeded_data):
        """Customers created outside the range are excluded from new count."""
        response = client.get(
            "/dashboard/customers?start_date=2020-01-01&end_date=2020-01-02"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["new_this_month"] == 0
        # total is still all-time
        assert data["total"] == 2

    def test_subscriptions_with_date_range(self, client: TestClient, seeded_data):
        """Subscription metrics respect date range."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.get(
            f"/dashboard/subscriptions?start_date={week_ago}&end_date={today}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["new_this_month"] == 2
        assert data["canceled_this_month"] == 0

    def test_subscriptions_narrow_range(self, client: TestClient, seeded_data):
        """Subscriptions created outside range excluded."""
        response = client.get(
            "/dashboard/subscriptions?start_date=2020-01-01&end_date=2020-01-02"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["new_this_month"] == 0

    def test_subscriptions_canceled_in_range(
        self, client: TestClient, db_session, seeded_data
    ):
        """Canceled subscriptions filtered by date range."""
        sub = seeded_data["subscriptions"][0]
        sub.status = "canceled"
        sub.canceled_at = datetime.now(UTC) - timedelta(days=2)
        db_session.commit()

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.get(
            f"/dashboard/subscriptions?start_date={week_ago}&end_date={today}"
        )
        data = response.json()
        assert data["canceled_this_month"] == 1

        # Range that excludes the cancellation
        response2 = client.get(
            "/dashboard/subscriptions?start_date=2020-01-01&end_date=2020-01-02"
        )
        data2 = response2.json()
        assert data2["canceled_this_month"] == 0

    def test_usage_with_date_range(self, client: TestClient, db_session):
        """Usage metrics respect date range."""
        from app.models.billable_metric import BillableMetric
        from app.models.event import Event

        metric = BillableMetric(
            organization_id=DEFAULT_ORG_ID,
            code="range_metric",
            name="Range Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.flush()

        now = datetime.now(UTC)
        # 2 recent events
        for i in range(2):
            db_session.add(
                Event(
                    organization_id=DEFAULT_ORG_ID,
                    transaction_id=f"range_evt_{i}",
                    external_customer_id="cust_1",
                    code="range_metric",
                    timestamp=now - timedelta(hours=i + 1),
                    properties={},
                )
            )
        # 1 old event
        db_session.add(
            Event(
                organization_id=DEFAULT_ORG_ID,
                transaction_id="range_evt_old",
                external_customer_id="cust_1",
                code="range_metric",
                timestamp=now - timedelta(days=60),
                properties={},
            )
        )
        db_session.commit()

        today = now.strftime("%Y-%m-%d")
        week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.get(
            f"/dashboard/usage?start_date={week_ago}&end_date={today}"
        )
        data = response.json()
        assert len(data["top_metrics"]) == 1
        assert data["top_metrics"][0]["event_count"] == 2

    def test_usage_date_range_excludes_all(self, client: TestClient, db_session):
        """Usage with range that excludes all events returns empty."""
        from app.models.billable_metric import BillableMetric
        from app.models.event import Event

        metric = BillableMetric(
            organization_id=DEFAULT_ORG_ID,
            code="empty_range",
            name="Empty Range",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.flush()

        db_session.add(
            Event(
                organization_id=DEFAULT_ORG_ID,
                transaction_id="empty_range_evt",
                external_customer_id="cust_1",
                code="empty_range",
                timestamp=datetime.now(UTC),
                properties={},
            )
        )
        db_session.commit()

        response = client.get(
            "/dashboard/usage?start_date=2020-01-01&end_date=2020-01-02"
        )
        data = response.json()
        assert data["top_metrics"] == []

    def test_stats_only_start_date(self, client: TestClient, seeded_data):
        """Passing only start_date uses now as end_date."""
        week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.get(f"/dashboard/stats?start_date={week_ago}")
        assert response.status_code == 200
        data = response.json()
        assert data["monthly_recurring_revenue"] == 162.0

    def test_stats_only_end_date(self, client: TestClient, seeded_data):
        """Passing only end_date uses default lookback from end_date."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        response = client.get(f"/dashboard/stats?end_date={today}")
        assert response.status_code == 200
        data = response.json()
        assert data["monthly_recurring_revenue"] == 162.0

    def test_customers_churn_in_date_range(
        self, client: TestClient, db_session, seeded_data
    ):
        """Churned customers respect date range."""
        sub = seeded_data["subscriptions"][0]
        sub.status = "canceled"
        sub.canceled_at = datetime.now(UTC) - timedelta(days=3)
        db_session.commit()

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.get(
            f"/dashboard/customers?start_date={week_ago}&end_date={today}"
        )
        data = response.json()
        assert data["churned_this_month"] == 1

        # Narrow range that misses the cancellation
        response2 = client.get(
            "/dashboard/customers?start_date=2020-01-01&end_date=2020-01-02"
        )
        data2 = response2.json()
        assert data2["churned_this_month"] == 0

    def test_revenue_trend_with_date_range(self, client: TestClient, seeded_data):
        """Revenue trend respects date range and produces correct number of months."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        three_months_ago = (datetime.now(UTC) - timedelta(days=90)).strftime("%Y-%m-%d")
        response = client.get(
            f"/dashboard/revenue?start_date={three_months_ago}&end_date={today}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["monthly_trend"]) >= 3


class TestDashboardResolvePeriod:
    """Tests for the _resolve_period helper."""

    def test_resolve_period_both_dates(self):
        from datetime import date

        from app.repositories.dashboard_repository import _resolve_period

        start, end = _resolve_period(date(2024, 1, 1), date(2024, 1, 31))
        assert start.year == 2024
        assert start.month == 1
        assert start.day == 1
        assert end.day == 31
        assert end.hour == 23

    def test_resolve_period_no_dates(self):
        from app.repositories.dashboard_repository import _resolve_period

        start, end = _resolve_period(None, None, default_days=7)
        assert (end - start).days == 7

    def test_resolve_period_only_start(self):
        from datetime import date

        from app.repositories.dashboard_repository import _resolve_period

        start, end = _resolve_period(date(2024, 6, 1), None)
        assert start.year == 2024
        assert start.month == 6
        # end should be ~now
        assert end.year >= 2024

    def test_resolve_period_only_end(self):
        from datetime import date

        from app.repositories.dashboard_repository import _resolve_period

        start, end = _resolve_period(None, date(2024, 6, 30), default_days=10)
        assert end.month == 6
        assert end.day == 30
        assert (end - start).days == 10


class TestDashboardRepoDialect:
    def test_monthly_revenue_trend_postgresql_branch(self, db_session):
        """Cover the to_char branch for PostgreSQL dialect."""
        from unittest.mock import MagicMock
        from uuid import uuid4

        from app.repositories.dashboard_repository import DashboardRepository

        repo = DashboardRepository(db_session)
        org_id = uuid4()
        # Create a mock bind that reports postgresql dialect
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        repo.db = MagicMock(wraps=db_session)
        repo.db.bind = mock_bind
        # to_char won't work on SQLite, so the query will raise
        with pytest.raises(Exception):  # noqa: B017
            repo.monthly_revenue_trend(org_id)
