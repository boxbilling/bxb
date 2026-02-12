import logging
from typing import Any

from arq import cron

from app.core.database import SessionLocal
from app.repositories.item_repository import ItemRepository
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


class WorkerSettings:
    functions = [update_item_prices, retry_failed_webhooks_task]
    cron_jobs = [
        cron(update_item_prices, hour=0, minute=0),  # midnight daily
        cron(
            retry_failed_webhooks_task,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
        ),
    ]
    redis_settings = redis_settings
