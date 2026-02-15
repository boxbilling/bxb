"""Webhook Endpoint and Webhook API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.webhook import Webhook
from app.models.webhook_endpoint import WebhookEndpoint
from app.repositories.webhook_endpoint_repository import WebhookEndpointRepository
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.webhook import (
    EndpointDeliveryStats,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    WebhookEndpointUpdate,
    WebhookResponse,
)
from app.services.webhook_service import WebhookService

router = APIRouter()


@router.post(
    "/",
    response_model=WebhookEndpointResponse,
    status_code=201,
    summary="Create webhook endpoint",
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Validation error"},
    },
)
async def create_webhook_endpoint(
    data: WebhookEndpointCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> WebhookEndpoint:
    """Create a new webhook endpoint."""
    repo = WebhookEndpointRepository(db)
    return repo.create(data, organization_id)


@router.get(
    "/",
    response_model=list[WebhookEndpointResponse],
    summary="List webhook endpoints",
    responses={401: {"description": "Unauthorized"}},
)
async def list_webhook_endpoints(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[WebhookEndpoint]:
    """List all webhook endpoints."""
    repo = WebhookEndpointRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(organization_id, skip=skip, limit=limit)


@router.get(
    "/delivery_stats",
    response_model=list[EndpointDeliveryStats],
    summary="Get delivery stats per endpoint",
    responses={401: {"description": "Unauthorized"}},
)
async def get_delivery_stats(
    db: Session = Depends(get_db),
) -> list[EndpointDeliveryStats]:
    """Get delivery success/failure stats grouped by webhook endpoint."""
    repo = WebhookRepository(db)
    raw_stats = repo.delivery_stats_by_endpoint()
    return [
        EndpointDeliveryStats(
            endpoint_id=s["endpoint_id"],
            total=s["total"],
            succeeded=s["succeeded"],
            failed=s["failed"],
            success_rate=round(s["succeeded"] / s["total"] * 100, 1) if s["total"] > 0 else 0.0,
        )
        for s in raw_stats
    ]


@router.get(
    "/{endpoint_id}",
    response_model=WebhookEndpointResponse,
    summary="Get webhook endpoint",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Webhook endpoint not found"},
    },
)
async def get_webhook_endpoint(
    endpoint_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> WebhookEndpoint:
    """Get a webhook endpoint by ID."""
    repo = WebhookEndpointRepository(db)
    endpoint = repo.get_by_id(endpoint_id, organization_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    return endpoint


@router.put(
    "/{endpoint_id}",
    response_model=WebhookEndpointResponse,
    summary="Update webhook endpoint",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Webhook endpoint not found"},
        422: {"description": "Validation error"},
    },
)
async def update_webhook_endpoint(
    endpoint_id: UUID,
    data: WebhookEndpointUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> WebhookEndpoint:
    """Update a webhook endpoint."""
    repo = WebhookEndpointRepository(db)
    endpoint = repo.update(endpoint_id, data, organization_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    return endpoint


@router.delete(
    "/{endpoint_id}",
    status_code=204,
    summary="Delete webhook endpoint",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Webhook endpoint not found"},
    },
)
async def delete_webhook_endpoint(
    endpoint_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a webhook endpoint."""
    repo = WebhookEndpointRepository(db)
    if not repo.delete(endpoint_id, organization_id):
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")


@router.get(
    "/hooks/list",
    response_model=list[WebhookResponse],
    summary="List recent webhooks",
    responses={401: {"description": "Unauthorized"}},
)
async def list_webhooks(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    webhook_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[Webhook]:
    """List recent webhooks with optional filters."""
    repo = WebhookRepository(db)
    response.headers["X-Total-Count"] = str(repo.count())
    return repo.get_all(
        skip=skip,
        limit=limit,
        webhook_type=webhook_type,
        status=status,
    )


@router.get(
    "/hooks/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook details",
    responses={404: {"description": "Webhook not found"}},
)
async def get_webhook(
    webhook_id: UUID,
    db: Session = Depends(get_db),
) -> Webhook:
    """Get webhook details."""
    repo = WebhookRepository(db)
    webhook = repo.get_by_id(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@router.post(
    "/hooks/{webhook_id}/retry",
    response_model=WebhookResponse,
    summary="Retry failed webhook",
    responses={
        400: {"description": "Only failed webhooks can be retried"},
        404: {"description": "Webhook not found"},
    },
)
async def retry_webhook(
    webhook_id: UUID,
    db: Session = Depends(get_db),
) -> Webhook:
    """Manually retry a failed webhook."""
    repo = WebhookRepository(db)
    webhook = repo.get_by_id(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if webhook.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed webhooks can be retried")

    service = WebhookService(db)
    repo.increment_retry(webhook_id)
    service.deliver_webhook(webhook_id)

    # Re-fetch to return updated state
    updated = repo.get_by_id(webhook_id)
    if not updated:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Webhook not found")
    return updated
