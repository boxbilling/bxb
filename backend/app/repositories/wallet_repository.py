"""Wallet repository for data access."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.wallet import Wallet, WalletStatus
from app.schemas.wallet import WalletCreate, WalletUpdate


class WalletRepository:
    """Repository for Wallet model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        customer_id: UUID | None = None,
        status: WalletStatus | None = None,
    ) -> list[Wallet]:
        """Get all wallets with optional filters."""
        query = self.db.query(Wallet).filter(Wallet.organization_id == organization_id)

        if customer_id:
            query = query.filter(Wallet.customer_id == customer_id)
        if status:
            query = query.filter(Wallet.status == status.value)

        return query.order_by(Wallet.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_id(self, wallet_id: UUID, organization_id: UUID | None = None) -> Wallet | None:
        """Get a wallet by ID."""
        query = self.db.query(Wallet).filter(Wallet.id == wallet_id)
        if organization_id is not None:
            query = query.filter(Wallet.organization_id == organization_id)
        return query.first()

    def get_by_customer_id(self, customer_id: UUID) -> list[Wallet]:
        """Get all wallets for a customer."""
        return (
            self.db.query(Wallet)
            .filter(Wallet.customer_id == customer_id)
            .order_by(Wallet.priority.asc(), Wallet.created_at.asc())
            .all()
        )

    def get_active_by_customer_id(self, customer_id: UUID) -> list[Wallet]:
        """Get active, non-expired wallets for a customer, ordered by priority ASC."""
        now = datetime.now(UTC)
        return (
            self.db.query(Wallet)
            .filter(
                Wallet.customer_id == customer_id,
                Wallet.status == WalletStatus.ACTIVE.value,
            )
            .filter(
                (Wallet.expiration_at.is_(None)) | (Wallet.expiration_at > now)
            )
            .order_by(Wallet.priority.asc(), Wallet.created_at.asc())
            .all()
        )

    def create(self, data: WalletCreate, organization_id: UUID | None = None) -> Wallet:
        """Create a new wallet."""
        wallet = Wallet(
            customer_id=data.customer_id,
            name=data.name,
            code=data.code,
            rate_amount=data.rate_amount,
            currency=data.currency,
            expiration_at=data.expiration_at,
            priority=data.priority,
            organization_id=organization_id,
        )
        self.db.add(wallet)
        self.db.commit()
        self.db.refresh(wallet)
        return wallet

    def update(self, wallet_id: UUID, data: WalletUpdate) -> Wallet | None:
        """Update a wallet."""
        wallet = self.get_by_id(wallet_id)
        if not wallet:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(wallet, key, value)

        self.db.commit()
        self.db.refresh(wallet)
        return wallet

    def terminate(self, wallet_id: UUID) -> Wallet | None:
        """Terminate a wallet (soft delete)."""
        wallet = self.get_by_id(wallet_id)
        if not wallet:
            return None
        if wallet.status == WalletStatus.TERMINATED.value:
            return wallet

        wallet.status = WalletStatus.TERMINATED.value  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(wallet)
        return wallet

    def update_balance(
        self, wallet_id: UUID, credits: Decimal, amount_cents: Decimal
    ) -> Wallet | None:
        """Add credits and balance to a wallet (for top-ups)."""
        wallet = self.get_by_id(wallet_id)
        if not wallet:
            return None

        wallet.credits_balance = Decimal(str(wallet.credits_balance)) + credits  # type: ignore[assignment]
        wallet.balance_cents = Decimal(str(wallet.balance_cents)) + amount_cents  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(wallet)
        return wallet

    def deduct_balance(
        self, wallet_id: UUID, credits: Decimal, amount_cents: Decimal
    ) -> Wallet | None:
        """Deduct credits and balance from a wallet (for consumption)."""
        wallet = self.get_by_id(wallet_id)
        if not wallet:
            return None

        wallet.credits_balance = Decimal(str(wallet.credits_balance)) - credits  # type: ignore[assignment]
        wallet.balance_cents = Decimal(str(wallet.balance_cents)) - amount_cents  # type: ignore[assignment]
        wallet.consumed_credits = Decimal(str(wallet.consumed_credits)) + credits  # type: ignore[assignment]
        wallet.consumed_amount_cents = Decimal(str(wallet.consumed_amount_cents)) + amount_cents  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(wallet)
        return wallet
