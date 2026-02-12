"""Tests for SubscriptionDatesService billing period calculations."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from app.models.plan import PlanInterval
from app.models.subscription import BillingTime
from app.services.subscription_dates import (
    SubscriptionDatesService,
    _add_interval,
    _add_months,
    _calendar_period_start,
    _subtract_interval,
)


@pytest.fixture
def service():
    return SubscriptionDatesService()


def _make_subscription(**kwargs: Any) -> Any:
    """Create a lightweight subscription-like object for pure-logic tests."""
    defaults = {
        "billing_time": BillingTime.CALENDAR.value,
        "trial_period_days": 0,
        "trial_ended_at": None,
        "subscription_at": None,
        "started_at": None,
        "ending_at": None,
        "created_at": datetime(2025, 1, 15, tzinfo=UTC),
        "pay_in_advance": False,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── Helper function tests ──────────────────────────────────────────


class TestAddInterval:
    def test_weekly(self):
        dt = datetime(2025, 3, 10, tzinfo=UTC)
        result = _add_interval(dt, PlanInterval.WEEKLY.value)
        assert result == datetime(2025, 3, 17, tzinfo=UTC)

    def test_monthly(self):
        dt = datetime(2025, 1, 15, tzinfo=UTC)
        result = _add_interval(dt, PlanInterval.MONTHLY.value)
        assert result == datetime(2025, 2, 15, tzinfo=UTC)

    def test_quarterly(self):
        dt = datetime(2025, 1, 1, tzinfo=UTC)
        result = _add_interval(dt, PlanInterval.QUARTERLY.value)
        assert result == datetime(2025, 4, 1, tzinfo=UTC)

    def test_yearly(self):
        dt = datetime(2025, 6, 15, tzinfo=UTC)
        result = _add_interval(dt, PlanInterval.YEARLY.value)
        assert result == datetime(2026, 6, 15, tzinfo=UTC)

    def test_unknown_interval(self):
        with pytest.raises(ValueError, match="Unknown interval"):
            _add_interval(datetime(2025, 1, 1, tzinfo=UTC), "biweekly")


class TestSubtractInterval:
    def test_weekly(self):
        dt = datetime(2025, 3, 17, tzinfo=UTC)
        result = _subtract_interval(dt, PlanInterval.WEEKLY.value)
        assert result == datetime(2025, 3, 10, tzinfo=UTC)

    def test_monthly(self):
        dt = datetime(2025, 2, 15, tzinfo=UTC)
        result = _subtract_interval(dt, PlanInterval.MONTHLY.value)
        assert result == datetime(2025, 1, 15, tzinfo=UTC)

    def test_quarterly(self):
        dt = datetime(2025, 4, 1, tzinfo=UTC)
        result = _subtract_interval(dt, PlanInterval.QUARTERLY.value)
        assert result == datetime(2025, 1, 1, tzinfo=UTC)

    def test_yearly(self):
        dt = datetime(2026, 6, 15, tzinfo=UTC)
        result = _subtract_interval(dt, PlanInterval.YEARLY.value)
        assert result == datetime(2025, 6, 15, tzinfo=UTC)

    def test_unknown_interval(self):
        with pytest.raises(ValueError, match="Unknown interval"):
            _subtract_interval(datetime(2025, 1, 1, tzinfo=UTC), "biweekly")


class TestAddMonths:
    def test_basic(self):
        assert _add_months(datetime(2025, 1, 15), 1) == datetime(2025, 2, 15)

    def test_clamp_end_of_month(self):
        # Jan 31 + 1 month = Feb 28
        result = _add_months(datetime(2025, 1, 31), 1)
        assert result == datetime(2025, 2, 28)

    def test_leap_year(self):
        result = _add_months(datetime(2024, 1, 31), 1)
        assert result == datetime(2024, 2, 29)

    def test_year_rollover(self):
        result = _add_months(datetime(2025, 11, 15), 3)
        assert result == datetime(2026, 2, 15)

    def test_subtract_months(self):
        result = _add_months(datetime(2025, 3, 15), -1)
        assert result == datetime(2025, 2, 15)

    def test_subtract_across_year(self):
        result = _add_months(datetime(2025, 1, 15), -1)
        assert result == datetime(2024, 12, 15)


class TestCalendarPeriodStart:
    def test_weekly_monday(self):
        # 2025-03-10 is a Monday
        ref = datetime(2025, 3, 10, 14, 30, tzinfo=UTC)
        result = _calendar_period_start(ref, PlanInterval.WEEKLY.value)
        assert result == datetime(2025, 3, 10, 0, 0, tzinfo=UTC)

    def test_weekly_midweek(self):
        # 2025-03-12 is a Wednesday
        ref = datetime(2025, 3, 12, 14, 30, tzinfo=UTC)
        result = _calendar_period_start(ref, PlanInterval.WEEKLY.value)
        assert result == datetime(2025, 3, 10, 0, 0, tzinfo=UTC)

    def test_monthly(self):
        ref = datetime(2025, 3, 15, 10, 0, tzinfo=UTC)
        result = _calendar_period_start(ref, PlanInterval.MONTHLY.value)
        assert result == datetime(2025, 3, 1, 0, 0, tzinfo=UTC)

    def test_quarterly_q1(self):
        ref = datetime(2025, 2, 15, tzinfo=UTC)
        result = _calendar_period_start(ref, PlanInterval.QUARTERLY.value)
        assert result == datetime(2025, 1, 1, 0, 0, tzinfo=UTC)

    def test_quarterly_q2(self):
        ref = datetime(2025, 5, 20, tzinfo=UTC)
        result = _calendar_period_start(ref, PlanInterval.QUARTERLY.value)
        assert result == datetime(2025, 4, 1, 0, 0, tzinfo=UTC)

    def test_quarterly_q3(self):
        ref = datetime(2025, 8, 1, tzinfo=UTC)
        result = _calendar_period_start(ref, PlanInterval.QUARTERLY.value)
        assert result == datetime(2025, 7, 1, 0, 0, tzinfo=UTC)

    def test_quarterly_q4(self):
        ref = datetime(2025, 12, 31, tzinfo=UTC)
        result = _calendar_period_start(ref, PlanInterval.QUARTERLY.value)
        assert result == datetime(2025, 10, 1, 0, 0, tzinfo=UTC)

    def test_yearly(self):
        ref = datetime(2025, 7, 4, tzinfo=UTC)
        result = _calendar_period_start(ref, PlanInterval.YEARLY.value)
        assert result == datetime(2025, 1, 1, 0, 0, tzinfo=UTC)

    def test_unknown_interval(self):
        with pytest.raises(ValueError, match="Unknown interval"):
            _calendar_period_start(datetime(2025, 1, 1, tzinfo=UTC), "biweekly")


# ── Billing period tests ───────────────────────────────────────────


class TestCalculateBillingPeriodCalendar:
    def test_monthly(self, service: SubscriptionDatesService):
        sub = _make_subscription(billing_time=BillingTime.CALENDAR.value)
        ref = datetime(2025, 3, 15, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.MONTHLY.value, ref)
        assert start == datetime(2025, 3, 1, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 4, 1, 0, 0, tzinfo=UTC)

    def test_weekly(self, service: SubscriptionDatesService):
        sub = _make_subscription(billing_time=BillingTime.CALENDAR.value)
        # 2025-03-12 is Wednesday
        ref = datetime(2025, 3, 12, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.WEEKLY.value, ref)
        assert start == datetime(2025, 3, 10, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 3, 17, 0, 0, tzinfo=UTC)

    def test_quarterly(self, service: SubscriptionDatesService):
        sub = _make_subscription(billing_time=BillingTime.CALENDAR.value)
        ref = datetime(2025, 5, 20, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.QUARTERLY.value, ref)
        assert start == datetime(2025, 4, 1, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 7, 1, 0, 0, tzinfo=UTC)

    def test_yearly(self, service: SubscriptionDatesService):
        sub = _make_subscription(billing_time=BillingTime.CALENDAR.value)
        ref = datetime(2025, 7, 4, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.YEARLY.value, ref)
        assert start == datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
        assert end == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

    def test_defaults_to_now(self, service: SubscriptionDatesService):
        sub = _make_subscription(billing_time=BillingTime.CALENDAR.value)
        now = datetime(2025, 6, 15, tzinfo=UTC)
        with patch("app.services.subscription_dates.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            start, end = service.calculate_billing_period(sub, PlanInterval.MONTHLY.value)
        assert start == datetime(2025, 6, 1, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 7, 1, 0, 0, tzinfo=UTC)


class TestCalculateBillingPeriodAnniversary:
    def test_monthly_same_day(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=datetime(2025, 1, 15, tzinfo=UTC),
        )
        ref = datetime(2025, 3, 20, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.MONTHLY.value, ref)
        assert start == datetime(2025, 3, 15, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 4, 15, 0, 0, tzinfo=UTC)

    def test_weekly(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=datetime(2025, 3, 5, tzinfo=UTC),
        )
        ref = datetime(2025, 3, 10, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.WEEKLY.value, ref)
        assert start == datetime(2025, 3, 5, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 3, 12, 0, 0, tzinfo=UTC)

    def test_quarterly(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=datetime(2025, 1, 10, tzinfo=UTC),
        )
        ref = datetime(2025, 5, 1, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.QUARTERLY.value, ref)
        assert start == datetime(2025, 4, 10, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 7, 10, 0, 0, tzinfo=UTC)

    def test_yearly(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        ref = datetime(2025, 8, 1, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.YEARLY.value, ref)
        assert start == datetime(2025, 6, 1, 0, 0, tzinfo=UTC)
        assert end == datetime(2026, 6, 1, 0, 0, tzinfo=UTC)

    def test_falls_back_to_subscription_at(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=None,
            subscription_at=datetime(2025, 2, 10, tzinfo=UTC),
        )
        ref = datetime(2025, 3, 15, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.MONTHLY.value, ref)
        assert start == datetime(2025, 3, 10, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 4, 10, 0, 0, tzinfo=UTC)

    def test_falls_back_to_created_at(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=None,
            subscription_at=None,
            created_at=datetime(2025, 1, 20, tzinfo=UTC),
        )
        ref = datetime(2025, 2, 25, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.MONTHLY.value, ref)
        assert start == datetime(2025, 2, 20, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 3, 20, 0, 0, tzinfo=UTC)

    def test_reference_before_anchor(self, service: SubscriptionDatesService):
        """Test when reference_date is before the subscription started."""
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=datetime(2025, 6, 15, tzinfo=UTC),
        )
        ref = datetime(2025, 5, 20, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.MONTHLY.value, ref)
        assert start == datetime(2025, 5, 15, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 6, 15, 0, 0, tzinfo=UTC)

    def test_reference_before_anchor_weekly(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=datetime(2025, 3, 15, tzinfo=UTC),
        )
        ref = datetime(2025, 3, 5, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.WEEKLY.value, ref)
        assert start == datetime(2025, 3, 1, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 3, 8, 0, 0, tzinfo=UTC)

    def test_reference_before_anchor_quarterly(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=datetime(2025, 6, 15, tzinfo=UTC),
        )
        ref = datetime(2025, 4, 1, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.QUARTERLY.value, ref)
        assert start == datetime(2025, 3, 15, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 6, 15, 0, 0, tzinfo=UTC)

    def test_reference_before_anchor_yearly(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=datetime(2025, 6, 15, tzinfo=UTC),
        )
        ref = datetime(2024, 8, 1, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.YEARLY.value, ref)
        assert start == datetime(2024, 6, 15, 0, 0, tzinfo=UTC)
        assert end == datetime(2025, 6, 15, 0, 0, tzinfo=UTC)

    def test_reference_well_before_anchor_yearly(self, service: SubscriptionDatesService):
        """Yearly backward walk needs multiple iterations."""
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=datetime(2025, 6, 15, tzinfo=UTC),
        )
        ref = datetime(2022, 8, 1, tzinfo=UTC)
        start, end = service.calculate_billing_period(sub, PlanInterval.YEARLY.value, ref)
        assert start == datetime(2022, 6, 15, 0, 0, tzinfo=UTC)
        assert end == datetime(2023, 6, 15, 0, 0, tzinfo=UTC)


# ── Charges period tests ───────────────────────────────────────────


class TestCalculateChargesPeriod:
    def test_full_period(self, service: SubscriptionDatesService):
        sub = _make_subscription()
        start, end = service.calculate_charges_period(
            sub,
            datetime(2025, 3, 1, tzinfo=UTC),
            datetime(2025, 4, 1, tzinfo=UTC),
        )
        assert start == datetime(2025, 3, 1, tzinfo=UTC)
        assert end == datetime(2025, 4, 1, tzinfo=UTC)

    def test_started_mid_period(self, service: SubscriptionDatesService):
        sub = _make_subscription(started_at=datetime(2025, 3, 15, tzinfo=UTC))
        start, end = service.calculate_charges_period(
            sub,
            datetime(2025, 3, 1, tzinfo=UTC),
            datetime(2025, 4, 1, tzinfo=UTC),
        )
        assert start == datetime(2025, 3, 15, tzinfo=UTC)
        assert end == datetime(2025, 4, 1, tzinfo=UTC)

    def test_ending_mid_period(self, service: SubscriptionDatesService):
        sub = _make_subscription(ending_at=datetime(2025, 3, 20, tzinfo=UTC))
        start, end = service.calculate_charges_period(
            sub,
            datetime(2025, 3, 1, tzinfo=UTC),
            datetime(2025, 4, 1, tzinfo=UTC),
        )
        assert start == datetime(2025, 3, 1, tzinfo=UTC)
        assert end == datetime(2025, 3, 20, tzinfo=UTC)

    def test_both_prorated(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            started_at=datetime(2025, 3, 10, tzinfo=UTC),
            ending_at=datetime(2025, 3, 25, tzinfo=UTC),
        )
        start, end = service.calculate_charges_period(
            sub,
            datetime(2025, 3, 1, tzinfo=UTC),
            datetime(2025, 4, 1, tzinfo=UTC),
        )
        assert start == datetime(2025, 3, 10, tzinfo=UTC)
        assert end == datetime(2025, 3, 25, tzinfo=UTC)

    def test_started_before_period(self, service: SubscriptionDatesService):
        """started_at before period start should not affect charges_start."""
        sub = _make_subscription(started_at=datetime(2025, 2, 1, tzinfo=UTC))
        start, end = service.calculate_charges_period(
            sub,
            datetime(2025, 3, 1, tzinfo=UTC),
            datetime(2025, 4, 1, tzinfo=UTC),
        )
        assert start == datetime(2025, 3, 1, tzinfo=UTC)
        assert end == datetime(2025, 4, 1, tzinfo=UTC)

    def test_ending_after_period(self, service: SubscriptionDatesService):
        """ending_at after period end should not affect charges_end."""
        sub = _make_subscription(ending_at=datetime(2025, 5, 1, tzinfo=UTC))
        start, end = service.calculate_charges_period(
            sub,
            datetime(2025, 3, 1, tzinfo=UTC),
            datetime(2025, 4, 1, tzinfo=UTC),
        )
        assert start == datetime(2025, 3, 1, tzinfo=UTC)
        assert end == datetime(2025, 4, 1, tzinfo=UTC)


# ── Trial period tests ─────────────────────────────────────────────


class TestIsInTrial:
    def test_no_trial(self, service: SubscriptionDatesService):
        sub = _make_subscription(trial_period_days=0)
        assert service.is_in_trial(sub) is False

    def test_trial_already_ended(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            trial_period_days=14,
            trial_ended_at=datetime(2025, 1, 10, tzinfo=UTC),
        )
        assert service.is_in_trial(sub) is False

    def test_in_trial(self, service: SubscriptionDatesService):
        future = datetime.now(UTC) + timedelta(days=7)
        sub = _make_subscription(
            trial_period_days=14,
            subscription_at=future - timedelta(days=7),
        )
        assert service.is_in_trial(sub) is True

    def test_trial_expired(self, service: SubscriptionDatesService):
        past = datetime.now(UTC) - timedelta(days=30)
        sub = _make_subscription(
            trial_period_days=14,
            subscription_at=past,
        )
        assert service.is_in_trial(sub) is False

    def test_trial_no_anchor(self, service: SubscriptionDatesService):
        """No anchor dates returns False (trial_end_date returns None)."""
        sub = _make_subscription(
            trial_period_days=14,
            subscription_at=None,
            started_at=None,
            created_at=None,
        )
        assert service.is_in_trial(sub) is False


class TestTrialEndDate:
    def test_no_trial(self, service: SubscriptionDatesService):
        sub = _make_subscription(trial_period_days=0)
        assert service.trial_end_date(sub) is None

    def test_uses_subscription_at(self, service: SubscriptionDatesService):
        anchor = datetime(2025, 3, 1, tzinfo=UTC)
        sub = _make_subscription(
            trial_period_days=14,
            subscription_at=anchor,
            started_at=datetime(2025, 3, 5, tzinfo=UTC),
        )
        assert service.trial_end_date(sub) == datetime(2025, 3, 15, tzinfo=UTC)

    def test_falls_back_to_started_at(self, service: SubscriptionDatesService):
        anchor = datetime(2025, 3, 5, tzinfo=UTC)
        sub = _make_subscription(
            trial_period_days=7,
            subscription_at=None,
            started_at=anchor,
        )
        assert service.trial_end_date(sub) == datetime(2025, 3, 12, tzinfo=UTC)

    def test_falls_back_to_created_at(self, service: SubscriptionDatesService):
        anchor = datetime(2025, 3, 10, tzinfo=UTC)
        sub = _make_subscription(
            trial_period_days=30,
            subscription_at=None,
            started_at=None,
            created_at=anchor,
        )
        assert service.trial_end_date(sub) == datetime(2025, 4, 9, tzinfo=UTC)

    def test_no_anchor(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            trial_period_days=14,
            subscription_at=None,
            started_at=None,
            created_at=None,
        )
        assert service.trial_end_date(sub) is None


# ── Proration tests ────────────────────────────────────────────────


class TestProrateAmount:
    def test_full_period(self, service: SubscriptionDatesService):
        start = datetime(2025, 3, 1, tzinfo=UTC)
        end = datetime(2025, 4, 1, tzinfo=UTC)
        result = service.prorate_amount(3100, start, end, start, end)
        assert result == 3100

    def test_half_period(self, service: SubscriptionDatesService):
        start = datetime(2025, 3, 1, tzinfo=UTC)
        end = datetime(2025, 3, 31, tzinfo=UTC)
        mid = datetime(2025, 3, 16, tzinfo=UTC)
        result = service.prorate_amount(3000, start, end, mid, end)
        # 15/30 * 3000 = 1500
        assert result == 1500

    def test_one_day(self, service: SubscriptionDatesService):
        start = datetime(2025, 3, 1, tzinfo=UTC)
        end = datetime(2025, 3, 31, tzinfo=UTC)
        prorate_start = datetime(2025, 3, 1, tzinfo=UTC)
        prorate_end = datetime(2025, 3, 2, tzinfo=UTC)
        result = service.prorate_amount(3000, start, end, prorate_start, prorate_end)
        # 1/30 * 3000 = 100
        assert result == 100

    def test_rounding_half_up(self, service: SubscriptionDatesService):
        start = datetime(2025, 3, 1, tzinfo=UTC)
        end = datetime(2025, 3, 31, tzinfo=UTC)
        prorate_start = datetime(2025, 3, 1, tzinfo=UTC)
        prorate_end = datetime(2025, 3, 8, tzinfo=UTC)
        # 7/30 * 1000 = 233.333... → 233
        result = service.prorate_amount(1000, start, end, prorate_start, prorate_end)
        assert result == 233

    def test_zero_total_days(self, service: SubscriptionDatesService):
        same = datetime(2025, 3, 1, tzinfo=UTC)
        result = service.prorate_amount(3000, same, same, same, same)
        assert result == 0

    def test_zero_prorate_days(self, service: SubscriptionDatesService):
        start = datetime(2025, 3, 1, tzinfo=UTC)
        end = datetime(2025, 4, 1, tzinfo=UTC)
        same = datetime(2025, 3, 15, tzinfo=UTC)
        result = service.prorate_amount(3000, start, end, same, same)
        assert result == 0

    def test_negative_total_days(self, service: SubscriptionDatesService):
        start = datetime(2025, 4, 1, tzinfo=UTC)
        end = datetime(2025, 3, 1, tzinfo=UTC)
        result = service.prorate_amount(3000, start, end, start, end)
        assert result == 0

    def test_negative_prorate_days(self, service: SubscriptionDatesService):
        start = datetime(2025, 3, 1, tzinfo=UTC)
        end = datetime(2025, 4, 1, tzinfo=UTC)
        result = service.prorate_amount(
            3000, start, end, datetime(2025, 3, 20, tzinfo=UTC), datetime(2025, 3, 10, tzinfo=UTC)
        )
        assert result == 0


# ── Next billing date tests ────────────────────────────────────────


class TestNextBillingDate:
    def test_calendar_monthly(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.CALENDAR.value,
            started_at=datetime(2025, 3, 1, tzinfo=UTC),
        )
        now = datetime(2025, 3, 15, tzinfo=UTC)
        with patch("app.services.subscription_dates.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = service.next_billing_date(sub, PlanInterval.MONTHLY.value)
        assert result == datetime(2025, 4, 1, 0, 0, tzinfo=UTC)

    def test_anniversary_monthly(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.ANNIVERSARY.value,
            started_at=datetime(2025, 1, 15, tzinfo=UTC),
        )
        now = datetime(2025, 3, 20, tzinfo=UTC)
        with patch("app.services.subscription_dates.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = service.next_billing_date(sub, PlanInterval.MONTHLY.value)
        assert result == datetime(2025, 4, 15, 0, 0, tzinfo=UTC)

    def test_in_trial_returns_trial_end(self, service: SubscriptionDatesService):
        """When in trial, next billing date is the trial end date."""
        future_anchor = datetime.now(UTC) - timedelta(days=3)
        sub = _make_subscription(
            billing_time=BillingTime.CALENDAR.value,
            trial_period_days=14,
            subscription_at=future_anchor,
        )
        result = service.next_billing_date(sub, PlanInterval.MONTHLY.value)
        expected = future_anchor + timedelta(days=14)
        assert result == expected

    def test_weekly(self, service: SubscriptionDatesService):
        sub = _make_subscription(
            billing_time=BillingTime.CALENDAR.value,
            started_at=datetime(2025, 3, 10, tzinfo=UTC),
        )
        # 2025-03-12 is Wednesday
        now = datetime(2025, 3, 12, tzinfo=UTC)
        with patch("app.services.subscription_dates.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = service.next_billing_date(sub, PlanInterval.WEEKLY.value)
        assert result == datetime(2025, 3, 17, 0, 0, tzinfo=UTC)
