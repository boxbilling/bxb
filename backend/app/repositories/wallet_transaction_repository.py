"""WalletTransaction repository for data access."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.wallet_transaction import TransactionType, WalletTransaction
from app.schemas.wallet_transaction import WalletTransactionCreate


class WalletTransactionRepository:
    """Repository for WalletTransaction model."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        data: WalletTransactionCreate,
        organization_id: UUID | None = None,
    ) -> WalletTransaction:
        """Create a new wallet transaction."""
        txn = WalletTransaction(
            wallet_id=data.wallet_id,
            customer_id=data.customer_id,
            transaction_type=data.transaction_type.value,
            transaction_status=data.transaction_status.value,
            source=data.source.value,
            status=data.status.value,
            amount=data.amount,
            credit_amount=data.credit_amount,
            invoice_id=data.invoice_id,
            organization_id=organization_id,
        )
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def get_by_id(self, transaction_id: UUID) -> WalletTransaction | None:
        """Get a wallet transaction by ID."""
        return (
            self.db.query(WalletTransaction).filter(WalletTransaction.id == transaction_id).first()
        )

    def get_by_wallet_id(
        self, wallet_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[WalletTransaction]:
        """Get all transactions for a wallet."""
        return (
            self.db.query(WalletTransaction)
            .filter(WalletTransaction.wallet_id == wallet_id)
            .order_by(WalletTransaction.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_customer_id(
        self, customer_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[WalletTransaction]:
        """Get all transactions for a customer."""
        return (
            self.db.query(WalletTransaction)
            .filter(WalletTransaction.customer_id == customer_id)
            .order_by(WalletTransaction.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_inbound_by_wallet_id(
        self, wallet_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[WalletTransaction]:
        """Get all inbound transactions for a wallet."""
        return (
            self.db.query(WalletTransaction)
            .filter(
                WalletTransaction.wallet_id == wallet_id,
                WalletTransaction.transaction_type == TransactionType.INBOUND.value,
            )
            .order_by(WalletTransaction.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_outbound_by_wallet_id(
        self, wallet_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[WalletTransaction]:
        """Get all outbound transactions for a wallet."""
        return (
            self.db.query(WalletTransaction)
            .filter(
                WalletTransaction.wallet_id == wallet_id,
                WalletTransaction.transaction_type == TransactionType.OUTBOUND.value,
            )
            .order_by(WalletTransaction.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def daily_balance_timeline(
        self,
        wallet_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, str | Decimal]]:
        """Get daily inbound/outbound aggregation for a wallet.

        Returns list of dicts with keys: date, inbound, outbound.
        """
        dialect = self.db.bind.dialect.name if self.db.bind else "sqlite"
        if dialect == "postgresql":
            day_expr = func.date_trunc("day", WalletTransaction.created_at)
        else:
            day_expr = func.date(WalletTransaction.created_at)

        inbound_sum = func.coalesce(
            func.sum(
                case(
                    (
                        WalletTransaction.transaction_type == TransactionType.INBOUND.value,
                        WalletTransaction.credit_amount,
                    ),
                    else_=Decimal("0"),
                )
            ),
            Decimal("0"),
        )
        outbound_sum = func.coalesce(
            func.sum(
                case(
                    (
                        WalletTransaction.transaction_type == TransactionType.OUTBOUND.value,
                        WalletTransaction.credit_amount,
                    ),
                    else_=Decimal("0"),
                )
            ),
            Decimal("0"),
        )

        query = (
            self.db.query(
                day_expr.label("day"),
                inbound_sum.label("inbound"),
                outbound_sum.label("outbound"),
            )
            .filter(WalletTransaction.wallet_id == wallet_id)
        )
        if start_date:
            query = query.filter(WalletTransaction.created_at >= start_date)
        if end_date:
            query = query.filter(WalletTransaction.created_at <= end_date)

        rows = query.group_by(day_expr).order_by(day_expr.asc()).all()

        return [
            {
                "date": str(row.day)[:10] if row.day else "",
                "inbound": Decimal(str(row.inbound)),
                "outbound": Decimal(str(row.outbound)),
            }
            for row in rows
        ]

    def avg_daily_consumption(self, wallet_id: UUID, days: int = 30) -> Decimal:
        """Calculate average daily outbound (consumption) over the last N days."""
        from datetime import UTC, timedelta

        cutoff = datetime.now(UTC) - timedelta(days=days)

        result = (
            self.db.query(func.coalesce(func.sum(WalletTransaction.credit_amount), Decimal("0")))
            .filter(
                WalletTransaction.wallet_id == wallet_id,
                WalletTransaction.transaction_type == TransactionType.OUTBOUND.value,
                WalletTransaction.created_at >= cutoff,
            )
            .scalar()
        )

        total = Decimal(str(result))
        return total / days
