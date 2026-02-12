"""Service for billing period calculation and subscription date logic."""

import calendar as cal
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.models.plan import PlanInterval
from app.models.subscription import BillingTime, Subscription


def _add_interval(dt: datetime, interval: str) -> datetime:
    """Add one billing interval to a datetime."""
    if interval == PlanInterval.WEEKLY.value:
        return dt + timedelta(weeks=1)
    elif interval == PlanInterval.MONTHLY.value:
        return _add_months(dt, 1)
    elif interval == PlanInterval.QUARTERLY.value:
        return _add_months(dt, 3)
    elif interval == PlanInterval.YEARLY.value:
        return _add_months(dt, 12)
    raise ValueError(f"Unknown interval: {interval}")


def _subtract_interval(dt: datetime, interval: str) -> datetime:
    """Subtract one billing interval from a datetime."""
    if interval == PlanInterval.WEEKLY.value:
        return dt - timedelta(weeks=1)
    elif interval == PlanInterval.MONTHLY.value:
        return _add_months(dt, -1)
    elif interval == PlanInterval.QUARTERLY.value:
        return _add_months(dt, -3)
    elif interval == PlanInterval.YEARLY.value:
        return _add_months(dt, -12)
    raise ValueError(f"Unknown interval: {interval}")


def _add_months(dt: datetime, months: int) -> datetime:
    """Add months to a datetime, clamping to last day of month."""
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    max_day = cal.monthrange(year, month)[1]
    day = min(dt.day, max_day)
    return dt.replace(year=year, month=month, day=day)


def _calendar_period_start(reference: datetime, interval: str) -> datetime:
    """Get the start of the calendar period containing the reference date."""
    if interval == PlanInterval.WEEKLY.value:
        # Week starts on Monday
        days_since_monday = reference.weekday()
        return reference.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=days_since_monday
        )
    elif interval == PlanInterval.MONTHLY.value:
        return reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif interval == PlanInterval.QUARTERLY.value:
        quarter_start_month = ((reference.month - 1) // 3) * 3 + 1
        return reference.replace(
            month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    elif interval == PlanInterval.YEARLY.value:
        return reference.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unknown interval: {interval}")


class SubscriptionDatesService:
    """Service for calculating billing periods, trial dates, and proration."""

    def calculate_billing_period(
        self,
        subscription: Subscription,
        interval: str,
        reference_date: datetime | None = None,
    ) -> tuple[datetime, datetime]:
        """Calculate the billing period for a subscription.

        Args:
            subscription: The subscription to calculate for.
            interval: The plan interval (weekly, monthly, quarterly, yearly).
            reference_date: Date to calculate the period for. Defaults to now.

        Returns:
            Tuple of (period_start, period_end).
        """
        if reference_date is None:
            reference_date = datetime.now(UTC)

        billing_time = str(subscription.billing_time)

        if billing_time == BillingTime.CALENDAR.value:
            period_start = _calendar_period_start(reference_date, interval)
            period_end = _add_interval(period_start, interval)
            return period_start, period_end

        # Anniversary mode: align to subscription start date
        anchor = subscription.started_at
        if anchor is None:
            anchor = subscription.subscription_at
        if anchor is None:
            anchor = subscription.created_at

        # Ensure anchor is timezone-aware (SQLite may strip tz info)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=UTC)

        # Walk forward from anchor to find the period containing reference_date
        period_start = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = _add_interval(period_start, interval)

        while period_end <= reference_date:
            period_start = period_end
            period_end = _add_interval(period_start, interval)

        # If reference_date is before the anchor, walk backwards
        while period_start > reference_date:
            period_end = period_start
            period_start = _subtract_interval(period_start, interval)

        return period_start, period_end

    def calculate_charges_period(
        self,
        subscription: Subscription,
        billing_period_start: datetime,
        billing_period_end: datetime,
    ) -> tuple[datetime, datetime]:
        """Calculate the charges period, which may differ for prorated scenarios.

        If the subscription started mid-period, charges start from started_at.
        If the subscription is ending mid-period, charges end at ending_at.

        Args:
            subscription: The subscription.
            billing_period_start: Start of the billing period.
            billing_period_end: End of the billing period.

        Returns:
            Tuple of (charges_start, charges_end).
        """
        charges_start = billing_period_start
        charges_end = billing_period_end

        # If subscription started after billing period start, prorate from started_at
        if subscription.started_at and subscription.started_at > billing_period_start:
            charges_start = subscription.started_at  # type: ignore[assignment]

        # If subscription is ending before billing period end, prorate to ending_at
        if subscription.ending_at and subscription.ending_at < billing_period_end:
            charges_end = subscription.ending_at  # type: ignore[assignment]

        return charges_start, charges_end

    def is_in_trial(self, subscription: Subscription) -> bool:
        """Check if a subscription is currently in its trial period.

        Args:
            subscription: The subscription to check.

        Returns:
            True if the subscription is currently in trial.
        """
        # If trial already ended, not in trial
        if subscription.trial_ended_at is not None:
            return False

        # No trial configured
        if subscription.trial_period_days == 0:
            return False

        trial_end = self.trial_end_date(subscription)
        if trial_end is None:
            return False

        return datetime.now(UTC) < trial_end

    def trial_end_date(self, subscription: Subscription) -> datetime | None:
        """Calculate the trial end date.

        Args:
            subscription: The subscription.

        Returns:
            The trial end datetime, or None if no trial.
        """
        if subscription.trial_period_days == 0:
            return None

        # Use subscription_at as the anchor, fall back to started_at, then created_at
        anchor = subscription.subscription_at
        if anchor is None:
            anchor = subscription.started_at
        if anchor is None:
            anchor = subscription.created_at

        if anchor is None:
            return None

        return anchor + timedelta(days=int(subscription.trial_period_days))  # type: ignore[return-value]

    def prorate_amount(
        self,
        amount_cents: int,
        period_start: datetime,
        period_end: datetime,
        prorate_start: datetime,
        prorate_end: datetime,
    ) -> int:
        """Calculate a prorated amount based on days in period.

        Args:
            amount_cents: The full-period amount in cents.
            period_start: Start of the full billing period.
            period_end: End of the full billing period.
            prorate_start: Start of the prorated portion.
            prorate_end: End of the prorated portion.

        Returns:
            The prorated amount in cents (rounded half-up).
        """
        total_days = (period_end - period_start).days
        if total_days <= 0:
            return 0

        prorate_days = (prorate_end - prorate_start).days
        if prorate_days <= 0:
            return 0

        ratio = Decimal(prorate_days) / Decimal(total_days)
        prorated = Decimal(amount_cents) * ratio
        return int(prorated.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def next_billing_date(
        self,
        subscription: Subscription,
        interval: str,
    ) -> datetime | None:
        """Calculate the next billing date for a subscription.

        Args:
            subscription: The subscription.
            interval: The plan interval.

        Returns:
            The next billing datetime, or None if not applicable.
        """
        now = datetime.now(UTC)

        # If subscription has a trial, next billing is after trial ends
        if self.is_in_trial(subscription):
            return self.trial_end_date(subscription)

        _, period_end = self.calculate_billing_period(subscription, interval, now)
        return period_end
