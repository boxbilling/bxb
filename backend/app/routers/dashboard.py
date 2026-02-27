from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import (
    CollectionMetrics,
    CustomerMetricsResponse,
    DailyRevenuePoint,
    DashboardStatsResponse,
    NetRevenueMetrics,
    PlanRevenueBreakdown,
    RecentActivityResponse,
    RecentInvoiceItem,
    RecentSubscriptionItem,
    RevenueAnalyticsResponse,
    RevenueByPlanResponse,
    RevenueByTypeBreakdown,
    RevenueDataPoint,
    RevenueResponse,
    SparklineData,
    SparklinePoint,
    SubscriptionMetricsResponse,
    SubscriptionPlanBreakdown,
    TopCustomerRevenue,
    TrendIndicator,
    UsageMetricsResponse,
    UsageMetricVolume,
)

router = APIRouter()


def _compute_trend(current: float, previous: float) -> TrendIndicator:
    """Build a TrendIndicator comparing current vs previous period."""
    change_percent = (
        None if previous == 0 else round(((current - previous) / previous) * 100, 1)
    )
    return TrendIndicator(previous_value=previous, change_percent=change_percent)


def _previous_period(
    start_date: date | None, end_date: date | None
) -> tuple[date, date]:
    """Return the immediately preceding period of equal length."""
    today = date.today()
    end = end_date or today
    start = start_date or (end - timedelta(days=30))
    duration = (end - start).days
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=duration)
    return prev_start, prev_end


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


_VALID_ACTIVITY_TYPES = {
    "customer_created",
    "subscription_created",
    "invoice_finalized",
    "payment_received",
    "subscription_canceled",
    "payment_failed",
    "credit_note_created",
    "wallet_topped_up",
}


@router.get(
    "/activity",
    response_model=list[RecentActivityResponse],
    summary="Get recent activity feed",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_recent_activity(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    type: str | None = Query(None, description="Filter by activity type"),
) -> list[RecentActivityResponse]:
    """Get recent billing activity, optionally filtered by type."""
    repo = DashboardRepository(db)
    activities: list[RecentActivityResponse] = []
    include_types = _VALID_ACTIVITY_TYPES
    if type and type in _VALID_ACTIVITY_TYPES:
        include_types = {type}

    if "customer_created" in include_types:
        for c in repo.recent_customers(organization_id):
            activities.append(
                RecentActivityResponse(
                    id=str(c.id),
                    type="customer_created",
                    description=f'New customer "{c.name}" created',
                    timestamp=c.created_at.isoformat() if c.created_at else "",
                    resource_type="customer",
                    resource_id=str(c.id),
                )
            )

    if "subscription_created" in include_types:
        for s in repo.recent_subscriptions(organization_id):
            activities.append(
                RecentActivityResponse(
                    id=str(s.id),
                    type="subscription_created",
                    description=f"Subscription {s.external_id} started",
                    timestamp=s.created_at.isoformat() if s.created_at else "",
                    resource_type="subscription",
                    resource_id=str(s.id),
                )
            )

    if "invoice_finalized" in include_types:
        for inv in repo.recent_invoices(organization_id):
            activities.append(
                RecentActivityResponse(
                    id=str(inv.id),
                    type="invoice_finalized",
                    description=f"Invoice {inv.invoice_number} {inv.status}",
                    timestamp=inv.created_at.isoformat() if inv.created_at else "",
                    resource_type="invoice",
                    resource_id=str(inv.id),
                )
            )

    if "payment_received" in include_types:
        for p in repo.recent_payments(organization_id):
            amount_str = f" ${float(p.amount):,.2f}" if p.amount else ""
            activities.append(
                RecentActivityResponse(
                    id=str(p.id),
                    type="payment_received",
                    description=f"Payment{amount_str} received",
                    timestamp=p.created_at.isoformat() if p.created_at else "",
                    resource_type="payment",
                    resource_id=str(p.id),
                )
            )

    if "subscription_canceled" in include_types:
        for s in repo.recent_canceled_subscriptions(organization_id):
            activities.append(
                RecentActivityResponse(
                    id=str(s.id),
                    type="subscription_canceled",
                    description=f"Subscription {s.external_id} {s.status}",
                    timestamp=(
                        s.canceled_at.isoformat() if s.canceled_at else
                        s.created_at.isoformat() if s.created_at else ""
                    ),
                    resource_type="subscription",
                    resource_id=str(s.id),
                )
            )

    if "payment_failed" in include_types:
        for p in repo.recent_failed_payments(organization_id):
            amount_str = f" ${float(p.amount):,.2f}" if p.amount else ""
            activities.append(
                RecentActivityResponse(
                    id=str(p.id),
                    type="payment_failed",
                    description=f"Payment{amount_str} failed",
                    timestamp=p.created_at.isoformat() if p.created_at else "",
                    resource_type="payment",
                    resource_id=str(p.id),
                )
            )

    if "credit_note_created" in include_types:
        for cn in repo.recent_credit_notes(organization_id):
            activities.append(
                RecentActivityResponse(
                    id=str(cn.id),
                    type="credit_note_created",
                    description=f"Credit note {cn.number} created",
                    timestamp=cn.created_at.isoformat() if cn.created_at else "",
                    resource_type="credit_note",
                    resource_id=str(cn.id),
                )
            )

    if "wallet_topped_up" in include_types:
        for wt in repo.recent_wallet_topups(organization_id):
            amount_str = f" {float(wt.credit_amount):,.2f} credits" if wt.credit_amount else ""
            activities.append(
                RecentActivityResponse(
                    id=str(wt.id),
                    type="wallet_topped_up",
                    description=f"Wallet topped up{amount_str}",
                    timestamp=wt.created_at.isoformat() if wt.created_at else "",
                    resource_type="wallet",
                    resource_id=str(wt.wallet_id),
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
    mrr = repo.sum_monthly_revenue(
        organization_id, start_date=start_date, end_date=end_date
    )
    prev_start, prev_end = _previous_period(start_date, end_date)
    prev_mrr = repo.sum_monthly_revenue(
        organization_id, start_date=prev_start, end_date=prev_end
    )
    return RevenueResponse(
        mrr_cents=mrr,
        total_revenue_this_month_cents=mrr,
        outstanding_invoices_cents=repo.outstanding_invoices_total(organization_id),
        overdue_amount_cents=repo.overdue_invoices_total(organization_id),
        currency="USD",
        monthly_trend=[
            RevenueDataPoint(month=m.month, revenue_cents=m.revenue)
            for m in trend
        ],
        mrr_trend=_compute_trend(mrr, prev_mrr),
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
    new_count = repo.new_customers_this_month(
        organization_id, start_date=start_date, end_date=end_date
    )
    churned_count = repo.churned_customers_this_month(
        organization_id, start_date=start_date, end_date=end_date
    )
    prev_start, prev_end = _previous_period(start_date, end_date)
    prev_new = repo.new_customers_this_month(
        organization_id, start_date=prev_start, end_date=prev_end
    )
    prev_churned = repo.churned_customers_this_month(
        organization_id, start_date=prev_start, end_date=prev_end
    )
    return CustomerMetricsResponse(
        total=repo.count_customers(organization_id),
        new_this_month=new_count,
        churned_this_month=churned_count,
        new_trend=_compute_trend(new_count, prev_new),
        churned_trend=_compute_trend(churned_count, prev_churned),
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
    new_count = repo.new_subscriptions_this_month(
        organization_id, start_date=start_date, end_date=end_date
    )
    canceled_count = repo.canceled_subscriptions_this_month(
        organization_id, start_date=start_date, end_date=end_date
    )
    prev_start, prev_end = _previous_period(start_date, end_date)
    prev_new = repo.new_subscriptions_this_month(
        organization_id, start_date=prev_start, end_date=prev_end
    )
    prev_canceled = repo.canceled_subscriptions_this_month(
        organization_id, start_date=prev_start, end_date=prev_end
    )
    return SubscriptionMetricsResponse(
        active=repo.count_active_subscriptions(organization_id),
        new_this_month=new_count,
        canceled_this_month=canceled_count,
        by_plan=[
            SubscriptionPlanBreakdown(plan_name=p.plan_name, count=p.count)
            for p in by_plan
        ],
        new_trend=_compute_trend(new_count, prev_new),
        canceled_trend=_compute_trend(canceled_count, prev_canceled),
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


@router.get(
    "/revenue_by_plan",
    response_model=RevenueByPlanResponse,
    summary="Get revenue breakdown by plan",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_revenue_by_plan(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    start_date: date | None = Query(None, description="Period start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="Period end date (YYYY-MM-DD)"),
) -> RevenueByPlanResponse:
    """Get revenue breakdown by plan for donut chart visualization."""
    repo = DashboardRepository(db)
    by_plan = repo.revenue_by_plan(
        organization_id, start_date=start_date, end_date=end_date
    )
    return RevenueByPlanResponse(
        by_plan=[
            PlanRevenueBreakdown(plan_name=p.plan_name, revenue_cents=p.revenue)
            for p in by_plan
        ],
        currency="USD",
    )


@router.get(
    "/recent_invoices",
    response_model=list[RecentInvoiceItem],
    summary="Get recent invoices for dashboard",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_recent_invoices(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[RecentInvoiceItem]:
    """Get the 5 most recent invoices with customer names."""
    repo = DashboardRepository(db)
    rows = repo.recent_invoices_with_customer(organization_id)
    return [
        RecentInvoiceItem(
            id=r.id,
            invoice_number=r.invoice_number,
            customer_name=r.customer_name,
            status=r.status,
            total_cents=r.total,
            currency=r.currency,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/recent_subscriptions",
    response_model=list[RecentSubscriptionItem],
    summary="Get recent subscriptions for dashboard",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_recent_subscriptions(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[RecentSubscriptionItem]:
    """Get the 5 most recent subscriptions with customer and plan names."""
    repo = DashboardRepository(db)
    rows = repo.recent_subscriptions_with_details(organization_id)
    return [
        RecentSubscriptionItem(
            id=r.id,
            external_id=r.external_id,
            customer_name=r.customer_name,
            plan_name=r.plan_name,
            status=r.status,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/sparklines",
    response_model=SparklineData,
    summary="Get sparkline data for stat cards",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_sparklines(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    start_date: date | None = Query(None, description="Period start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="Period end date (YYYY-MM-DD)"),
) -> SparklineData:
    """Get daily data points for sparkline charts in stat cards."""
    repo = DashboardRepository(db)
    return SparklineData(
        mrr=[
            SparklinePoint(date=p.date, value=p.value)
            for p in repo.daily_revenue(
                organization_id, start_date=start_date, end_date=end_date
            )
        ],
        new_customers=[
            SparklinePoint(date=p.date, value=p.value)
            for p in repo.daily_new_customers(
                organization_id, start_date=start_date, end_date=end_date
            )
        ],
        new_subscriptions=[
            SparklinePoint(date=p.date, value=p.value)
            for p in repo.daily_new_subscriptions(
                organization_id, start_date=start_date, end_date=end_date
            )
        ],
    )


@router.get(
    "/revenue_analytics",
    response_model=RevenueAnalyticsResponse,
    summary="Get revenue analytics deep-dive",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_revenue_analytics(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
    start_date: date | None = Query(None, description="Period start date (YYYY-MM-DD)"),
    end_date: date | None = Query(None, description="Period end date (YYYY-MM-DD)"),
) -> RevenueAnalyticsResponse:
    """Get comprehensive revenue analytics: daily trend, by type, top customers,
    collection metrics, and net revenue."""
    repo = DashboardRepository(db)

    daily = repo.daily_revenue(
        organization_id, start_date=start_date, end_date=end_date
    )
    by_type = repo.revenue_by_invoice_type(
        organization_id, start_date=start_date, end_date=end_date
    )
    top_custs = repo.top_customers_by_revenue(
        organization_id, start_date=start_date, end_date=end_date
    )
    coll = repo.collection_metrics(
        organization_id, start_date=start_date, end_date=end_date
    )
    net = repo.net_revenue(
        organization_id, start_date=start_date, end_date=end_date
    )

    collection_rate = (
        round((coll.total_collected / coll.total_invoiced) * 100, 1)
        if coll.total_invoiced > 0
        else 0.0
    )

    return RevenueAnalyticsResponse(
        daily_revenue=[
            DailyRevenuePoint(date=p.date, revenue_cents=p.value) for p in daily
        ],
        revenue_by_type=[
            RevenueByTypeBreakdown(
                invoice_type=r.invoice_type, revenue_cents=r.revenue, count=r.count
            )
            for r in by_type
        ],
        top_customers=[
            TopCustomerRevenue(
                customer_id=r.customer_id,
                customer_name=r.customer_name,
                revenue_cents=r.revenue,
                invoice_count=r.invoice_count,
            )
            for r in top_custs
        ],
        collection=CollectionMetrics(
            total_invoiced_cents=coll.total_invoiced,
            total_collected_cents=coll.total_collected,
            collection_rate=collection_rate,
            average_days_to_payment=coll.avg_days_to_payment,
            overdue_count=coll.overdue_count,
            overdue_amount_cents=coll.overdue_amount,
        ),
        net_revenue=NetRevenueMetrics(
            gross_revenue_cents=net.gross_revenue,
            refunds_cents=net.refunds,
            credit_notes_cents=net.credit_notes_total,
            net_revenue_cents=net.gross_revenue - net.refunds - net.credit_notes_total,
            currency="USD",
        ),
        currency="USD",
    )
