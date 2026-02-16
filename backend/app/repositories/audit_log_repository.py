"""Repository for AuditLog CRUD operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.audit_log import AuditLog
from app.models.customer import generate_uuid


class AuditLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        organization_id: UUID,
        resource_type: str,
        resource_id: UUID,
        action: str,
        changes: dict[str, Any],
        actor_type: str,
        actor_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            id=generate_uuid(),
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            changes=changes,
            actor_type=actor_type,
            actor_id=actor_id,
            metadata_=metadata,
        )
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        return audit_log

    def get_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        resource_type: str | None = None,
        action: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        actor_type: str | None = None,
        order_by: str | None = None,
    ) -> list[AuditLog]:
        query = self.db.query(AuditLog).filter(
            AuditLog.organization_id == organization_id
        )
        if resource_type is not None:
            query = query.filter(AuditLog.resource_type == resource_type)
        if action is not None:
            query = query.filter(AuditLog.action == action)
        if start_date is not None:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date is not None:
            query = query.filter(AuditLog.created_at <= end_date)
        if actor_type is not None:
            query = query.filter(AuditLog.actor_type == actor_type)
        query = apply_order_by(query, AuditLog, order_by)
        return query.offset(skip).limit(limit).all()
