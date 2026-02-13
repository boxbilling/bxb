from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import DashboardStatsResponse, RecentActivityResponse

router = APIRouter()


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_stats(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> DashboardStatsResponse:
    """Get dashboard statistics."""
    repo = DashboardRepository(db)
    return DashboardStatsResponse(
        total_customers=repo.count_customers(organization_id),
        active_subscriptions=repo.count_active_subscriptions(organization_id),
        monthly_recurring_revenue=repo.sum_monthly_revenue(organization_id),
        total_invoiced=repo.sum_total_invoiced(organization_id),
        currency="USD",
    )


@router.get("/activity", response_model=list[RecentActivityResponse])
async def get_recent_activity(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[RecentActivityResponse]:
    """Get recent billing activity."""
    repo = DashboardRepository(db)
    activities: list[RecentActivityResponse] = []

    for c in repo.recent_customers(organization_id):
        activities.append(
            RecentActivityResponse(
                id=str(c.id),
                type="customer_created",
                description=f'New customer "{c.name}" created',
                timestamp=c.created_at.isoformat() if c.created_at else "",
            )
        )

    for s in repo.recent_subscriptions(organization_id):
        activities.append(
            RecentActivityResponse(
                id=str(s.id),
                type="subscription_created",
                description=f"Subscription {s.external_id} started",
                timestamp=s.created_at.isoformat() if s.created_at else "",
            )
        )

    for inv in repo.recent_invoices(organization_id):
        activities.append(
            RecentActivityResponse(
                id=str(inv.id),
                type="invoice_finalized",
                description=f"Invoice {inv.invoice_number} {inv.status}",
                timestamp=inv.created_at.isoformat() if inv.created_at else "",
            )
        )

    for p in repo.recent_payments(organization_id):
        activities.append(
            RecentActivityResponse(
                id=str(p.id),
                type="payment_received",
                description="Payment received for invoice",
                timestamp=p.created_at.isoformat() if p.created_at else "",
            )
        )

    activities.sort(key=lambda a: a.timestamp, reverse=True)
    return activities[:10]
