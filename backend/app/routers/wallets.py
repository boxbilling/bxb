"""Wallet API endpoints."""

from datetime import datetime
from decimal import Decimal
from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.wallet import Wallet, WalletStatus
from app.models.wallet_transaction import WalletTransaction
from app.repositories.wallet_repository import WalletRepository
from app.repositories.wallet_transaction_repository import WalletTransactionRepository
from app.schemas.wallet import (
    BalanceTimelinePoint,
    BalanceTimelineResponse,
    DepletionForecastResponse,
    WalletCreate,
    WalletResponse,
    WalletTopUp,
    WalletTransferRequest,
    WalletTransferResponse,
    WalletUpdate,
)
from app.schemas.wallet_transaction import WalletTransactionResponse
from app.services.wallet_service import WalletService

router = APIRouter()


@router.post(
    "/",
    response_model=WalletResponse,
    status_code=201,
    summary="Create wallet",
    responses={
        400: {"description": "Invalid customer reference or validation error"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        422: {"description": "Validation error"},
    },
)
async def create_wallet(
    data: WalletCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Wallet:
    """Create a wallet for a customer."""
    service = WalletService(db)
    try:
        return service.create_wallet(  # type: ignore[return-value]
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


@router.get(
    "/",
    response_model=list[WalletResponse],
    summary="List wallets",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_wallets(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    customer_id: UUID | None = None,
    status: WalletStatus | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Wallet]:
    """List wallets with optional filters."""
    repo = WalletRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(
        organization_id,
        skip=skip,
        limit=limit,
        customer_id=customer_id,
        status=status,
    )


@router.get(
    "/{wallet_id}",
    response_model=WalletResponse,
    summary="Get wallet",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Wallet not found"},
    },
)
async def get_wallet(
    wallet_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Wallet:
    """Get a wallet by ID."""
    repo = WalletRepository(db)
    wallet = repo.get_by_id(wallet_id, organization_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.put(
    "/{wallet_id}",
    response_model=WalletResponse,
    summary="Update wallet",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Wallet not found"},
        422: {"description": "Validation error"},
    },
)
async def update_wallet(
    wallet_id: UUID,
    data: WalletUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Wallet:
    """Update a wallet (name, expiration_at, priority)."""
    repo = WalletRepository(db)
    wallet = repo.update(wallet_id, data)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.delete(
    "/{wallet_id}",
    status_code=204,
    summary="Terminate wallet",
    responses={
        400: {"description": "Wallet cannot be terminated in current state"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Wallet not found"},
    },
)
async def terminate_wallet(
    wallet_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
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


@router.post(
    "/{wallet_id}/top_up",
    response_model=WalletResponse,
    summary="Top up wallet",
    responses={
        400: {"description": "Invalid top-up amount or wallet state"},
        401: {"description": "Unauthorized – invalid or missing API key"},
    },
)
async def top_up_wallet(
    wallet_id: UUID,
    data: WalletTopUp,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Wallet:
    """Top up a wallet with credits."""
    service = WalletService(db)
    try:
        return service.top_up_wallet(  # type: ignore[return-value]
            wallet_id=wallet_id,
            credits=data.credits,
            source=data.source,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get(
    "/{wallet_id}/transactions",
    response_model=list[WalletTransactionResponse],
    summary="List wallet transactions",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Wallet not found"},
    },
)
async def list_wallet_transactions(
    wallet_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[WalletTransaction]:
    """List transactions for a wallet."""
    # Verify wallet exists
    wallet_repo = WalletRepository(db)
    wallet = wallet_repo.get_by_id(wallet_id, organization_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    txn_repo = WalletTransactionRepository(db)
    return txn_repo.get_by_wallet_id(wallet_id, skip=skip, limit=limit)


@router.get(
    "/{wallet_id}/balance_timeline",
    response_model=BalanceTimelineResponse,
    summary="Get wallet balance timeline",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Wallet not found"},
    },
)
async def get_balance_timeline(
    wallet_id: UUID,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> BalanceTimelineResponse:
    """Get daily balance timeline for a wallet showing credits in/out over time."""
    wallet_repo = WalletRepository(db)
    wallet = wallet_repo.get_by_id(wallet_id, organization_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    txn_repo = WalletTransactionRepository(db)
    raw_points = txn_repo.daily_balance_timeline(wallet_id, start_date, end_date)

    # Compute running balance
    running_balance = Decimal("0")
    points = []
    for p in raw_points:
        inbound = Decimal(str(p["inbound"]))
        outbound = Decimal(str(p["outbound"]))
        running_balance += inbound - outbound
        points.append(
            BalanceTimelinePoint(
                date=str(p["date"]),
                inbound=inbound,
                outbound=outbound,
                balance=running_balance,
            )
        )

    return BalanceTimelineResponse(wallet_id=wallet_id, points=points)


@router.get(
    "/{wallet_id}/depletion_forecast",
    response_model=DepletionForecastResponse,
    summary="Get wallet depletion forecast",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Wallet not found"},
    },
)
async def get_depletion_forecast(
    wallet_id: UUID,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> DepletionForecastResponse:
    """Get projected depletion date based on consumption rate."""
    wallet_repo = WalletRepository(db)
    wallet = wallet_repo.get_by_id(wallet_id, organization_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    txn_repo = WalletTransactionRepository(db)
    avg_daily = txn_repo.avg_daily_consumption(wallet_id, days=days)

    balance = Decimal(str(wallet.balance_cents))
    projected_date = None
    days_remaining = None

    if avg_daily > 0 and balance > 0:
        from datetime import UTC, timedelta

        remaining_days = int(ceil(float(balance / avg_daily)))
        days_remaining = remaining_days
        projected_date = datetime.now(UTC) + timedelta(days=remaining_days)

    return DepletionForecastResponse(
        wallet_id=wallet_id,
        current_balance_cents=balance,
        avg_daily_consumption=avg_daily,
        projected_depletion_date=projected_date,
        days_remaining=days_remaining,
    )


@router.post(
    "/transfer",
    response_model=WalletTransferResponse,
    summary="Transfer credits between wallets",
    responses={
        400: {"description": "Invalid transfer request"},
        401: {"description": "Unauthorized – invalid or missing API key"},
    },
)
async def transfer_credits(
    data: WalletTransferRequest,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> WalletTransferResponse:
    """Transfer credits from one wallet to another."""
    service = WalletService(db)
    try:
        source, target = service.transfer_credits(
            source_wallet_id=data.source_wallet_id,
            target_wallet_id=data.target_wallet_id,
            credits=data.credits,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return WalletTransferResponse(
        source_wallet=WalletResponse.model_validate(source),
        target_wallet=WalletResponse.model_validate(target),
        credits_transferred=data.credits,
    )
