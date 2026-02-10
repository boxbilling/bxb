"""Tests for background tasks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks import enqueue_task, enqueue_task_ping, get_redis_pool


class TestTasks:
    @pytest.mark.asyncio
    async def test_get_redis_pool(self):
        """Test get_redis_pool creates a pool."""
        mock_pool = MagicMock()

        with patch("app.tasks.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_pool

            result = await get_redis_pool()

            assert result == mock_pool
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_task(self):
        """Test enqueue_task enqueues a job and closes the pool."""
        mock_job = MagicMock()
        mock_job.job_id = "job-123"

        mock_pool = MagicMock()
        mock_pool.enqueue_job = AsyncMock(return_value=mock_job)
        mock_pool.close = AsyncMock()

        with patch("app.tasks.get_redis_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool

            result = await enqueue_task("my_task", "arg1", kwarg1="value1")

            assert result == mock_job
            mock_pool.enqueue_job.assert_called_once_with("my_task", "arg1", kwarg1="value1")
            mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_task_closes_pool_on_error(self):
        """Test enqueue_task closes pool even when job enqueue fails."""
        mock_pool = MagicMock()
        mock_pool.enqueue_job = AsyncMock(side_effect=Exception("Redis error"))
        mock_pool.close = AsyncMock()

        with patch("app.tasks.get_redis_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool

            with pytest.raises(Exception, match="Redis error"):
                await enqueue_task("failing_task")

            # Pool should still be closed
            mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_task_ping(self):
        """Test enqueue_task_ping helper function."""
        mock_job = MagicMock()
        mock_job.job_id = "ping-job-456"

        with patch("app.tasks.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_job

            result = await enqueue_task_ping()

            assert result == mock_job
            mock_enqueue.assert_called_once_with("task_ping")
