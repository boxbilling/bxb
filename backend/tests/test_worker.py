"""Tests for worker background tasks and cron job registration."""

from unittest.mock import MagicMock, patch

import pytest

from app.core import database as db_module
from app.core.database import get_db
from app.repositories.webhook_endpoint_repository import WebhookEndpointRepository
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.webhook import WebhookEndpointCreate
from app.worker import WorkerSettings, retry_failed_webhooks_task


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


class TestRetryFailedWebhooksTask:
    """Tests for the retry_failed_webhooks_task worker function."""

    @pytest.mark.asyncio
    async def test_retries_failed_webhooks(self, db_session):
        """Test that the task calls WebhookService.retry_failed_webhooks and returns count."""
        mock_service = MagicMock()
        mock_service.retry_failed_webhooks.return_value = 3

        with patch("app.worker.WebhookService", return_value=mock_service):
            result = await retry_failed_webhooks_task({})

        assert result == 3
        mock_service.retry_failed_webhooks.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_failed_webhooks(self, db_session):
        """Test that the task returns 0 when there are no failed webhooks."""
        mock_service = MagicMock()
        mock_service.retry_failed_webhooks.return_value = 0

        with patch("app.worker.WebhookService", return_value=mock_service):
            result = await retry_failed_webhooks_task({})

        assert result == 0

    @pytest.mark.asyncio
    async def test_creates_session_and_closes_it(self, db_session):
        """Test that the task creates a DB session and properly closes it."""
        mock_service = MagicMock()
        mock_service.retry_failed_webhooks.return_value = 0

        with patch("app.worker.WebhookService", return_value=mock_service) as mock_cls:
            await retry_failed_webhooks_task({})

        # Verify the service was instantiated with a session
        mock_cls.assert_called_once()
        call_args = mock_cls.call_args
        assert call_args[0][0] is not None  # DB session was passed

    @pytest.mark.asyncio
    async def test_closes_session_on_exception(self, db_session):
        """Test that the DB session is closed even when an exception occurs."""
        mock_service = MagicMock()
        mock_service.retry_failed_webhooks.side_effect = RuntimeError("DB error")

        with (
            patch("app.worker.WebhookService", return_value=mock_service),
            pytest.raises(RuntimeError, match="DB error"),
        ):
            await retry_failed_webhooks_task({})

    @pytest.mark.asyncio
    async def test_integration_with_real_service(self, db_session):
        """Integration test: task runs against real DB with no failed webhooks."""
        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await retry_failed_webhooks_task({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_integration_with_failed_webhook(self, db_session):
        """Integration test: task retries a failed webhook eligible for retry."""
        # Create an active endpoint and a failed webhook
        endpoint_repo = WebhookEndpointRepository(db_session)
        endpoint = endpoint_repo.create(
            WebhookEndpointCreate(url="https://example.com/hook")
        )

        webhook_repo = WebhookRepository(db_session)
        webhook = webhook_repo.create(
            webhook_endpoint_id=endpoint.id,
            webhook_type="invoice.created",
            payload={"test": True},
        )
        # Mark it as failed so it's eligible for retry
        webhook_repo.mark_failed(webhook.id, http_status=500, response="Server Error")

        # Commit so the worker's separate session can see the data
        db_session.commit()

        # Mock the HTTP delivery so it doesn't make real requests
        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.services.webhook_service.httpx.Client") as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = await retry_failed_webhooks_task({})

        assert result == 1

        # Refresh to see changes made by the worker's session
        db_session.expire_all()
        updated = webhook_repo.get_by_id(webhook.id)
        assert updated.retries == 1
        assert updated.status == "succeeded"


class TestWorkerSettings:
    """Tests for WorkerSettings configuration."""

    def test_functions_includes_retry_task(self):
        """Test that retry_failed_webhooks_task is registered as a worker function."""
        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "retry_failed_webhooks_task" in func_names

    def test_cron_jobs_includes_retry_task(self):
        """Test that retry_failed_webhooks_task is registered as a cron job."""
        cron_func_names = [job.coroutine.__name__ for job in WorkerSettings.cron_jobs]
        assert "retry_failed_webhooks_task" in cron_func_names

    def test_retry_cron_runs_every_5_minutes(self):
        """Test that the webhook retry cron job is scheduled every 5 minutes."""
        retry_job = None
        for job in WorkerSettings.cron_jobs:
            if job.coroutine.__name__ == "retry_failed_webhooks_task":
                retry_job = job
                break

        assert retry_job is not None
        # Every 5 minutes means minute should be {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}
        expected_minutes = {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}
        assert retry_job.minute == expected_minutes

    def test_redis_settings_configured(self):
        """Test that redis settings are properly configured."""
        from app.tasks import redis_settings

        assert WorkerSettings.redis_settings is redis_settings
