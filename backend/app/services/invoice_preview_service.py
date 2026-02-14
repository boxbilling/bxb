"""Service for previewing invoices without persisting any records."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.charge import Charge, ChargeModel
from app.models.fee import FeeType
from app.models.subscription import SubscriptionStatus
from app.repositories.charge_filter_repository import ChargeFilterRepository
from app.repositories.charge_repository import ChargeRepository
from app.repositories.commitment_repository import CommitmentRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.fee import FeeCreate
from app.schemas.invoice_preview import FeePreview, InvoicePreviewResponse
from app.services.charge_models.factory import get_charge_calculator
from app.services.coupon_service import CouponApplicationService
from app.services.events_query import fetch_event_properties
from app.services.tax_service import TaxCalculationService
from app.services.usage_aggregation import UsageAggregationService


class InvoicePreviewService:
    """Service for previewing invoices without persisting."""

    def __init__(self, db: Session):
        self.db = db
        self.subscription_repo = SubscriptionRepository(db)
        self.charge_repo = ChargeRepository(db)
        self.charge_filter_repo = ChargeFilterRepository(db)
        self.commitment_repo = CommitmentRepository(db)
        self.usage_service = UsageAggregationService(db)
        self.coupon_service = CouponApplicationService(db)
        self.tax_service = TaxCalculationService(db)

    def preview_invoice(
        self,
        subscription_id: UUID,
        external_customer_id: str,
        billing_period_start: datetime | None = None,
        billing_period_end: datetime | None = None,
    ) -> InvoicePreviewResponse:
        """Preview an invoice for a subscription without persisting anything.

        Runs the same charge calculation logic as InvoiceGenerationService but
        does NOT persist any Invoice, Fee, or coupon consumption records.

        Args:
            subscription_id: The subscription to preview billing for.
            external_customer_id: The external customer ID for usage lookup.
            billing_period_start: Start of the billing period (defaults to current).
            billing_period_end: End of the billing period (defaults to current).

        Returns:
            InvoicePreviewResponse with subtotal, taxes, discounts, and fees.

        Raises:
            ValueError: If subscription not found or not active.
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        if subscription.status != SubscriptionStatus.ACTIVE.value:
            raise ValueError("Can only preview invoices for active subscriptions")

        # Default billing period to current month if not specified
        if billing_period_start is None or billing_period_end is None:
            now = datetime.now()
            billing_period_start = billing_period_start or now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            billing_period_end = billing_period_end or now

        plan_id = UUID(str(subscription.plan_id))
        customer_id = UUID(str(subscription.customer_id))
        charges = self.charge_repo.get_by_plan_id(plan_id)

        # Calculate fees for each charge (same logic as InvoiceGenerationService)
        fee_creates: list[FeeCreate] = []
        for charge in charges:
            charge_id = UUID(str(charge.id))
            charge_filters = self.charge_filter_repo.get_by_charge_id(charge_id)

            if charge_filters:
                filtered_fees = self._calculate_filtered_charge_fees(
                    charge=charge,
                    charge_filters=charge_filters,
                    customer_id=customer_id,
                    subscription_id=subscription_id,
                    external_customer_id=external_customer_id,
                    billing_period_start=billing_period_start,
                    billing_period_end=billing_period_end,
                )
                fee_creates.extend(filtered_fees)
            else:
                fee_data = self._calculate_charge_fee(
                    charge=charge,
                    customer_id=customer_id,
                    subscription_id=subscription_id,
                    external_customer_id=external_customer_id,
                    billing_period_start=billing_period_start,
                    billing_period_end=billing_period_end,
                )
                if fee_data:
                    fee_creates.append(fee_data)

        # Generate commitment true-up fees
        commitment_fees = self._generate_commitment_true_up_fees(
            plan_id=plan_id,
            customer_id=customer_id,
            subscription_id=subscription_id,
            charge_fees=fee_creates,
        )
        fee_creates.extend(commitment_fees)

        # Calculate subtotal
        subtotal = sum((fc.amount_cents for fc in fee_creates), Decimal("0"))

        # Calculate taxes (read-only — no AppliedTax records created)
        tax_amount = Decimal("0")
        for fc in fee_creates:
            taxes = self.tax_service.get_applicable_taxes(
                customer_id=customer_id,
                plan_id=plan_id,
                charge_id=fc.charge_id,
            )
            if taxes:
                result = self.tax_service.calculate_tax(fc.amount_cents, taxes)
                tax_amount += result.taxes_amount_cents

        # Calculate coupon discounts (read-only — no coupon consumption)
        coupons_amount = Decimal("0")
        if subtotal > 0:
            coupon_discount = self.coupon_service.calculate_coupon_discount(
                customer_id=customer_id,
                subtotal_cents=subtotal,
            )
            coupons_amount = coupon_discount.total_discount_cents

        # Calculate progressive billing credits (read-only)
        from app.services.progressive_billing_service import ProgressiveBillingService

        progressive_service = ProgressiveBillingService(self.db)
        prepaid_credit_amount = progressive_service.calculate_progressive_billing_credit(
            subscription_id=subscription_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
        )

        # Calculate total
        total = subtotal - coupons_amount + tax_amount - prepaid_credit_amount
        if total < 0:
            total = Decimal("0")

        # Build fee previews
        fees = self._build_fee_previews(fee_creates, charges)

        return InvoicePreviewResponse(
            subtotal=subtotal,
            tax_amount=tax_amount,
            coupons_amount=coupons_amount,
            prepaid_credit_amount=prepaid_credit_amount,
            total=total,
            currency="USD",
            fees=fees,
        )

    def _build_fee_previews(
        self, fee_creates: list[FeeCreate], charges: list[Charge]
    ) -> list[FeePreview]:
        """Convert FeeCreate objects into FeePreview response objects."""
        charge_map = {UUID(str(c.id)): c for c in charges}
        previews: list[FeePreview] = []
        for fc in fee_creates:
            charge_model_str: str | None = None
            if fc.charge_id and fc.charge_id in charge_map:
                charge_model_str = str(charge_map[fc.charge_id].charge_model)
            previews.append(
                FeePreview(
                    description=fc.description or "",
                    units=fc.units,
                    unit_amount_cents=fc.unit_amount_cents,
                    amount_cents=fc.amount_cents,
                    charge_model=charge_model_str,
                    metric_code=fc.metric_code,
                )
            )
        return previews

    def _generate_commitment_true_up_fees(
        self,
        plan_id: UUID,
        customer_id: UUID,
        subscription_id: UUID,
        charge_fees: list[FeeCreate],
    ) -> list[FeeCreate]:
        """Generate true-up fees for minimum commitments (preview only)."""
        commitments = self.commitment_repo.get_by_plan_id(plan_id)
        if not commitments:
            return []

        total_charge_amount = sum(fc.amount_cents for fc in charge_fees)

        true_up_fees: list[FeeCreate] = []
        for commitment in commitments:
            if commitment.commitment_type != "minimum_commitment":
                continue

            commitment_amount = Decimal(str(commitment.amount_cents))
            if total_charge_amount >= commitment_amount:
                continue

            true_up_amount = commitment_amount - total_charge_amount
            description = (
                str(commitment.invoice_display_name)
                if commitment.invoice_display_name
                else "Minimum commitment true-up"
            )
            true_up_fees.append(
                FeeCreate(
                    customer_id=customer_id,
                    subscription_id=subscription_id,
                    charge_id=None,
                    commitment_id=UUID(str(commitment.id)),
                    fee_type=FeeType.COMMITMENT,
                    amount_cents=true_up_amount,
                    total_amount_cents=true_up_amount,
                    units=Decimal("1"),
                    events_count=0,
                    unit_amount_cents=true_up_amount,
                    description=description,
                    metric_code=None,
                    properties={},
                )
            )

        return true_up_fees

    def _calculate_charge_fee(
        self,
        charge: Charge,
        customer_id: UUID,
        subscription_id: UUID,
        external_customer_id: str,
        billing_period_start: datetime,
        billing_period_end: datetime,
    ) -> FeeCreate | None:
        """Calculate a Fee for a charge (same logic as InvoiceGenerationService)."""
        charge_model = ChargeModel(charge.charge_model)
        properties: dict[str, Any] = dict(charge.properties) if charge.properties else {}
        unit_price = Decimal(str(properties.get("unit_price", 0)))
        min_price = Decimal(str(properties.get("min_price", 0)))
        max_price = Decimal(str(properties.get("max_price", 0)))

        events_count = 0
        event_properties_list: list[dict[str, Any]] = []
        if charge.billable_metric_id:
            from app.repositories.billable_metric_repository import (
                BillableMetricRepository,
            )

            metric_repo = BillableMetricRepository(self.db)
            metric_id = UUID(str(charge.billable_metric_id))
            metric = metric_repo.get_by_id(metric_id)
            if not metric:
                return None

            metric_code = str(metric.code)
            usage_result = self.usage_service.aggregate_usage_with_count(
                external_customer_id=external_customer_id,
                code=metric_code,
                from_timestamp=billing_period_start,
                to_timestamp=billing_period_end,
            )
            usage = usage_result.value
            events_count = usage_result.events_count

            if charge_model == ChargeModel.DYNAMIC:
                event_properties_list = fetch_event_properties(
                    self.db,
                    external_customer_id,
                    metric_code,
                    billing_period_start,
                    billing_period_end,
                )

            description = str(metric.name)
        else:
            usage = Decimal(1)
            description = "Subscription Fee"
            metric_code = None

        calculator = get_charge_calculator(charge_model)
        if not calculator:
            return None

        amount = Decimal("0")
        quantity = Decimal("0")

        if charge_model == ChargeModel.STANDARD:
            quantity = usage
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
            quantity = usage
            amount = calculator(units=usage, properties=properties)

        elif charge_model == ChargeModel.PERCENTAGE:
            total_amount = Decimal(str(properties.get("base_amount", 0)))
            event_count = int(properties.get("event_count", 0))
            quantity = Decimal(1)
            amount = calculator(
                units=usage,
                properties=properties,
                total_amount=total_amount,
                event_count=event_count,
            )

        elif charge_model == ChargeModel.GRADUATED_PERCENTAGE:
            usage_amount = Decimal(str(properties.get("base_amount", usage)))
            quantity = Decimal(1)
            amount = calculator(total_amount=usage_amount, properties=properties)

        elif charge_model == ChargeModel.CUSTOM:
            quantity = usage
            amount = calculator(units=usage, properties=properties)

        else:  # ChargeModel.DYNAMIC
            quantity = Decimal(events_count)
            amount = calculator(events=event_properties_list, properties=properties)

        if amount == 0 and quantity == 0:
            return None

        return FeeCreate(
            customer_id=customer_id,
            subscription_id=subscription_id,
            charge_id=UUID(str(charge.id)),
            fee_type=FeeType.CHARGE,
            amount_cents=amount,
            total_amount_cents=amount,
            units=quantity,
            events_count=events_count,
            unit_amount_cents=unit_price if quantity else amount,
            description=description,
            metric_code=metric_code,
            properties=properties,
        )

    def _calculate_filtered_charge_fees(
        self,
        charge: Charge,
        charge_filters: list[Any],
        customer_id: UUID,
        subscription_id: UUID,
        external_customer_id: str,
        billing_period_start: datetime,
        billing_period_end: datetime,
    ) -> list[FeeCreate]:
        """Calculate fees for a charge that has filters (preview only)."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.repositories.billable_metric_repository import (
            BillableMetricRepository,
        )

        fees: list[FeeCreate] = []

        if not charge.billable_metric_id:
            return fees

        metric_repo = BillableMetricRepository(self.db)
        metric_id = UUID(str(charge.billable_metric_id))
        metric = metric_repo.get_by_id(metric_id)
        if not metric:
            return fees

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
                from_timestamp=billing_period_start,
                to_timestamp=billing_period_end,
                filters=filters,
            )
            usage = usage_result.value
            events_count = usage_result.events_count

            base_properties: dict[str, Any] = (
                dict(charge.properties) if charge.properties else {}
            )
            filter_properties: dict[str, Any] = dict(cf.properties) if cf.properties else {}
            properties = {**base_properties, **filter_properties}

            unit_price = Decimal(str(properties.get("unit_price", 0)))

            event_properties_list: list[dict[str, Any]] = []
            if charge_model == ChargeModel.DYNAMIC:
                event_properties_list = fetch_event_properties(
                    self.db,
                    external_customer_id,
                    metric_code,
                    billing_period_start,
                    billing_period_end,
                    filters=filters,
                )

            calculator = get_charge_calculator(charge_model)
            if not calculator:
                continue

            amount = Decimal("0")
            quantity = Decimal("0")

            if charge_model == ChargeModel.STANDARD:
                min_price = Decimal(str(properties.get("min_price", 0)))
                max_price = Decimal(str(properties.get("max_price", 0)))
                quantity = usage
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
                quantity = usage
                amount = calculator(units=usage, properties=properties)

            elif charge_model == ChargeModel.PERCENTAGE:
                total_amount = Decimal(str(properties.get("base_amount", 0)))
                event_count = int(properties.get("event_count", 0))
                quantity = Decimal(1)
                amount = calculator(
                    units=usage,
                    properties=properties,
                    total_amount=total_amount,
                    event_count=event_count,
                )

            elif charge_model == ChargeModel.GRADUATED_PERCENTAGE:
                usage_amount = Decimal(str(properties.get("base_amount", usage)))
                quantity = Decimal(1)
                amount = calculator(total_amount=usage_amount, properties=properties)

            elif charge_model == ChargeModel.CUSTOM:
                quantity = usage
                amount = calculator(units=usage, properties=properties)

            else:  # ChargeModel.DYNAMIC
                quantity = Decimal(events_count)
                amount = calculator(events=event_properties_list, properties=properties)

            if amount == 0 and quantity == 0:
                continue

            description = (
                str(cf.invoice_display_name) if cf.invoice_display_name else str(metric.name)
            )

            fees.append(
                FeeCreate(
                    customer_id=customer_id,
                    subscription_id=subscription_id,
                    charge_id=UUID(str(charge.id)),
                    fee_type=FeeType.CHARGE,
                    amount_cents=amount,
                    total_amount_cents=amount,
                    units=quantity,
                    events_count=events_count,
                    unit_amount_cents=unit_price if quantity else amount,
                    description=description,
                    metric_code=metric_code,
                    properties=properties,
                )
            )

        return fees
