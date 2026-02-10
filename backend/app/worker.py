import logging

from arq import cron

from app.core.database import SessionLocal
from app.repositories.item_repository import ItemRepository
from app.tasks import redis_settings

logger = logging.getLogger(__name__)


async def update_item_prices(ctx: dict) -> int:
    """Example task: apply a 10% discount to all items with quantity > 100."""
    db = SessionLocal()
    try:
        repo = ItemRepository(db)
        count = repo.apply_bulk_discount(min_quantity=100, discount=0.1)
        logger.info("Updated prices for %d items", count)
        return count
    finally:
        db.close()


class WorkerSettings:
    functions = [update_item_prices]
    cron_jobs = [
        cron(update_item_prices, hour=0, minute=0),  # midnight daily
    ]
    redis_settings = redis_settings
