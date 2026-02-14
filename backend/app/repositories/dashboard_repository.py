from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import Subscription, SubscriptionStatus


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
