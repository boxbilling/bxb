"""Service for checking usage thresholds and managing threshold state."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.applied_usage_threshold import AppliedUsageThreshold
from app.models.charge import Charge, ChargeModel
from app.models.subscription import SubscriptionStatus
from app.models.usage_threshold import UsageThreshold
from app.repositories.applied_usage_threshold_repository import (
    AppliedUsageThresholdRepository,
)
from app.repositories.charge_repository import ChargeRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_threshold_repository import UsageThresholdRepository
from app.services.charge_models.factory import get_charge_calculator
from app.services.usage_aggregation import UsageAggregationService
from app.services.webhook_service import WebhookService


class UsageThresholdService:
    """Service for checking usage thresholds and triggering actions."""

    def __init__(self, db: Session):
        self.db = db
        self.subscription_repo = SubscriptionRepository(db)
        self.threshold_repo = UsageThresholdRepository(db)
        self.applied_repo = AppliedUsageThresholdRepository(db)
        self.charge_repo = ChargeRepository(db)
        self.usage_service = UsageAggregationService(db)
        self.webhook_service = WebhookService(db)

    def check_thresholds(
        self,
        subscription_id: UUID,
        billing_period_start: datetime,
        billing_period_end: datetime,
        external_customer_id: str,
    ) -> list[AppliedUsageThreshold]:
        """Check if any usage thresholds have been crossed for a subscription.

        Called after event ingestion. Looks up all thresholds for the
        subscription (subscription-level first, then plan-level), calculates
        current period usage, and records any newly crossed thresholds.

        Args:
            subscription_id: The subscription to check thresholds for.
            billing_period_start: Start of the current billing period.
            billing_period_end: End of the current billing period.
            external_customer_id: The external customer ID for usage lookup.

        Returns:
            List of newly created AppliedUsageThreshold records.
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        if subscription.status != SubscriptionStatus.ACTIVE.value:
            return []

        plan_id = UUID(str(subscription.plan_id))

        # Get thresholds: subscription-level first, then plan-level
        thresholds = self._get_effective_thresholds(subscription_id, plan_id)
        if not thresholds:
            return []

        # Calculate current period usage amount
        current_usage = self.get_current_usage_amount(
            subscription_id=subscription_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            external_customer_id=external_customer_id,
        )

        crossed: list[AppliedUsageThreshold] = []
        now = datetime.now(UTC)

        for threshold in thresholds:
            threshold_id = UUID(str(threshold.id))
            threshold_amount = Decimal(str(threshold.amount_cents))

            # Skip if already crossed in current period
            if self.applied_repo.has_been_crossed(
                threshold_id, subscription_id, billing_period_start
            ):
                continue

            # Check if current usage meets or exceeds threshold
            if current_usage >= threshold_amount:
                record = self.applied_repo.create(
                    usage_threshold_id=threshold_id,
                    subscription_id=subscription_id,
                    crossed_at=now,
                    organization_id=UUID(str(subscription.organization_id)),
                    lifetime_usage_amount_cents=current_usage,
                )
                crossed.append(record)

                # Trigger webhook
                self.webhook_service.send_webhook(
                    webhook_type="usage_threshold.crossed",
                    object_type="usage_threshold",
                    object_id=threshold_id,
                    payload={
                        "usage_threshold_id": str(threshold_id),
                        "subscription_id": str(subscription_id),
                        "threshold_amount_cents": str(threshold_amount),
                        "current_usage_amount_cents": str(current_usage),
                        "crossed_at": now.isoformat(),
                    },
                )

        return crossed

    def get_current_usage_amount(
        self,
        subscription_id: UUID,
        billing_period_start: datetime,
        billing_period_end: datetime,
        external_customer_id: str,
    ) -> Decimal:
        """Calculate the projected invoice amount for the current billing period.

        Reuses the same charge calculation logic as InvoiceGenerationService
        to determine the total projected amount.

        Args:
            subscription_id: The subscription to calculate for.
            billing_period_start: Start of the billing period.
            billing_period_end: End of the billing period.
            external_customer_id: The external customer ID for usage lookup.

        Returns:
            Total projected amount in cents.
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        plan_id = UUID(str(subscription.plan_id))
        charges = self.charge_repo.get_by_plan_id(plan_id)

        total = Decimal("0")
        for charge in charges:
            amount = self._calculate_charge_amount(
                charge=charge,
                external_customer_id=external_customer_id,
                billing_period_start=billing_period_start,
                billing_period_end=billing_period_end,
            )
            total += amount

        return total

    def reset_recurring_thresholds(
        self,
        subscription_id: UUID,
        period_start: datetime,
    ) -> int:
        """Clear crossed status for recurring thresholds at period start.

        For recurring thresholds, previous period crossings should not
        prevent the threshold from being checked again in the new period.
        This is handled naturally by the `has_been_crossed` method which
        only looks at crossings >= period_start. This method is provided
        as an explicit API for documentation and future extensibility.

        Args:
            subscription_id: The subscription to reset thresholds for.
            period_start: The start of the new billing period.

        Returns:
            Number of recurring thresholds that are now eligible for crossing.
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        plan_id = UUID(str(subscription.plan_id))
        thresholds = self._get_effective_thresholds(subscription_id, plan_id)

        count = 0
        for threshold in thresholds:
            if threshold.recurring:
                threshold_id = UUID(str(threshold.id))
                # Recurring thresholds are automatically "reset" because
                # has_been_crossed checks crossed_at >= period_start.
                # Count those that haven't been crossed in the new period.
                if not self.applied_repo.has_been_crossed(
                    threshold_id, subscription_id, period_start
                ):
                    count += 1

        return count

    def _get_effective_thresholds(
        self,
        subscription_id: UUID,
        plan_id: UUID,
    ) -> list[UsageThreshold]:
        """Get effective thresholds for a subscription.

        Subscription-level thresholds take priority. If the subscription
        has its own thresholds, plan-level thresholds are also included.
        Both sets are returned sorted by amount_cents ascending.

        Args:
            subscription_id: The subscription to get thresholds for.
            plan_id: The plan to get thresholds from.

        Returns:
            Combined list of thresholds sorted by amount.
        """
        sub_thresholds = self.threshold_repo.get_by_subscription_id(subscription_id)
        plan_thresholds = self.threshold_repo.get_by_plan_id(plan_id)
        all_thresholds = sub_thresholds + plan_thresholds
        all_thresholds.sort(key=lambda t: Decimal(str(t.amount_cents)))
        return all_thresholds

    def _calculate_charge_amount(
        self,
        charge: Charge,
        external_customer_id: str,
        billing_period_start: datetime,
        billing_period_end: datetime,
    ) -> Decimal:
        """Calculate the amount for a single charge.

        Reuses the same logic as InvoiceGenerationService._calculate_charge_fee
        but only returns the amount.

        Args:
            charge: The charge to calculate.
            external_customer_id: The customer's external ID for usage lookup.
            billing_period_start: Start of the billing period.
            billing_period_end: End of the billing period.

        Returns:
            Calculated amount in cents.
        """
        charge_model = ChargeModel(charge.charge_model)
        properties: dict[str, Any] = dict(charge.properties) if charge.properties else {}
        min_price = Decimal(str(properties.get("min_price", 0)))
        max_price = Decimal(str(properties.get("max_price", 0)))

        # Get usage for the metric
        from app.repositories.billable_metric_repository import (
            BillableMetricRepository,
        )

        event_properties_list: list[dict[str, Any]] = []
        metric_repo = BillableMetricRepository(self.db)
        metric_id = UUID(str(charge.billable_metric_id))
        metric = metric_repo.get_by_id(metric_id)
        if not metric:
            return Decimal("0")

        metric_code = str(metric.code)
        usage_result = self.usage_service.aggregate_usage_with_count(
            external_customer_id=external_customer_id,
            code=metric_code,
            from_timestamp=billing_period_start,
            to_timestamp=billing_period_end,
        )
        usage = usage_result.value

        # For dynamic charges, fetch raw event properties
        if charge_model == ChargeModel.DYNAMIC:
            from app.services.events_query import fetch_event_properties

            event_properties_list = fetch_event_properties(
                self.db,
                external_customer_id,
                metric_code,
                billing_period_start,
                billing_period_end,
            )

        calculator = get_charge_calculator(charge_model)
        assert calculator is not None  # All ChargeModel values have calculators

        if charge_model == ChargeModel.STANDARD:
            amount = calculator(units=usage, properties=properties)
            if min_price and amount < min_price:
                amount = min_price
            if max_price and amount > max_price:
                amount = max_price

        elif charge_model in (
            ChargeModel.GRADUATED,
            ChargeModel.VOLUME,
            ChargeModel.PACKAGE,
        ):
            amount = calculator(units=usage, properties=properties)

        elif charge_model == ChargeModel.PERCENTAGE:
            total_amount = Decimal(str(properties.get("base_amount", 0)))
            event_count = int(properties.get("event_count", 0))
            amount = calculator(
                units=usage,
                properties=properties,
                total_amount=total_amount,
                event_count=event_count,
            )

        elif charge_model == ChargeModel.GRADUATED_PERCENTAGE:
            usage_amount = Decimal(str(properties.get("base_amount", usage)))
            amount = calculator(total_amount=usage_amount, properties=properties)

        elif charge_model == ChargeModel.CUSTOM:
            amount = calculator(units=usage, properties=properties)

        else:
            # DYNAMIC (remaining case)
            amount = calculator(events=event_properties_list, properties=properties)

        return amount
