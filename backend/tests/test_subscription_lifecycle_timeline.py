"""Tests for subscription lifecycle timeline endpoint."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.subscription_lifecycle import LifecycleEvent, SubscriptionLifecycleResponse


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


def create_customer(db_session, external_id: str = "cust_lc_1") -> Customer:
    customer = Customer(
        external_id=external_id,
        name="Lifecycle Customer",
        email="lc@example.com",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


def create_plan(db_session, code: str = "lc_plan") -> Plan:
    plan = Plan(
        code=code,
        name="Lifecycle Plan",
        interval=PlanInterval.MONTHLY.value,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


def create_subscription(
    db_session,
    customer: Customer,
    plan: Plan,
    external_id: str = "sub_lc_1",
    status: str = SubscriptionStatus.ACTIVE.value,
    started_at: datetime | None = None,
    trial_ended_at: datetime | None = None,
    trial_period_days: int = 0,
    downgraded_at: datetime | None = None,
    canceled_at: datetime | None = None,
    ending_at: datetime | None = None,
    paused_at: datetime | None = None,
    resumed_at: datetime | None = None,
) -> Subscription:
    now = datetime.now(UTC)
    sub = Subscription(
        external_id=external_id,
        customer_id=customer.id,
        plan_id=plan.id,
        status=status,
        started_at=started_at,
        trial_ended_at=trial_ended_at,
        trial_period_days=trial_period_days,
        downgraded_at=downgraded_at,
        canceled_at=canceled_at,
        ending_at=ending_at,
        paused_at=paused_at,
        resumed_at=resumed_at,
        created_at=now,
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


def create_invoice(
    db_session,
    customer: Customer,
    subscription: Subscription,
    invoice_number: str = "INV-001",
    status: str = InvoiceStatus.FINALIZED.value,
    total: Decimal = Decimal("10000"),
    currency: str = "USD",
    created_at: datetime | None = None,
) -> Invoice:
    now = created_at or datetime.now(UTC)
    inv = Invoice(
        invoice_number=invoice_number,
        customer_id=customer.id,
        subscription_id=subscription.id,
        status=status,
        total=total,
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        currency=currency,
        created_at=now,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


def create_payment(
    db_session,
    invoice: Invoice,
    customer: Customer,
    amount: Decimal = Decimal("10000"),
    status: str = PaymentStatus.SUCCEEDED.value,
    provider: str = PaymentProvider.STRIPE.value,
    currency: str = "USD",
    created_at: datetime | None = None,
) -> Payment:
    now = created_at or datetime.now(UTC)
    pmt = Payment(
        invoice_id=invoice.id,
        customer_id=customer.id,
        amount=amount,
        currency=currency,
        status=status,
        provider=provider,
        created_at=now,
    )
    db_session.add(pmt)
    db_session.commit()
    db_session.refresh(pmt)
    return pmt


class TestSubscriptionLifecycleSchemas:
    """Test lifecycle schema models."""

    def test_lifecycle_event_minimal(self):
        event = LifecycleEvent(
            timestamp=datetime.now(UTC),
            event_type="subscription",
            title="Created",
        )
        assert event.description is None
        assert event.status is None
        assert event.resource_id is None
        assert event.metadata is None

    def test_lifecycle_event_full(self):
        event = LifecycleEvent(
            timestamp=datetime.now(UTC),
            event_type="invoice",
            title="Invoice INV-001",
            description="Total: USD 100.00",
            status="finalized",
            resource_id="abc-123",
            resource_type="invoice",
            metadata={"invoice_number": "INV-001"},
        )
        assert event.description == "Total: USD 100.00"
        assert event.resource_type == "invoice"

    def test_lifecycle_response(self):
        resp = SubscriptionLifecycleResponse(events=[
            LifecycleEvent(
                timestamp=datetime.now(UTC),
                event_type="subscription",
                title="Created",
            )
        ])
        assert len(resp.events) == 1


class TestSubscriptionLifecycleAPI:
    """Test the GET /v1/subscriptions/{id}/lifecycle endpoint."""

    def test_lifecycle_not_found(self, client: TestClient):
        fake_id = uuid.uuid4()
        resp = client.get(f"/v1/subscriptions/{fake_id}/lifecycle")
        assert resp.status_code == 404

    def test_lifecycle_basic_subscription(self, client: TestClient, db_session):
        """Minimal subscription with only creation event."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        sub = create_subscription(db_session, customer, plan)

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) >= 1
        # First event should be subscription creation
        assert data["events"][0]["event_type"] == "subscription"
        assert data["events"][0]["title"] == "Subscription created"
        assert data["events"][0]["status"] == "created"

    def test_lifecycle_with_started_at(self, client: TestClient, db_session):
        """Subscription with a started_at date different from created_at."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        started = datetime.now(UTC) + timedelta(hours=1)
        sub = create_subscription(db_session, customer, plan, started_at=started)

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        types = [e["event_type"] for e in data["events"]]
        assert "subscription" in types
        assert "status_change" in types
        # Find the activation event
        activation = [e for e in data["events"] if e["title"] == "Subscription activated"]
        assert len(activation) == 1
        assert activation[0]["status"] == "active"

    def test_lifecycle_with_trial_ended(self, client: TestClient, db_session):
        """Subscription where trial has ended."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        trial_end = datetime.now(UTC) + timedelta(days=7)
        sub = create_subscription(
            db_session, customer, plan,
            trial_ended_at=trial_end,
            trial_period_days=7,
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        trial_events = [e for e in data["events"] if e["title"] == "Trial period ended"]
        assert len(trial_events) == 1
        assert "7 days" in trial_events[0]["description"]

    def test_lifecycle_with_downgrade(self, client: TestClient, db_session):
        """Subscription that has been downgraded."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        downgraded = datetime.now(UTC) + timedelta(days=15)
        sub = create_subscription(
            db_session, customer, plan,
            downgraded_at=downgraded,
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        plan_changes = [e for e in data["events"] if e["title"] == "Plan changed"]
        assert len(plan_changes) == 1
        assert plan_changes[0]["status"] == "changed"

    def test_lifecycle_canceled(self, client: TestClient, db_session):
        """Subscription that has been canceled."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        canceled = datetime.now(UTC) + timedelta(days=30)
        sub = create_subscription(
            db_session, customer, plan,
            status=SubscriptionStatus.CANCELED.value,
            canceled_at=canceled,
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        cancel_events = [e for e in data["events"] if e["title"] == "Subscription canceled"]
        assert len(cancel_events) == 1
        assert cancel_events[0]["status"] == "canceled"

    def test_lifecycle_terminated(self, client: TestClient, db_session):
        """Subscription that has been terminated."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        ended = datetime.now(UTC) + timedelta(days=45)
        sub = create_subscription(
            db_session, customer, plan,
            status=SubscriptionStatus.TERMINATED.value,
            ending_at=ended,
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        term_events = [e for e in data["events"] if e["title"] == "Subscription terminated"]
        assert len(term_events) == 1
        assert term_events[0]["status"] == "terminated"

    def test_lifecycle_with_invoices(self, client: TestClient, db_session):
        """Subscription with associated invoices."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        sub = create_subscription(db_session, customer, plan)
        inv = create_invoice(
            db_session, customer, sub,
            invoice_number="INV-LC-001",
            total=Decimal("50000"),
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        invoice_events = [e for e in data["events"] if e["event_type"] == "invoice"]
        assert len(invoice_events) == 1
        assert "INV-LC-001" in invoice_events[0]["title"]
        assert "USD 500.00" in invoice_events[0]["description"]
        assert invoice_events[0]["status"] == "finalized"
        assert invoice_events[0]["resource_type"] == "invoice"
        assert invoice_events[0]["resource_id"] == str(inv.id)

    def test_lifecycle_with_payments(self, client: TestClient, db_session):
        """Subscription with invoices and payments."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        sub = create_subscription(db_session, customer, plan)
        inv = create_invoice(
            db_session, customer, sub,
            invoice_number="INV-LC-002",
            total=Decimal("20000"),
        )
        create_payment(
            db_session, inv, customer,
            amount=Decimal("20000"),
            status=PaymentStatus.SUCCEEDED.value,
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        payment_events = [e for e in data["events"] if e["event_type"] == "payment"]
        assert len(payment_events) == 1
        assert payment_events[0]["title"] == "Payment succeeded"
        assert "USD 200.00" in payment_events[0]["description"]
        assert "INV-LC-002" in payment_events[0]["description"]
        assert payment_events[0]["resource_type"] == "payment"
        assert payment_events[0]["metadata"]["provider"] == "stripe"

    def test_lifecycle_failed_payment(self, client: TestClient, db_session):
        """Payment with failed status."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        sub = create_subscription(db_session, customer, plan)
        inv = create_invoice(db_session, customer, sub, invoice_number="INV-LC-003")
        create_payment(
            db_session, inv, customer,
            status=PaymentStatus.FAILED.value,
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        payment_events = [e for e in data["events"] if e["event_type"] == "payment"]
        assert len(payment_events) == 1
        assert payment_events[0]["title"] == "Payment failed"
        assert payment_events[0]["status"] == "failed"

    def test_lifecycle_chronological_order(self, client: TestClient, db_session):
        """Events are sorted chronologically."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        now = datetime.now(UTC)
        sub = create_subscription(
            db_session, customer, plan,
            started_at=now + timedelta(hours=1),
        )
        inv = create_invoice(
            db_session, customer, sub,
            invoice_number="INV-LC-004",
            created_at=now + timedelta(hours=2),
        )
        create_payment(
            db_session, inv, customer,
            created_at=now + timedelta(hours=3),
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        timestamps = [e["timestamp"] for e in data["events"]]
        assert timestamps == sorted(timestamps)

    def test_lifecycle_no_invoices_no_payments(self, client: TestClient, db_session):
        """Subscription with no invoices or payments only shows subscription events."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        sub = create_subscription(db_session, customer, plan)

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        assert all(e["event_type"] in ("subscription", "status_change") for e in data["events"])

    def test_lifecycle_multiple_invoices_and_payments(self, client: TestClient, db_session):
        """Full lifecycle with multiple invoices and payments."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        now = datetime.now(UTC)
        sub = create_subscription(
            db_session, customer, plan,
            started_at=now + timedelta(hours=1),
        )

        inv1 = create_invoice(
            db_session, customer, sub,
            invoice_number="INV-MULTI-001",
            total=Decimal("10000"),
            created_at=now + timedelta(days=30),
        )
        create_payment(
            db_session, inv1, customer,
            amount=Decimal("10000"),
            created_at=now + timedelta(days=31),
        )

        create_invoice(
            db_session, customer, sub,
            invoice_number="INV-MULTI-002",
            total=Decimal("15000"),
            status=InvoiceStatus.DRAFT.value,
            created_at=now + timedelta(days=60),
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        invoice_events = [e for e in data["events"] if e["event_type"] == "invoice"]
        assert len(invoice_events) == 2
        payment_events = [e for e in data["events"] if e["event_type"] == "payment"]
        assert len(payment_events) == 1

    def test_lifecycle_full_lifecycle(self, client: TestClient, db_session):
        """Full lifecycle: created -> activated -> trial ended -> invoiced -> paid -> canceled -> terminated."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        now = datetime.now(UTC)
        sub = create_subscription(
            db_session, customer, plan,
            started_at=now + timedelta(hours=1),
            trial_ended_at=now + timedelta(days=7),
            trial_period_days=7,
            canceled_at=now + timedelta(days=90),
            ending_at=now + timedelta(days=95),
            status=SubscriptionStatus.TERMINATED.value,
        )

        inv = create_invoice(
            db_session, customer, sub,
            invoice_number="INV-FULL-001",
            total=Decimal("30000"),
            status=InvoiceStatus.PAID.value,
            created_at=now + timedelta(days=30),
        )
        create_payment(
            db_session, inv, customer,
            amount=Decimal("30000"),
            created_at=now + timedelta(days=32),
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        titles = [e["title"] for e in data["events"]]
        assert "Subscription created" in titles
        assert "Subscription activated" in titles
        assert "Trial period ended" in titles
        assert "Invoice INV-FULL-001" in titles
        assert "Payment succeeded" in titles
        assert "Subscription canceled" in titles
        assert "Subscription terminated" in titles
        # Verify ordering
        timestamps = [e["timestamp"] for e in data["events"]]
        assert timestamps == sorted(timestamps)

    def test_lifecycle_invoices_from_other_subscription_excluded(self, client: TestClient, db_session):
        """Invoices from other subscriptions are not included."""
        customer = create_customer(db_session)
        plan = create_plan(db_session)
        sub1 = create_subscription(db_session, customer, plan, external_id="sub_lc_a")
        sub2 = create_subscription(db_session, customer, plan, external_id="sub_lc_b")

        # Invoice on sub2 should not appear in sub1's lifecycle
        create_invoice(
            db_session, customer, sub2,
            invoice_number="INV-OTHER-001",
        )
        create_invoice(
            db_session, customer, sub1,
            invoice_number="INV-OWN-001",
        )

        resp = client.get(f"/v1/subscriptions/{sub1.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        invoice_events = [e for e in data["events"] if e["event_type"] == "invoice"]
        assert len(invoice_events) == 1
        assert "INV-OWN-001" in invoice_events[0]["title"]

    def test_lifecycle_includes_paused_event(self, client: TestClient, db_session):
        """Test that paused_at appears in lifecycle timeline."""
        customer = create_customer(db_session, "cust_lc_paused")
        plan = create_plan(db_session, "plan_lc_paused")
        now = datetime.now(UTC)
        sub = create_subscription(
            db_session, customer, plan,
            external_id="sub_lc_paused",
            status=SubscriptionStatus.PAUSED.value,
            started_at=now - timedelta(days=10),
            paused_at=now - timedelta(days=2),
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        paused_events = [e for e in data["events"] if "paused" in e.get("title", "").lower()]
        assert len(paused_events) == 1
        assert paused_events[0]["status"] == "paused"

    def test_lifecycle_includes_resumed_event(self, client: TestClient, db_session):
        """Test that resumed_at appears in lifecycle timeline."""
        customer = create_customer(db_session, "cust_lc_resumed")
        plan = create_plan(db_session, "plan_lc_resumed")
        now = datetime.now(UTC)
        sub = create_subscription(
            db_session, customer, plan,
            external_id="sub_lc_resumed",
            status=SubscriptionStatus.ACTIVE.value,
            started_at=now - timedelta(days=10),
            resumed_at=now - timedelta(days=1),
        )

        resp = client.get(f"/v1/subscriptions/{sub.id}/lifecycle")
        assert resp.status_code == 200
        data = resp.json()
        resumed_events = [e for e in data["events"] if "resumed" in e.get("title", "").lower()]
        assert len(resumed_events) == 1
        assert resumed_events[0]["status"] == "active"
