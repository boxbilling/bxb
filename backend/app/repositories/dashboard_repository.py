from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.billable_metric import BillableMetric
from app.models.customer import Customer
from app.models.event import Event
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentStatus
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.wallet import Wallet, WalletStatus


def _resolve_period(
    start_date: date | None, end_date: date | None, default_days: int = 30
) -> tuple[datetime, datetime]:
    """Return (start_dt, end_dt) as UTC datetimes from optional date params."""
    end_dt = (
        datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=UTC)
        if end_date
        else datetime.now(UTC)
    )
    start_dt = (
        datetime(start_date.year, start_date.month, start_date.day, tzinfo=UTC)
        if start_date
        else end_dt - timedelta(days=default_days)
    )
    return start_dt, end_dt


@dataclass
class MonthlyRevenue:
    month: str
    revenue: float


@dataclass
class PlanSubscriptionCount:
    plan_name: str
    count: int


@dataclass
class PlanRevenue:
    plan_name: str
    revenue: float


@dataclass
class MetricUsage:
    metric_name: str
    metric_code: str
    event_count: int


@dataclass
class RecentInvoiceRow:
    id: str
    invoice_number: str
    customer_name: str
    status: str
    total: float
    currency: str
    created_at: str


@dataclass
class RecentSubscriptionRow:
    id: str
    external_id: str
    customer_name: str
    plan_name: str
    status: str
    created_at: str


class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db

    def count_customers(self, organization_id: UUID) -> int:
        return (
            self.db.query(sa_func.count(Customer.id))
            .filter(Customer.organization_id == organization_id)
            .scalar()
            or 0
        )

    def count_active_subscriptions(self, organization_id: UUID) -> int:
        return (
            self.db.query(sa_func.count(Subscription.id))
            .filter(
                Subscription.organization_id == organization_id,
                Subscription.status == SubscriptionStatus.ACTIVE.value,
            )
            .scalar()
            or 0
        )

    def sum_monthly_revenue(
        self,
        organization_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> float:
        start_dt, end_dt = _resolve_period(start_date, end_date, default_days=30)
        result = (
            self.db.query(sa_func.coalesce(sa_func.sum(Invoice.total), 0))
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.status.in_(["finalized", "paid"]),
                Invoice.issued_at >= start_dt,
                Invoice.issued_at <= end_dt,
            )
            .scalar()
            or 0
        )
        return float(result)

    def sum_total_invoiced(self, organization_id: UUID) -> float:
        result = (
            self.db.query(sa_func.coalesce(sa_func.sum(Invoice.total), 0))
            .filter(Invoice.organization_id == organization_id)
            .scalar()
            or 0
        )
        return float(result)

    def recent_customers(self, organization_id: UUID, limit: int = 5) -> list[Customer]:
        return (
            self.db.query(Customer)
            .filter(Customer.organization_id == organization_id)
            .order_by(Customer.created_at.desc())
            .limit(limit)
            .all()
        )

    def recent_subscriptions(self, organization_id: UUID, limit: int = 5) -> list[Subscription]:
        return (
            self.db.query(Subscription)
            .filter(Subscription.organization_id == organization_id)
            .order_by(Subscription.created_at.desc())
            .limit(limit)
            .all()
        )

    def recent_invoices(self, organization_id: UUID, limit: int = 5) -> list[Invoice]:
        return (
            self.db.query(Invoice)
            .filter(Invoice.organization_id == organization_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
            .all()
        )

    def recent_payments(self, organization_id: UUID, limit: int = 5) -> list[Payment]:
        return (
            self.db.query(Payment)
            .filter(
                Payment.organization_id == organization_id,
                Payment.status == PaymentStatus.SUCCEEDED.value,
            )
            .order_by(Payment.created_at.desc())
            .limit(limit)
            .all()
        )

    # --- Revenue analytics ---

    def outstanding_invoices_total(self, organization_id: UUID) -> float:
        """Sum of finalized (unpaid) invoices."""
        result = (
            self.db.query(sa_func.coalesce(sa_func.sum(Invoice.total), 0))
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.status == "finalized",
            )
            .scalar()
            or 0
        )
        return float(result)

    def overdue_invoices_total(self, organization_id: UUID) -> float:
        """Sum of finalized invoices whose due_date has passed."""
        now = datetime.now(UTC)
        result = (
            self.db.query(sa_func.coalesce(sa_func.sum(Invoice.total), 0))
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.status == "finalized",
                Invoice.due_date.isnot(None),
                Invoice.due_date < now,
            )
            .scalar()
            or 0
        )
        return float(result)

    def monthly_revenue_trend(
        self,
        organization_id: UUID,
        months: int = 12,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[MonthlyRevenue]:
        """Revenue per month for the last N months, ordered oldest first."""
        if start_date or end_date:
            start_dt, end_dt = _resolve_period(start_date, end_date, default_days=months * 31)
            # Calculate months from the date range
            months = max(
                1,
                (end_dt.year - start_dt.year) * 12 + end_dt.month - start_dt.month + 1,
            )
            now = end_dt
            cutoff = start_dt
        else:
            now = datetime.now(UTC)
            cutoff = now - timedelta(days=months * 31)

        # Build a year-month expression compatible with both SQLite and PostgreSQL
        dialect = self.db.bind.dialect.name if self.db.bind else ""
        if dialect == "postgresql":
            month_expr = sa_func.to_char(Invoice.issued_at, "YYYY-MM")
        else:
            month_expr = sa_func.strftime("%Y-%m", Invoice.issued_at)

        rows = (
            self.db.query(
                month_expr.label("month"),
                sa_func.coalesce(sa_func.sum(Invoice.total), 0).label("revenue"),
            )
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.status.in_(["finalized", "paid"]),
                Invoice.issued_at.isnot(None),
                Invoice.issued_at >= cutoff,
                Invoice.issued_at <= now,
            )
            .group_by(month_expr)
            .order_by(month_expr)
            .all()
        )

        # Build entries for all months (dict preserves insertion order, setdefault deduplicates)
        revenue_map = {row.month: float(row.revenue) for row in rows}
        months_dict: dict[str, float] = {}

        for i in range(months - 1, -1, -1):
            d = now - timedelta(days=i * 30)
            key = d.strftime("%Y-%m")
            months_dict.setdefault(key, revenue_map.get(key, 0.0))

        return [MonthlyRevenue(month=k, revenue=v) for k, v in months_dict.items()]

    # --- Customer analytics ---

    def new_customers_this_month(
        self,
        organization_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        """Count of customers created in the period (default: current calendar month)."""
        if start_date or end_date:
            start_dt, end_dt = _resolve_period(start_date, end_date, default_days=30)
        else:
            now = datetime.now(UTC)
            start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
        return (
            self.db.query(sa_func.count(Customer.id))
            .filter(
                Customer.organization_id == organization_id,
                Customer.created_at >= start_dt,
                Customer.created_at <= end_dt,
            )
            .scalar()
            or 0
        )

    def churned_customers_this_month(
        self,
        organization_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        """Count of customers whose subscriptions were all canceled/terminated in the period."""
        if start_date or end_date:
            start_dt, end_dt = _resolve_period(start_date, end_date, default_days=30)
        else:
            now = datetime.now(UTC)
            start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
        return (
            self.db.query(sa_func.count(sa_func.distinct(Subscription.customer_id)))
            .filter(
                Subscription.organization_id == organization_id,
                Subscription.status.in_(
                    [SubscriptionStatus.CANCELED.value, SubscriptionStatus.TERMINATED.value]
                ),
                Subscription.canceled_at.isnot(None),
                Subscription.canceled_at >= start_dt,
                Subscription.canceled_at <= end_dt,
            )
            .scalar()
            or 0
        )

    # --- Subscription analytics ---

    def new_subscriptions_this_month(
        self,
        organization_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        if start_date or end_date:
            start_dt, end_dt = _resolve_period(start_date, end_date, default_days=30)
        else:
            now = datetime.now(UTC)
            start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
        return (
            self.db.query(sa_func.count(Subscription.id))
            .filter(
                Subscription.organization_id == organization_id,
                Subscription.created_at >= start_dt,
                Subscription.created_at <= end_dt,
            )
            .scalar()
            or 0
        )

    def canceled_subscriptions_this_month(
        self,
        organization_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        if start_date or end_date:
            start_dt, end_dt = _resolve_period(start_date, end_date, default_days=30)
        else:
            now = datetime.now(UTC)
            start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
        return (
            self.db.query(sa_func.count(Subscription.id))
            .filter(
                Subscription.organization_id == organization_id,
                Subscription.status.in_(
                    [SubscriptionStatus.CANCELED.value, SubscriptionStatus.TERMINATED.value]
                ),
                Subscription.canceled_at.isnot(None),
                Subscription.canceled_at >= start_dt,
                Subscription.canceled_at <= end_dt,
            )
            .scalar()
            or 0
        )

    def subscriptions_by_plan(
        self, organization_id: UUID
    ) -> list[PlanSubscriptionCount]:
        """Active subscription counts grouped by plan name."""
        rows = (
            self.db.query(
                Plan.name.label("plan_name"),
                sa_func.count(Subscription.id).label("sub_count"),
            )
            .join(Plan, Subscription.plan_id == Plan.id)
            .filter(
                Subscription.organization_id == organization_id,
                Subscription.status == SubscriptionStatus.ACTIVE.value,
            )
            .group_by(Plan.name)
            .order_by(sa_func.count(Subscription.id).desc())
            .all()
        )
        return [
            PlanSubscriptionCount(plan_name=row.plan_name, count=row.sub_count)
            for row in rows
        ]

    # --- Usage analytics ---

    def top_metrics_by_usage(
        self,
        organization_id: UUID,
        limit: int = 5,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[MetricUsage]:
        """Top billable metrics by event count in the given period (default: last 30 days)."""
        start_dt, end_dt = _resolve_period(start_date, end_date, default_days=30)
        rows = (
            self.db.query(
                BillableMetric.name.label("metric_name"),
                BillableMetric.code.label("metric_code"),
                sa_func.count(Event.id).label("event_count"),
            )
            .join(BillableMetric, Event.code == BillableMetric.code)
            .filter(
                Event.organization_id == organization_id,
                BillableMetric.organization_id == organization_id,
                Event.timestamp >= start_dt,
                Event.timestamp <= end_dt,
            )
            .group_by(BillableMetric.name, BillableMetric.code)
            .order_by(sa_func.count(Event.id).desc())
            .limit(limit)
            .all()
        )
        return [
            MetricUsage(
                metric_name=row.metric_name,
                metric_code=row.metric_code,
                event_count=row.event_count,
            )
            for row in rows
        ]

    # --- Revenue by plan ---

    def revenue_by_plan(
        self,
        organization_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[PlanRevenue]:
        """Revenue grouped by plan from finalized/paid invoices linked via subscriptions."""
        start_dt, end_dt = _resolve_period(start_date, end_date, default_days=30)
        rows = (
            self.db.query(
                Plan.name.label("plan_name"),
                sa_func.coalesce(sa_func.sum(Invoice.total), 0).label("revenue"),
            )
            .join(Subscription, Invoice.subscription_id == Subscription.id)
            .join(Plan, Subscription.plan_id == Plan.id)
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.status.in_(["finalized", "paid"]),
                Invoice.issued_at.isnot(None),
                Invoice.issued_at >= start_dt,
                Invoice.issued_at <= end_dt,
            )
            .group_by(Plan.name)
            .order_by(sa_func.sum(Invoice.total).desc())
            .all()
        )
        return [
            PlanRevenue(plan_name=row.plan_name, revenue=float(row.revenue))
            for row in rows
        ]

    # --- Recent items with joined names ---

    def recent_invoices_with_customer(
        self, organization_id: UUID, limit: int = 5
    ) -> list[RecentInvoiceRow]:
        """Return recent invoices joined with customer name."""
        rows = (
            self.db.query(
                Invoice.id,
                Invoice.invoice_number,
                Customer.name.label("customer_name"),
                Invoice.status,
                Invoice.total,
                Invoice.currency,
                Invoice.created_at,
            )
            .join(Customer, Invoice.customer_id == Customer.id)
            .filter(Invoice.organization_id == organization_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            RecentInvoiceRow(
                id=str(r.id),
                invoice_number=r.invoice_number,
                customer_name=r.customer_name,
                status=r.status,
                total=float(r.total),
                currency=r.currency,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ]

    def recent_subscriptions_with_details(
        self, organization_id: UUID, limit: int = 5
    ) -> list[RecentSubscriptionRow]:
        """Return recent subscriptions joined with customer and plan names."""
        rows = (
            self.db.query(
                Subscription.id,
                Subscription.external_id,
                Customer.name.label("customer_name"),
                Plan.name.label("plan_name"),
                Subscription.status,
                Subscription.created_at,
            )
            .join(Customer, Subscription.customer_id == Customer.id)
            .join(Plan, Subscription.plan_id == Plan.id)
            .filter(Subscription.organization_id == organization_id)
            .order_by(Subscription.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            RecentSubscriptionRow(
                id=str(r.id),
                external_id=r.external_id,
                customer_name=r.customer_name,
                plan_name=r.plan_name,
                status=r.status,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ]

    # --- Wallet summary ---

    def total_wallet_credits(self, organization_id: UUID) -> float:
        """Sum of credits_balance across all active wallets."""
        result = (
            self.db.query(sa_func.coalesce(sa_func.sum(Wallet.credits_balance), 0))
            .filter(
                Wallet.organization_id == organization_id,
                Wallet.status == WalletStatus.ACTIVE.value,
            )
            .scalar()
            or 0
        )
        return float(result)
