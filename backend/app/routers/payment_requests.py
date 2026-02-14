"""PaymentRequest API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.payment_request import PaymentRequest
from app.repositories.payment_request_repository import PaymentRequestRepository
from app.schemas.payment_request import (
    PaymentRequestCreate,
    PaymentRequestInvoiceResponse,
    PaymentRequestResponse,
)
from app.services.payment_request_service import PaymentRequestService

router = APIRouter()


def _pr_to_response(
    pr: PaymentRequest,
    repo: PaymentRequestRepository,
) -> PaymentRequestResponse:
    """Build a PaymentRequestResponse with invoice join rows loaded."""
    pr_id: UUID = pr.id  # type: ignore[assignment]
    invoices = repo.get_invoices(pr_id)
    invoice_responses = [PaymentRequestInvoiceResponse.model_validate(inv) for inv in invoices]
    resp = PaymentRequestResponse.model_validate(pr)
    resp.invoices = invoice_responses
    return resp


@router.post(
    "/",
    response_model=PaymentRequestResponse,
    status_code=201,
    summary="Create payment request",
    responses={
        400: {"description": "Invalid customer or invoice reference"},
        401: {"description": "Unauthorized"},
    },
)
async def create_payment_request(
    data: PaymentRequestCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> PaymentRequestResponse:
    """Create a manual payment request."""
    service = PaymentRequestService(db)
    try:
        pr = service.create_manual_payment_request(
            organization_id=organization_id,
            customer_id=data.customer_id,
            invoice_ids=data.invoice_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    repo = PaymentRequestRepository(db)
    return _pr_to_response(pr, repo)


@router.get(
    "/",
    response_model=list[PaymentRequestResponse],
    summary="List payment requests",
    responses={401: {"description": "Unauthorized"}},
)
async def list_payment_requests(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    customer_id: UUID | None = None,
    payment_status: str | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[PaymentRequestResponse]:
    """List payment requests with optional filters."""
    repo = PaymentRequestRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    prs = repo.get_all(
        organization_id,
        skip=skip,
        limit=limit,
        customer_id=customer_id,
        payment_status=payment_status,
    )
    return [_pr_to_response(pr, repo) for pr in prs]


@router.get(
    "/{request_id}",
    response_model=PaymentRequestResponse,
    summary="Get payment request",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Payment request not found"},
    },
)
async def get_payment_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> PaymentRequestResponse:
    """Get a payment request by ID."""
    repo = PaymentRequestRepository(db)
    pr = repo.get_by_id(request_id, organization_id)
    if not pr:
        raise HTTPException(status_code=404, detail="Payment request not found")
    return _pr_to_response(pr, repo)
