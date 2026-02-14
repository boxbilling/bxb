from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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


@dataclass
class MonthlyRevenue:
    month: str
    revenue: float


@dataclass
class PlanSubscriptionCount:
    plan_name: str
    count: int


@dataclass
class MetricUsage:
    metric_name: str
    metric_code: str
    event_count: int


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

    def sum_monthly_revenue(self, organization_id: UUID) -> float:
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        result = (
            self.db.query(sa_func.coalesce(sa_func.sum(Invoice.total), 0))
            .filter(
                Invoice.organization_id == organization_id,
                Invoice.status.in_(["finalized", "paid"]),
                Invoice.issued_at >= thirty_days_ago,
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
        self, organization_id: UUID, months: int = 12
    ) -> list[MonthlyRevenue]:
        """Revenue per month for the last N months, ordered oldest first."""
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

    def new_customers_this_month(self, organization_id: UUID) -> int:
        """Count of customers created in the current calendar month."""
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (
            self.db.query(sa_func.count(Customer.id))
            .filter(
                Customer.organization_id == organization_id,
                Customer.created_at >= month_start,
            )
            .scalar()
            or 0
        )

    def churned_customers_this_month(self, organization_id: UUID) -> int:
        """Count of customers whose subscriptions were all canceled/terminated this month."""
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (
            self.db.query(sa_func.count(sa_func.distinct(Subscription.customer_id)))
            .filter(
                Subscription.organization_id == organization_id,
                Subscription.status.in_(
                    [SubscriptionStatus.CANCELED.value, SubscriptionStatus.TERMINATED.value]
                ),
                Subscription.canceled_at.isnot(None),
                Subscription.canceled_at >= month_start,
            )
            .scalar()
            or 0
        )

    # --- Subscription analytics ---

    def new_subscriptions_this_month(self, organization_id: UUID) -> int:
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (
            self.db.query(sa_func.count(Subscription.id))
            .filter(
                Subscription.organization_id == organization_id,
                Subscription.created_at >= month_start,
            )
            .scalar()
            or 0
        )

    def canceled_subscriptions_this_month(self, organization_id: UUID) -> int:
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (
            self.db.query(sa_func.count(Subscription.id))
            .filter(
                Subscription.organization_id == organization_id,
                Subscription.status.in_(
                    [SubscriptionStatus.CANCELED.value, SubscriptionStatus.TERMINATED.value]
                ),
                Subscription.canceled_at.isnot(None),
                Subscription.canceled_at >= month_start,
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
        self, organization_id: UUID, limit: int = 5
    ) -> list[MetricUsage]:
        """Top billable metrics by event count in the last 30 days."""
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
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
                Event.timestamp >= thirty_days_ago,
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
