"""Wallet service for managing prepaid credits."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.invoice_settlement import SettlementType
from app.models.wallet import Wallet, WalletStatus
from app.repositories.invoice_settlement_repository import InvoiceSettlementRepository
from app.repositories.wallet_repository import WalletRepository
from app.repositories.wallet_transaction_repository import WalletTransactionRepository
from app.schemas.invoice_settlement import InvoiceSettlementCreate
from app.schemas.wallet import WalletCreate
from app.schemas.wallet_transaction import (
    TransactionSource,
    TransactionStatus,
    TransactionTransactionStatus,
    TransactionType,
    WalletTransactionCreate,
)


@dataclass
class ConsumptionResult:
    """Result of a credit consumption operation."""

    total_consumed: Decimal
    remaining_amount: Decimal


class WalletService:
    """Service for wallet business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.wallet_repo = WalletRepository(db)
        self.txn_repo = WalletTransactionRepository(db)

    def create_wallet(
        self,
        customer_id: UUID,
        name: str | None = None,
        code: str | None = None,
        rate_amount: Decimal = Decimal("1"),
        currency: str = "USD",
        expiration_at: datetime | None = None,
        priority: int = 1,
        initial_granted_credits: Decimal | None = None,
    ) -> Wallet | None:
        """Create a wallet, optionally granting initial credits via inbound transaction."""
        # Check for duplicate code within same customer
        if code is not None:
            existing = self.wallet_repo.get_by_customer_id(customer_id)
            for w in existing:
                if w.code == code:
                    raise ValueError(f"Wallet with code '{code}' already exists for this customer")

        wallet = self.wallet_repo.create(
            WalletCreate(
                customer_id=customer_id,
                name=name,
                code=code,
                rate_amount=rate_amount,
                currency=currency,
                expiration_at=expiration_at,
                priority=priority,
            )
        )

        if initial_granted_credits and initial_granted_credits > 0:
            self.top_up_wallet(
                wallet_id=wallet.id,  # type: ignore[arg-type]
                credits=initial_granted_credits,
                source="manual",
            )
            # Refresh wallet to get updated balance
            wallet = self.wallet_repo.get_by_id(wallet.id)  # type: ignore[arg-type,assignment]

        return wallet

    def terminate_wallet(self, wallet_id: UUID) -> Wallet | None:
        """Terminate a wallet, preventing further transactions."""
        wallet = self.wallet_repo.get_by_id(wallet_id)
        if not wallet:
            raise ValueError(f"Wallet {wallet_id} not found")

        if wallet.status == WalletStatus.TERMINATED.value:
            raise ValueError("Wallet is already terminated")

        return self.wallet_repo.terminate(wallet_id)

    def top_up_wallet(
        self,
        wallet_id: UUID,
        credits: Decimal,
        source: str = "manual",
    ) -> Wallet | None:
        """Top up a wallet with credits. Creates an inbound transaction and updates balance."""
        wallet = self.wallet_repo.get_by_id(wallet_id)
        if not wallet:
            raise ValueError(f"Wallet {wallet_id} not found")

        if wallet.status == WalletStatus.TERMINATED.value:
            raise ValueError("Cannot top up a terminated wallet")

        if credits <= 0:
            raise ValueError("Credits must be positive")

        rate = Decimal(str(wallet.rate_amount))
        amount_cents = credits * rate

        # Create inbound transaction
        self.txn_repo.create(
            WalletTransactionCreate(
                wallet_id=wallet_id,
                customer_id=wallet.customer_id,  # type: ignore[arg-type]
                transaction_type=TransactionType.INBOUND,
                transaction_status=TransactionTransactionStatus.GRANTED,
                source=TransactionSource(source),
                status=TransactionStatus.SETTLED,
                amount=credits,
                credit_amount=amount_cents,
            )
        )

        # Update wallet balance
        return self.wallet_repo.update_balance(wallet_id, credits, amount_cents)

    def consume_credits(
        self,
        customer_id: UUID,
        amount_cents: Decimal,
        invoice_id: UUID | None = None,
    ) -> ConsumptionResult:
        """Priority-based consumption algorithm.

        1. Get all active, non-expired wallets ordered by priority ASC, created_at ASC
        2. For each wallet: calculate max consumable = min(wallet.balance_cents, remaining_amount)
        3. Deduct from wallet, create outbound transaction
        4. Continue until amount fully consumed or no wallets remain
        5. Return total consumed and remaining uncovered amount
        """
        remaining = Decimal(str(amount_cents))
        total_consumed = Decimal("0")

        wallets = self.wallet_repo.get_active_by_customer_id(customer_id)

        for wallet in wallets:
            if remaining <= 0:
                break

            wallet_balance = Decimal(str(wallet.balance_cents))
            if wallet_balance <= 0:
                continue

            consumable = min(wallet_balance, remaining)
            rate = Decimal(str(wallet.rate_amount))
            credits_consumed = consumable / rate if rate > 0 else Decimal("0")

            # Deduct from wallet
            self.wallet_repo.deduct_balance(wallet.id, credits_consumed, consumable)  # type: ignore[arg-type]

            # Create outbound transaction
            self.txn_repo.create(
                WalletTransactionCreate(
                    wallet_id=wallet.id,  # type: ignore[arg-type]
                    customer_id=customer_id,
                    transaction_type=TransactionType.OUTBOUND,
                    transaction_status=TransactionTransactionStatus.INVOICED,
                    source=TransactionSource.MANUAL,
                    status=TransactionStatus.SETTLED,
                    amount=credits_consumed,
                    credit_amount=consumable,
                    invoice_id=invoice_id,
                )
            )

            # Record settlement if this is for an invoice
            if invoice_id is not None:
                settlement_repo = InvoiceSettlementRepository(self.db)
                settlement_repo.create(
                    InvoiceSettlementCreate(
                        invoice_id=invoice_id,
                        settlement_type=SettlementType.WALLET_CREDIT,
                        source_id=wallet.id,  # type: ignore[arg-type]
                        amount_cents=consumable,
                    )
                )

            total_consumed += consumable
            remaining -= consumable

        return ConsumptionResult(
            total_consumed=total_consumed,
            remaining_amount=remaining,
        )

    def get_customer_balance(self, customer_id: UUID) -> Decimal:
        """Get total balance across all active wallets for a customer."""
        wallets = self.wallet_repo.get_active_by_customer_id(customer_id)
        return sum(
            (Decimal(str(w.balance_cents)) for w in wallets),
            Decimal("0"),
        )

    def check_expired_wallets(self) -> list[UUID]:
        """Find and terminate expired wallets. Returns list of terminated wallet IDs."""
        now = datetime.now(UTC)
        terminated_ids = []

        # Get all active wallets across all customers — we query directly
        from app.models.wallet import Wallet

        wallets = (
            self.db.query(Wallet)
            .filter(
                Wallet.status == WalletStatus.ACTIVE.value,
                Wallet.expiration_at.isnot(None),
                Wallet.expiration_at <= now,
            )
            .all()
        )

        for wallet in wallets:
            self.wallet_repo.terminate(wallet.id)  # type: ignore[arg-type]
            terminated_ids.append(wallet.id)

        return terminated_ids  # type: ignore[return-value]
