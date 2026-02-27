"""DunningCampaign repository for data access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.customer import Customer
from app.models.dunning_campaign import DunningCampaign
from app.models.dunning_campaign_threshold import DunningCampaignThreshold
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_request import PaymentRequest
from app.models.payment_request_invoice import PaymentRequestInvoice
from app.schemas.dunning_campaign import (
    CampaignPreviewInvoiceGroup,
    CampaignPreviewResponse,
    CampaignTimelineEvent,
    CampaignTimelineResponse,
    DunningCampaignCreate,
    DunningCampaignPerformanceStats,
    DunningCampaignUpdate,
    ExecutionHistoryEntry,
    ExecutionHistoryInvoice,
)


class DunningCampaignRepository:
    """Repository for DunningCampaign model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
        order_by: str | None = None,
    ) -> list[DunningCampaign]:
        """Get all dunning campaigns for an organization."""
        query = self.db.query(DunningCampaign).filter(
            DunningCampaign.organization_id == organization_id,
        )
        if status is not None:
            query = query.filter(DunningCampaign.status == status)
        query = apply_order_by(query, DunningCampaign, order_by)
        return query.offset(skip).limit(limit).all()

    def count(self, organization_id: UUID) -> int:
        """Count dunning campaigns for an organization."""
        return (
            self.db.query(func.count(DunningCampaign.id))
            .filter(DunningCampaign.organization_id == organization_id)
            .scalar()
            or 0
        )

    def get_by_id(
        self,
        campaign_id: UUID,
        organization_id: UUID,
    ) -> DunningCampaign | None:
        """Get a dunning campaign by ID."""
        return (
            self.db.query(DunningCampaign)
            .filter(
                DunningCampaign.id == campaign_id,
                DunningCampaign.organization_id == organization_id,
            )
            .first()
        )

    def get_by_code(
        self,
        code: str,
        organization_id: UUID,
    ) -> DunningCampaign | None:
        """Get a dunning campaign by code."""
        return (
            self.db.query(DunningCampaign)
            .filter(
                DunningCampaign.code == code,
                DunningCampaign.organization_id == organization_id,
            )
            .first()
        )

    def create(
        self,
        data: DunningCampaignCreate,
        organization_id: UUID,
    ) -> DunningCampaign:
        """Create a new dunning campaign with thresholds."""
        thresholds_data = data.thresholds
        campaign = DunningCampaign(
            **data.model_dump(exclude={"thresholds"}),
            organization_id=organization_id,
        )
        self.db.add(campaign)
        self.db.flush()

        for threshold_data in thresholds_data:
            threshold = DunningCampaignThreshold(
                dunning_campaign_id=campaign.id,
                **threshold_data.model_dump(),
            )
            self.db.add(threshold)

        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def update(
        self,
        campaign_id: UUID,
        data: DunningCampaignUpdate,
        organization_id: UUID,
    ) -> DunningCampaign | None:
        """Update a dunning campaign."""
        campaign = self.get_by_id(campaign_id, organization_id)
        if not campaign:
            return None

        update_data = data.model_dump(exclude_unset=True, exclude={"thresholds"})
        for key, value in update_data.items():
            setattr(campaign, key, value)

        # If thresholds are provided, replace them
        if data.thresholds is not None:
            self.db.query(DunningCampaignThreshold).filter(
                DunningCampaignThreshold.dunning_campaign_id == campaign_id,
            ).delete()
            for threshold_data in data.thresholds:
                threshold = DunningCampaignThreshold(
                    dunning_campaign_id=campaign_id,
                    **threshold_data.model_dump(),
                )
                self.db.add(threshold)

        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def delete(self, campaign_id: UUID, organization_id: UUID) -> bool:
        """Delete a dunning campaign."""
        campaign = self.get_by_id(campaign_id, organization_id)
        if not campaign:
            return False
        # Thresholds are cascade deleted via FK
        self.db.delete(campaign)
        self.db.commit()
        return True

    def get_thresholds(self, campaign_id: UUID) -> list[DunningCampaignThreshold]:
        """Get all thresholds for a dunning campaign."""
        return (
            self.db.query(DunningCampaignThreshold)
            .filter(DunningCampaignThreshold.dunning_campaign_id == campaign_id)
            .all()
        )

    def performance_stats(
        self,
        organization_id: UUID,
    ) -> DunningCampaignPerformanceStats:
        """Get performance statistics for dunning campaigns."""
        # Campaign counts
        total_campaigns = self.count(organization_id)
        active_campaigns: int = (
            self.db.query(func.count(DunningCampaign.id))
            .filter(
                DunningCampaign.organization_id == organization_id,
                DunningCampaign.status == "active",
            )
            .scalar()
            or 0
        )

        # Payment request stats (only those linked to dunning campaigns)
        pr_stats: Any = (
            self.db.query(
                func.count(PaymentRequest.id).label("total"),
                func.sum(
                    case(
                        (PaymentRequest.payment_status == "succeeded", 1),
                        else_=0,
                    )
                ).label("succeeded"),
                func.sum(
                    case(
                        (PaymentRequest.payment_status == "failed", 1),
                        else_=0,
                    )
                ).label("failed"),
                func.sum(
                    case(
                        (PaymentRequest.payment_status == "pending", 1),
                        else_=0,
                    )
                ).label("pending"),
                func.sum(
                    case(
                        (PaymentRequest.payment_status == "succeeded", PaymentRequest.amount_cents),
                        else_=Decimal("0"),
                    )
                ).label("recovered"),
                func.sum(
                    case(
                        (PaymentRequest.payment_status != "succeeded", PaymentRequest.amount_cents),
                        else_=Decimal("0"),
                    )
                ).label("outstanding"),
            )
            .filter(
                PaymentRequest.organization_id == organization_id,
                PaymentRequest.dunning_campaign_id.isnot(None),
            )
            .first()
        )

        total_pr = int(pr_stats.total or 0) if pr_stats else 0
        succeeded = int(pr_stats.succeeded or 0) if pr_stats else 0
        failed = int(pr_stats.failed or 0) if pr_stats else 0
        pending = int(pr_stats.pending or 0) if pr_stats else 0
        recovered = Decimal(str(pr_stats.recovered or 0)) if pr_stats else Decimal("0")
        outstanding = Decimal(str(pr_stats.outstanding or 0)) if pr_stats else Decimal("0")

        recovery_rate = (succeeded / total_pr * 100) if total_pr > 0 else 0.0

        return DunningCampaignPerformanceStats(
            total_campaigns=total_campaigns,
            active_campaigns=active_campaigns,
            total_payment_requests=total_pr,
            succeeded_requests=succeeded,
            failed_requests=failed,
            pending_requests=pending,
            recovery_rate=round(recovery_rate, 1),
            total_recovered_amount_cents=recovered,
            total_outstanding_amount_cents=outstanding,
        )

    def execution_history(
        self,
        campaign_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ExecutionHistoryEntry]:
        """Get payment requests linked to this campaign with customer/invoice details."""
        rows = (
            self.db.query(PaymentRequest, Customer.name)
            .outerjoin(Customer, Customer.id == PaymentRequest.customer_id)
            .filter(
                PaymentRequest.dunning_campaign_id == campaign_id,
                PaymentRequest.organization_id == organization_id,
            )
            .order_by(PaymentRequest.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        entries: list[ExecutionHistoryEntry] = []
        for pr, customer_name in rows:
            # Get linked invoices via join
            linked_invoices = (
                self.db.query(Invoice)
                .join(PaymentRequestInvoice, PaymentRequestInvoice.invoice_id == Invoice.id)
                .filter(PaymentRequestInvoice.payment_request_id == pr.id)
                .all()
            )
            invoices: list[ExecutionHistoryInvoice] = [
                ExecutionHistoryInvoice(
                    id=UUID(str(inv.id)),
                    invoice_number=str(inv.invoice_number),
                    amount_cents=Decimal(str(inv.total_cents)),
                    currency=str(inv.currency),
                    status=str(inv.status),
                )
                for inv in linked_invoices
            ]

            entries.append(
                ExecutionHistoryEntry(
                    id=pr.id,
                    customer_id=pr.customer_id,
                    customer_name=customer_name,
                    amount_cents=Decimal(str(pr.amount_cents)),
                    amount_currency=pr.amount_currency,
                    payment_status=pr.payment_status,
                    payment_attempts=pr.payment_attempts,
                    ready_for_payment_processing=pr.ready_for_payment_processing,
                    invoices=invoices,
                    created_at=pr.created_at,
                    updated_at=pr.updated_at,
                )
            )

        return entries

    def campaign_timeline(
        self,
        campaign_id: UUID,
        organization_id: UUID,
    ) -> CampaignTimelineResponse:
        """Build a chronological timeline of campaign events."""
        events: list[CampaignTimelineEvent] = []

        # 1. Campaign created event
        campaign = self.get_by_id(campaign_id, organization_id)
        if not campaign:
            return CampaignTimelineResponse(events=[])

        created_at: datetime = campaign.created_at  # type: ignore[assignment]
        updated_at: datetime | None = campaign.updated_at  # type: ignore[assignment]

        events.append(
            CampaignTimelineEvent(
                event_type="campaign_created",
                timestamp=created_at,
                description=f"Campaign '{campaign.name}' created",
            )
        )

        # 2. Status changes (if updated_at differs from created_at)
        if updated_at and updated_at != created_at:
            events.append(
                CampaignTimelineEvent(
                    event_type="campaign_updated",
                    timestamp=updated_at,
                    description=f"Campaign updated (status: {campaign.status})",
                )
            )

        # 3. Payment request events
        prs = (
            self.db.query(PaymentRequest, Customer.name)
            .outerjoin(Customer, Customer.id == PaymentRequest.customer_id)
            .filter(
                PaymentRequest.dunning_campaign_id == campaign_id,
                PaymentRequest.organization_id == organization_id,
            )
            .order_by(PaymentRequest.created_at.asc())
            .all()
        )

        for pr, customer_name in prs:
            # PR created
            events.append(
                CampaignTimelineEvent(
                    event_type="payment_request_created",
                    timestamp=pr.created_at,
                    description=f"Payment request created for {customer_name or 'Unknown'}",
                    payment_request_id=pr.id,
                    customer_name=customer_name,
                    amount_cents=Decimal(str(pr.amount_cents)),
                    amount_currency=pr.amount_currency,
                    payment_status=pr.payment_status,
                    attempt_number=0,
                )
            )

            # Attempts (inferred from payment_attempts count)
            attempts: int = pr.payment_attempts or 0
            if attempts > 0 and pr.payment_status in ("succeeded", "failed"):
                events.append(
                    CampaignTimelineEvent(
                        event_type=f"payment_{pr.payment_status}",
                        timestamp=pr.updated_at,
                        description=(
                            f"Payment {pr.payment_status}"
                            f" for {customer_name or 'Unknown'}"
                            f" after {attempts} attempt{'s' if attempts != 1 else ''}"
                        ),
                        payment_request_id=pr.id,
                        customer_name=customer_name,
                        amount_cents=Decimal(str(pr.amount_cents)),
                        amount_currency=pr.amount_currency,
                        payment_status=pr.payment_status,
                        attempt_number=attempts,
                    )
                )

        # Sort by timestamp
        events.sort(key=lambda e: e.timestamp)

        return CampaignTimelineResponse(events=events)

    def campaign_preview(
        self,
        campaign_id: UUID,
        organization_id: UUID,
    ) -> CampaignPreviewResponse | None:
        """Simulate what the campaign would do if executed now (no side effects)."""
        campaign = self.get_by_id(campaign_id, organization_id)
        if not campaign:
            return None

        thresholds = self.get_thresholds(campaign_id)

        # Find overdue, unpaid invoices
        now = datetime.now(UTC)
        overdue_invoices: list[Any] = (
            self.db.query(Invoice, Customer.name)
            .outerjoin(Customer, Customer.id == Invoice.customer_id)
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.status == InvoiceStatus.FINALIZED.value,
                Invoice.due_date <= now,
            )
            .all()
        )

        total_overdue = len(overdue_invoices)
        total_overdue_amount = Decimal("0")
        for inv, _ in overdue_invoices:
            total_overdue_amount += Decimal(str(inv.total_cents))

        # Count existing pending PRs for this campaign
        existing_pending: int = (
            self.db.query(func.count(PaymentRequest.id))
            .filter(
                PaymentRequest.organization_id == organization_id,
                PaymentRequest.dunning_campaign_id == campaign_id,
                PaymentRequest.payment_status == "pending",
            )
            .scalar()
            or 0
        )

        # Group by customer+currency
        customer_currency_groups: dict[tuple[UUID, str], list[tuple[Any, str | None]]] = {}
        for inv, cust_name in overdue_invoices:
            key = (inv.customer_id, inv.currency)
            customer_currency_groups.setdefault(key, []).append((inv, cust_name))

        # Filter out invoices already in pending PRs
        existing_invoice_ids: set[UUID] = set()
        pending_prs = (
            self.db.query(PaymentRequest)
            .filter(
                PaymentRequest.organization_id == organization_id,
                PaymentRequest.payment_status == "pending",
            )
            .all()
        )
        for pr in pending_prs:
            joins = (
                self.db.query(PaymentRequestInvoice)
                .filter(PaymentRequestInvoice.payment_request_id == pr.id)
                .all()
            )
            for j in joins:
                existing_invoice_ids.add(UUID(str(j.invoice_id)))

        groups: list[CampaignPreviewInvoiceGroup] = []
        for (customer_id, currency), inv_list in customer_currency_groups.items():
            new_invoices = [
                (inv, name) for inv, name in inv_list if inv.id not in existing_invoice_ids
            ]
            if not new_invoices:
                continue

            outstanding = Decimal("0")
            for inv, _ in new_invoices:
                outstanding += Decimal(str(inv.total_cents))

            # Check thresholds
            matching_threshold = None
            for threshold in thresholds:
                if threshold.currency == currency:
                    matching_threshold = threshold
                    break

            if matching_threshold is None:
                continue

            threshold_amount = Decimal(str(matching_threshold.amount_cents))
            if outstanding < threshold_amount:
                continue

            cust_name = new_invoices[0][1]
            invoice_details = [
                ExecutionHistoryInvoice(
                    id=inv.id,
                    invoice_number=str(inv.invoice_number),
                    amount_cents=Decimal(str(inv.total_cents)),
                    currency=str(inv.currency),
                    status=str(inv.status),
                )
                for inv, _ in new_invoices
            ]

            groups.append(
                CampaignPreviewInvoiceGroup(
                    customer_id=customer_id,
                    customer_name=cust_name,
                    currency=currency,
                    total_outstanding_cents=outstanding,
                    matching_threshold_cents=threshold_amount,
                    invoice_count=len(new_invoices),
                    invoices=invoice_details,
                )
            )

        return CampaignPreviewResponse(
            campaign_id=campaign_id,
            campaign_name=str(campaign.name),
            status=str(campaign.status),
            total_overdue_invoices=total_overdue,
            total_overdue_amount_cents=total_overdue_amount,
            payment_requests_to_create=len(groups),
            groups=groups,
            existing_pending_requests=existing_pending,
        )
