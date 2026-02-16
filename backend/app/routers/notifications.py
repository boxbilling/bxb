"""Notification API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationCountResponse, NotificationResponse

router = APIRouter()


@router.get(
    "/",
    response_model=list[NotificationResponse],
    summary="List notifications",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_notifications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    category: str | None = None,
    is_read: bool | None = None,
    order_by: str | None = Query(default=None),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[NotificationResponse]:
    """List notifications with optional filters."""
    repo = NotificationRepository(db)
    notifications = repo.get_all(
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        category=category,
        is_read=is_read,
        order_by=order_by,
    )
    return [NotificationResponse.model_validate(n) for n in notifications]


@router.get(
    "/unread_count",
    response_model=NotificationCountResponse,
    summary="Get unread notification count",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_unread_count(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> NotificationCountResponse:
    """Get the count of unread notifications."""
    repo = NotificationRepository(db)
    count = repo.count_unread(organization_id)
    return NotificationCountResponse(unread_count=count)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a notification as read",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Notification not found"},
    },
)
async def mark_as_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> NotificationResponse:
    """Mark a single notification as read."""
    repo = NotificationRepository(db)
    notification = repo.get_by_id(notification_id)
    if notification is None or notification.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Notification not found")
    updated = repo.mark_as_read(notification_id)
    return NotificationResponse.model_validate(updated)


@router.post(
    "/read_all",
    response_model=NotificationCountResponse,
    summary="Mark all notifications as read",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def mark_all_as_read(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> NotificationCountResponse:
    """Mark all unread notifications as read."""
    repo = NotificationRepository(db)
    count = repo.mark_all_as_read(organization_id)
    return NotificationCountResponse(unread_count=count)
