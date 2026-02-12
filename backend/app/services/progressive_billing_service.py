"""Service for progressive billing — early invoicing when usage crosses thresholds."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceType
from app.models.subscription import SubscriptionStatus
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.usage_threshold_service import UsageThresholdService


class ProgressiveBillingService:
    """Generates incremental invoices when usage thresholds are crossed."""

    def __init__(self, db: Session):
        self.db = db
        self.subscription_repo = SubscriptionRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.usage_threshold_service = UsageThresholdService(db)

    def generate_progressive_invoice(
        self,
        subscription_id: UUID,
        threshold_id: UUID,
        billing_period_start: datetime,
        billing_period_end: datetime,
        external_customer_id: str,
    ) -> Invoice:
        """Generate a progressive billing invoice when a threshold is crossed.

        Calculates current period usage, subtracts any previously billed
        progressive amounts, and creates an invoice for the difference.

        Args:
            subscription_id: The subscription being billed.
            threshold_id: The threshold that was crossed (for audit trail).
            billing_period_start: Start of the billing period.
            billing_period_end: End of the billing period.
            external_customer_id: External customer ID for usage lookup.

        Returns:
            The created progressive billing invoice.

        Raises:
            ValueError: If subscription not found or not active.
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        if subscription.status != SubscriptionStatus.ACTIVE.value:
            raise ValueError("Can only generate progressive invoices for active subscriptions")

        # Calculate current period usage total
        current_usage = self.usage_threshold_service.get_current_usage_amount(
            subscription_id=subscription_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            external_customer_id=external_customer_id,
        )

        # Subtract already-billed progressive amounts for this period
        already_billed = self._get_already_billed_progressive_total(
            subscription_id=subscription_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
        )

        progressive_amount = current_usage - already_billed
        if progressive_amount <= 0:
            progressive_amount = Decimal("0")

        customer_id = UUID(str(subscription.customer_id))

        from app.schemas.invoice import InvoiceCreate, InvoiceLineItem

        line_items = []
        if progressive_amount > 0:
            line_items.append(
                InvoiceLineItem(
                    description="Progressive billing charge",
                    quantity=Decimal("1"),
                    unit_price=progressive_amount,
                    amount=progressive_amount,
                )
            )

        invoice_data = InvoiceCreate(
            customer_id=customer_id,
            subscription_id=subscription_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            invoice_type=InvoiceType.PROGRESSIVE_BILLING,
            line_items=line_items,
        )

        invoice = self.invoice_repo.create(invoice_data)
        return invoice

    def calculate_progressive_billing_credit(
        self,
        subscription_id: UUID,
        billing_period_start: datetime,
        billing_period_end: datetime,
    ) -> Decimal:
        """Calculate the total progressive billing credit for a billing period.

        Sums all non-voided progressive billing invoices for this subscription
        in this billing period. This amount should be credited on the final
        end-of-period invoice.

        Args:
            subscription_id: The subscription to calculate credits for.
            billing_period_start: Start of the billing period.
            billing_period_end: End of the billing period.

        Returns:
            Total progressive billing credit amount in cents.
        """
        return self._get_already_billed_progressive_total(
            subscription_id=subscription_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
        )

    def _get_already_billed_progressive_total(
        self,
        subscription_id: UUID,
        billing_period_start: datetime,
        billing_period_end: datetime,
    ) -> Decimal:
        """Get the total already-billed progressive billing amount for a period."""
        progressive_invoices = self.invoice_repo.get_progressive_billing_invoices(
            subscription_id=subscription_id,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
        )
        return sum(
            (Decimal(str(inv.total)) for inv in progressive_invoices),
            Decimal("0"),
        )
