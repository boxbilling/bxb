from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.charge import Charge, ChargeModel
from app.models.invoice import Invoice
from app.models.subscription import SubscriptionStatus
from app.repositories.charge_repository import ChargeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.subscription_repository import SubscriptionRepository
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
        self.usage_service = UsageAggregationService(db)

    def generate_invoice(
        self,
        subscription_id: UUID,
        billing_period_start: datetime,
        billing_period_end: datetime,
        external_customer_id: str,
    ) -> Invoice:
        """Generate an invoice for a subscription and billing period.

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

        # Generate line items
        line_items = []

        for charge in charges:
            line_item = self._calculate_charge(
                charge=charge,
                external_customer_id=external_customer_id,
                billing_period_start=billing_period_start,
                billing_period_end=billing_period_end,
            )
            if line_item:
                line_items.append(line_item)

        # Create invoice
        customer_id = UUID(str(subscription.customer_id))
        invoice_data = InvoiceCreate(
            customer_id=customer_id,
            subscription_id=subscription_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            line_items=line_items,
        )

        return self.invoice_repo.create(invoice_data)

    def _calculate_charge(
        self,
        charge: Charge,
        external_customer_id: str,
        billing_period_start: datetime,
        billing_period_end: datetime,
    ) -> InvoiceLineItem | None:
        """Calculate a line item for a charge.

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
