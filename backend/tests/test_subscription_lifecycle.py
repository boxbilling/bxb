"""Tests for SubscriptionLifecycleService."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

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
        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 1
        assert credit_notes[0].total_amount_cents > 0

        # Should have created a prorated invoice (original + new prorated)
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
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
        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
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

        webhooks = (
            db_session.query(Webhook)
            .filter(Webhook.webhook_type == "subscription.plan_changed")
            .all()
        )
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
        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
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

        webhooks = (
            db_session.query(Webhook)
            .filter(Webhook.webhook_type == "subscription.plan_changed")
            .all()
        )
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

        webhooks = (
            db_session.query(Webhook)
            .filter(Webhook.webhook_type == "subscription.plan_changed")
            .all()
        )
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

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
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
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_activate_no_pay_in_advance_no_invoice(self, db_session):
        """Test activating without pay-in-advance does not generate invoice."""
        customer = _create_customer(db_session, "cust_act_nopia")
        plan = _create_plan(db_session, "plan_act_nopia", 10000)
        sub = _create_pending_subscription(db_session, customer, plan, "sub_act_nopia")

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
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

        webhooks = (
            db_session.query(Webhook).filter(Webhook.webhook_type == "subscription.started").all()
        )
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

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
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

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
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

        webhooks = (
            db_session.query(Webhook)
            .filter(Webhook.webhook_type == "subscription.trial_ended")
            .all()
        )
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

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
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

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
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

        webhooks = (
            db_session.query(Webhook)
            .filter(Webhook.webhook_type == "subscription.plan_changed")
            .all()
        )
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

        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
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
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_process_trial_end_plan_not_found(self, db_session):
        """Test processing trial end when plan_id references non-existent plan."""
        customer = _create_customer(db_session, "cust_te_nop")
        plan = _create_plan(db_session, "plan_te_nop", 10000)
        sub = _create_active_subscription(
            db_session,
            customer,
            plan,
            "sub_te_nop",
            pay_in_advance=True,
            trial_period_days=14,
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
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
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
        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 0

        # Only the original invoice, no prorated invoice
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1  # original only


class TestTerminateSubscription:
    def test_terminate_skip(self, db_session):
        """Test terminating with skip action (no financial ops)."""
        customer = _create_customer(db_session, "cust_term_skip")
        plan = _create_plan(db_session, "plan_term_skip", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_skip")

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id, "skip")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.TERMINATED.value
        assert sub.ending_at is not None

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_terminate_generate_invoice(self, db_session):
        """Test terminating with generate_invoice action."""
        customer = _create_customer(db_session, "cust_term_inv")
        plan = _create_plan(db_session, "plan_term_inv", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_inv")

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id, "generate_invoice")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.TERMINATED.value
        assert sub.ending_at is not None

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        assert "Final invoice" in invoices[0].line_items[0]["description"]

    def test_terminate_generate_credit_note(self, db_session):
        """Test terminating with generate_credit_note action."""
        customer = _create_customer(db_session, "cust_term_cn")
        plan = _create_plan(db_session, "plan_term_cn", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_cn")

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
        service.terminate_subscription(sub.id, "generate_credit_note")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.TERMINATED.value

        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 1
        assert credit_notes[0].total_amount_cents > 0

    def test_terminate_credit_note_no_invoice(self, db_session):
        """Test terminating with credit_note but no invoice skips CN."""
        customer = _create_customer(db_session, "cust_term_cn_noinv")
        plan = _create_plan(db_session, "plan_term_cn_noinv", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_cn_noinv")

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id, "generate_credit_note")

        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 0

    def test_terminate_not_found(self, db_session):
        """Test terminating non-existent subscription."""
        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.terminate_subscription(uuid.uuid4(), "skip")

    def test_terminate_already_terminated(self, db_session):
        """Test terminating already terminated subscription."""
        customer = _create_customer(db_session, "cust_term_already")
        plan = _create_plan(db_session, "plan_term_already")
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_already")
        sub.status = SubscriptionStatus.TERMINATED.value
        db_session.commit()
        db_session.refresh(sub)

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="active, pending, or paused"):
            service.terminate_subscription(sub.id, "skip")

    def test_terminate_pending_subscription(self, db_session):
        """Test terminating a pending subscription (skip financial ops)."""
        customer = _create_customer(db_session, "cust_term_pend")
        plan = _create_plan(db_session, "plan_term_pend", 10000)
        sub = _create_pending_subscription(db_session, customer, plan, "sub_term_pend")

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id, "generate_invoice")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.TERMINATED.value
        # No invoice for pending subscription
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_terminate_triggers_webhook(self, db_session):
        """Test termination triggers subscription.terminated webhook."""
        _create_webhook_endpoint(db_session)
        customer = _create_customer(db_session, "cust_term_wh")
        plan = _create_plan(db_session, "plan_term_wh")
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_wh")

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id, "skip")

        from app.models.webhook import Webhook

        webhooks = (
            db_session.query(Webhook)
            .filter(Webhook.webhook_type == "subscription.terminated")
            .all()
        )
        assert len(webhooks) == 1
        assert webhooks[0].payload["on_termination_action"] == "skip"

    def test_terminate_zero_amount_no_invoice(self, db_session):
        """Test termination with zero-amount plan skips invoice."""
        customer = _create_customer(db_session, "cust_term_zero")
        plan = _create_plan(db_session, "plan_term_zero", 0)
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_zero")

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id, "generate_invoice")

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_terminate_default_action(self, db_session):
        """Test termination with default action (generate_invoice)."""
        customer = _create_customer(db_session, "cust_term_def")
        plan = _create_plan(db_session, "plan_term_def", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_def")

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id)

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.TERMINATED.value

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1

    def test_terminate_invoice_zero_proration(self, db_session):
        """Test terminate generate_invoice when proration is 0."""
        customer = _create_customer(db_session, "cust_term_zerp")
        plan = _create_plan(db_session, "plan_term_zerp", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_zerp")

        service = SubscriptionLifecycleService(db_session)
        prorate_path = "app.services.subscription_lifecycle.SubscriptionDatesService.prorate_amount"
        with patch(prorate_path, return_value=0):
            service.terminate_subscription(sub.id, "generate_invoice")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.TERMINATED.value
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_terminate_credit_note_zero_proration(self, db_session):
        """Test terminate credit_note when remaining proration is 0."""
        customer = _create_customer(db_session, "cust_term_cn_zerp")
        plan = _create_plan(db_session, "plan_term_cn_zerp", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_cn_zerp")

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
        prorate_path = "app.services.subscription_lifecycle.SubscriptionDatesService.prorate_amount"
        with patch(prorate_path, return_value=0):
            service.terminate_subscription(sub.id, "generate_credit_note")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.TERMINATED.value
        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 0


class TestCancelSubscription:
    def test_cancel_skip(self, db_session):
        """Test canceling with skip action (no financial ops)."""
        customer = _create_customer(db_session, "cust_can_skip")
        plan = _create_plan(db_session, "plan_can_skip", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_skip")

        service = SubscriptionLifecycleService(db_session)
        service.cancel_subscription(sub.id, "skip")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.CANCELED.value
        assert sub.canceled_at is not None

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_cancel_generate_invoice(self, db_session):
        """Test canceling with generate_invoice action."""
        customer = _create_customer(db_session, "cust_can_inv")
        plan = _create_plan(db_session, "plan_can_inv", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_inv")

        service = SubscriptionLifecycleService(db_session)
        service.cancel_subscription(sub.id, "generate_invoice")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.CANCELED.value

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1

    def test_cancel_generate_credit_note(self, db_session):
        """Test canceling with generate_credit_note action."""
        customer = _create_customer(db_session, "cust_can_cn")
        plan = _create_plan(db_session, "plan_can_cn", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_cn")

        # Create an existing invoice for credit note reference
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
        service.cancel_subscription(sub.id, "generate_credit_note")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.CANCELED.value

        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 1

    def test_cancel_not_found(self, db_session):
        """Test canceling non-existent subscription."""
        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.cancel_subscription(uuid.uuid4(), "skip")

    def test_cancel_already_canceled(self, db_session):
        """Test canceling already canceled subscription."""
        customer = _create_customer(db_session, "cust_can_already")
        plan = _create_plan(db_session, "plan_can_already")
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_already")
        sub.status = SubscriptionStatus.CANCELED.value
        db_session.commit()
        db_session.refresh(sub)

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="active, pending, or paused"):
            service.cancel_subscription(sub.id, "skip")

    def test_cancel_pending_subscription(self, db_session):
        """Test canceling a pending subscription."""
        customer = _create_customer(db_session, "cust_can_pend")
        plan = _create_plan(db_session, "plan_can_pend", 10000)
        sub = _create_pending_subscription(db_session, customer, plan, "sub_can_pend")

        service = SubscriptionLifecycleService(db_session)
        service.cancel_subscription(sub.id, "generate_invoice")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.CANCELED.value
        assert sub.canceled_at is not None
        # No invoice for pending subscription
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_cancel_triggers_webhook(self, db_session):
        """Test cancel triggers subscription.canceled webhook."""
        _create_webhook_endpoint(db_session)
        customer = _create_customer(db_session, "cust_can_wh")
        plan = _create_plan(db_session, "plan_can_wh")
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_wh")

        service = SubscriptionLifecycleService(db_session)
        service.cancel_subscription(sub.id, "skip")

        from app.models.webhook import Webhook

        webhooks = (
            db_session.query(Webhook).filter(Webhook.webhook_type == "subscription.canceled").all()
        )
        assert len(webhooks) == 1
        assert webhooks[0].payload["on_termination_action"] == "skip"

    def test_cancel_zero_amount_no_invoice(self, db_session):
        """Test cancel with zero-amount plan skips invoice."""
        customer = _create_customer(db_session, "cust_can_zero")
        plan = _create_plan(db_session, "plan_can_zero", 0)
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_zero")

        service = SubscriptionLifecycleService(db_session)
        service.cancel_subscription(sub.id, "generate_invoice")

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_cancel_invoice_zero_proration(self, db_session):
        """Test cancel generate_invoice when proration is 0."""
        customer = _create_customer(db_session, "cust_can_zerp")
        plan = _create_plan(db_session, "plan_can_zerp", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_zerp")

        service = SubscriptionLifecycleService(db_session)
        prorate_path = "app.services.subscription_lifecycle.SubscriptionDatesService.prorate_amount"
        with patch(prorate_path, return_value=0):
            service.cancel_subscription(sub.id, "generate_invoice")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.CANCELED.value
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_cancel_credit_note_zero_proration(self, db_session):
        """Test cancel credit_note when remaining proration is 0."""
        customer = _create_customer(db_session, "cust_can_cn_zerp")
        plan = _create_plan(db_session, "plan_can_cn_zerp", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_cn_zerp")

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
        prorate_path = "app.services.subscription_lifecycle.SubscriptionDatesService.prorate_amount"
        with patch(prorate_path, return_value=0):
            service.cancel_subscription(sub.id, "generate_credit_note")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.CANCELED.value
        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 0


class TestGracePeriodInvoiceDates:
    def test_invoice_dates_default_grace_period(self, db_session):
        """Test invoice dates with default grace period (0 days, 30 day term)."""
        customer = _create_customer(db_session, "cust_gp_default")
        plan = _create_plan(db_session, "plan_gp_default", 15000)
        sub = _create_pending_subscription(
            db_session, customer, plan, "sub_gp_default", pay_in_advance=True
        )

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        invoice = invoices[0]
        # Default: grace_period=0, net_payment_term=30
        # issued_at = billing_period_end + 0 days
        assert invoice.issued_at is not None
        assert invoice.due_date is not None
        # due_date should be 30 days after issued_at
        diff = invoice.due_date - invoice.issued_at
        assert diff.days == 30

    def test_invoice_dates_custom_grace_period(self, db_session):
        """Test invoice dates with custom grace period and payment term."""
        customer = _create_customer(db_session, "cust_gp_custom")
        customer.invoice_grace_period = 5
        customer.net_payment_term = 45
        db_session.commit()
        db_session.refresh(customer)

        plan = _create_plan(db_session, "plan_gp_custom", 20000)
        sub = _create_pending_subscription(
            db_session, customer, plan, "sub_gp_custom", pay_in_advance=True
        )

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        invoice = invoices[0]

        # issued_at = billing_period_end + 5 days
        issued_to_period_end = invoice.issued_at - invoice.billing_period_end
        assert issued_to_period_end.days == 5

        # due_date = issued_at + 45 days
        due_to_issued = invoice.due_date - invoice.issued_at
        assert due_to_issued.days == 45

    def test_invoice_dates_zero_net_payment_term(self, db_session):
        """Test invoice with zero net_payment_term (due immediately on issuance)."""
        customer = _create_customer(db_session, "cust_gp_zero_npt")
        customer.invoice_grace_period = 3
        customer.net_payment_term = 0
        db_session.commit()
        db_session.refresh(customer)

        plan = _create_plan(db_session, "plan_gp_zero_npt", 10000)
        sub = _create_pending_subscription(
            db_session, customer, plan, "sub_gp_zero_npt", pay_in_advance=True
        )

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        invoice = invoices[0]

        # issued_at = billing_period_end + 3 days
        issued_to_period_end = invoice.issued_at - invoice.billing_period_end
        assert issued_to_period_end.days == 3

        # due_date = issued_at + 0 days (same as issued_at)
        assert invoice.due_date == invoice.issued_at

    def test_termination_invoice_respects_grace_period(self, db_session):
        """Test that termination invoices also respect grace period settings."""
        customer = _create_customer(db_session, "cust_gp_term")
        customer.invoice_grace_period = 7
        customer.net_payment_term = 60
        db_session.commit()
        db_session.refresh(customer)

        plan = _create_plan(db_session, "plan_gp_term", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_gp_term")

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id, "generate_invoice")

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        invoice = invoices[0]

        assert invoice.issued_at is not None
        assert invoice.due_date is not None
        # due_date = issued_at + 60 days
        diff = invoice.due_date - invoice.issued_at
        assert diff.days == 60

    def test_cancel_invoice_respects_grace_period(self, db_session):
        """Test that cancellation invoices respect grace period settings."""
        customer = _create_customer(db_session, "cust_gp_cancel")
        customer.invoice_grace_period = 10
        customer.net_payment_term = 15
        db_session.commit()
        db_session.refresh(customer)

        plan = _create_plan(db_session, "plan_gp_cancel", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_gp_cancel")

        service = SubscriptionLifecycleService(db_session)
        service.cancel_subscription(sub.id, "generate_invoice")

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        invoice = invoices[0]

        assert invoice.issued_at is not None
        assert invoice.due_date is not None
        diff = invoice.due_date - invoice.issued_at
        assert diff.days == 15

    def test_trial_end_invoice_respects_grace_period(self, db_session):
        """Test that trial end invoices respect grace period settings."""
        customer = _create_customer(db_session, "cust_gp_trial")
        customer.invoice_grace_period = 2
        customer.net_payment_term = 14
        db_session.commit()
        db_session.refresh(customer)

        plan = _create_plan(db_session, "plan_gp_trial", 10000)
        sub = _create_active_subscription(
            db_session,
            customer,
            plan,
            "sub_gp_trial",
            pay_in_advance=True,
            trial_period_days=14,
        )

        service = SubscriptionLifecycleService(db_session)
        service.process_trial_end(sub.id)

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        invoice = invoices[0]

        assert invoice.issued_at is not None
        assert invoice.due_date is not None
        diff = invoice.due_date - invoice.issued_at
        assert diff.days == 14

    def test_invoice_no_dates_when_customer_not_found(self, db_session):
        """Test invoice created without dates when customer lookup fails."""
        customer = _create_customer(db_session, "cust_gp_nocust")
        plan = _create_plan(db_session, "plan_gp_nocust", 10000)
        sub = _create_pending_subscription(
            db_session, customer, plan, "sub_gp_nocust", pay_in_advance=True
        )

        # Point customer_id to a non-existent UUID
        fake_cust_id = uuid.uuid4()
        db_session.execute(
            Subscription.__table__.update()
            .where(Subscription.id == sub.id)
            .values(customer_id=str(fake_cust_id))
        )
        db_session.commit()
        db_session.expire(sub)

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        invoice = invoices[0]
        # No customer found, so no grace period dates set
        assert invoice.issued_at is None
        assert invoice.due_date is None


class TestBillingTimeLifecycleInteractions:
    """Test that billing_time (calendar vs anniversary) correctly affects lifecycle operations."""

    def test_upgrade_anniversary_billing_calculates_correct_period(self, db_session):
        """Test upgrade with anniversary billing uses subscription start date for period calc."""
        customer = _create_customer(db_session, "cust_bt_up")
        plan_a = _create_plan(db_session, "plan_bt_up_a", 10000)
        plan_b = _create_plan(db_session, "plan_bt_up_b", 20000)
        sub = _create_active_subscription(
            db_session, customer, plan_a, "sub_bt_up", pay_in_advance=True
        )
        sub.billing_time = "anniversary"
        db_session.commit()
        db_session.refresh(sub)

        # Create existing invoice for credit note
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
        assert sub.billing_time == "anniversary"

        # Should have credit note
        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 1

    def test_terminate_anniversary_billing_prorates_correctly(self, db_session):
        """Test termination with anniversary billing generates correct prorated invoice."""
        customer = _create_customer(db_session, "cust_bt_term")
        plan = _create_plan(db_session, "plan_bt_term", 30000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_bt_term")
        sub.billing_time = "anniversary"
        db_session.commit()
        db_session.refresh(sub)

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id, "generate_invoice")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.TERMINATED.value

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        # Prorated amount should be less than full plan amount
        assert invoices[0].total < 30000

    def test_downgrade_end_of_period_anniversary_billing(self, db_session):
        """Test end-of-period downgrade with anniversary billing tracks correctly."""
        customer = _create_customer(db_session, "cust_bt_dg")
        plan_a = _create_plan(db_session, "plan_bt_dg_a", 20000)
        plan_b = _create_plan(db_session, "plan_bt_dg_b", 5000)
        sub = _create_active_subscription(db_session, customer, plan_a, "sub_bt_dg")
        sub.billing_time = "anniversary"
        db_session.commit()
        db_session.refresh(sub)

        service = SubscriptionLifecycleService(db_session)
        service.downgrade_plan(sub.id, plan_b.id, effective_at="end_of_period")

        db_session.refresh(sub)
        assert str(sub.plan_id) == str(plan_a.id)  # Not changed yet
        assert sub.downgraded_at is not None
        assert str(sub.previous_plan_id) == str(plan_b.id)  # Target plan
        assert sub.billing_time == "anniversary"


class TestPayInAdvanceInvoiceGeneration:
    """Test that pay_in_advance correctly generates invoices at period start."""

    def test_pay_in_advance_activation_invoice_has_full_amount(self, db_session):
        """Test pay_in_advance activation generates invoice with full plan amount."""
        customer = _create_customer(db_session, "cust_pia_full")
        plan = _create_plan(db_session, "plan_pia_full", 25000)
        sub = _create_pending_subscription(
            db_session, customer, plan, "sub_pia_full", pay_in_advance=True
        )

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        assert invoices[0].total == Decimal("25000")
        # Invoice should have proper billing period
        assert invoices[0].billing_period_start is not None
        assert invoices[0].billing_period_end is not None

    def test_pay_in_advance_upgrade_generates_both_credit_and_invoice(self, db_session):
        """Test upgrade with pay_in_advance generates credit note for old + invoice for new."""
        customer = _create_customer(db_session, "cust_pia_upgrade")
        plan_a = _create_plan(db_session, "plan_pia_upg_a", 10000)
        plan_b = _create_plan(db_session, "plan_pia_upg_b", 30000)
        sub = _create_active_subscription(
            db_session, customer, plan_a, "sub_pia_upgrade", pay_in_advance=True
        )

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

        # Verify credit note for old plan
        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 1
        assert "plan change" in credit_notes[0].description.lower()

        # Verify prorated invoice for new plan
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 2  # original + prorated

    def test_no_pay_in_advance_upgrade_skips_financials(self, db_session):
        """Test upgrade without pay_in_advance does not generate credit notes or invoices."""
        customer = _create_customer(db_session, "cust_nopia_up")
        plan_a = _create_plan(db_session, "plan_nopia_a", 10000)
        plan_b = _create_plan(db_session, "plan_nopia_b", 20000)
        sub = _create_active_subscription(
            db_session, customer, plan_a, "sub_nopia_up", pay_in_advance=False
        )

        service = SubscriptionLifecycleService(db_session)
        service.upgrade_plan(sub.id, plan_b.id)

        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 0

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0


class TestTrialActivationAndProcessing:
    """Test trial period lifecycle: activation with trial, and trial end processing."""

    def test_activate_with_trial_sets_active_but_no_invoice(self, db_session):
        """Test activating subscription with trial: becomes active but no invoice generated."""
        customer = _create_customer(db_session, "cust_trial_act")
        plan = _create_plan(db_session, "plan_trial_act", 20000)
        sub = _create_pending_subscription(
            db_session,
            customer,
            plan,
            "sub_trial_act",
            pay_in_advance=True,
            trial_period_days=14,
        )

        service = SubscriptionLifecycleService(db_session)
        service.activate_pending_subscription(sub.id)

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.ACTIVE.value
        assert sub.started_at is not None
        # No invoice during trial even with pay_in_advance
        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 0

    def test_trial_end_processing_generates_invoice_pay_in_advance(self, db_session):
        """Test processing trial end with pay_in_advance generates first invoice."""
        customer = _create_customer(db_session, "cust_trial_end_pia")
        plan = _create_plan(db_session, "plan_trial_end_pia", 15000)
        sub = _create_active_subscription(
            db_session,
            customer,
            plan,
            "sub_trial_end_pia",
            pay_in_advance=True,
            trial_period_days=14,
        )

        service = SubscriptionLifecycleService(db_session)
        service.process_trial_end(sub.id)

        db_session.refresh(sub)
        assert sub.trial_ended_at is not None

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        # Invoice should have proper description
        assert "post-trial" in invoices[0].line_items[0]["description"].lower()

    def test_trial_end_preserves_original_trial_ended_at(self, db_session):
        """Test calling process_trial_end twice preserves the original trial_ended_at timestamp."""
        customer = _create_customer(db_session, "cust_trial_idem")
        plan = _create_plan(db_session, "plan_trial_idem", 10000)
        sub = _create_active_subscription(
            db_session,
            customer,
            plan,
            "sub_trial_idem",
            trial_period_days=14,
        )

        service = SubscriptionLifecycleService(db_session)
        service.process_trial_end(sub.id)

        db_session.refresh(sub)
        original_ended_at = sub.trial_ended_at
        assert original_ended_at is not None

        # Second call should not overwrite trial_ended_at
        service.process_trial_end(sub.id)

        db_session.refresh(sub)
        assert sub.trial_ended_at.replace(tzinfo=None) == original_ended_at.replace(tzinfo=None)


class TestTerminationActionsComprehensive:
    """Comprehensive tests for all three termination actions with varied scenarios."""

    def test_terminate_generate_invoice_prorated_amount(self, db_session):
        """Test termination with generate_invoice creates prorated final invoice."""
        customer = _create_customer(db_session, "cust_term_prorate")
        plan = _create_plan(db_session, "plan_term_prorate", 30000)  # $300/month
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_prorate")

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id, "generate_invoice")

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1
        # Prorated amount should be less than full amount
        assert 0 < invoices[0].total < 30000

    def test_cancel_generate_credit_note_requires_invoice(self, db_session):
        """Test cancel with generate_credit_note only creates CN when invoice exists."""
        customer = _create_customer(db_session, "cust_can_cn_req")
        plan = _create_plan(db_session, "plan_can_cn_req", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_cn_req")

        # No existing invoice
        service = SubscriptionLifecycleService(db_session)
        service.cancel_subscription(sub.id, "generate_credit_note")

        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 0

    def test_terminate_credit_note_with_finalized_invoice(self, db_session):
        """Test terminate with credit_note works when only finalized invoice exists."""
        customer = _create_customer(db_session, "cust_term_cn_fin")
        plan = _create_plan(db_session, "plan_term_cn_fin", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_cn_fin")

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
        service.terminate_subscription(sub.id, "generate_credit_note")

        credit_notes = (
            db_session.query(CreditNote).filter(CreditNote.customer_id == customer.id).all()
        )
        assert len(credit_notes) == 1
        assert credit_notes[0].total_amount_cents > 0

    def test_cancel_default_action_generates_invoice(self, db_session):
        """Test cancel with default action (generate_invoice) generates an invoice."""
        customer = _create_customer(db_session, "cust_can_def")
        plan = _create_plan(db_session, "plan_can_def", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_def")

        service = SubscriptionLifecycleService(db_session)
        service.cancel_subscription(sub.id)

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.CANCELED.value

        invoices = db_session.query(Invoice).filter(Invoice.subscription_id == sub.id).all()
        assert len(invoices) == 1


class TestPauseSubscription:
    def test_pause_active_subscription(self, db_session):
        """Test pausing an active subscription."""
        customer = _create_customer(db_session, "cust_pause")
        plan = _create_plan(db_session, "plan_pause", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_pause")

        service = SubscriptionLifecycleService(db_session)
        service.pause_subscription(sub.id)

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.PAUSED.value
        assert sub.paused_at is not None

    def test_pause_not_found(self, db_session):
        """Test pausing non-existent subscription."""
        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.pause_subscription(uuid.uuid4())

    def test_pause_not_active(self, db_session):
        """Test pausing a non-active subscription raises error."""
        customer = _create_customer(db_session, "cust_pause_pend")
        plan = _create_plan(db_session, "plan_pause_pend")
        sub = _create_pending_subscription(db_session, customer, plan, "sub_pause_pend")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="active"):
            service.pause_subscription(sub.id)

    def test_pause_triggers_webhook(self, db_session):
        """Test pausing triggers subscription.paused webhook."""
        _create_webhook_endpoint(db_session)
        customer = _create_customer(db_session, "cust_pause_wh")
        plan = _create_plan(db_session, "plan_pause_wh")
        sub = _create_active_subscription(db_session, customer, plan, "sub_pause_wh")

        service = SubscriptionLifecycleService(db_session)
        service.pause_subscription(sub.id)

        from app.models.webhook import Webhook

        webhooks = (
            db_session.query(Webhook)
            .filter(Webhook.webhook_type == "subscription.paused")
            .all()
        )
        assert len(webhooks) == 1
        assert webhooks[0].payload["subscription_id"] == str(sub.id)

    def test_pause_already_paused(self, db_session):
        """Test pausing an already paused subscription raises error."""
        customer = _create_customer(db_session, "cust_pause_dup")
        plan = _create_plan(db_session, "plan_pause_dup")
        sub = _create_active_subscription(db_session, customer, plan, "sub_pause_dup")
        sub.status = SubscriptionStatus.PAUSED.value
        db_session.commit()
        db_session.refresh(sub)

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="active"):
            service.pause_subscription(sub.id)


class TestResumeSubscription:
    def test_resume_paused_subscription(self, db_session):
        """Test resuming a paused subscription."""
        customer = _create_customer(db_session, "cust_resume")
        plan = _create_plan(db_session, "plan_resume", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_resume")

        service = SubscriptionLifecycleService(db_session)
        service.pause_subscription(sub.id)

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.PAUSED.value

        service.resume_subscription(sub.id)

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.ACTIVE.value
        assert sub.paused_at is None
        assert sub.resumed_at is not None

    def test_resume_not_found(self, db_session):
        """Test resuming non-existent subscription."""
        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.resume_subscription(uuid.uuid4())

    def test_resume_not_paused(self, db_session):
        """Test resuming a non-paused subscription raises error."""
        customer = _create_customer(db_session, "cust_resume_act")
        plan = _create_plan(db_session, "plan_resume_act")
        sub = _create_active_subscription(db_session, customer, plan, "sub_resume_act")

        service = SubscriptionLifecycleService(db_session)
        with pytest.raises(ValueError, match="paused"):
            service.resume_subscription(sub.id)

    def test_resume_triggers_webhook(self, db_session):
        """Test resuming triggers subscription.resumed webhook."""
        _create_webhook_endpoint(db_session)
        customer = _create_customer(db_session, "cust_resume_wh")
        plan = _create_plan(db_session, "plan_resume_wh")
        sub = _create_active_subscription(db_session, customer, plan, "sub_resume_wh")

        service = SubscriptionLifecycleService(db_session)
        service.pause_subscription(sub.id)
        service.resume_subscription(sub.id)

        from app.models.webhook import Webhook

        webhooks = (
            db_session.query(Webhook)
            .filter(Webhook.webhook_type == "subscription.resumed")
            .all()
        )
        assert len(webhooks) == 1
        assert webhooks[0].payload["subscription_id"] == str(sub.id)


class TestTerminatePausedSubscription:
    def test_terminate_paused_subscription(self, db_session):
        """Test terminating a paused subscription."""
        customer = _create_customer(db_session, "cust_term_paused")
        plan = _create_plan(db_session, "plan_term_paused", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_term_paused")
        sub.status = SubscriptionStatus.PAUSED.value
        db_session.commit()
        db_session.refresh(sub)

        service = SubscriptionLifecycleService(db_session)
        service.terminate_subscription(sub.id, "skip")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.TERMINATED.value
        assert sub.ending_at is not None

    def test_cancel_paused_subscription(self, db_session):
        """Test canceling a paused subscription."""
        customer = _create_customer(db_session, "cust_can_paused")
        plan = _create_plan(db_session, "plan_can_paused", 10000)
        sub = _create_active_subscription(db_session, customer, plan, "sub_can_paused")
        sub.status = SubscriptionStatus.PAUSED.value
        db_session.commit()
        db_session.refresh(sub)

        service = SubscriptionLifecycleService(db_session)
        service.cancel_subscription(sub.id, "skip")

        db_session.refresh(sub)
        assert sub.status == SubscriptionStatus.CANCELED.value
        assert sub.canceled_at is not None


class TestWebhookEventTypes:
    def test_new_event_types_in_list(self):
        """Test that new subscription lifecycle events are in WEBHOOK_EVENT_TYPES."""
        from app.services.webhook_service import WEBHOOK_EVENT_TYPES

        assert "subscription.started" in WEBHOOK_EVENT_TYPES
        assert "subscription.paused" in WEBHOOK_EVENT_TYPES
        assert "subscription.resumed" in WEBHOOK_EVENT_TYPES
        assert "subscription.plan_changed" in WEBHOOK_EVENT_TYPES
        assert "subscription.trial_ended" in WEBHOOK_EVENT_TYPES
