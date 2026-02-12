"""Dunning service for automated payment recovery via campaigns."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_request import PaymentRequest
from app.repositories.dunning_campaign_repository import DunningCampaignRepository
from app.repositories.payment_request_repository import PaymentRequestRepository
from app.services.webhook_service import WebhookService


class DunningService:
    """Service for dunning campaign evaluation and payment request lifecycle."""

    def __init__(self, db: Session):
        self.db = db
        self.campaign_repo = DunningCampaignRepository(db)
        self.pr_repo = PaymentRequestRepository(db)
        self.webhook_service = WebhookService(db)

    def check_and_create_payment_requests(
        self, organization_id: UUID,
    ) -> list[PaymentRequest]:
        """Background job: find overdue invoices and create payment requests.

        1. Find all customers with overdue, unpaid invoices
        2. For each customer: sum outstanding amounts per currency
        3. Check against active dunning campaign thresholds
        4. If threshold exceeded: create PaymentRequest linking invoices
        5. Trigger payment_request.created webhook
        """
        created_requests: list[PaymentRequest] = []

        # Get active dunning campaigns for this organization
        active_campaigns = self.campaign_repo.get_all(
            organization_id, status="active",
        )
        if not active_campaigns:
            return created_requests

        # Find overdue, unpaid invoices (finalized but not paid, past due date)
        now = datetime.now(UTC)
        overdue_invoices: list[Invoice] = (
            self.db.query(Invoice)
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.status == InvoiceStatus.FINALIZED.value,
                Invoice.due_date <= now,
            )
            .all()
        )

        if not overdue_invoices:
            return created_requests

        # Group invoices by customer_id and currency
        customer_currency_invoices: dict[
            tuple[UUID, str], list[Invoice]
        ] = {}
        for inv in overdue_invoices:
            cust_id: UUID = inv.customer_id  # type: ignore[assignment]
            curr: str = inv.currency  # type: ignore[assignment]
            key = (cust_id, curr)
            customer_currency_invoices.setdefault(key, []).append(inv)

        # For each customer+currency group, check campaign thresholds
        for (customer_id, currency), invoices in (
            customer_currency_invoices.items()
        ):
            # Check if any existing pending PR already covers these invoices
            existing_prs = self.pr_repo.get_all(
                organization_id,
                customer_id=customer_id,
                payment_status="pending",
            )
            existing_invoice_ids: set[UUID] = set()
            for pr in existing_prs:
                pr_id: UUID = pr.id  # type: ignore[assignment]
                for join_row in self.pr_repo.get_invoices(pr_id):
                    inv_id: UUID = join_row.invoice_id  # type: ignore[assignment]
                    existing_invoice_ids.add(inv_id)

            # Filter out invoices already in a pending payment request
            new_invoices = [
                inv for inv in invoices
                if inv.id not in existing_invoice_ids
            ]
            if not new_invoices:
                continue

            new_outstanding = Decimal("0")
            for inv in new_invoices:
                new_outstanding += Decimal(str(inv.total))

            # Check thresholds across all active campaigns
            for campaign in active_campaigns:
                campaign_id: UUID = campaign.id  # type: ignore[assignment]
                thresholds = self.campaign_repo.get_thresholds(campaign_id)
                matching_threshold = None
                for threshold in thresholds:
                    if threshold.currency == currency:
                        matching_threshold = threshold
                        break

                if matching_threshold is None:
                    continue

                threshold_amount = Decimal(str(matching_threshold.amount_cents))
                if new_outstanding >= threshold_amount:
                    # Create payment request
                    inv_ids: list[UUID] = [
                        inv.id  # type: ignore[misc]
                        for inv in new_invoices
                    ]
                    pr = self.pr_repo.create(
                        organization_id=organization_id,
                        customer_id=customer_id,
                        amount_cents=new_outstanding,
                        amount_currency=currency,
                        invoice_ids=inv_ids,
                        dunning_campaign_id=campaign_id,
                    )
                    created_requests.append(pr)

                    # Trigger webhook
                    self.webhook_service.send_webhook(
                        webhook_type="payment_request.created",
                        object_type="payment_request",
                        object_id=pr.id,  # type: ignore[arg-type]
                        payload={
                            "payment_request_id": str(pr.id),
                            "customer_id": str(customer_id),
                            "amount_cents": str(new_outstanding),
                            "amount_currency": currency,
                            "dunning_campaign_id": str(campaign_id),
                        },
                    )
                    # Only use first matching campaign per customer+currency
                    break

        return created_requests

    def process_payment_requests(
        self, organization_id: UUID,
    ) -> list[PaymentRequest]:
        """Background job: process pending payment requests.

        1. Find pending PaymentRequests where ready=True
        2. For each: attempt payment via customer's payment provider
        3. On success: mark succeeded, update linked invoices
        4. On failure: increment payment_attempts, check max_attempts
        5. If max_attempts reached: mark failed, trigger webhook
        """
        processed: list[PaymentRequest] = []

        pending_requests: list[PaymentRequest] = (
            self.db.query(PaymentRequest)
            .filter(
                PaymentRequest.organization_id == organization_id,
                PaymentRequest.payment_status == "pending",
                PaymentRequest.ready_for_payment_processing.is_(True),
            )
            .all()
        )

        for pr in pending_requests:
            if not self.evaluate_retry_eligibility(pr):
                continue

            # Increment attempt count
            pr_id: UUID = pr.id  # type: ignore[assignment]
            self.pr_repo.increment_attempts(pr_id, organization_id)

            # Mark as not ready to avoid re-processing on next run.
            # Status will be updated by payment provider webhook or manual action.
            pr.ready_for_payment_processing = False  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(pr)

            processed.append(pr)

        return processed

    def mark_payment_request_succeeded(
        self, payment_request_id: UUID, organization_id: UUID,
    ) -> PaymentRequest | None:
        """Mark a payment request as succeeded and update linked invoices."""
        pr = self.pr_repo.update_status(
            payment_request_id, organization_id, "succeeded",
        )
        if not pr:
            return None

        # Mark linked invoices as paid
        join_rows = self.pr_repo.get_invoices(payment_request_id)
        for join_row in join_rows:
            invoice = (
                self.db.query(Invoice)
                .filter(Invoice.id == join_row.invoice_id)
                .first()
            )
            if invoice and invoice.status == InvoiceStatus.FINALIZED.value:
                invoice.status = InvoiceStatus.PAID.value  # type: ignore[assignment]
                invoice.paid_at = datetime.now(UTC)  # type: ignore[assignment]

        self.db.commit()
        self.db.refresh(pr)

        self.webhook_service.send_webhook(
            webhook_type="payment_request.payment_succeeded",
            object_type="payment_request",
            object_id=payment_request_id,
            payload={
                "payment_request_id": str(payment_request_id),
                "customer_id": str(pr.customer_id),
            },
        )

        return pr

    def mark_payment_request_failed(
        self, payment_request_id: UUID, organization_id: UUID,
    ) -> PaymentRequest | None:
        """Mark a payment request as failed and trigger webhook."""
        pr = self.pr_repo.update_status(
            payment_request_id, organization_id, "failed",
        )
        if not pr:
            return None

        self.webhook_service.send_webhook(
            webhook_type="payment_request.payment_failed",
            object_type="payment_request",
            object_id=payment_request_id,
            payload={
                "payment_request_id": str(payment_request_id),
                "customer_id": str(pr.customer_id),
            },
        )

        return pr

    def evaluate_retry_eligibility(
        self, payment_request: PaymentRequest,
    ) -> bool:
        """Check if enough days have passed since last attempt for retry.

        Uses the dunning campaign's days_between_attempts to determine
        eligibility. If no campaign is linked, always eligible.
        """
        attempts: int = payment_request.payment_attempts  # type: ignore[assignment]
        if attempts == 0:
            return True

        if payment_request.dunning_campaign_id is None:
            return True

        org_id: UUID = payment_request.organization_id  # type: ignore[assignment]
        dc_id: UUID = payment_request.dunning_campaign_id  # type: ignore[assignment]
        campaign = self.campaign_repo.get_by_id(dc_id, org_id)
        if not campaign:
            return True

        # Check max attempts
        max_attempts: int = campaign.max_attempts  # type: ignore[assignment]
        if attempts >= max_attempts:
            return False

        # Check days between attempts using updated_at as proxy for last
        # attempt time
        if payment_request.updated_at:
            updated = payment_request.updated_at
            if hasattr(updated, "replace") and updated.tzinfo is None:
                updated = updated.replace(tzinfo=UTC)
            days: int = int(campaign.days_between_attempts)
            next_eligible = updated + timedelta(days=days)
            if datetime.now(UTC) < next_eligible:
                return False

        return True
