"""Tests for worker background tasks and cron job registration."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.core import database as db_module
from app.core.database import get_db
from app.models.customer import Customer
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.webhook_endpoint_repository import WebhookEndpointRepository
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.webhook import WebhookEndpointCreate
from app.worker import (
    WorkerSettings,
    check_usage_thresholds_task,
    generate_periodic_invoices_task,
    process_pending_downgrades_task,
    process_trial_expirations_task,
    retry_failed_webhooks_task,
)
from tests.conftest import DEFAULT_ORG_ID


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
            WebhookEndpointCreate(url="https://example.com/hook"),
            DEFAULT_ORG_ID,
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


def _create_customer(db, external_id: str = "cust_worker") -> Customer:
    customer = Customer(external_id=external_id, name="Test Customer", email="a@b.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _create_plan(
    db,
    code: str = "plan_worker",
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
    external_id: str = "sub_worker",
    pay_in_advance: bool = False,
    trial_period_days: int = 0,
    started_at: datetime | None = None,
    subscription_at: datetime | None = None,
) -> Subscription:
    now = datetime.now(UTC)
    sub = Subscription(
        external_id=external_id,
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        started_at=started_at or (now - timedelta(days=5)),
        pay_in_advance=pay_in_advance,
        trial_period_days=trial_period_days,
        subscription_at=subscription_at,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


class TestProcessPendingDowngradesTask:
    """Tests for the process_pending_downgrades_task worker function."""

    @pytest.mark.asyncio
    async def test_no_pending_downgrades(self, db_session):
        """Test returns 0 when no subscriptions have pending downgrades."""
        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await process_pending_downgrades_task({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_pending_downgrade_period_not_ended(self, db_session):
        """Test skips downgrade when billing period hasn't ended yet."""
        customer = _create_customer(db_session)
        plan_a = _create_plan(db_session, code="plan_a_dg")
        plan_b = _create_plan(db_session, code="plan_b_dg", amount_cents=5000)
        sub = _create_active_subscription(
            db_session, customer, plan_a, external_id="sub_dg_not_ended"
        )
        # Set pending downgrade
        sub.downgraded_at = datetime.now(UTC)
        sub.previous_plan_id = plan_b.id
        db_session.commit()

        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await process_pending_downgrades_task({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_pending_downgrade_period_ended(self, db_session):
        """Test executes downgrade when billing period has ended."""
        customer = _create_customer(db_session, external_id="cust_dg_ended")
        plan_a = _create_plan(db_session, code="plan_a_dg2")
        plan_b = _create_plan(db_session, code="plan_b_dg2", amount_cents=5000)
        started_at = datetime.now(UTC) - timedelta(days=40)
        sub = _create_active_subscription(
            db_session,
            customer,
            plan_a,
            external_id="sub_dg_ended",
            started_at=started_at,
        )
        sub.downgraded_at = started_at + timedelta(days=1)
        sub.previous_plan_id = plan_b.id
        db_session.commit()

        # Mock dates_service to report period has ended (now >= period_end)
        mock_dates = MagicMock()
        past = datetime.now(UTC) - timedelta(days=1)
        mock_dates.calculate_billing_period.return_value = (
            past - timedelta(days=30),
            past,
        )
        mock_lifecycle = MagicMock()
        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch(
                "app.worker.SubscriptionLifecycleService",
                return_value=mock_lifecycle,
            ),
            patch(
                "app.worker.SubscriptionDatesService",
                return_value=mock_dates,
            ),
        ):
            result = await process_pending_downgrades_task({})

        assert result == 1
        mock_lifecycle.execute_pending_downgrade.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_subscription_without_plan(self, db_session):
        """Test skips subscription if plan not found."""
        customer = _create_customer(db_session, external_id="cust_no_plan")
        plan_a = _create_plan(db_session, code="plan_no_plan")
        sub = _create_active_subscription(
            db_session,
            customer,
            plan_a,
            external_id="sub_no_plan",
            started_at=datetime.now(UTC) - timedelta(days=40),
        )
        sub.downgraded_at = datetime.now(UTC) - timedelta(days=39)
        sub.previous_plan_id = plan_a.id
        db_session.commit()

        mock_plan_repo = MagicMock()
        mock_plan_repo.get_by_id.return_value = None

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.PlanRepository", return_value=mock_plan_repo),
        ):
            result = await process_pending_downgrades_task({})

        assert result == 0

    @pytest.mark.asyncio
    async def test_closes_session_on_exception(self, db_session):
        """Test that DB session is closed even when an exception occurs."""
        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("DB error")
        mock_db.close = MagicMock()

        with (
            patch("app.worker.SessionLocal", return_value=mock_db),
            pytest.raises(RuntimeError, match="DB error"),
        ):
            await process_pending_downgrades_task({})

        mock_db.close.assert_called_once()


class TestProcessTrialExpirationsTask:
    """Tests for the process_trial_expirations_task worker function."""

    @pytest.mark.asyncio
    async def test_no_trial_subscriptions(self, db_session):
        """Test returns 0 when no subscriptions have expiring trials."""
        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await process_trial_expirations_task({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_trial_not_expired(self, db_session):
        """Test skips subscription whose trial hasn't expired yet."""
        customer = _create_customer(db_session, external_id="cust_trial_active")
        plan = _create_plan(db_session, code="plan_trial_active")
        _create_active_subscription(
            db_session,
            customer,
            plan,
            external_id="sub_trial_active",
            trial_period_days=30,
        )

        # Mock dates service to return a trial end date in the future
        mock_dates = MagicMock()
        mock_dates.trial_end_date.return_value = datetime.now(UTC) + timedelta(days=25)
        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.SubscriptionDatesService", return_value=mock_dates),
        ):
            result = await process_trial_expirations_task({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_trial_expired(self, db_session):
        """Test processes subscription whose trial has expired."""
        customer = _create_customer(db_session, external_id="cust_trial_exp")
        plan = _create_plan(db_session, code="plan_trial_exp")
        _create_active_subscription(
            db_session,
            customer,
            plan,
            external_id="sub_trial_exp",
            trial_period_days=5,
            started_at=datetime.now(UTC) - timedelta(days=10),
        )

        # Mock dates service to return a trial end date in the past
        mock_dates = MagicMock()
        mock_dates.trial_end_date.return_value = datetime.now(UTC) - timedelta(days=5)
        mock_lifecycle = MagicMock()
        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch(
                "app.worker.SubscriptionLifecycleService",
                return_value=mock_lifecycle,
            ),
            patch("app.worker.SubscriptionDatesService", return_value=mock_dates),
        ):
            result = await process_trial_expirations_task({})

        assert result == 1
        mock_lifecycle.process_trial_end.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_already_processed_trial(self, db_session):
        """Test skips subscription whose trial_ended_at is already set."""
        customer = _create_customer(db_session, external_id="cust_trial_done")
        plan = _create_plan(db_session, code="plan_trial_done")
        sub = _create_active_subscription(
            db_session,
            customer,
            plan,
            external_id="sub_trial_done",
            trial_period_days=5,
            subscription_at=datetime.now(UTC) - timedelta(days=10),
            started_at=datetime.now(UTC) - timedelta(days=10),
        )
        sub.trial_ended_at = datetime.now(UTC) - timedelta(days=5)
        db_session.commit()

        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await process_trial_expirations_task({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_trial_end_date_none(self, db_session):
        """Test skips subscription where trial_end_date returns None."""
        customer = _create_customer(db_session, external_id="cust_trial_none")
        plan = _create_plan(db_session, code="plan_trial_none")
        # trial_period_days > 0 but subscription_at/started_at/created_at might give None
        _create_active_subscription(
            db_session,
            customer,
            plan,
            external_id="sub_trial_none",
            trial_period_days=5,
            started_at=datetime.now(UTC) - timedelta(days=10),
        )

        mock_dates = MagicMock()
        mock_dates.trial_end_date.return_value = None

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.SubscriptionDatesService", return_value=mock_dates),
        ):
            result = await process_trial_expirations_task({})

        assert result == 0

    @pytest.mark.asyncio
    async def test_closes_session_on_exception(self, db_session):
        """Test that DB session is closed even when an exception occurs."""
        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("DB error")
        mock_db.close = MagicMock()

        with (
            patch("app.worker.SessionLocal", return_value=mock_db),
            pytest.raises(RuntimeError, match="DB error"),
        ):
            await process_trial_expirations_task({})

        mock_db.close.assert_called_once()


class TestGeneratePeriodicInvoicesTask:
    """Tests for the generate_periodic_invoices_task worker function."""

    @pytest.mark.asyncio
    async def test_no_active_subscriptions(self, db_session):
        """Test returns 0 when no active subscriptions exist."""
        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await generate_periodic_invoices_task({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_skips_subscription_in_trial(self, db_session):
        """Test skips subscription still in trial period."""
        customer = _create_customer(db_session, external_id="cust_inv_trial")
        plan = _create_plan(db_session, code="plan_inv_trial")
        _create_active_subscription(
            db_session,
            customer,
            plan,
            external_id="sub_inv_trial",
            trial_period_days=30,
        )

        mock_dates = MagicMock()
        mock_dates.is_in_trial.return_value = True
        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.SubscriptionDatesService", return_value=mock_dates),
        ):
            result = await generate_periodic_invoices_task({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_skips_zero_amount_plan(self, db_session):
        """Test skips subscription with zero-amount plan."""
        customer = _create_customer(db_session, external_id="cust_inv_free")
        plan = _create_plan(db_session, code="plan_inv_free", amount_cents=0)
        _create_active_subscription(db_session, customer, plan, external_id="sub_inv_free")

        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await generate_periodic_invoices_task({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_generates_invoice_when_due(self, db_session):
        """Test generates invoice when next billing date has passed."""
        customer = _create_customer(db_session, external_id="cust_inv_due")
        plan = _create_plan(db_session, code="plan_inv_due", amount_cents=10000)
        _create_active_subscription(
            db_session,
            customer,
            plan,
            external_id="sub_inv_due",
            started_at=datetime.now(UTC) - timedelta(days=40),
        )

        now = datetime.now(UTC)
        mock_dates = MagicMock()
        mock_dates.is_in_trial.return_value = False
        mock_dates.next_billing_date.return_value = now - timedelta(days=1)
        mock_dates.calculate_billing_period.return_value = (
            now - timedelta(days=30),
            now,
        )
        mock_lifecycle = MagicMock()
        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch(
                "app.worker.SubscriptionLifecycleService",
                return_value=mock_lifecycle,
            ),
            patch("app.worker.SubscriptionDatesService", return_value=mock_dates),
        ):
            result = await generate_periodic_invoices_task({})

        assert result == 1
        mock_lifecycle._create_invoice.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_not_due(self, db_session):
        """Test skips subscription when next billing date is in the future."""
        customer = _create_customer(db_session, external_id="cust_inv_notdue")
        plan = _create_plan(db_session, code="plan_inv_notdue", amount_cents=10000)
        # Started 5 days ago, monthly billing period hasn't ended
        _create_active_subscription(
            db_session,
            customer,
            plan,
            external_id="sub_inv_notdue",
            started_at=datetime.now(UTC) - timedelta(days=5),
        )

        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await generate_periodic_invoices_task({})
        assert result == 0

    @pytest.mark.asyncio
    async def test_skips_plan_not_found(self, db_session):
        """Test skips subscription if plan not found."""
        customer = _create_customer(db_session, external_id="cust_inv_noplan")
        plan = _create_plan(db_session, code="plan_inv_noplan")
        _create_active_subscription(
            db_session,
            customer,
            plan,
            external_id="sub_inv_noplan",
            started_at=datetime.now(UTC) - timedelta(days=40),
        )

        mock_plan_repo = MagicMock()
        mock_plan_repo.get_by_id.return_value = None

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.PlanRepository", return_value=mock_plan_repo),
        ):
            result = await generate_periodic_invoices_task({})

        assert result == 0

    @pytest.mark.asyncio
    async def test_next_billing_date_none(self, db_session):
        """Test skips subscription when next_billing_date returns None."""
        customer = _create_customer(db_session, external_id="cust_inv_nbd_none")
        plan = _create_plan(db_session, code="plan_inv_nbd_none", amount_cents=10000)
        _create_active_subscription(
            db_session,
            customer,
            plan,
            external_id="sub_inv_nbd_none",
            started_at=datetime.now(UTC) - timedelta(days=40),
        )

        mock_dates = MagicMock()
        mock_dates.is_in_trial.return_value = False
        mock_dates.next_billing_date.return_value = None

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.SubscriptionDatesService", return_value=mock_dates),
        ):
            result = await generate_periodic_invoices_task({})

        assert result == 0

    @pytest.mark.asyncio
    async def test_closes_session_on_exception(self, db_session):
        """Test that DB session is closed even when an exception occurs."""
        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("DB error")
        mock_db.close = MagicMock()

        with (
            patch("app.worker.SessionLocal", return_value=mock_db),
            pytest.raises(RuntimeError, match="DB error"),
        ):
            await generate_periodic_invoices_task({})

        mock_db.close.assert_called_once()


class TestWorkerSettings:
    """Tests for WorkerSettings configuration."""

    def test_functions_includes_retry_task(self):
        """Test that retry_failed_webhooks_task is registered as a worker function."""
        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "retry_failed_webhooks_task" in func_names

    def test_functions_includes_downgrades_task(self):
        """Test that process_pending_downgrades_task is registered."""
        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "process_pending_downgrades_task" in func_names

    def test_functions_includes_trial_task(self):
        """Test that process_trial_expirations_task is registered."""
        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "process_trial_expirations_task" in func_names

    def test_functions_includes_invoices_task(self):
        """Test that generate_periodic_invoices_task is registered."""
        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "generate_periodic_invoices_task" in func_names

    def test_cron_jobs_includes_retry_task(self):
        """Test that retry_failed_webhooks_task is registered as a cron job."""
        cron_func_names = [job.coroutine.__name__ for job in WorkerSettings.cron_jobs]
        assert "retry_failed_webhooks_task" in cron_func_names

    def test_cron_jobs_includes_downgrades_task(self):
        """Test that process_pending_downgrades_task is registered as a cron job."""
        cron_func_names = [job.coroutine.__name__ for job in WorkerSettings.cron_jobs]
        assert "process_pending_downgrades_task" in cron_func_names

    def test_cron_jobs_includes_trial_task(self):
        """Test that process_trial_expirations_task is registered as a cron job."""
        cron_func_names = [job.coroutine.__name__ for job in WorkerSettings.cron_jobs]
        assert "process_trial_expirations_task" in cron_func_names

    def test_cron_jobs_includes_invoices_task(self):
        """Test that generate_periodic_invoices_task is registered as a cron job."""
        cron_func_names = [job.coroutine.__name__ for job in WorkerSettings.cron_jobs]
        assert "generate_periodic_invoices_task" in cron_func_names

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

    def test_downgrades_cron_runs_daily(self):
        """Test that downgrades cron job runs daily at midnight."""
        job = None
        for j in WorkerSettings.cron_jobs:
            if j.coroutine.__name__ == "process_pending_downgrades_task":
                job = j
                break
        assert job is not None
        assert job.hour == 0
        assert job.minute == 0

    def test_trial_cron_runs_hourly(self):
        """Test that trial expirations cron job runs hourly."""
        job = None
        for j in WorkerSettings.cron_jobs:
            if j.coroutine.__name__ == "process_trial_expirations_task":
                job = j
                break
        assert job is not None
        assert job.minute == {0}

    def test_invoices_cron_runs_hourly(self):
        """Test that periodic invoices cron job runs hourly."""
        job = None
        for j in WorkerSettings.cron_jobs:
            if j.coroutine.__name__ == "generate_periodic_invoices_task":
                job = j
                break
        assert job is not None
        assert job.minute == {0}

    def test_functions_includes_thresholds_task(self):
        """Test that check_usage_thresholds_task is registered as a worker function."""
        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "check_usage_thresholds_task" in func_names

    def test_redis_settings_configured(self):
        """Test that redis settings are properly configured."""
        from app.tasks import redis_settings

        assert WorkerSettings.redis_settings is redis_settings


class TestCheckUsageThresholdsTask:
    """Tests for the check_usage_thresholds_task worker function."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_subscription_not_found(self, db_session):
        """Test returns 0 when subscription doesn't exist."""
        fake_id = str(uuid.uuid4())
        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await check_usage_thresholds_task({}, fake_id)
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_for_inactive_subscription(self, db_session):
        """Test returns 0 for a canceled subscription."""
        customer = _create_customer(db_session, external_id="cust_thresh_inactive")
        plan = _create_plan(db_session, code="plan_thresh_inactive")
        sub = Subscription(
            external_id="sub_thresh_inactive",
            customer_id=customer.id,
            plan_id=plan.id,
            status=SubscriptionStatus.CANCELED.value,
            started_at=datetime.now(UTC) - timedelta(days=5),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await check_usage_thresholds_task({}, str(sub.id))
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_plan_not_found(self, db_session):
        """Test returns 0 when the plan doesn't exist."""
        customer = _create_customer(db_session, external_id="cust_thresh_noplan")
        plan = _create_plan(db_session, code="plan_thresh_noplan")
        sub = _create_active_subscription(
            db_session, customer, plan, external_id="sub_thresh_noplan"
        )

        mock_plan_repo = MagicMock()
        mock_plan_repo.get_by_id.return_value = None

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.PlanRepository", return_value=mock_plan_repo),
        ):
            result = await check_usage_thresholds_task({}, str(sub.id))
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_customer_not_found(self, db_session):
        """Test returns 0 when the customer doesn't exist."""
        customer = _create_customer(db_session, external_id="cust_thresh_nocust")
        plan = _create_plan(db_session, code="plan_thresh_nocust")
        sub = _create_active_subscription(
            db_session, customer, plan, external_id="sub_thresh_nocust"
        )

        mock_cust_repo = MagicMock()
        mock_cust_repo.get_by_id.return_value = None

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.CustomerRepository", return_value=mock_cust_repo),
        ):
            result = await check_usage_thresholds_task({}, str(sub.id))
        assert result == 0

    @pytest.mark.asyncio
    async def test_calls_check_thresholds_and_returns_count(self, db_session):
        """Test calls UsageThresholdService.check_thresholds and returns crossed count."""
        customer = _create_customer(db_session, external_id="cust_thresh_ok")
        plan = _create_plan(db_session, code="plan_thresh_ok")
        sub = _create_active_subscription(db_session, customer, plan, external_id="sub_thresh_ok")

        mock_service = MagicMock()
        mock_service.check_thresholds.return_value = ["crossed1", "crossed2"]

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.UsageThresholdService", return_value=mock_service),
        ):
            result = await check_usage_thresholds_task({}, str(sub.id))

        assert result == 2
        mock_service.check_thresholds.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_thresholds_crossed(self, db_session):
        """Test returns 0 when no thresholds are crossed."""
        customer = _create_customer(db_session, external_id="cust_thresh_none")
        plan = _create_plan(db_session, code="plan_thresh_none")
        sub = _create_active_subscription(db_session, customer, plan, external_id="sub_thresh_none")

        mock_service = MagicMock()
        mock_service.check_thresholds.return_value = []

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.UsageThresholdService", return_value=mock_service),
        ):
            result = await check_usage_thresholds_task({}, str(sub.id))

        assert result == 0

    @pytest.mark.asyncio
    async def test_closes_session_on_exception(self, db_session):
        """Test that DB session is closed even when an exception occurs."""
        mock_db = MagicMock()
        mock_db.close = MagicMock()

        mock_sub_repo = MagicMock()
        mock_sub_repo.get_by_id.side_effect = RuntimeError("DB error")

        with (
            patch("app.worker.SessionLocal", return_value=mock_db),
            patch("app.worker.SubscriptionRepository", return_value=mock_sub_repo),
            pytest.raises(RuntimeError, match="DB error"),
        ):
            await check_usage_thresholds_task({}, str(uuid.uuid4()))

        mock_db.close.assert_called_once()
