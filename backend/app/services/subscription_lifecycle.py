"""Service for subscription lifecycle management: upgrades, downgrades, activation, and trials."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.credit_note import CreditNoteReason, CreditNoteType
from app.models.invoice import InvoiceStatus
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.credit_note_repository import CreditNoteRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.credit_note import CreditNoteCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.services.subscription_dates import SubscriptionDatesService
from app.services.webhook_service import WebhookService


class SubscriptionLifecycleService:
    """Service for managing subscription lifecycle events."""

    def __init__(self, db: Session):
        self.db = db
        self.subscription_repo = SubscriptionRepository(db)
        self.plan_repo = PlanRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.credit_note_repo = CreditNoteRepository(db)
        self.dates_service = SubscriptionDatesService()
        self.webhook_service = WebhookService(db)

    def upgrade_plan(self, subscription_id: UUID, new_plan_id: UUID) -> None:
        """Upgrade a subscription to a new plan (immediate effect).

        1. Validate new plan exists and is different from current
        2. If pay_in_advance: generate credit note for remaining period on old plan
        3. Set previous_plan_id to current plan, update plan_id to new plan
        4. If pay_in_advance: generate prorated invoice for remaining period on new plan
        5. Trigger subscription.plan_changed webhook
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        if subscription.status != SubscriptionStatus.ACTIVE.value:
            raise ValueError("Can only upgrade active subscriptions")

        if str(subscription.plan_id) == str(new_plan_id):
            raise ValueError("New plan must be different from current plan")

        new_plan = self.plan_repo.get_by_id(new_plan_id)
        if not new_plan:
            raise ValueError(f"Plan {new_plan_id} not found")

        old_plan = self.plan_repo.get_by_id(UUID(str(subscription.plan_id)))
        now = datetime.now(UTC)

        if subscription.pay_in_advance and old_plan:
            interval = str(old_plan.interval)
            period_start, period_end = self.dates_service.calculate_billing_period(
                subscription, interval, now
            )
            self._generate_plan_change_credit_note(
                subscription, old_plan, period_start, period_end, now
            )

        # Update subscription
        old_plan_id = subscription.plan_id
        subscription.previous_plan_id = old_plan_id
        subscription.plan_id = new_plan_id  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(subscription)

        if subscription.pay_in_advance:
            interval = str(new_plan.interval)
            period_start, period_end = self.dates_service.calculate_billing_period(
                subscription, interval, now
            )
            self._generate_prorated_invoice(
                subscription, new_plan, period_start, period_end, now
            )

        self.webhook_service.send_webhook(
            webhook_type="subscription.plan_changed",
            object_type="subscription",
            object_id=subscription.id,  # type: ignore[arg-type]
            payload={
                "subscription_id": str(subscription.id),
                "previous_plan_id": str(old_plan_id),
                "new_plan_id": str(new_plan_id),
                "change_type": "upgrade",
            },
        )

    def downgrade_plan(
        self,
        subscription_id: UUID,
        new_plan_id: UUID,
        effective_at: str = "end_of_period",
    ) -> None:
        """Downgrade a subscription to a new plan.

        If effective_at="end_of_period": schedule plan change at period end.
        If effective_at="immediate": same as upgrade but with downgrade tracking.
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        if subscription.status != SubscriptionStatus.ACTIVE.value:
            raise ValueError("Can only downgrade active subscriptions")

        if str(subscription.plan_id) == str(new_plan_id):
            raise ValueError("New plan must be different from current plan")

        new_plan = self.plan_repo.get_by_id(new_plan_id)
        if not new_plan:
            raise ValueError(f"Plan {new_plan_id} not found")

        now = datetime.now(UTC)

        if effective_at == "end_of_period":
            # Schedule downgrade for end of period
            subscription.downgraded_at = now  # type: ignore[assignment]
            subscription.previous_plan_id = new_plan_id  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(subscription)

            self.webhook_service.send_webhook(
                webhook_type="subscription.plan_changed",
                object_type="subscription",
                object_id=subscription.id,  # type: ignore[arg-type]
                payload={
                    "subscription_id": str(subscription.id),
                    "previous_plan_id": str(subscription.plan_id),
                    "new_plan_id": str(new_plan_id),
                    "change_type": "downgrade",
                    "effective_at": "end_of_period",
                },
            )
        else:
            # Immediate downgrade - similar to upgrade
            old_plan = self.plan_repo.get_by_id(UUID(str(subscription.plan_id)))

            if subscription.pay_in_advance and old_plan:
                interval = str(old_plan.interval)
                period_start, period_end = self.dates_service.calculate_billing_period(
                    subscription, interval, now
                )
                self._generate_plan_change_credit_note(
                    subscription, old_plan, period_start, period_end, now
                )

            old_plan_id = subscription.plan_id
            subscription.previous_plan_id = old_plan_id
            subscription.plan_id = new_plan_id  # type: ignore[assignment]
            subscription.downgraded_at = now  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(subscription)

            if subscription.pay_in_advance:
                interval = str(new_plan.interval)
                period_start, period_end = self.dates_service.calculate_billing_period(
                    subscription, interval, now
                )
                self._generate_prorated_invoice(
                    subscription, new_plan, period_start, period_end, now
                )

            self.webhook_service.send_webhook(
                webhook_type="subscription.plan_changed",
                object_type="subscription",
                object_id=subscription.id,  # type: ignore[arg-type]
                payload={
                    "subscription_id": str(subscription.id),
                    "previous_plan_id": str(old_plan_id),
                    "new_plan_id": str(new_plan_id),
                    "change_type": "downgrade",
                    "effective_at": "immediate",
                },
            )

    def activate_pending_subscription(self, subscription_id: UUID) -> None:
        """Activate a pending subscription.

        1. Set status=active, started_at=now
        2. If trial_period_days > 0: don't bill until trial ends
        3. If pay_in_advance and no trial: generate first invoice
        4. Trigger subscription.started webhook
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        if subscription.status != SubscriptionStatus.PENDING.value:
            raise ValueError("Can only activate pending subscriptions")

        now = datetime.now(UTC)
        subscription.status = SubscriptionStatus.ACTIVE.value  # type: ignore[assignment]
        subscription.started_at = now  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(subscription)

        has_trial = subscription.trial_period_days and subscription.trial_period_days > 0

        if subscription.pay_in_advance and not has_trial:
            plan = self.plan_repo.get_by_id(UUID(str(subscription.plan_id)))
            if plan:
                interval = str(plan.interval)
                period_start, period_end = self.dates_service.calculate_billing_period(
                    subscription, interval, now
                )
                amount_cents = int(plan.amount_cents)
                if amount_cents > 0:
                    self._create_invoice(
                        subscription,
                        plan,
                        period_start,
                        period_end,
                        amount_cents,
                        "Subscription fee",
                    )

        self.webhook_service.send_webhook(
            webhook_type="subscription.started",
            object_type="subscription",
            object_id=subscription.id,  # type: ignore[arg-type]
            payload={"subscription_id": str(subscription.id)},
        )

    def process_trial_end(self, subscription_id: UUID) -> None:
        """Process the end of a trial period.

        1. Set trial_ended_at=now if not already set
        2. Generate first invoice (pay_in_advance) or mark for next billing cycle
        3. Trigger subscription.trial_ended webhook
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        if subscription.status != SubscriptionStatus.ACTIVE.value:
            raise ValueError("Can only process trial end for active subscriptions")

        now = datetime.now(UTC)

        if not subscription.trial_ended_at:
            subscription.trial_ended_at = now  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(subscription)

        if subscription.pay_in_advance:
            plan = self.plan_repo.get_by_id(UUID(str(subscription.plan_id)))
            if plan:
                interval = str(plan.interval)
                period_start, period_end = self.dates_service.calculate_billing_period(
                    subscription, interval, now
                )
                amount_cents = int(plan.amount_cents)
                if amount_cents > 0:
                    self._create_invoice(
                        subscription,
                        plan,
                        period_start,
                        period_end,
                        amount_cents,
                        "Subscription fee (post-trial)",
                    )

        self.webhook_service.send_webhook(
            webhook_type="subscription.trial_ended",
            object_type="subscription",
            object_id=subscription.id,  # type: ignore[arg-type]
            payload={"subscription_id": str(subscription.id)},
        )

    def _generate_plan_change_credit_note(
        self,
        subscription: Subscription,
        plan: Plan,
        period_start: datetime,
        period_end: datetime,
        change_date: datetime,
    ) -> None:
        """Generate a credit note for remaining period on old plan after a plan change."""
        amount_cents = int(plan.amount_cents)
        prorated = self.dates_service.prorate_amount(
            amount_cents, period_start, period_end, change_date, period_end
        )
        if prorated <= 0:
            return

        # Find an existing invoice for this subscription/period
        customer_id = UUID(str(subscription.customer_id))
        subscription_id = UUID(str(subscription.id))
        invoices = self.invoice_repo.get_all(
            subscription_id=subscription_id,
            status=InvoiceStatus.DRAFT,
        )
        if not invoices:
            invoices = self.invoice_repo.get_all(
                subscription_id=subscription_id,
                status=InvoiceStatus.FINALIZED,
            )

        if not invoices:
            return

        invoice = invoices[0]
        cn_number = f"CN-{datetime.now(UTC).strftime('%Y%m%d')}-{str(subscription_id)[:8]}"
        credit_note_data = CreditNoteCreate(
            number=cn_number,
            invoice_id=UUID(str(invoice.id)),
            customer_id=customer_id,
            credit_note_type=CreditNoteType.CREDIT,
            reason=CreditNoteReason.ORDER_CHANGE,
            description=f"Credit for plan change - remaining period on {plan.name}",
            credit_amount_cents=Decimal(str(prorated)),
            total_amount_cents=Decimal(str(prorated)),
            currency=str(plan.currency),
        )
        self.credit_note_repo.create(credit_note_data)

    def _generate_prorated_invoice(
        self,
        subscription: Subscription,
        plan: Plan,
        period_start: datetime,
        period_end: datetime,
        change_date: datetime,
    ) -> None:
        """Generate a prorated invoice for remaining period on new plan after a plan change."""
        amount_cents = int(plan.amount_cents)
        prorated = self.dates_service.prorate_amount(
            amount_cents, period_start, period_end, change_date, period_end
        )
        if prorated <= 0:
            return

        self._create_invoice(
            subscription,
            plan,
            period_start,
            period_end,
            prorated,
            f"Prorated subscription fee - {plan.name}",
        )

    def _create_invoice(
        self,
        subscription: Subscription,
        plan: Plan,
        period_start: datetime,
        period_end: datetime,
        amount_cents: int,
        description: str,
    ) -> None:
        """Create an invoice for a subscription."""
        line_item = InvoiceLineItem(
            description=description,
            quantity=Decimal("1"),
            unit_price=Decimal(str(amount_cents)),
            amount=Decimal(str(amount_cents)),
        )
        invoice_data = InvoiceCreate(
            customer_id=UUID(str(subscription.customer_id)),
            subscription_id=UUID(str(subscription.id)),
            billing_period_start=period_start,
            billing_period_end=period_end,
            currency=str(plan.currency),
            line_items=[line_item],
        )
        self.invoice_repo.create(invoice_data)

    def execute_pending_downgrade(self, subscription_id: UUID) -> None:
        """Execute a pending downgrade (called by background job).

        Swaps plan_id with previous_plan_id (which stored the target plan),
        clears downgrade tracking fields.
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        if not subscription.downgraded_at or not subscription.previous_plan_id:
            raise ValueError("No pending downgrade for this subscription")

        new_plan_id = subscription.previous_plan_id
        old_plan_id = subscription.plan_id

        subscription.plan_id = new_plan_id
        subscription.previous_plan_id = old_plan_id
        subscription.downgraded_at = None  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(subscription)

        self.webhook_service.send_webhook(
            webhook_type="subscription.plan_changed",
            object_type="subscription",
            object_id=subscription.id,  # type: ignore[arg-type]
            payload={
                "subscription_id": str(subscription.id),
                "previous_plan_id": str(old_plan_id),
                "new_plan_id": str(new_plan_id),
                "change_type": "downgrade_executed",
            },
        )
