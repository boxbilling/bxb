"""Tests for pagination across all list endpoints.

Verifies that skip/limit query parameters and X-Total-Count response header
work correctly for every paginated list endpoint in the API.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.billable_metric import AggregationType
from app.models.event import Event
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.repositories.add_on_repository import AddOnRepository
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.coupon_repository import CouponRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.tax_repository import TaxRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.add_on import AddOnCreate
from app.schemas.billable_metric import BillableMetricCreate
from app.schemas.coupon import CouponCreate
from app.schemas.customer import CustomerCreate
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
from app.schemas.tax import TaxCreate
from app.schemas.wallet import WalletCreate
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


# ---------------------------------------------------------------------------
# Helper: create N resources using the repository layer
# ---------------------------------------------------------------------------


def _create_customers(db_session, count: int):
    repo = CustomerRepository(db_session)
    return [
        repo.create(
            CustomerCreate(external_id=f"pag_cust_{i}", name=f"Pag Customer {i}"),
            DEFAULT_ORG_ID,
        )
        for i in range(count)
    ]


def _create_plans(db_session, count: int):
    repo = PlanRepository(db_session)
    return [
        repo.create(
            PlanCreate(code=f"pag_plan_{i}", name=f"Pag Plan {i}", interval="monthly"),
            DEFAULT_ORG_ID,
        )
        for i in range(count)
    ]


def _create_subscriptions(db_session, customers, plan, count: int):
    repo = SubscriptionRepository(db_session)
    return [
        repo.create(
            SubscriptionCreate(
                external_id=f"pag_sub_{i}",
                customer_id=customers[i % len(customers)].id,
                plan_id=plan.id,
            ),
            DEFAULT_ORG_ID,
        )
        for i in range(count)
    ]


def _create_invoices(db_session, customer, subscription, count: int):
    now = datetime.now(UTC)
    invoices = []
    for i in range(count):
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number=f"PAG-INV-{i:03d}",
            customer_id=customer.id,
            subscription_id=subscription.id,
            status=InvoiceStatus.FINALIZED.value,
            billing_period_start=now - timedelta(days=30),
            billing_period_end=now,
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            total=Decimal("100.00"),
            currency="USD",
            issued_at=now,
            line_items=[],
        )
        db_session.add(inv)
        invoices.append(inv)
    db_session.commit()
    return invoices


def _create_wallets(db_session, customer_id, count: int):
    repo = WalletRepository(db_session)
    return [
        repo.create(
            WalletCreate(customer_id=customer_id, name=f"Pag Wallet {i}", code=f"pag_w_{i}"),
            DEFAULT_ORG_ID,
        )
        for i in range(count)
    ]


def _create_coupons(db_session, count: int):
    repo = CouponRepository(db_session)
    return [
        repo.create(
            CouponCreate(
                code=f"pag_coupon_{i}",
                name=f"Pag Coupon {i}",
                coupon_type="fixed_amount",
                frequency="once",
                amount_cents=Decimal("500"),
                amount_currency="USD",
            ),
            DEFAULT_ORG_ID,
        )
        for i in range(count)
    ]


def _create_add_ons(db_session, count: int):
    repo = AddOnRepository(db_session)
    return [
        repo.create(
            AddOnCreate(
                code=f"pag_addon_{i}",
                name=f"Pag AddOn {i}",
                amount_cents=Decimal("1000"),
            ),
            DEFAULT_ORG_ID,
        )
        for i in range(count)
    ]


def _create_taxes(db_session, count: int):
    repo = TaxRepository(db_session)
    return [
        repo.create(
            TaxCreate(code=f"pag_tax_{i}", name=f"Pag Tax {i}", rate=Decimal("8.5")),
            DEFAULT_ORG_ID,
        )
        for i in range(count)
    ]


def _create_billable_metrics(db_session, count: int):
    repo = BillableMetricRepository(db_session)
    return [
        repo.create(
            BillableMetricCreate(
                code=f"pag_metric_{i}",
                name=f"Pag Metric {i}",
                aggregation_type=AggregationType.COUNT,
            ),
            DEFAULT_ORG_ID,
        )
        for i in range(count)
    ]


def _create_events(db_session, metric_code: str, count: int):
    now = datetime.now(UTC)
    events = []
    for i in range(count):
        evt = Event(
            organization_id=DEFAULT_ORG_ID,
            transaction_id=f"pag_evt_{i}",
            external_customer_id="pag_cust_0",
            code=metric_code,
            timestamp=now - timedelta(minutes=i),
            properties={},
        )
        db_session.add(evt)
        events.append(evt)
    db_session.commit()
    return events


def _create_payments(db_session, invoice, customer, count: int):
    payments = []
    for _i in range(count):
        p = Payment(
            organization_id=DEFAULT_ORG_ID,
            invoice_id=invoice.id,
            customer_id=customer.id,
            amount=Decimal("10.00"),
            currency="USD",
            status=PaymentStatus.SUCCEEDED.value,
            provider="stripe",
        )
        db_session.add(p)
        payments.append(p)
    db_session.commit()
    return payments


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

TOTAL_ITEMS = 5


class TestCustomersPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        _create_customers(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/customers/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        _create_customers(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/customers/?skip=2&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)

    def test_skip_beyond_total(self, client: TestClient, db_session):
        _create_customers(db_session, TOTAL_ITEMS)
        resp = client.get(f"/v1/customers/?skip={TOTAL_ITEMS + 10}")
        assert resp.status_code == 200
        assert len(resp.json()) == 0
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)

    def test_limit_validation(self, client: TestClient, db_session):
        resp = client.get("/v1/customers/?limit=0")
        assert resp.status_code == 422

        resp = client.get("/v1/customers/?limit=1001")
        assert resp.status_code == 422

    def test_skip_validation(self, client: TestClient, db_session):
        resp = client.get("/v1/customers/?skip=-1")
        assert resp.status_code == 422


class TestPlansPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        _create_plans(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/plans/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        _create_plans(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/plans/?skip=3&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)


class TestSubscriptionsPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        customers = _create_customers(db_session, TOTAL_ITEMS)
        plans = _create_plans(db_session, 1)
        _create_subscriptions(db_session, customers, plans[0], TOTAL_ITEMS)
        resp = client.get("/v1/subscriptions/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        customers = _create_customers(db_session, TOTAL_ITEMS)
        plans = _create_plans(db_session, 1)
        _create_subscriptions(db_session, customers, plans[0], TOTAL_ITEMS)
        resp = client.get("/v1/subscriptions/?skip=1&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestInvoicesPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        customers = _create_customers(db_session, 1)
        plans = _create_plans(db_session, 1)
        subs = _create_subscriptions(db_session, customers, plans[0], 1)
        _create_invoices(db_session, customers[0], subs[0], TOTAL_ITEMS)
        resp = client.get("/v1/invoices/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        customers = _create_customers(db_session, 1)
        plans = _create_plans(db_session, 1)
        subs = _create_subscriptions(db_session, customers, plans[0], 1)
        _create_invoices(db_session, customers[0], subs[0], TOTAL_ITEMS)
        resp = client.get("/v1/invoices/?skip=2&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)


class TestEventsPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        metrics = _create_billable_metrics(db_session, 1)
        _create_events(db_session, metrics[0].code, TOTAL_ITEMS)
        resp = client.get("/v1/events/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        metrics = _create_billable_metrics(db_session, 1)
        _create_events(db_session, metrics[0].code, TOTAL_ITEMS)
        resp = client.get("/v1/events/?skip=1&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)


class TestWalletsPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        customers = _create_customers(db_session, 1)
        _create_wallets(db_session, customers[0].id, TOTAL_ITEMS)
        resp = client.get("/v1/wallets/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        customers = _create_customers(db_session, 1)
        _create_wallets(db_session, customers[0].id, TOTAL_ITEMS)
        resp = client.get("/v1/wallets/?skip=1&limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 3
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)


class TestCouponsPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        _create_coupons(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/coupons/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        _create_coupons(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/coupons/?skip=4&limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)


class TestAddOnsPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        _create_add_ons(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/add_ons/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        _create_add_ons(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/add_ons/?skip=2&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)


class TestTaxesPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        _create_taxes(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/taxes/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        _create_taxes(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/taxes/?skip=3&limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)


class TestFeesPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        """Fees endpoint returns X-Total-Count=0 with no data."""
        resp = client.get("/v1/fees/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == "0"
        assert resp.json() == []


class TestPaymentsPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        customers = _create_customers(db_session, 1)
        plans = _create_plans(db_session, 1)
        subs = _create_subscriptions(db_session, customers, plans[0], 1)
        invoices = _create_invoices(db_session, customers[0], subs[0], 1)
        _create_payments(db_session, invoices[0], customers[0], TOTAL_ITEMS)
        resp = client.get("/v1/payments/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        customers = _create_customers(db_session, 1)
        plans = _create_plans(db_session, 1)
        subs = _create_subscriptions(db_session, customers, plans[0], 1)
        invoices = _create_invoices(db_session, customers[0], subs[0], 1)
        _create_payments(db_session, invoices[0], customers[0], TOTAL_ITEMS)
        resp = client.get("/v1/payments/?skip=2&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)


class TestBillableMetricsPagination:
    def test_total_count_header(self, client: TestClient, db_session):
        _create_billable_metrics(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/billable_metrics/")
        assert resp.status_code == 200
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)
        assert len(resp.json()) == TOTAL_ITEMS

    def test_skip_and_limit(self, client: TestClient, db_session):
        _create_billable_metrics(db_session, TOTAL_ITEMS)
        resp = client.get("/v1/billable_metrics/?skip=1&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.headers["X-Total-Count"] == str(TOTAL_ITEMS)


class TestPaginationDefaults:
    """Test that default values work correctly (skip=0, limit=100)."""

    def test_default_skip_and_limit(self, client: TestClient, db_session):
        _create_customers(db_session, 3)
        resp = client.get("/v1/customers/")
        assert resp.status_code == 200
        assert len(resp.json()) == 3
        assert resp.headers["X-Total-Count"] == "3"

    def test_empty_collection_returns_zero_count(self, client: TestClient):
        resp = client.get("/v1/customers/")
        assert resp.status_code == 200
        assert resp.json() == []
        assert resp.headers["X-Total-Count"] == "0"

    def test_limit_one(self, client: TestClient, db_session):
        _create_customers(db_session, 3)
        resp = client.get("/v1/customers/?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.headers["X-Total-Count"] == "3"
