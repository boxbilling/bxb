from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job

from app.core.config import settings

# Redis connection settings
redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)


async def get_redis_pool() -> ArqRedis:
    """Get or create Redis pool for arq"""
    return await create_pool(redis_settings)


async def enqueue_task(task_name: str, *args: Any, **kwargs: Any) -> Job:
    """
    Enqueue a task to the arq worker.

    Args:
        task_name: Name of the task function
        *args: Positional arguments for the task
        **kwargs: Keyword arguments for the task

    Returns:
        Job object from arq
    """
    pool = await get_redis_pool()
    try:
        job = await pool.enqueue_job(task_name, *args, **kwargs)
        return job  # type: ignore[return-value]
    finally:
        await pool.close()


# ===== Example Tasks =====
async def enqueue_task_ping() -> Job:
    """Enqueue a simple ping task for testing"""
    return await enqueue_task("task_ping")


async def enqueue_retry_failed_webhooks() -> Job:
    """Enqueue a task to retry failed webhooks."""
    return await enqueue_task("retry_failed_webhooks_task")
