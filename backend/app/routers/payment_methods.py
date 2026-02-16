"""Payment methods API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.payment_method import PaymentMethod
from app.repositories.customer_repository import CustomerRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.schemas.payment_method import (
    PaymentMethodCreate,
    PaymentMethodResponse,
    SetupSessionCreate,
    SetupSessionResponse,
)
from app.services.payment_provider import get_payment_provider

router = APIRouter()


@router.get(
    "/",
    response_model=list[PaymentMethodResponse],
    summary="List payment methods",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_payment_methods(
    response: Response,
    customer_id: UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    order_by: str | None = Query(default=None),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[PaymentMethod]:
    """List payment methods with optional customer filter."""
    repo = PaymentMethodRepository(db)
    return repo.get_all(
        organization_id=organization_id,
        customer_id=customer_id,
        skip=skip,
        limit=limit,
        order_by=order_by,
    )


@router.get(
    "/{payment_method_id}",
    response_model=PaymentMethodResponse,
    summary="Get payment method",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Payment method not found"},
    },
)
async def get_payment_method(
    payment_method_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> PaymentMethod:
    """Get a payment method by ID."""
    repo = PaymentMethodRepository(db)
    pm = repo.get_by_id(payment_method_id, organization_id)
    if not pm:
        raise HTTPException(status_code=404, detail="Payment method not found")
    return pm


@router.post(
    "/",
    response_model=PaymentMethodResponse,
    status_code=201,
    summary="Create payment method",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        422: {"description": "Validation error"},
    },
)
async def create_payment_method(
    data: PaymentMethodCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> PaymentMethod:
    """Create a new payment method."""
    repo = PaymentMethodRepository(db)
    return repo.create(data, organization_id)


@router.delete(
    "/{payment_method_id}",
    status_code=204,
    summary="Delete payment method",
    responses={
        400: {"description": "Cannot delete default payment method"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Payment method not found"},
    },
)
async def delete_payment_method(
    payment_method_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a payment method. Returns 400 if it is the default."""
    repo = PaymentMethodRepository(db)
    pm = repo.get_by_id(payment_method_id, organization_id)
    if not pm:
        raise HTTPException(status_code=404, detail="Payment method not found")
    if pm.is_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the default payment method",
        )
    repo.delete(payment_method_id, organization_id)


@router.post(
    "/{payment_method_id}/set_default",
    response_model=PaymentMethodResponse,
    summary="Set default payment method",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Payment method not found"},
    },
)
async def set_default_payment_method(
    payment_method_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> PaymentMethod:
    """Set a payment method as the default for its customer."""
    repo = PaymentMethodRepository(db)
    # Verify it belongs to this organization
    pm = repo.get_by_id(payment_method_id, organization_id)
    if not pm:
        raise HTTPException(status_code=404, detail="Payment method not found")
    result = repo.set_default(payment_method_id)
    if not result:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Payment method not found")
    return result


@router.post(
    "/setup",
    response_model=SetupSessionResponse,
    summary="Create setup session",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer not found"},
        501: {"description": "Provider does not support setup sessions"},
        503: {"description": "Payment provider not configured"},
    },
)
async def create_setup_session(
    data: SetupSessionCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> SetupSessionResponse:
    """Create a setup session for saving payment details."""
    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(data.customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    provider_svc = get_payment_provider(data.provider)
    try:
        session = provider_svc.create_checkout_setup_session(
            customer_id=data.customer_id,
            customer_email=customer.email,  # type: ignore[arg-type]
            success_url=data.success_url,
            cancel_url=data.cancel_url,
        )
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail=f"{data.provider.value} does not support setup sessions",
        ) from None
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Payment provider not configured",
        ) from None

    return SetupSessionResponse(
        setup_id=session.provider_setup_id,
        setup_url=session.setup_url,
        provider=data.provider.value,
        expires_at=session.expires_at,
    )
