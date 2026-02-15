"""Repository for IdempotencyRecord CRUD operations."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.customer import generate_uuid
from app.models.idempotency_record import IdempotencyRecord


class IdempotencyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, organization_id: UUID, idempotency_key: str) -> IdempotencyRecord | None:
        return (
            self.db.query(IdempotencyRecord)
            .filter(
                IdempotencyRecord.organization_id == organization_id,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
            .first()
        )

    def create(
        self,
        *,
        organization_id: UUID,
        idempotency_key: str,
        request_method: str,
        request_path: str,
        response_status: int | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> IdempotencyRecord:
        record = IdempotencyRecord(
            id=generate_uuid(),
            organization_id=organization_id,
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            response_status=response_status,
            response_body=response_body,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_response(
        self,
        record: IdempotencyRecord,
        response_status: int,
        response_body: dict[str, Any],
    ) -> IdempotencyRecord:
        record.response_status = response_status  # type: ignore[assignment]
        record.response_body = response_body  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete_expired(self, max_age_hours: int = 24) -> int:
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        count = (
            self.db.query(IdempotencyRecord)
            .filter(IdempotencyRecord.created_at < cutoff)
            .delete()
        )
        self.db.commit()
        return int(count)
