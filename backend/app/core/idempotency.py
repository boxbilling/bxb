"""Idempotency support for API endpoints.

Provides a FastAPI dependency that checks for the ``Idempotency-Key`` header.
If a cached response exists for the key, the dependency returns a JSONResponse
directly; otherwise it returns ``None`` so the endpoint can proceed normally.
After the endpoint completes, call ``record_idempotency_response`` to persist
the response for future replays.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.repositories.idempotency_repository import IdempotencyRepository


@dataclass
class IdempotencyResult:
    """Holds pending idempotency key info for later recording."""

    key: str
    method: str
    path: str


def check_idempotency(
    request: Request,
    db: Session,
    organization_id: UUID,
) -> JSONResponse | IdempotencyResult | None:
    """Check the ``Idempotency-Key`` header for a cached response.

    Returns:
        - ``None`` if no ``Idempotency-Key`` header is present (no idempotency).
        - A ``JSONResponse`` with the cached response and ``Idempotency-Replayed: true``
          header if a completed record already exists.
        - An ``IdempotencyResult`` with the key details if this is a new request that
          should be recorded after processing.
    """
    key = request.headers.get("Idempotency-Key")
    if not key:
        return None

    repo = IdempotencyRepository(db)
    existing = repo.get_by_key(organization_id, key)

    if existing is not None and existing.response_status is not None:
        response = JSONResponse(
            content=existing.response_body,
            status_code=int(existing.response_status),
        )
        response.headers["Idempotency-Replayed"] = "true"
        return response

    if existing is None:
        repo.create(
            organization_id=organization_id,
            idempotency_key=key,
            request_method=request.method,
            request_path=request.url.path,
        )

    return IdempotencyResult(
        key=key,
        method=request.method,
        path=request.url.path,
    )


def record_idempotency_response(
    db: Session,
    organization_id: UUID,
    key: str,
    status: int,
    body: dict[str, Any],
) -> None:
    """Persist the endpoint response so subsequent calls return the cached result."""
    repo = IdempotencyRepository(db)
    record = repo.get_by_key(organization_id, key)
    if record is not None:
        repo.update_response(record, status, body)
