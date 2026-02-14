"""Audit service for recording state changes to billing entities."""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.audit_log_repository import AuditLogRepository


class AuditService:
    """Service for recording audit trail entries."""

    def __init__(self, db: Session):
        self.repo = AuditLogRepository(db)

    def log_create(
        self,
        resource_type: str,
        resource_id: UUID,
        organization_id: UUID,
        actor_type: str = "system",
        actor_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Log a resource creation event."""
        self.repo.create(
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action="created",
            changes=data or {},
            actor_type=actor_type,
            actor_id=actor_id,
        )

    def log_update(
        self,
        resource_type: str,
        resource_id: UUID,
        organization_id: UUID,
        actor_type: str = "system",
        actor_id: str | None = None,
        old_data: dict[str, Any] | None = None,
        new_data: dict[str, Any] | None = None,
    ) -> None:
        """Log a resource update event, auto-diffing changed fields."""
        old = old_data or {}
        new = new_data or {}
        changes: dict[str, Any] = {}
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}
        if not changes:
            return
        self.repo.create(
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action="updated",
            changes=changes,
            actor_type=actor_type,
            actor_id=actor_id,
        )

    def log_status_change(
        self,
        resource_type: str,
        resource_id: UUID,
        organization_id: UUID,
        old_status: str,
        new_status: str,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> None:
        """Log a status change event."""
        self.repo.create(
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action="status_changed",
            changes={"status": {"old": old_status, "new": new_status}},
            actor_type=actor_type,
            actor_id=actor_id,
        )
