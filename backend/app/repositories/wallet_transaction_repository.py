"""WalletTransaction repository for data access."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.wallet_transaction import TransactionType, WalletTransaction
from app.schemas.wallet_transaction import WalletTransactionCreate


class WalletTransactionRepository:
    """Repository for WalletTransaction model."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, data: WalletTransactionCreate) -> WalletTransaction:
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
        )
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def get_by_id(self, transaction_id: UUID) -> WalletTransaction | None:
        """Get a wallet transaction by ID."""
        return (
            self.db.query(WalletTransaction)
            .filter(WalletTransaction.id == transaction_id)
            .first()
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
