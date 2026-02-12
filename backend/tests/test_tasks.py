"""Tests for background tasks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks import (
    enqueue_check_dunning,
    enqueue_check_usage_thresholds,
    enqueue_generate_periodic_invoices,
    enqueue_process_payment_requests,
    enqueue_process_pending_downgrades,
    enqueue_process_trial_expirations,
    enqueue_retry_failed_webhooks,
    enqueue_task,
    enqueue_task_ping,
    get_redis_pool,
)


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

    @pytest.mark.asyncio
    async def test_enqueue_retry_failed_webhooks(self):
        """Test enqueue_retry_failed_webhooks helper function."""
        mock_job = MagicMock()
        mock_job.job_id = "retry-job-789"

        with patch("app.tasks.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_job

            result = await enqueue_retry_failed_webhooks()

            assert result == mock_job
            mock_enqueue.assert_called_once_with("retry_failed_webhooks_task")

    @pytest.mark.asyncio
    async def test_enqueue_process_pending_downgrades(self):
        """Test enqueue_process_pending_downgrades helper function."""
        mock_job = MagicMock()
        mock_job.job_id = "downgrades-job-001"

        with patch("app.tasks.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_job

            result = await enqueue_process_pending_downgrades()

            assert result == mock_job
            mock_enqueue.assert_called_once_with("process_pending_downgrades_task")

    @pytest.mark.asyncio
    async def test_enqueue_process_trial_expirations(self):
        """Test enqueue_process_trial_expirations helper function."""
        mock_job = MagicMock()
        mock_job.job_id = "trials-job-002"

        with patch("app.tasks.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_job

            result = await enqueue_process_trial_expirations()

            assert result == mock_job
            mock_enqueue.assert_called_once_with("process_trial_expirations_task")

    @pytest.mark.asyncio
    async def test_enqueue_generate_periodic_invoices(self):
        """Test enqueue_generate_periodic_invoices helper function."""
        mock_job = MagicMock()
        mock_job.job_id = "invoices-job-003"

        with patch("app.tasks.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_job

            result = await enqueue_generate_periodic_invoices()

            assert result == mock_job
            mock_enqueue.assert_called_once_with("generate_periodic_invoices_task")

    @pytest.mark.asyncio
    async def test_enqueue_check_dunning(self):
        """Test enqueue_check_dunning helper function."""
        mock_job = MagicMock()
        mock_job.job_id = "dunning-job-004"

        with patch("app.tasks.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_job

            result = await enqueue_check_dunning()

            assert result == mock_job
            mock_enqueue.assert_called_once_with("check_dunning_task")

    @pytest.mark.asyncio
    async def test_enqueue_process_payment_requests(self):
        """Test enqueue_process_payment_requests helper function."""
        mock_job = MagicMock()
        mock_job.job_id = "payment-requests-job-005"

        with patch("app.tasks.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_job

            result = await enqueue_process_payment_requests()

            assert result == mock_job
            mock_enqueue.assert_called_once_with("process_payment_requests_task")

    @pytest.mark.asyncio
    async def test_enqueue_check_usage_thresholds(self):
        """Test enqueue_check_usage_thresholds helper function."""
        mock_job = MagicMock()
        mock_job.job_id = "thresholds-job-006"

        with patch("app.tasks.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_job

            result = await enqueue_check_usage_thresholds("sub-uuid-123")

            assert result == mock_job
            mock_enqueue.assert_called_once_with(
                "check_usage_thresholds_task", "sub-uuid-123"
            )
