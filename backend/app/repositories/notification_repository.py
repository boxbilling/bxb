"""Repository for Notification CRUD operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.customer import generate_uuid
from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        organization_id: UUID,
        category: str,
        title: str,
        message: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> Notification:
        notification = Notification(
            id=generate_uuid(),
            organization_id=organization_id,
            category=category,
            title=title,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_by_id(self, notification_id: UUID) -> Notification | None:
        return (
            self.db.query(Notification)
            .filter(Notification.id == notification_id)
            .first()
        )

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 50,
        category: str | None = None,
        is_read: bool | None = None,
        order_by: str | None = None,
    ) -> list[Notification]:
        query = self.db.query(Notification).filter(
            Notification.organization_id == organization_id
        )
        if category is not None:
            query = query.filter(Notification.category == category)
        if is_read is not None:
            query = query.filter(Notification.is_read == is_read)
        query = apply_order_by(query, Notification, order_by)
        return query.offset(skip).limit(limit).all()

    def count_unread(self, organization_id: UUID) -> int:
        return (
            self.db.query(Notification)
            .filter(
                Notification.organization_id == organization_id,
                Notification.is_read == False,  # noqa: E712
            )
            .count()
        )

    def mark_as_read(self, notification_id: UUID) -> Notification | None:
        notification = self.get_by_id(notification_id)
        if notification is None:
            return None
        notification.is_read = True  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_all_as_read(self, organization_id: UUID) -> int:
        count = (
            self.db.query(Notification)
            .filter(
                Notification.organization_id == organization_id,
                Notification.is_read == False,  # noqa: E712
            )
            .update({"is_read": True})
        )
        self.db.commit()
        return count
