from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import (
    CustomerMetricsResponse,
    DashboardStatsResponse,
    RecentActivityResponse,
    RevenueDataPoint,
    RevenueResponse,
    SubscriptionMetricsResponse,
    SubscriptionPlanBreakdown,
    UsageMetricsResponse,
    UsageMetricVolume,
)

router = APIRouter()


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get dashboard statistics",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_stats(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    start_date: date | None = Query(None, description="Period start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="Period end date (YYYY-MM-DD)"),
) -> DashboardStatsResponse:
    """Get dashboard statistics."""
    repo = DashboardRepository(db)
    return DashboardStatsResponse(
        total_customers=repo.count_customers(organization_id),
        active_subscriptions=repo.count_active_subscriptions(organization_id),
        monthly_recurring_revenue=repo.sum_monthly_revenue(
            organization_id, start_date=start_date, end_date=end_date
        ),
        total_invoiced=repo.sum_total_invoiced(organization_id),
        total_wallet_credits=repo.total_wallet_credits(organization_id),
        currency="USD",
    )


@router.get(
    "/activity",
    response_model=list[RecentActivityResponse],
    summary="Get recent activity feed",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
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


@router.get(
    "/revenue",
    response_model=RevenueResponse,
    summary="Get revenue analytics",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_revenue(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    start_date: date | None = Query(None, description="Period start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="Period end date (YYYY-MM-DD)"),
) -> RevenueResponse:
    """Get revenue analytics: MRR, total this month, outstanding, overdue, and trend."""
    repo = DashboardRepository(db)
    trend = repo.monthly_revenue_trend(
        organization_id, start_date=start_date, end_date=end_date
    )
    return RevenueResponse(
        mrr=repo.sum_monthly_revenue(
            organization_id, start_date=start_date, end_date=end_date
        ),
        total_revenue_this_month=repo.sum_monthly_revenue(
            organization_id, start_date=start_date, end_date=end_date
        ),
        outstanding_invoices=repo.outstanding_invoices_total(organization_id),
        overdue_amount=repo.overdue_invoices_total(organization_id),
        currency="USD",
        monthly_trend=[
            RevenueDataPoint(month=m.month, revenue=m.revenue)
            for m in trend
        ],
    )


@router.get(
    "/customers",
    response_model=CustomerMetricsResponse,
    summary="Get customer metrics",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_customer_metrics(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    start_date: date | None = Query(None, description="Period start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="Period end date (YYYY-MM-DD)"),
) -> CustomerMetricsResponse:
    """Get customer metrics: total, new this month, churned this month."""
    repo = DashboardRepository(db)
    return CustomerMetricsResponse(
        total=repo.count_customers(organization_id),
        new_this_month=repo.new_customers_this_month(
            organization_id, start_date=start_date, end_date=end_date
        ),
        churned_this_month=repo.churned_customers_this_month(
            organization_id, start_date=start_date, end_date=end_date
        ),
    )


@router.get(
    "/subscriptions",
    response_model=SubscriptionMetricsResponse,
    summary="Get subscription metrics",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_subscription_metrics(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    start_date: date | None = Query(None, description="Period start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="Period end date (YYYY-MM-DD)"),
) -> SubscriptionMetricsResponse:
    """Get subscription metrics: active, new, canceled, by-plan breakdown."""
    repo = DashboardRepository(db)
    by_plan = repo.subscriptions_by_plan(organization_id)
    return SubscriptionMetricsResponse(
        active=repo.count_active_subscriptions(organization_id),
        new_this_month=repo.new_subscriptions_this_month(
            organization_id, start_date=start_date, end_date=end_date
        ),
        canceled_this_month=repo.canceled_subscriptions_this_month(
            organization_id, start_date=start_date, end_date=end_date
        ),
        by_plan=[
            SubscriptionPlanBreakdown(plan_name=p.plan_name, count=p.count)
            for p in by_plan
        ],
    )


@router.get(
    "/usage",
    response_model=UsageMetricsResponse,
    summary="Get top usage metrics",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_usage_metrics(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    start_date: date | None = Query(None, description="Period start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="Period end date (YYYY-MM-DD)"),
) -> UsageMetricsResponse:
    """Get top billable metrics by usage volume in the given period."""
    repo = DashboardRepository(db)
    top = repo.top_metrics_by_usage(
        organization_id, start_date=start_date, end_date=end_date
    )
    return UsageMetricsResponse(
        top_metrics=[
            UsageMetricVolume(
                metric_name=m.metric_name,
                metric_code=m.metric_code,
                event_count=m.event_count,
            )
            for m in top
        ],
    )
