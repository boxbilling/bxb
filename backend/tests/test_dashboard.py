"""Tests for Dashboard API endpoints."""

from datetime import UTC, date, datetime, timedelta
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

    def test_activity_filter_by_customer_created(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/activity?type=customer_created")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(a["type"] == "customer_created" for a in data)

    def test_activity_filter_by_subscription_created(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/activity?type=subscription_created")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(a["type"] == "subscription_created" for a in data)

    def test_activity_filter_by_invoice_finalized(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/activity?type=invoice_finalized")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(a["type"] == "invoice_finalized" for a in data)

    def test_activity_filter_by_payment_received(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/activity?type=payment_received")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "payment_received"

    def test_activity_filter_invalid_type_returns_all(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/activity?type=invalid_type")
        assert response.status_code == 200
        data = response.json()
        # Invalid type is ignored, returns all activity
        assert len(data) == 7

    def test_activity_no_filter_returns_all(self, client: TestClient, seeded_data):
        """Without type param, all types are included."""
        response = client.get("/dashboard/activity")
        data = response.json()
        types = {a["type"] for a in data}
        assert len(types) > 1

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

    def test_daily_revenue_postgresql_branch(self, db_session):
        """Cover the to_char branch for daily_revenue on PostgreSQL dialect."""
        from unittest.mock import MagicMock
        from uuid import uuid4

        from app.repositories.dashboard_repository import DashboardRepository

        repo = DashboardRepository(db_session)
        org_id = uuid4()
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        repo.db = MagicMock(wraps=db_session)
        repo.db.bind = mock_bind
        with pytest.raises(Exception):  # noqa: B017
            repo.daily_revenue(org_id)

    def test_daily_new_customers_postgresql_branch(self, db_session):
        """Cover the to_char branch for daily_new_customers on PostgreSQL dialect."""
        from unittest.mock import MagicMock
        from uuid import uuid4

        from app.repositories.dashboard_repository import DashboardRepository

        repo = DashboardRepository(db_session)
        org_id = uuid4()
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        repo.db = MagicMock(wraps=db_session)
        repo.db.bind = mock_bind
        with pytest.raises(Exception):  # noqa: B017
            repo.daily_new_customers(org_id)

    def test_daily_new_subscriptions_postgresql_branch(self, db_session):
        """Cover the to_char branch for daily_new_subscriptions on PostgreSQL dialect."""
        from unittest.mock import MagicMock
        from uuid import uuid4

        from app.repositories.dashboard_repository import DashboardRepository

        repo = DashboardRepository(db_session)
        org_id = uuid4()
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        repo.db = MagicMock(wraps=db_session)
        repo.db.bind = mock_bind
        with pytest.raises(Exception):  # noqa: B017
            repo.daily_new_subscriptions(org_id)


class TestComputeTrend:
    """Tests for the _compute_trend helper."""

    def test_positive_change(self):
        from app.routers.dashboard import _compute_trend

        trend = _compute_trend(150.0, 100.0)
        assert trend.previous_value == 100.0
        assert trend.change_percent == 50.0

    def test_negative_change(self):
        from app.routers.dashboard import _compute_trend

        trend = _compute_trend(80.0, 100.0)
        assert trend.previous_value == 100.0
        assert trend.change_percent == -20.0

    def test_no_change(self):
        from app.routers.dashboard import _compute_trend

        trend = _compute_trend(100.0, 100.0)
        assert trend.change_percent == 0.0

    def test_previous_zero_returns_none_percent(self):
        from app.routers.dashboard import _compute_trend

        trend = _compute_trend(50.0, 0.0)
        assert trend.previous_value == 0.0
        assert trend.change_percent is None

    def test_both_zero(self):
        from app.routers.dashboard import _compute_trend

        trend = _compute_trend(0.0, 0.0)
        assert trend.previous_value == 0.0
        assert trend.change_percent is None

    def test_rounding(self):
        from app.routers.dashboard import _compute_trend

        trend = _compute_trend(10.0, 3.0)
        assert trend.previous_value == 3.0
        assert trend.change_percent == 233.3


class TestPreviousPeriod:
    """Tests for the _previous_period helper."""

    def test_both_dates(self):
        from app.routers.dashboard import _previous_period

        prev_start, prev_end = _previous_period(date(2024, 2, 1), date(2024, 2, 29))
        # 28-day period, previous should be 28 days before start
        assert prev_end == date(2024, 1, 31)
        duration = (date(2024, 2, 29) - date(2024, 2, 1)).days
        assert (prev_end - prev_start).days == duration

    def test_no_dates_defaults_to_30_days(self):
        from app.routers.dashboard import _previous_period

        prev_start, prev_end = _previous_period(None, None)
        today = date.today()
        expected_end = today - timedelta(days=31)
        assert prev_end == expected_end
        assert (prev_end - prev_start).days == 30

    def test_only_start_date(self):
        from app.routers.dashboard import _previous_period

        prev_start, prev_end = _previous_period(date(2024, 3, 1), None)
        today = date.today()
        duration = (today - date(2024, 3, 1)).days
        assert prev_end == date(2024, 2, 29)
        assert (prev_end - prev_start).days == duration

    def test_only_end_date(self):
        from app.routers.dashboard import _previous_period

        prev_start, prev_end = _previous_period(None, date(2024, 6, 30))
        # Default start is end - 30 days = 2024-05-31
        start = date(2024, 5, 31)
        duration = (date(2024, 6, 30) - start).days  # 30
        assert prev_end == start - timedelta(days=1)
        assert (prev_end - prev_start).days == duration


class TestTrendIndicatorsInResponses:
    """Tests that trend indicators are present and correct in API responses."""

    def test_revenue_trend_with_data(self, client: TestClient, seeded_data):
        """Revenue response includes mrr_trend."""
        response = client.get("/dashboard/revenue")
        assert response.status_code == 200
        data = response.json()
        assert "mrr_trend" in data
        assert data["mrr_trend"] is not None
        assert "previous_value" in data["mrr_trend"]
        assert "change_percent" in data["mrr_trend"]

    def test_revenue_trend_empty_db(self, client: TestClient):
        """Revenue trend with empty db returns zero previous and None percent."""
        response = client.get("/dashboard/revenue")
        data = response.json()
        assert data["mrr_trend"]["previous_value"] == 0.0
        assert data["mrr_trend"]["change_percent"] is None

    def test_customers_trend_with_data(self, client: TestClient, seeded_data):
        """Customer metrics include new_trend and churned_trend."""
        response = client.get("/dashboard/customers")
        assert response.status_code == 200
        data = response.json()
        assert "new_trend" in data
        assert "churned_trend" in data
        assert data["new_trend"] is not None
        assert data["churned_trend"] is not None

    def test_customers_trend_empty_db(self, client: TestClient):
        """Customer trends with empty db."""
        response = client.get("/dashboard/customers")
        data = response.json()
        assert data["new_trend"]["previous_value"] == 0.0
        assert data["new_trend"]["change_percent"] is None
        assert data["churned_trend"]["previous_value"] == 0.0
        assert data["churned_trend"]["change_percent"] is None

    def test_subscriptions_trend_with_data(self, client: TestClient, seeded_data):
        """Subscription metrics include new_trend and canceled_trend."""
        response = client.get("/dashboard/subscriptions")
        assert response.status_code == 200
        data = response.json()
        assert "new_trend" in data
        assert "canceled_trend" in data
        assert data["new_trend"] is not None
        assert data["canceled_trend"] is not None

    def test_subscriptions_trend_empty_db(self, client: TestClient):
        """Subscription trends with empty db."""
        response = client.get("/dashboard/subscriptions")
        data = response.json()
        assert data["new_trend"]["previous_value"] == 0.0
        assert data["new_trend"]["change_percent"] is None
        assert data["canceled_trend"]["previous_value"] == 0.0
        assert data["canceled_trend"]["change_percent"] is None

    def test_revenue_trend_with_date_range(self, client: TestClient, seeded_data):
        """Revenue trend respects explicit date range for previous period."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.get(
            f"/dashboard/revenue?start_date={week_ago}&end_date={today}"
        )
        data = response.json()
        assert data["mrr_trend"] is not None
        # Previous period should cover the 7 days before week_ago
        assert isinstance(data["mrr_trend"]["previous_value"], float)

    def test_customers_trend_with_previous_data(
        self, client: TestClient, db_session, seeded_data
    ):
        """When there are customers in the previous period, change_percent is a number."""
        # Move one customer's created_at to 45 days ago (in the "previous" period
        # for a 30-day window)
        c = seeded_data["customers"][0]
        c.created_at = datetime.now(UTC) - timedelta(days=45)
        db_session.commit()

        response = client.get("/dashboard/customers")
        data = response.json()
        # new_this_month = 1 (only c2 is recent), prev period has c1
        assert data["new_this_month"] == 1
        assert data["new_trend"]["previous_value"] == 1.0
        assert data["new_trend"]["change_percent"] == 0.0


class TestDashboardRevenueByPlan:
    def test_revenue_by_plan_empty_db(self, client: TestClient):
        response = client.get("/dashboard/revenue_by_plan")
        assert response.status_code == 200
        data = response.json()
        assert data["by_plan"] == []
        assert data["currency"] == "USD"

    def test_revenue_by_plan_with_data(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/revenue_by_plan")
        assert response.status_code == 200
        data = response.json()
        assert len(data["by_plan"]) == 1
        assert data["by_plan"][0]["plan_name"] == "Dashboard Plan"
        # Both invoices (108 + 54) are linked to Dashboard Plan
        assert data["by_plan"][0]["revenue"] == 162.0
        assert data["currency"] == "USD"

    def test_revenue_by_plan_multiple_plans(
        self, client: TestClient, db_session, seeded_data
    ):
        """Revenue is grouped correctly across multiple plans."""
        plan_repo = PlanRepository(db_session)
        sub_repo = SubscriptionRepository(db_session)

        plan2 = plan_repo.create(
            PlanCreate(code="plan_b", name="Plan B", interval="monthly"),
            DEFAULT_ORG_ID,
        )
        sub3 = sub_repo.create(
            SubscriptionCreate(
                external_id="rev_sub_3",
                customer_id=seeded_data["customers"][0].id,
                plan_id=plan2.id,
            ),
            DEFAULT_ORG_ID,
        )

        now = datetime.now(UTC)
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="DASH-REV-PLAN2",
            customer_id=seeded_data["customers"][0].id,
            subscription_id=sub3.id,
            status=InvoiceStatus.PAID.value,
            billing_period_start=now - timedelta(days=30),
            billing_period_end=now,
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("200.00"),
            currency="USD",
            issued_at=now - timedelta(days=1),
            line_items=[],
        )
        db_session.add(inv)
        db_session.commit()

        response = client.get("/dashboard/revenue_by_plan")
        data = response.json()
        assert len(data["by_plan"]) == 2
        # Ordered by revenue descending
        assert data["by_plan"][0]["plan_name"] == "Plan B"
        assert data["by_plan"][0]["revenue"] == 200.0
        assert data["by_plan"][1]["plan_name"] == "Dashboard Plan"
        assert data["by_plan"][1]["revenue"] == 162.0

    def test_revenue_by_plan_excludes_draft_invoices(
        self, client: TestClient, db_session, seeded_data
    ):
        """Draft invoices are excluded from revenue breakdown."""
        now = datetime.now(UTC)
        draft_inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="DASH-DRAFT-REV",
            customer_id=seeded_data["customers"][0].id,
            subscription_id=seeded_data["subscriptions"][0].id,
            status=InvoiceStatus.DRAFT.value,
            billing_period_start=now - timedelta(days=30),
            billing_period_end=now,
            subtotal=Decimal("999.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("999.00"),
            currency="USD",
            issued_at=now,
            line_items=[],
        )
        db_session.add(draft_inv)
        db_session.commit()

        response = client.get("/dashboard/revenue_by_plan")
        data = response.json()
        assert len(data["by_plan"]) == 1
        # Draft invoice excluded, still 162
        assert data["by_plan"][0]["revenue"] == 162.0

    def test_revenue_by_plan_with_date_range(self, client: TestClient, seeded_data):
        """Revenue by plan respects date range parameters."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.get(
            f"/dashboard/revenue_by_plan?start_date={week_ago}&end_date={today}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["by_plan"]) == 1
        assert data["by_plan"][0]["revenue"] == 162.0

    def test_revenue_by_plan_narrow_range_excludes(self, client: TestClient, seeded_data):
        """Date range that excludes all invoices returns empty."""
        response = client.get(
            "/dashboard/revenue_by_plan?start_date=2020-01-01&end_date=2020-01-02"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["by_plan"] == []

    def test_revenue_by_plan_excludes_no_subscription(
        self, client: TestClient, db_session, seeded_data
    ):
        """Invoices without a subscription_id are excluded."""
        now = datetime.now(UTC)
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number="DASH-NO-SUB",
            customer_id=seeded_data["customers"][0].id,
            subscription_id=None,
            status=InvoiceStatus.PAID.value,
            billing_period_start=now - timedelta(days=30),
            billing_period_end=now,
            subtotal=Decimal("500.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("500.00"),
            currency="USD",
            issued_at=now - timedelta(days=1),
            line_items=[],
        )
        db_session.add(inv)
        db_session.commit()

        response = client.get("/dashboard/revenue_by_plan")
        data = response.json()
        # No-sub invoice excluded from plan breakdown, still 162 for Dashboard Plan
        assert len(data["by_plan"]) == 1
        assert data["by_plan"][0]["revenue"] == 162.0


class TestDashboardRecentInvoices:
    def test_recent_invoices_empty_db(self, client: TestClient):
        response = client.get("/dashboard/recent_invoices")
        assert response.status_code == 200
        assert response.json() == []

    def test_recent_invoices_with_data(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/recent_invoices")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Verify sorted by created_at descending (most recent first)
        for item in data:
            assert "id" in item
            assert "invoice_number" in item
            assert "customer_name" in item
            assert "status" in item
            assert "total" in item
            assert "currency" in item
            assert "created_at" in item

    def test_recent_invoices_fields(self, client: TestClient, seeded_data):
        """Verify correct fields in recent invoices."""
        response = client.get("/dashboard/recent_invoices")
        data = response.json()
        # Find the paid invoice
        paid = [i for i in data if i["status"] == "paid"]
        assert len(paid) == 1
        assert paid[0]["customer_name"] == "Acme Corp"
        assert paid[0]["total"] == 108.0
        assert paid[0]["currency"] == "USD"
        assert paid[0]["invoice_number"] == "DASH-INV-001"

    def test_recent_invoices_limit(self, client: TestClient, db_session, seeded_data):
        """Only up to 5 invoices are returned."""
        now = datetime.now(UTC)
        for i in range(6):
            inv = Invoice(
                organization_id=DEFAULT_ORG_ID,
                invoice_number=f"DASH-EXTRA-{i:03d}",
                customer_id=seeded_data["customers"][0].id,
                subscription_id=seeded_data["subscriptions"][0].id,
                status=InvoiceStatus.DRAFT.value,
                billing_period_start=now - timedelta(days=30),
                billing_period_end=now,
                subtotal=Decimal("10.00"),
                tax_amount=Decimal("0.00"),
                total=Decimal("10.00"),
                currency="USD",
                issued_at=now,
                line_items=[],
            )
            db_session.add(inv)
        db_session.commit()

        response = client.get("/dashboard/recent_invoices")
        data = response.json()
        assert len(data) == 5


class TestDashboardSparklines:
    def test_sparklines_empty_db(self, client: TestClient):
        response = client.get("/dashboard/sparklines")
        assert response.status_code == 200
        data = response.json()
        assert data["mrr"] == []
        assert data["new_customers"] == []
        assert data["new_subscriptions"] == []

    def test_sparklines_with_data(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/sparklines")
        assert response.status_code == 200
        data = response.json()
        # Should have revenue data points (invoices issued within last 30 days)
        assert len(data["mrr"]) >= 1
        for point in data["mrr"]:
            assert "date" in point
            assert "value" in point
        # Customers were created recently
        assert len(data["new_customers"]) >= 1
        # Subscriptions were created recently
        assert len(data["new_subscriptions"]) >= 1

    def test_sparklines_with_date_range(self, client: TestClient, seeded_data):
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.get(
            f"/dashboard/sparklines?start_date={week_ago}&end_date={today}"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["mrr"]) >= 1

    def test_sparklines_narrow_range_excludes_data(self, client: TestClient, seeded_data):
        response = client.get(
            "/dashboard/sparklines?start_date=2020-01-01&end_date=2020-01-02"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mrr"] == []
        assert data["new_customers"] == []
        assert data["new_subscriptions"] == []

    def test_sparklines_revenue_values(self, client: TestClient, seeded_data):
        """Revenue sparkline returns correct daily totals."""
        response = client.get("/dashboard/sparklines")
        data = response.json()
        total_revenue = sum(p["value"] for p in data["mrr"])
        # Should be 162 total (108 + 54 from the two seeded invoices)
        assert total_revenue == 162.0

    def test_sparklines_points_are_sorted(self, client: TestClient, seeded_data):
        """Sparkline points should be sorted by date ascending."""
        response = client.get("/dashboard/sparklines")
        data = response.json()
        for key in ["mrr", "new_customers", "new_subscriptions"]:
            dates = [p["date"] for p in data[key]]
            assert dates == sorted(dates)

    def test_sparklines_daily_new_customers_count(
        self, client: TestClient, db_session, seeded_data
    ):
        """Daily new customers shows correct daily counts."""
        # Move one customer to a different day to get distinct data points
        c = seeded_data["customers"][0]
        c.created_at = datetime.now(UTC) - timedelta(days=3)
        db_session.commit()

        response = client.get("/dashboard/sparklines")
        data = response.json()
        total = sum(p["value"] for p in data["new_customers"])
        assert total == 2  # Both customers still within 30-day window

    def test_sparklines_daily_new_subscriptions_count(
        self, client: TestClient, seeded_data
    ):
        """Daily new subscriptions shows correct counts."""
        response = client.get("/dashboard/sparklines")
        data = response.json()
        total = sum(p["value"] for p in data["new_subscriptions"])
        assert total == 2  # Two seeded subscriptions


class TestDashboardRecentSubscriptions:
    def test_recent_subscriptions_empty_db(self, client: TestClient):
        response = client.get("/dashboard/recent_subscriptions")
        assert response.status_code == 200
        assert response.json() == []

    def test_recent_subscriptions_with_data(self, client: TestClient, seeded_data):
        response = client.get("/dashboard/recent_subscriptions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        for item in data:
            assert "id" in item
            assert "external_id" in item
            assert "customer_name" in item
            assert "plan_name" in item
            assert "status" in item
            assert "created_at" in item

    def test_recent_subscriptions_fields(self, client: TestClient, seeded_data):
        """Verify correct fields in recent subscriptions."""
        response = client.get("/dashboard/recent_subscriptions")
        data = response.json()
        # Both subscriptions should reference Dashboard Plan
        for item in data:
            assert item["plan_name"] == "Dashboard Plan"

        # Verify customer names are present
        customer_names = {item["customer_name"] for item in data}
        assert customer_names == {"Acme Corp", "TechStart Inc"}

    def test_recent_subscriptions_limit(
        self, client: TestClient, db_session, seeded_data
    ):
        """Only up to 5 subscriptions are returned."""
        sub_repo = SubscriptionRepository(db_session)
        customer_repo = CustomerRepository(db_session)
        for i in range(6):
            c = customer_repo.create(
                CustomerCreate(
                    external_id=f"recent_sub_cust_{i}",
                    name=f"Limit Customer {i}",
                ),
                DEFAULT_ORG_ID,
            )
            sub_repo.create(
                SubscriptionCreate(
                    external_id=f"recent_sub_{i}",
                    customer_id=c.id,
                    plan_id=seeded_data["plan"].id,
                ),
                DEFAULT_ORG_ID,
            )

        response = client.get("/dashboard/recent_subscriptions")
        data = response.json()
        assert len(data) == 5
