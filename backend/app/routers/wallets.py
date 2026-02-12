"""Wallet API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.wallet import Wallet, WalletStatus
from app.models.wallet_transaction import WalletTransaction
from app.repositories.wallet_repository import WalletRepository
from app.repositories.wallet_transaction_repository import WalletTransactionRepository
from app.schemas.wallet import WalletCreate, WalletResponse, WalletTopUp, WalletUpdate
from app.schemas.wallet_transaction import WalletTransactionResponse
from app.services.wallet_service import WalletService

router = APIRouter()


@router.post("/", response_model=WalletResponse, status_code=201)
async def create_wallet(
    data: WalletCreate,
    db: Session = Depends(get_db),
) -> Wallet:
    """Create a wallet for a customer."""
    service = WalletService(db)
    try:
        return service.create_wallet(
            customer_id=data.customer_id,
            name=data.name,
            code=data.code,
            rate_amount=data.rate_amount,
            currency=data.currency,
            expiration_at=data.expiration_at,
            priority=data.priority,
            initial_granted_credits=data.initial_granted_credits,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/", response_model=list[WalletResponse])
async def list_wallets(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    customer_id: UUID | None = None,
    status: WalletStatus | None = None,
    db: Session = Depends(get_db),
) -> list[Wallet]:
    """List wallets with optional filters."""
    repo = WalletRepository(db)
    return repo.get_all(skip=skip, limit=limit, customer_id=customer_id, status=status)


@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet(
    wallet_id: UUID,
    db: Session = Depends(get_db),
) -> Wallet:
    """Get a wallet by ID."""
    repo = WalletRepository(db)
    wallet = repo.get_by_id(wallet_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.put("/{wallet_id}", response_model=WalletResponse)
async def update_wallet(
    wallet_id: UUID,
    data: WalletUpdate,
    db: Session = Depends(get_db),
) -> Wallet:
    """Update a wallet (name, expiration_at, priority)."""
    repo = WalletRepository(db)
    wallet = repo.update(wallet_id, data)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.delete("/{wallet_id}", status_code=204)
async def terminate_wallet(
    wallet_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Terminate a wallet (soft delete: sets status=terminated)."""
    service = WalletService(db)
    try:
        service.terminate_wallet(wallet_id)
    except ValueError as e:
        detail = str(e)
        if "not found" in detail:
            raise HTTPException(status_code=404, detail=detail) from None
        raise HTTPException(status_code=400, detail=detail) from None


@router.post("/{wallet_id}/top_up", response_model=WalletResponse)
async def top_up_wallet(
    wallet_id: UUID,
    data: WalletTopUp,
    db: Session = Depends(get_db),
) -> Wallet:
    """Top up a wallet with credits."""
    service = WalletService(db)
    try:
        return service.top_up_wallet(
            wallet_id=wallet_id,
            credits=data.credits,
            source=data.source,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/{wallet_id}/transactions", response_model=list[WalletTransactionResponse])
async def list_wallet_transactions(
    wallet_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[WalletTransaction]:
    """List transactions for a wallet."""
    # Verify wallet exists
    wallet_repo = WalletRepository(db)
    wallet = wallet_repo.get_by_id(wallet_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    txn_repo = WalletTransactionRepository(db)
    return txn_repo.get_by_wallet_id(wallet_id, skip=skip, limit=limit)
