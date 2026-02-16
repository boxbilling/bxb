from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.schemas.search import GlobalSearchResponse, SearchResult

router = APIRouter()


@router.get(
    "/",
    response_model=GlobalSearchResponse,
    summary="Global search across customers, invoices, subscriptions, and plans",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def global_search(
    q: str = Query(
        ...,
        min_length=1,
        max_length=255,
        description="Search query string",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum results per type",
    ),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> GlobalSearchResponse:
    """Search across customers, invoices, subscriptions, and plans."""
    results: list[SearchResult] = []
    query_pattern = f"%{q}%"

    # Search customers (by name, email, external_id)
    customers = (
        db.query(Customer)
        .filter(
            Customer.organization_id == organization_id,
            or_(
                Customer.name.ilike(query_pattern),
                Customer.email.ilike(query_pattern),
                Customer.external_id.ilike(query_pattern),
            ),
        )
        .limit(limit)
        .all()
    )
    for c in customers:
        subtitle = str(c.email) if c.email else f"ID: {c.external_id}"
        results.append(
            SearchResult(
                type="customer",
                id=str(c.id),
                title=str(c.name),
                subtitle=subtitle,
                url=f"/admin/customers/{c.id}",
            )
        )

    # Search invoices (by invoice_number)
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.organization_id == organization_id,
            Invoice.invoice_number.ilike(query_pattern),
        )
        .limit(limit)
        .all()
    )
    for inv in invoices:
        results.append(
            SearchResult(
                type="invoice",
                id=str(inv.id),
                title=f"Invoice {inv.invoice_number}",
                subtitle=f"{inv.status} — {inv.currency} {inv.total}",
                url=f"/admin/invoices/{inv.id}",
            )
        )

    # Search subscriptions (by external_id)
    subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.organization_id == organization_id,
            Subscription.external_id.ilike(query_pattern),
        )
        .limit(limit)
        .all()
    )
    for sub in subscriptions:
        results.append(
            SearchResult(
                type="subscription",
                id=str(sub.id),
                title=f"Subscription {sub.external_id}",
                subtitle=str(sub.status),
                url=f"/admin/subscriptions/{sub.id}",
            )
        )

    # Search plans (by name, code)
    plans = (
        db.query(Plan)
        .filter(
            Plan.organization_id == organization_id,
            or_(
                Plan.name.ilike(query_pattern),
                Plan.code.ilike(query_pattern),
            ),
        )
        .limit(limit)
        .all()
    )
    for p in plans:
        results.append(
            SearchResult(
                type="plan",
                id=str(p.id),
                title=str(p.name),
                subtitle=f"Code: {p.code} — {p.interval}",
                url=f"/admin/plans/{p.id}",
            )
        )

    return GlobalSearchResponse(
        query=q,
        results=results,
        total_count=len(results),
    )
