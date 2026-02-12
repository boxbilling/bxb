"""Tests for SubscriptionLifecycleService."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.database import get_db
from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.webhook_endpoint import WebhookEndpoint
from app.repositories.invoice_repository import InvoiceRepository
from app.services.subscription_lifecycle import SubscriptionLifecycleService


@pytest.fixture
def db_session():
    """Create a database session for direct repository testing."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


def _create_customer(db, external_id: str = "cust_lc") -> Customer:
    customer = Customer(external_id=external_id, name=f"Customer {external_id}", email="a@b.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _create_plan(
    db,
    code: str = "plan_a",
    amount_cents: int = 10000,
    interval: str = PlanInterval.MONTHLY.value,
) -> Plan:
    plan = Plan(code=code, name=f"Plan {code}", interval=interval, amount_cents=amount_cents)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _create_active_subscription(
    db,
    customer: Customer,
    plan: Plan,
    external_id: str = "sub_lc",
    pay_in_advance: bool = False,
    trial_period_days: int = 0,
) -> Subscription:
    now = datetime.now(UTC)
    sub = Subscription(
        external_id=external_id,
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        started_at=now - timedelta(days=5),
        pay_in_advance=pay_in_advance,
        trial_period_days=trial_period_days,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def _create_pending_subscription(
    db,
    customer: Customer,
    plan: Plan,
    external_id: str = "sub_pending_lc",
    pay_in_advance: bool = False,
    trial_period_days: int = 0,
) -> Subscription:
    sub = Subscription(
        external_id=external_id,
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.PENDING.value,
        pay_in_advance=pay_in_advance,
        trial_period_days=trial_period_days,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def _create_webhook_endpoint(db) -> WebhookEndpoint:
    endpoint = WebhookEndpoint(url="https://example.com/hook")
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


class TestUpgradePlan:
    def test_upgrade_plan_basic(self, db_session):
        """Test basic plan upgrade without pay_in_advance."""
        customer = _create_customer(db_session, "cust_up_basic")
        plan_a = _create_plan(db_session, "plan_up_a", 5000)
        plan_b = _create_plan(db_session, "plan_up_b", 10000)
        sub = _create_active_subscription(db_session, customer, plan_a, "sub_up_basic")

        service = SubscriptionLifecycleService(db_session)
        service.upgrade_plan(sub.id, plan_b.id)

        db_session.refresh(sub)
        assert str(sub.plan_id) == str(plan_b.id)
        assert str(sub.previous_plan_id) == str(plan_a.id)

    def test_upgrade_plan_not_found(self, db_session):
        """Test upgrade with non-existent subscription."""
        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.upgrade_plan(uuid.uuid4(), uuid.uuid4())

    def test_upgrade_plan_not_active(self, db_session):
        """Test upgrade of non-active subscription."""
        customer = _create_customer(db_session, "cust_up_na")
        plan = _create_plan(db_session, "plan_up_na")
        sub = _create_pending_subscription(db_session, customer, plan, "sub_up_na")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="active"):
            service.upgrade_plan(sub.id, uuid.uuid4())

    def test_upgrade_plan_same_plan(self, db_session):
        """Test upgrade to the same plan."""
        customer = _create_customer(db_session, "cust_up_same")
        plan = _create_plan(db_session, "plan_up_same")
        sub = _create_active_subscription(db_session, customer, plan, "sub_up_same")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="different"):
            service.upgrade_plan(sub.id, plan.id)

    def test_upgrade_plan_new_plan_not_found(self, db_session):
        """Test upgrade to non-existent plan."""
        customer = _create_customer(db_session, "cust_up_nf")
        plan = _create_plan(db_session, "plan_up_nf")
        sub = _create_active_subscription(db_session, customer, plan, "sub_up_nf")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="Plan .* not found"):
            service.upgrade_plan(sub.id, uuid.uuid4())

    def test_upgrade_plan_pay_in_advance_generates_credit_and_invoice(self, db_session):
        """Test upgrade with pay_in_advance generates credit note and prorated invoice."""
        customer = _create_customer(db_session, "cust_up_pia")
        plan_a = _create_plan(db_session, "plan_up_pia_a", 10000)
        plan_b = _create_plan(db_session, "plan_up_pia_b", 20000)
        sub = _create_active_subscription(
            db_session, customer, plan_a, "sub_up_pia", pay_in_advance=True
        )

        # Create an existing invoice so credit note can reference it
        invoice_repo = InvoiceRepository(db_session)
        from app.schemas.invoice import InvoiceCreate

        invoice_repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=sub.id,
                billing_period_start=datetime.now(UTC) - timedelta(days=5),
                billing_period_end=datetime.now(UTC) + timedelta(days=25),
            )
        )

        service = SubscriptionLifecycleService(db_session)
        service.upgrade_plan(sub.id, plan_b.id)

        db_session.refresh(sub)
        assert str(sub.plan_id) == str(plan_b.id)

        # Should have created a credit note
        credit_notes = db_session.query(CreditNote).filter(
            CreditNote.customer_id == customer.id
        ).all()
        assert len(credit_notes) == 1
        assert credit_notes[0].total_amount_cents > 0

        # Should have created a prorated invoice (original + new prorated)
        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 2  # original + prorated

    def test_upgrade_plan_pay_in_advance_no_invoice_no_credit_note(self, db_session):
        """Test upgrade with pay_in_advance but no existing invoice skips credit note."""
        customer = _create_customer(db_session, "cust_up_pia_noinv")
        plan_a = _create_plan(db_session, "plan_up_pia_noinv_a", 10000)
        plan_b = _create_plan(db_session, "plan_up_pia_noinv_b", 20000)
        sub = _create_active_subscription(
            db_session, customer, plan_a, "sub_up_pia_noinv", pay_in_advance=True
        )

        service = SubscriptionLifecycleService(db_session)
        service.upgrade_plan(sub.id, plan_b.id)

        # No credit note should be created (no existing invoice)
        credit_notes = db_session.query(CreditNote).filter(
            CreditNote.customer_id == customer.id
        ).all()
        assert len(credit_notes) == 0

    def test_upgrade_plan_triggers_webhook(self, db_session):
        """Test upgrade triggers subscription.plan_changed webhook."""
        _create_webhook_endpoint(db_session)
        customer = _create_customer(db_session, "cust_up_wh")
        plan_a = _create_plan(db_session, "plan_up_wh_a", 5000)
        plan_b = _create_plan(db_session, "plan_up_wh_b", 10000)
        sub = _create_active_subscription(db_session, customer, plan_a, "sub_up_wh")

        service = SubscriptionLifecycleService(db_session)
        service.upgrade_plan(sub.id, plan_b.id)

        from app.models.webhook import Webhook

        webhooks = db_session.query(Webhook).filter(
            Webhook.webhook_type == "subscription.plan_changed"
        ).all()
        assert len(webhooks) == 1
        assert webhooks[0].payload["change_type"] == "upgrade"


class TestDowngradePlan:
    def test_downgrade_plan_end_of_period(self, db_session):
        """Test downgrade scheduled for end of period."""
        customer = _create_customer(db_session, "cust_dg_eop")
        plan_a = _create_plan(db_session, "plan_dg_a", 10000)
        plan_b = _create_plan(db_session, "plan_dg_b", 5000)
        sub = _create_active_subscription(db_session, customer, plan_a, "sub_dg_eop")

        service = SubscriptionLifecycleService(db_session)
        service.downgrade_plan(sub.id, plan_b.id, effective_at="end_of_period")

        db_session.refresh(sub)
        # Plan should NOT have changed yet
        assert str(sub.plan_id) == str(plan_a.id)
        # Downgrade should be tracked
        assert sub.downgraded_at is not None
        # previous_plan_id stores the TARGET plan for end_of_period downgrades
        assert str(sub.previous_plan_id) == str(plan_b.id)

    def test_downgrade_plan_immediate(self, db_session):
        """Test immediate downgrade."""
        customer = _create_customer(db_session, "cust_dg_imm")
        plan_a = _create_plan(db_session, "plan_dg_imm_a", 10000)
        plan_b = _create_plan(db_session, "plan_dg_imm_b", 5000)
        sub = _create_active_subscription(db_session, customer, plan_a, "sub_dg_imm")

        service = SubscriptionLifecycleService(db_session)
        service.downgrade_plan(sub.id, plan_b.id, effective_at="immediate")

        db_session.refresh(sub)
        assert str(sub.plan_id) == str(plan_b.id)
        assert str(sub.previous_plan_id) == str(plan_a.id)
        assert sub.downgraded_at is not None

    def test_downgrade_plan_not_found(self, db_session):
        """Test downgrade with non-existent subscription."""
        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.downgrade_plan(uuid.uuid4(), uuid.uuid4())

    def test_downgrade_plan_not_active(self, db_session):
        """Test downgrade of non-active subscription."""
        customer = _create_customer(db_session, "cust_dg_na")
        plan = _create_plan(db_session, "plan_dg_na")
        sub = _create_pending_subscription(db_session, customer, plan, "sub_dg_na")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="active"):
            service.downgrade_plan(sub.id, uuid.uuid4())

    def test_downgrade_plan_same_plan(self, db_session):
        """Test downgrade to same plan."""
        customer = _create_customer(db_session, "cust_dg_same")
        plan = _create_plan(db_session, "plan_dg_same")
        sub = _create_active_subscription(db_session, customer, plan, "sub_dg_same")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="different"):
            service.downgrade_plan(sub.id, plan.id)

    def test_downgrade_plan_not_found_new_plan(self, db_session):
        """Test downgrade to non-existent plan."""
        customer = _create_customer(db_session, "cust_dg_nf")
        plan = _create_plan(db_session, "plan_dg_nf")
        sub = _create_active_subscription(db_session, customer, plan, "sub_dg_nf")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="Plan .* not found"):
            service.downgrade_plan(sub.id, uuid.uuid4())

    def test_downgrade_plan_immediate_pay_in_advance(self, db_session):
        """Test immediate downgrade with pay_in_advance generates financial records."""
        customer = _create_customer(db_session, "cust_dg_pia")
        plan_a = _create_plan(db_session, "plan_dg_pia_a", 20000)
        plan_b = _create_plan(db_session, "plan_dg_pia_b", 5000)
        sub = _create_active_subscription(
            db_session, customer, plan_a, "sub_dg_pia", pay_in_advance=True
        )

        # Create existing invoice
        invoice_repo = InvoiceRepository(db_session)
        from app.schemas.invoice import InvoiceCreate

        invoice_repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=sub.id,
                billing_period_start=datetime.now(UTC) - timedelta(days=5),
                billing_period_end=datetime.now(UTC) + timedelta(days=25),
            )
        )

        service = SubscriptionLifecycleService(db_session)
        service.downgrade_plan(sub.id, plan_b.id, effective_at="immediate")

        db_session.refresh(sub)
        assert str(sub.plan_id) == str(plan_b.id)

        # Credit note from old plan
        credit_notes = db_session.query(CreditNote).filter(
            CreditNote.customer_id == customer.id
        ).all()
        assert len(credit_notes) == 1

    def test_downgrade_plan_end_of_period_triggers_webhook(self, db_session):
        """Test end-of-period downgrade triggers webhook."""
        _create_webhook_endpoint(db_session)
        customer = _create_customer(db_session, "cust_dg_wh_eop")
        plan_a = _create_plan(db_session, "plan_dg_wh_a", 10000)
        plan_b = _create_plan(db_session, "plan_dg_wh_b", 5000)
        sub = _create_active_subscription(db_session, customer, plan_a, "sub_dg_wh_eop")

        service = SubscriptionLifecycleService(db_session)
        service.downgrade_plan(sub.id, plan_b.id, effective_at="end_of_period")

        from app.models.webhook import Webhook

        webhooks = db_session.query(Webhook).filter(
            Webhook.webhook_type == "subscription.plan_changed"
        ).all()
        assert len(webhooks) == 1
        assert webhooks[0].payload["effective_at"] == "end_of_period"

    def test_downgrade_plan_immediate_triggers_webhook(self, db_session):
        """Test immediate downgrade triggers webhook."""
        _create_webhook_endpoint(db_session)
        customer = _create_customer(db_session, "cust_dg_wh_imm")
        plan_a = _create_plan(db_session, "plan_dg_wh_imm_a", 10000)
        plan_b = _create_plan(db_session, "plan_dg_wh_imm_b", 5000)
        sub = _create_active_subscription(db_session, customer, plan_a, "sub_dg_wh_imm")

        service = SubscriptionLifecycleService(db_session)
        service.downgrade_plan(sub.id, plan_b.id, effective_at="immediate")

        from app.models.webhook import Webhook

        webhooks = db_session.query(Webhook).filter(
            Webhook.webhook_type == "subscription.plan_changed"
        ).all()
        assert len(webhooks) == 1
        assert webhooks[0].payload["effective_at"] == "immediate"
        assert webhooks[0].payload["change_type"] == "downgrade"


class TestActivatePendingSubscription:
    def test_activate_basic(self, db_session):
        """Test activating a pending subscription."""
        customer = _create_customer(db_session, "cust_act")
        plan = _create_plan(db_session, "plan_act")
        sub = _create_pending_subscription(db_session, customer, plan, "sub_act")

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.ACTIVE.value
        assert sub.started_at is not None

    def test_activate_not_found(self, db_session):
        """Test activating non-existent subscription."""
        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.activate_pending_subscription(uuid.uuid4())

    def test_activate_not_pending(self, db_session):
        """Test activating an already active subscription."""
        customer = _create_customer(db_session, "cust_act_na")
        plan = _create_plan(db_session, "plan_act_na")
        sub = _create_active_subscription(db_session, customer, plan, "sub_act_na")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="pending"):
            service.activate_pending_subscription(sub.id)

    def test_activate_pay_in_advance_generates_invoice(self, db_session):
        """Test activating pay-in-advance subscription generates invoice."""
        customer = _create_customer(db_session, "cust_act_pia")
        plan = _create_plan(db_session, "plan_act_pia", 15000)
        sub = _create_pending_subscription(
            db_session, customer, plan, "sub_act_pia", pay_in_advance=True
        )

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 1
        assert invoices[0].total == Decimal("15000")

    def test_activate_with_trial_no_invoice(self, db_session):
        """Test activating with trial does not generate invoice."""
        customer = _create_customer(db_session, "cust_act_trial")
        plan = _create_plan(db_session, "plan_act_trial", 10000)
        sub = _create_pending_subscription(
            db_session,
            customer,
            plan,
            "sub_act_trial",
            pay_in_advance=True,
            trial_period_days=14,
        )

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.ACTIVE.value

        # No invoice because of trial
        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 0

    def test_activate_no_pay_in_advance_no_invoice(self, db_session):
        """Test activating without pay-in-advance does not generate invoice."""
        customer = _create_customer(db_session, "cust_act_nopia")
        plan = _create_plan(db_session, "plan_act_nopia", 10000)
        sub = _create_pending_subscription(db_session, customer, plan, "sub_act_nopia")

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 0

    def test_activate_triggers_webhook(self, db_session):
        """Test activation triggers subscription.started webhook."""
        _create_webhook_endpoint(db_session)
        customer = _create_customer(db_session, "cust_act_wh")
        plan = _create_plan(db_session, "plan_act_wh")
        sub = _create_pending_subscription(db_session, customer, plan, "sub_act_wh")

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        from app.models.webhook import Webhook

        webhooks = db_session.query(Webhook).filter(
            Webhook.webhook_type == "subscription.started"
        ).all()
        assert len(webhooks) == 1

    def test_activate_pay_in_advance_zero_amount_no_invoice(self, db_session):
        """Test activating pay-in-advance with zero amount plan does not generate invoice."""
        customer = _create_customer(db_session, "cust_act_zero")
        plan = _create_plan(db_session, "plan_act_zero", 0)
        sub = _create_pending_subscription(
            db_session, customer, plan, "sub_act_zero", pay_in_advance=True
        )

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 0


class TestProcessTrialEnd:
    def test_process_trial_end_basic(self, db_session):
        """Test processing trial end."""
        customer = _create_customer(db_session, "cust_te")
        plan = _create_plan(db_session, "plan_te")
        sub = _create_active_subscription(
            db_session, customer, plan, "sub_te", trial_period_days=14
        )

        service = SubscriptionLifecycleService(db_session)
        service.process_trial_end(sub.id)

        db_session.refresh(sub)
        assert sub.trial_ended_at is not None

    def test_process_trial_end_not_found(self, db_session):
        """Test processing trial end for non-existent subscription."""
        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.process_trial_end(uuid.uuid4())

    def test_process_trial_end_not_active(self, db_session):
        """Test processing trial end for non-active subscription."""
        customer = _create_customer(db_session, "cust_te_na")
        plan = _create_plan(db_session, "plan_te_na")
        sub = _create_pending_subscription(db_session, customer, plan, "sub_te_na")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="active"):
            service.process_trial_end(sub.id)

    def test_process_trial_end_pay_in_advance_generates_invoice(self, db_session):
        """Test processing trial end with pay_in_advance generates invoice."""
        customer = _create_customer(db_session, "cust_te_pia")
        plan = _create_plan(db_session, "plan_te_pia", 10000)
        sub = _create_active_subscription(
            db_session,
            customer,
            plan,
            "sub_te_pia",
            pay_in_advance=True,
            trial_period_days=14,
        )

        service = SubscriptionLifecycleService(db_session)
        service.process_trial_end(sub.id)

        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 1

    def test_process_trial_end_already_ended(self, db_session):
        """Test processing trial end when trial already ended (idempotent)."""
        customer = _create_customer(db_session, "cust_te_already")
        plan = _create_plan(db_session, "plan_te_already")
        sub = _create_active_subscription(
            db_session, customer, plan, "sub_te_already", trial_period_days=14
        )

        # Set trial_ended_at manually
        original_time = datetime.now(UTC) - timedelta(days=1)
        sub.trial_ended_at = original_time
        db_session.commit()
        db_session.refresh(sub)

        service = SubscriptionLifecycleService(db_session)
        service.process_trial_end(sub.id)

        db_session.refresh(sub)
        # Should not have been overwritten
        assert sub.trial_ended_at.replace(tzinfo=None) == original_time.replace(tzinfo=None)

    def test_process_trial_end_triggers_webhook(self, db_session):
        """Test trial end triggers subscription.trial_ended webhook."""
        _create_webhook_endpoint(db_session)
        customer = _create_customer(db_session, "cust_te_wh")
        plan = _create_plan(db_session, "plan_te_wh")
        sub = _create_active_subscription(
            db_session, customer, plan, "sub_te_wh", trial_period_days=14
        )

        service = SubscriptionLifecycleService(db_session)
        service.process_trial_end(sub.id)

        from app.models.webhook import Webhook

        webhooks = db_session.query(Webhook).filter(
            Webhook.webhook_type == "subscription.trial_ended"
        ).all()
        assert len(webhooks) == 1

    def test_process_trial_end_no_pay_in_advance_no_invoice(self, db_session):
        """Test processing trial end without pay_in_advance does not generate invoice."""
        customer = _create_customer(db_session, "cust_te_nopia")
        plan = _create_plan(db_session, "plan_te_nopia", 10000)
        sub = _create_active_subscription(
            db_session, customer, plan, "sub_te_nopia", trial_period_days=14
        )

        service = SubscriptionLifecycleService(db_session)
        service.process_trial_end(sub.id)

        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 0

    def test_process_trial_end_pay_in_advance_zero_amount_no_invoice(self, db_session):
        """Test processing trial end with pay_in_advance but zero plan amount."""
        customer = _create_customer(db_session, "cust_te_zero")
        plan = _create_plan(db_session, "plan_te_zero", 0)
        sub = _create_active_subscription(
            db_session,
            customer,
            plan,
            "sub_te_zero",
            pay_in_advance=True,
            trial_period_days=14,
        )

        service = SubscriptionLifecycleService(db_session)
        service.process_trial_end(sub.id)

        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 0


class TestExecutePendingDowngrade:
    def test_execute_pending_downgrade(self, db_session):
        """Test executing a pending downgrade."""
        customer = _create_customer(db_session, "cust_exec_dg")
        plan_a = _create_plan(db_session, "plan_exec_a", 10000)
        plan_b = _create_plan(db_session, "plan_exec_b", 5000)
        sub = _create_active_subscription(db_session, customer, plan_a, "sub_exec_dg")

        # Set up pending downgrade (previous_plan_id = target plan)
        sub.downgraded_at = datetime.now(UTC) - timedelta(days=1)
        sub.previous_plan_id = plan_b.id
        db_session.commit()
        db_session.refresh(sub)

        service = SubscriptionLifecycleService(db_session)
        service.execute_pending_downgrade(sub.id)

        db_session.refresh(sub)
        assert str(sub.plan_id) == str(plan_b.id)
        assert str(sub.previous_plan_id) == str(plan_a.id)
        assert sub.downgraded_at is None

    def test_execute_pending_downgrade_not_found(self, db_session):
        """Test executing downgrade for non-existent subscription."""
        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.execute_pending_downgrade(uuid.uuid4())

    def test_execute_pending_downgrade_no_pending(self, db_session):
        """Test executing downgrade when no downgrade is pending."""
        customer = _create_customer(db_session, "cust_exec_nopend")
        plan = _create_plan(db_session, "plan_exec_nopend")
        sub = _create_active_subscription(db_session, customer, plan, "sub_exec_nopend")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="No pending downgrade"):
            service.execute_pending_downgrade(sub.id)

    def test_execute_pending_downgrade_triggers_webhook(self, db_session):
        """Test executing pending downgrade triggers webhook."""
        _create_webhook_endpoint(db_session)
        customer = _create_customer(db_session, "cust_exec_wh")
        plan_a = _create_plan(db_session, "plan_exec_wh_a", 10000)
        plan_b = _create_plan(db_session, "plan_exec_wh_b", 5000)
        sub = _create_active_subscription(db_session, customer, plan_a, "sub_exec_wh")

        sub.downgraded_at = datetime.now(UTC) - timedelta(days=1)
        sub.previous_plan_id = plan_b.id
        db_session.commit()

        service = SubscriptionLifecycleService(db_session)
        service.execute_pending_downgrade(sub.id)

        from app.models.webhook import Webhook

        webhooks = db_session.query(Webhook).filter(
            Webhook.webhook_type == "subscription.plan_changed"
        ).all()
        assert len(webhooks) == 1
        assert webhooks[0].payload["change_type"] == "downgrade_executed"


class TestPlanChangeCreditNote:
    def test_credit_note_uses_finalized_invoice_when_no_draft(self, db_session):
        """Test credit note falls back to finalized invoice if no draft exists."""
        customer = _create_customer(db_session, "cust_cn_fin")
        plan_a = _create_plan(db_session, "plan_cn_fin_a", 10000)
        plan_b = _create_plan(db_session, "plan_cn_fin_b", 20000)
        sub = _create_active_subscription(
            db_session, customer, plan_a, "sub_cn_fin", pay_in_advance=True
        )

        # Create a finalized invoice (not draft)
        invoice_repo = InvoiceRepository(db_session)
        from app.schemas.invoice import InvoiceCreate

        invoice = invoice_repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=sub.id,
                billing_period_start=datetime.now(UTC) - timedelta(days=5),
                billing_period_end=datetime.now(UTC) + timedelta(days=25),
            )
        )
        invoice_repo.finalize(invoice.id)

        service = SubscriptionLifecycleService(db_session)
        service.upgrade_plan(sub.id, plan_b.id)

        credit_notes = db_session.query(CreditNote).filter(
            CreditNote.customer_id == customer.id
        ).all()
        assert len(credit_notes) == 1


class TestEdgeCases:
    def test_activate_plan_not_found(self, db_session):
        """Test activating when plan_id references a non-existent plan (plan lookup returns None)."""
        customer = _create_customer(db_session, "cust_act_nop")
        plan = _create_plan(db_session, "plan_act_nop", 10000)
        sub = _create_pending_subscription(
            db_session, customer, plan, "sub_act_nop", pay_in_advance=True
        )

        # Point plan_id to a non-existent UUID (bypass FK with raw update on SQLite)
        fake_id = uuid.uuid4()
        db_session.execute(
            Subscription.__table__.update()
            .where(Subscription.id == sub.id)
            .values(plan_id=str(fake_id))
        )
        db_session.commit()
        db_session.expire(sub)

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.ACTIVE.value
        # No invoice because plan wasn't found
        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 0

    def test_process_trial_end_plan_not_found(self, db_session):
        """Test processing trial end when plan_id references non-existent plan."""
        customer = _create_customer(db_session, "cust_te_nop")
        plan = _create_plan(db_session, "plan_te_nop", 10000)
        sub = _create_active_subscription(
            db_session, customer, plan, "sub_te_nop",
            pay_in_advance=True, trial_period_days=14,
        )

        # Point plan_id to a non-existent UUID
        fake_id = uuid.uuid4()
        db_session.execute(
            Subscription.__table__.update()
            .where(Subscription.id == sub.id)
            .values(plan_id=str(fake_id))
        )
        db_session.commit()
        db_session.expire(sub)

        service = SubscriptionLifecycleService(db_session)
        service.process_trial_end(sub.id)

        db_session.refresh(sub)
        assert sub.trial_ended_at is not None
        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 0

    def test_upgrade_pay_in_advance_zero_amount_plan_no_credit_or_invoice(self, db_session):
        """Test upgrade with pay_in_advance and zero-amount plans skips financial records."""
        customer = _create_customer(db_session, "cust_up_zero")
        plan_a = _create_plan(db_session, "plan_up_zero_a", 0)
        plan_b = _create_plan(db_session, "plan_up_zero_b", 0)
        sub = _create_active_subscription(
            db_session, customer, plan_a, "sub_up_zero", pay_in_advance=True
        )

        # Create existing invoice for credit note lookup
        invoice_repo = InvoiceRepository(db_session)
        from app.schemas.invoice import InvoiceCreate

        invoice_repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=sub.id,
                billing_period_start=datetime.now(UTC) - timedelta(days=5),
                billing_period_end=datetime.now(UTC) + timedelta(days=25),
            )
        )

        service = SubscriptionLifecycleService(db_session)
        service.upgrade_plan(sub.id, plan_b.id)

        # No credit note because prorated amount is 0
        credit_notes = db_session.query(CreditNote).filter(
            CreditNote.customer_id == customer.id
        ).all()
        assert len(credit_notes) == 0

        # Only the original invoice, no prorated invoice
        invoices = db_session.query(Invoice).filter(
            Invoice.subscription_id == sub.id
        ).all()
        assert len(invoices) == 1  # original only


class TestWebhookEventTypes:
    def test_new_event_types_in_list(self):
        """Test that new subscription lifecycle events are in WEBHOOK_EVENT_TYPES."""
        from app.services.webhook_service import WEBHOOK_EVENT_TYPES

        assert "subscription.started" in WEBHOOK_EVENT_TYPES
        assert "subscription.plan_changed" in WEBHOOK_EVENT_TYPES
        assert "subscription.trial_ended" in WEBHOOK_EVENT_TYPES
