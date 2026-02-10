from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings

# Redis connection settings
redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)


async def get_redis_pool():
    """Get or create Redis pool for arq"""
    return await create_pool(redis_settings)


async def enqueue_task(task_name: str, *args, **kwargs):
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
        return job
    finally:
        await pool.close()


# ===== Example Tasks =====
async def enqueue_task_ping():
    """Enqueue a simple ping task for testing"""
    return await enqueue_task("task_ping")
