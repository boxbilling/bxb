import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from arq import cron

from app.core.database import SessionLocal
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.item_repository import ItemRepository
from app.repositories.plan_repository import PlanRepository
from app.services.subscription_dates import SubscriptionDatesService
from app.services.subscription_lifecycle import SubscriptionLifecycleService
from app.services.webhook_service import WebhookService
from app.tasks import redis_settings

logger = logging.getLogger(__name__)


async def update_item_prices(ctx: dict[str, Any]) -> int:
    """Example task: apply a 10% discount to all items with quantity > 100."""
    db = SessionLocal()
    try:
        repo = ItemRepository(db)
        count = repo.apply_bulk_discount(min_quantity=100, discount=0.1)
        logger.info("Updated prices for %d items", count)
        return count
    finally:
        db.close()


async def retry_failed_webhooks_task(ctx: dict[str, Any]) -> int:
    """Background task: retry failed webhooks with exponential backoff.

    Runs every 5 minutes to find failed webhooks eligible for retry
    and re-delivers them.
    """
    db = SessionLocal()
    try:
        service = WebhookService(db)
        count = service.retry_failed_webhooks()
        if count > 0:
            logger.info("Retried %d failed webhooks", count)
        return count
    finally:
        db.close()


async def process_pending_downgrades_task(ctx: dict[str, Any]) -> int:
    """Background task: find subscriptions with pending downgrades whose billing period
    has ended, and execute the plan change.

    Runs daily.
    """
    db = SessionLocal()
    try:
        now = datetime.now(UTC)

        # Find active subscriptions with a pending downgrade
        subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE.value,
                Subscription.downgraded_at.isnot(None),
                Subscription.previous_plan_id.isnot(None),
            )
            .all()
        )

        dates_service = SubscriptionDatesService()
        plan_repo = PlanRepository(db)
        count = 0

        for sub in subscriptions:
            plan = plan_repo.get_by_id(UUID(str(sub.plan_id)))
            if not plan:
                continue
            interval = str(plan.interval)
            _, period_end = dates_service.calculate_billing_period(
                sub, interval, now
            )
            if now >= period_end:
                lifecycle = SubscriptionLifecycleService(db)
                lifecycle.execute_pending_downgrade(UUID(str(sub.id)))
                count += 1

        if count > 0:
            logger.info("Processed %d pending downgrades", count)
        return count
    finally:
        db.close()


async def process_trial_expirations_task(ctx: dict[str, Any]) -> int:
    """Background task: find active subscriptions whose trial period has expired
    but hasn't been processed yet.

    Runs hourly.
    """
    db = SessionLocal()
    try:
        now = datetime.now(UTC)

        # Find active subscriptions with trial that hasn't been processed
        subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE.value,
                Subscription.trial_period_days > 0,
                Subscription.trial_ended_at.is_(None),
            )
            .all()
        )

        dates_service = SubscriptionDatesService()
        count = 0

        for sub in subscriptions:
            trial_end = dates_service.trial_end_date(sub)
            if trial_end is not None and now >= trial_end:
                lifecycle = SubscriptionLifecycleService(db)
                lifecycle.process_trial_end(UUID(str(sub.id)))
                count += 1

        if count > 0:
            logger.info("Processed %d trial expirations", count)
        return count
    finally:
        db.close()


async def generate_periodic_invoices_task(ctx: dict[str, Any]) -> int:
    """Background task: find active subscriptions due for billing and generate invoices.

    For pay_in_advance subscriptions: generate invoice when the next billing period starts.
    For pay_in_arrear subscriptions: generate invoice when the current billing period ends.

    Runs hourly.
    """
    db = SessionLocal()
    try:
        now = datetime.now(UTC)

        # Find active subscriptions (not in trial)
        subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.status == SubscriptionStatus.ACTIVE.value,
            )
            .all()
        )

        dates_service = SubscriptionDatesService()
        plan_repo = PlanRepository(db)
        count = 0

        for sub in subscriptions:
            # Skip subscriptions still in trial
            if dates_service.is_in_trial(sub):
                continue

            plan = plan_repo.get_by_id(UUID(str(sub.plan_id)))
            if not plan or int(plan.amount_cents) <= 0:
                continue

            interval = str(plan.interval)
            next_billing = dates_service.next_billing_date(sub, interval)
            if next_billing is not None and now >= next_billing:
                lifecycle = SubscriptionLifecycleService(db)
                period_start, period_end = dates_service.calculate_billing_period(
                    sub, interval, now
                )
                amount_cents = int(plan.amount_cents)
                lifecycle._create_invoice(
                    sub,
                    plan,
                    period_start,
                    period_end,
                    amount_cents,
                    "Subscription fee",
                )
                count += 1

        if count > 0:
            logger.info("Generated %d periodic invoices", count)
        return count
    finally:
        db.close()


class WorkerSettings:
    functions = [
        update_item_prices,
        retry_failed_webhooks_task,
        process_pending_downgrades_task,
        process_trial_expirations_task,
        generate_periodic_invoices_task,
    ]
    cron_jobs = [
        cron(update_item_prices, hour=0, minute=0),  # midnight daily
        cron(
            retry_failed_webhooks_task,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
        ),
        cron(process_pending_downgrades_task, hour=0, minute=0),  # daily at midnight
        cron(process_trial_expirations_task, minute={0}),  # hourly
        cron(generate_periodic_invoices_task, minute={0}),  # hourly
    ]
    redis_settings = redis_settings
