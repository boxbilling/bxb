from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.charge import Charge, ChargeModel
from app.models.fee import FeeType
from app.models.invoice import Invoice
from app.models.subscription import SubscriptionStatus
from app.repositories.charge_repository import ChargeRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.fee import FeeCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.services.charge_models.factory import get_charge_calculator
from app.services.usage_aggregation import UsageAggregationService


class InvoiceGenerationService:
    """Service for generating invoices from subscriptions and usage."""

    def __init__(self, db: Session):
        self.db = db
        self.subscription_repo = SubscriptionRepository(db)
        self.charge_repo = ChargeRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.fee_repo = FeeRepository(db)
        self.usage_service = UsageAggregationService(db)

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
        if fee_creates:
            invoice_uuid = UUID(str(invoice.id))
            for fc in fee_creates:
                fc.invoice_id = invoice_uuid
            self.fee_repo.create_bulk(fee_creates)

        return invoice

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
            total_amount_cents=amount,  # No taxes yet
            units=quantity,
            events_count=events_count,
            unit_amount_cents=unit_price if quantity else amount,
            description=description,
            metric_code=metric_code,
            properties=properties,
        )

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
