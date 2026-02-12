from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.charge import Charge, ChargeModel
from app.models.fee import FeeType
from app.models.invoice import Invoice
from app.models.subscription import SubscriptionStatus
from app.repositories.charge_filter_repository import ChargeFilterRepository
from app.repositories.charge_repository import ChargeRepository
from app.repositories.commitment_repository import CommitmentRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.fee import FeeCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.services.charge_models.factory import get_charge_calculator
from app.services.coupon_service import CouponApplicationService
from app.services.tax_service import TaxCalculationService
from app.services.usage_aggregation import UsageAggregationService


class InvoiceGenerationService:
    """Service for generating invoices from subscriptions and usage."""

    def __init__(self, db: Session):
        self.db = db
        self.subscription_repo = SubscriptionRepository(db)
        self.charge_repo = ChargeRepository(db)
        self.charge_filter_repo = ChargeFilterRepository(db)
        self.commitment_repo = CommitmentRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.fee_repo = FeeRepository(db)
        self.usage_service = UsageAggregationService(db)
        self.coupon_service = CouponApplicationService(db)
        self.tax_service = TaxCalculationService(db)

    def generate_invoice(
        self,
        subscription_id: UUID,
        billing_period_start: datetime,
        billing_period_end: datetime,
        external_customer_id: str,
    ) -> Invoice:
        """Generate an invoice for a subscription and billing period.

        Creates Fee records as the source of truth for line items, then populates
        the Invoice's line_items JSON for backward compatibility.

        Args:
            subscription_id: The subscription to bill
            billing_period_start: Start of the billing period
            billing_period_end: End of the billing period
            external_customer_id: The external customer ID for usage lookup

        Returns:
            The created invoice
        """
        # Get subscription
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        if subscription.status != SubscriptionStatus.ACTIVE.value:
            raise ValueError("Can only generate invoices for active subscriptions")

        # Get plan charges
        plan_id = UUID(str(subscription.plan_id))
        charges = self.charge_repo.get_by_plan_id(plan_id)

        # Calculate fees for each charge
        customer_id = UUID(str(subscription.customer_id))
        fee_creates: list[FeeCreate] = []

        for charge in charges:
            charge_id = UUID(str(charge.id))
            charge_filters = self.charge_filter_repo.get_by_charge_id(charge_id)

            if charge_filters:
                # Filtered charge: create separate fees per filter
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
                # Unfiltered charge: single aggregation, single fee
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

        # Build line_items for backward compatibility (before invoice creation)
        line_items = [
            InvoiceLineItem(
                description=fc.description or "",
                quantity=fc.units,
                unit_price=fc.unit_amount_cents,
                amount=fc.amount_cents,
                charge_id=fc.charge_id,
                metric_code=fc.metric_code,
            )
            for fc in fee_creates
        ]

        # Create invoice
        invoice_data = InvoiceCreate(
            customer_id=customer_id,
            subscription_id=subscription_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            line_items=line_items,
        )

        invoice = self.invoice_repo.create(invoice_data)

        # Create Fee records linked to the invoice
        created_fees = []
        if fee_creates:
            invoice_uuid = UUID(str(invoice.id))
            for fc in fee_creates:
                fc.invoice_id = invoice_uuid
            created_fees = self.fee_repo.create_bulk(fee_creates)

        # Apply taxes to each fee
        for fee in created_fees:
            fee_id = UUID(str(fee.id))
            fee_charge_id = UUID(str(fee.charge_id)) if fee.charge_id else None
            taxes = self.tax_service.get_applicable_taxes(
                customer_id=customer_id,
                plan_id=plan_id,
                charge_id=fee_charge_id,
            )
            if taxes:
                self.tax_service.apply_taxes_to_fee(fee_id, taxes)

        # Apply coupon discounts
        subtotal = Decimal(str(invoice.subtotal))
        if subtotal > 0:
            coupon_discount = self.coupon_service.calculate_coupon_discount(
                customer_id=customer_id,
                subtotal_cents=subtotal,
            )
            if coupon_discount.total_discount_cents > 0:
                invoice.coupons_amount_cents = coupon_discount.total_discount_cents  # type: ignore[assignment]
                invoice.total = subtotal - coupon_discount.total_discount_cents  # type: ignore[assignment]
                self.db.commit()
                self.db.refresh(invoice)

                # Consume applied coupons
                for applied_coupon_id in coupon_discount.applied_coupon_ids:
                    self.coupon_service.consume_applied_coupon(applied_coupon_id)

        # Aggregate fee-level taxes into invoice totals
        if created_fees:
            self.tax_service.apply_taxes_to_invoice(invoice_uuid)
            self.db.refresh(invoice)

        # Subtract progressive billing credits for end-of-period invoices
        from app.services.progressive_billing_service import ProgressiveBillingService

        progressive_service = ProgressiveBillingService(self.db)
        progressive_credit = progressive_service.calculate_progressive_billing_credit(
            subscription_id=subscription_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
        )
        if progressive_credit > 0:
            current_total = Decimal(str(invoice.total))
            invoice.progressive_billing_credit_amount_cents = progressive_credit  # type: ignore[assignment]
            adjusted = current_total - progressive_credit
            invoice.total = adjusted if adjusted > 0 else Decimal("0")  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(invoice)

        return invoice

    def _generate_commitment_true_up_fees(
        self,
        plan_id: UUID,
        customer_id: UUID,
        subscription_id: UUID,
        charge_fees: list[FeeCreate],
    ) -> list[FeeCreate]:
        """Generate true-up fees for minimum commitments.

        For each minimum_commitment on the plan, if total charge fees are less
        than the commitment amount, create a true-up fee for the difference.

        Args:
            plan_id: The plan to check commitments for
            customer_id: The customer ID for the fee
            subscription_id: The subscription ID for the fee
            charge_fees: The already-calculated charge fees

        Returns:
            List of commitment true-up FeeCreate objects (may be empty)
        """
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
        """Calculate a Fee for a charge.

        Returns:
            FeeCreate or None if no charges apply
        """
        charge_model = ChargeModel(charge.charge_model)
        properties: dict[str, Any] = dict(charge.properties) if charge.properties else {}
        unit_price = Decimal(str(properties.get("unit_price", 0)))
        min_price = Decimal(str(properties.get("min_price", 0)))
        max_price = Decimal(str(properties.get("max_price", 0)))

        # Get usage for the metric
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

            # For dynamic charges, fetch raw event properties
            if charge_model == ChargeModel.DYNAMIC:
                from app.models.event import Event

                raw_events = (
                    self.db.query(Event)
                    .filter(
                        Event.external_customer_id == external_customer_id,
                        Event.code == metric_code,
                        Event.timestamp >= billing_period_start,
                        Event.timestamp < billing_period_end,
                    )
                    .all()
                )
                event_properties_list = [
                    dict(e.properties) if e.properties else {} for e in raw_events
                ]

            description = str(metric.name)
        else:
            usage = Decimal(1)  # For flat fee charges
            description = "Subscription Fee"
            metric_code = None

        # Get the calculator for this charge model
        calculator = get_charge_calculator(charge_model)
        if not calculator:
            return None

        # Calculate amount based on charge model using factory
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

        elif charge_model == ChargeModel.DYNAMIC:
            quantity = Decimal(events_count)
            amount = calculator(events=event_properties_list, properties=properties)

        else:
            return None

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
        """Calculate fees for a charge that has filters.

        For each ChargeFilter, aggregate usage matching the filter's key-value
        pairs and calculate a separate fee using the filter's properties.

        Returns:
            List of FeeCreate objects, one per applicable filter.
        """
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.repositories.billable_metric_repository import (
            BillableMetricRepository,
        )

        fees: list[FeeCreate] = []

        # Resolve metric info (needed for all filters)
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
            # Build filter dict from ChargeFilterValues
            filter_values = self.charge_filter_repo.get_filter_values(
                UUID(str(cf.id))
            )
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

            # Aggregate usage with these filters applied
            usage_result = self.usage_service.aggregate_usage_with_count(
                external_customer_id=external_customer_id,
                code=metric_code,
                from_timestamp=billing_period_start,
                to_timestamp=billing_period_end,
                filters=filters,
            )
            usage = usage_result.value
            events_count = usage_result.events_count

            # Use the ChargeFilter's properties (override), falling back to
            # the charge's base properties for any missing keys
            base_properties: dict[str, Any] = (
                dict(charge.properties) if charge.properties else {}
            )
            filter_properties: dict[str, Any] = (
                dict(cf.properties) if cf.properties else {}
            )
            properties = {**base_properties, **filter_properties}

            unit_price = Decimal(str(properties.get("unit_price", 0)))

            # For dynamic charges, fetch filtered raw event properties
            event_properties_list: list[dict[str, Any]] = []
            if charge_model == ChargeModel.DYNAMIC:
                from app.models.event import Event

                raw_events = (
                    self.db.query(Event)
                    .filter(
                        Event.external_customer_id == external_customer_id,
                        Event.code == metric_code,
                        Event.timestamp >= billing_period_start,
                        Event.timestamp < billing_period_end,
                    )
                    .all()
                )
                # Apply same property filters to raw events
                event_properties_list = [
                    dict(e.properties) if e.properties else {}
                    for e in raw_events
                    if all(
                        dict(e.properties or {}).get(k) == v
                        for k, v in filters.items()
                    )
                ]

            # Get calculator and compute amount
            calculator = get_charge_calculator(charge_model)
            if not calculator:
                continue

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

            elif charge_model == ChargeModel.DYNAMIC:
                quantity = Decimal(events_count)
                amount = calculator(
                    events=event_properties_list, properties=properties
                )

            else:
                continue

            if amount == 0 and quantity == 0:
                continue

            # Use filter's invoice_display_name if set, otherwise metric name
            description = (
                str(cf.invoice_display_name)
                if cf.invoice_display_name
                else str(metric.name)
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

    def _calculate_charge(
        self,
        charge: Charge,
        external_customer_id: str,
        billing_period_start: datetime,
        billing_period_end: datetime,
    ) -> InvoiceLineItem | None:
        """Calculate a line item for a charge.

        Deprecated: Use _calculate_charge_fee() instead. Kept for backward compatibility.

        Returns:
            InvoiceLineItem or None if no charges apply
        """
        charge_model = ChargeModel(charge.charge_model)
        properties: dict[str, Any] = dict(charge.properties) if charge.properties else {}
        unit_price = Decimal(str(properties.get("unit_price", 0)))
        min_price = Decimal(str(properties.get("min_price", 0)))
        max_price = Decimal(str(properties.get("max_price", 0)))

        # Get usage for the metric
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
            usage = self.usage_service.aggregate_usage(
                external_customer_id=external_customer_id,
                code=metric_code,
                from_timestamp=billing_period_start,
                to_timestamp=billing_period_end,
            )

            # For dynamic charges, fetch raw event properties
            if charge_model == ChargeModel.DYNAMIC:
                from app.models.event import Event

                raw_events = (
                    self.db.query(Event)
                    .filter(
                        Event.external_customer_id == external_customer_id,
                        Event.code == metric_code,
                        Event.timestamp >= billing_period_start,
                        Event.timestamp < billing_period_end,
                    )
                    .all()
                )
                event_properties_list = [
                    dict(e.properties) if e.properties else {} for e in raw_events
                ]

            description = str(metric.name)
        else:
            usage = Decimal(1)  # For flat fee charges
            description = "Subscription Fee"
            metric_code = None

        # Get the calculator for this charge model
        calculator = get_charge_calculator(charge_model)
        if not calculator:
            return None

        # Calculate amount based on charge model using factory
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

        elif charge_model == ChargeModel.DYNAMIC:
            quantity = usage
            amount = calculator(events=event_properties_list, properties=properties)

        else:
            return None

        if amount == 0 and quantity == 0:
            return None

        return InvoiceLineItem(
            description=description,
            quantity=quantity,
            unit_price=unit_price if quantity else amount,
            amount=amount,
            charge_id=UUID(str(charge.id)),
            metric_code=metric_code,
        )
