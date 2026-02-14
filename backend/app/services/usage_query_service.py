"""Service for querying current and projected usage for a subscription."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.billable_metric_filter import BillableMetricFilter
from app.models.charge import ChargeModel
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.repositories.charge_filter_repository import ChargeFilterRepository
from app.repositories.charge_repository import ChargeRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.usage import (
    BillableMetricUsage,
    ChargeUsage,
    CurrentUsageResponse,
)
from app.services.charge_models.factory import get_charge_calculator
from app.services.events_query import fetch_event_properties
from app.services.subscription_dates import SubscriptionDatesService
from app.services.usage_aggregation import UsageAggregationService


class UsageQueryService:
    """Query current and projected usage for a subscription."""

    def __init__(self, db: Session):
        self.db = db
        self.subscription_repo = SubscriptionRepository(db)
        self.charge_repo = ChargeRepository(db)
        self.charge_filter_repo = ChargeFilterRepository(db)
        self.usage_service = UsageAggregationService(db)
        self.dates_service = SubscriptionDatesService()

    def get_current_usage(
        self,
        subscription_id: UUID,
        external_customer_id: str,
    ) -> CurrentUsageResponse:
        """Get current usage for a subscription in the current billing period."""
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        return self._compute_usage(subscription, external_customer_id)

    def get_projected_usage(
        self,
        subscription_id: UUID,
        external_customer_id: str,
    ) -> CurrentUsageResponse:
        """Get projected usage for a subscription.

        For now this is identical to current usage since we don't have forecasting.
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        return self._compute_usage(subscription, external_customer_id)

    def _compute_usage(
        self,
        subscription: Subscription,
        external_customer_id: str,
    ) -> CurrentUsageResponse:
        """Compute usage for a subscription in its current billing period."""
        plan = self.db.query(Plan).filter(Plan.id == subscription.plan_id).first()
        if not plan:
            raise ValueError(f"Plan {subscription.plan_id} not found")

        interval = str(plan.interval)
        currency = str(plan.currency)

        period_start, period_end = self.dates_service.calculate_billing_period(
            subscription, interval
        )

        plan_id = UUID(str(subscription.plan_id))
        charges = self.charge_repo.get_by_plan_id(plan_id)

        charge_usages: list[ChargeUsage] = []
        total_amount = Decimal(0)

        for charge in charges:
            charge_id = UUID(str(charge.id))
            charge_filters = self.charge_filter_repo.get_by_charge_id(charge_id)

            if charge_filters:
                filtered_usages = self._compute_filtered_charge_usage(
                    charge=charge,
                    charge_filters=charge_filters,
                    external_customer_id=external_customer_id,
                    period_start=period_start,
                    period_end=period_end,
                )
                for cu in filtered_usages:
                    total_amount += cu.amount_cents
                charge_usages.extend(filtered_usages)
            else:
                single_usage = self._compute_charge_usage(
                    charge=charge,
                    external_customer_id=external_customer_id,
                    period_start=period_start,
                    period_end=period_end,
                )
                if single_usage is not None:
                    total_amount += single_usage.amount_cents
                    charge_usages.append(single_usage)

        return CurrentUsageResponse(
            from_datetime=period_start,
            to_datetime=period_end,
            amount_cents=total_amount,
            currency=currency,
            charges=charge_usages,
        )

    def _compute_charge_usage(
        self,
        charge: Any,
        external_customer_id: str,
        period_start: Any,
        period_end: Any,
    ) -> ChargeUsage | None:
        """Compute usage for a single unfiltered charge."""
        from app.repositories.billable_metric_repository import BillableMetricRepository

        metric_repo = BillableMetricRepository(self.db)
        metric_id = UUID(str(charge.billable_metric_id))
        metric = metric_repo.get_by_id(metric_id)
        if not metric:
            return None

        metric_code = str(metric.code)
        usage_result = self.usage_service.aggregate_usage_with_count(
            external_customer_id=external_customer_id,
            code=metric_code,
            from_timestamp=period_start,
            to_timestamp=period_end,
        )

        charge_model = ChargeModel(charge.charge_model)
        properties: dict[str, Any] = dict(charge.properties) if charge.properties else {}

        amount = self._calculate_amount(
            charge_model=charge_model,
            properties=properties,
            usage=usage_result.value,
            events_count=usage_result.events_count,
            external_customer_id=external_customer_id,
            metric_code=metric_code,
            period_start=period_start,
            period_end=period_end,
        )

        return ChargeUsage(
            billable_metric=BillableMetricUsage(
                code=metric_code,
                name=str(metric.name),
                aggregation_type=str(metric.aggregation_type),
            ),
            units=usage_result.value,
            amount_cents=amount,
            charge_model=str(charge.charge_model),
            filters={},
        )

    def _compute_filtered_charge_usage(
        self,
        charge: Any,
        charge_filters: list[Any],
        external_customer_id: str,
        period_start: Any,
        period_end: Any,
    ) -> list[ChargeUsage]:
        """Compute usage for a charge with filters."""
        from app.repositories.billable_metric_repository import BillableMetricRepository

        results: list[ChargeUsage] = []

        metric_repo = BillableMetricRepository(self.db)
        metric_id = UUID(str(charge.billable_metric_id))
        metric = metric_repo.get_by_id(metric_id)
        if not metric:
            return results

        metric_code = str(metric.code)
        charge_model = ChargeModel(charge.charge_model)

        for cf in charge_filters:
            filter_values = self.charge_filter_repo.get_filter_values(UUID(str(cf.id)))
            if not filter_values:
                continue

            filters: dict[str, str] = {}
            for fv in filter_values:
                bmf = (
                    self.db.query(BillableMetricFilter)
                    .filter(BillableMetricFilter.id == fv.billable_metric_filter_id)
                    .first()
                )
                if bmf is None:
                    continue
                filters[str(bmf.key)] = str(fv.value)

            if not filters:
                continue

            usage_result = self.usage_service.aggregate_usage_with_count(
                external_customer_id=external_customer_id,
                code=metric_code,
                from_timestamp=period_start,
                to_timestamp=period_end,
                filters=filters,
            )

            base_properties: dict[str, Any] = (
                dict(charge.properties) if charge.properties else {}
            )
            filter_properties: dict[str, Any] = dict(cf.properties) if cf.properties else {}
            properties = {**base_properties, **filter_properties}

            amount = self._calculate_amount(
                charge_model=charge_model,
                properties=properties,
                usage=usage_result.value,
                events_count=usage_result.events_count,
                external_customer_id=external_customer_id,
                metric_code=metric_code,
                period_start=period_start,
                period_end=period_end,
                filters=filters,
            )

            results.append(
                ChargeUsage(
                    billable_metric=BillableMetricUsage(
                        code=metric_code,
                        name=str(metric.name),
                        aggregation_type=str(metric.aggregation_type),
                    ),
                    units=usage_result.value,
                    amount_cents=amount,
                    charge_model=str(charge.charge_model),
                    filters=filters,
                )
            )

        return results

    def _calculate_amount(
        self,
        charge_model: ChargeModel,
        properties: dict[str, Any],
        usage: Decimal,
        events_count: int,
        external_customer_id: str,
        metric_code: str,
        period_start: Any,
        period_end: Any,
        filters: dict[str, str] | None = None,
    ) -> Decimal:
        """Calculate the charge amount using the charge model calculator."""
        calculator = get_charge_calculator(charge_model)
        if not calculator:
            return Decimal(0)

        if charge_model == ChargeModel.STANDARD:
            amount = calculator(units=usage, properties=properties)
            min_price = Decimal(str(properties.get("min_price", 0)))
            max_price = Decimal(str(properties.get("max_price", 0)))
            if min_price and amount < min_price:
                amount = min_price
            if max_price and amount > max_price:
                amount = max_price
            return amount

        if charge_model in (
            ChargeModel.GRADUATED,
            ChargeModel.VOLUME,
            ChargeModel.PACKAGE,
        ):
            return calculator(units=usage, properties=properties)

        if charge_model == ChargeModel.PERCENTAGE:
            total_amount = Decimal(str(properties.get("base_amount", 0)))
            event_count = int(properties.get("event_count", 0))
            return calculator(
                units=usage,
                properties=properties,
                total_amount=total_amount,
                event_count=event_count,
            )

        if charge_model == ChargeModel.GRADUATED_PERCENTAGE:
            usage_amount = Decimal(str(properties.get("base_amount", usage)))
            return calculator(total_amount=usage_amount, properties=properties)

        if charge_model == ChargeModel.CUSTOM:
            return calculator(units=usage, properties=properties)

        # DYNAMIC charge model
        event_properties_list = fetch_event_properties(
            self.db,
            external_customer_id,
            metric_code,
            period_start,
            period_end,
            filters=filters,
        )
        return calculator(events=event_properties_list, properties=properties)
