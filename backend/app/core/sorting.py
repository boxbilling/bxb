"""Shared sorting utilities for repository queries."""

from __future__ import annotations

from sqlalchemy import asc, desc
from sqlalchemy.orm import Query

from app.core.database import Base


def apply_order_by(
    query: Query,  # type: ignore[type-arg]
    model: type[Base],
    order_by: str | None,
    default_field: str = "created_at",
    default_direction: str = "desc",
) -> Query:  # type: ignore[type-arg]
    """Apply ordering to a SQLAlchemy query.

    Args:
        query: The SQLAlchemy query to sort.
        model: The SQLAlchemy model class.
        order_by: Sort string in "field:direction" format (e.g. "name:asc").
            If None, uses default_field and default_direction.
        default_field: Default column to sort by.
        default_direction: Default sort direction ("asc" or "desc").

    Returns:
        The query with ordering applied.
    """
    field = default_field
    direction = default_direction

    if order_by:
        parts = order_by.split(":", 1)
        candidate_field = parts[0]
        candidate_direction = parts[1] if len(parts) > 1 else "asc"

        # Validate column exists on model
        if hasattr(model, candidate_field):
            field = candidate_field
            if candidate_direction in ("asc", "desc"):
                direction = candidate_direction
            else:
                direction = default_direction

    column = getattr(model, field)
    order_func = asc if direction == "asc" else desc
    return query.order_by(order_func(column))
