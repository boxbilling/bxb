"""Repository for PaymentMethod CRUD operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.payment_method import PaymentMethod
from app.schemas.payment_method import PaymentMethodCreate, PaymentMethodUpdate


class PaymentMethodRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        customer_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[PaymentMethod]:
        query = self.db.query(PaymentMethod).filter(
            PaymentMethod.organization_id == organization_id
        )
        if customer_id is not None:
            query = query.filter(PaymentMethod.customer_id == customer_id)
        query = apply_order_by(query, PaymentMethod, order_by)
        return query.offset(skip).limit(limit).all()

    def get_by_id(
        self, payment_method_id: UUID, organization_id: UUID | None = None
    ) -> PaymentMethod | None:
        query = self.db.query(PaymentMethod).filter(PaymentMethod.id == payment_method_id)
        if organization_id is not None:
            query = query.filter(PaymentMethod.organization_id == organization_id)
        return query.first()

    def get_by_customer_id(
        self, customer_id: UUID, organization_id: UUID
    ) -> list[PaymentMethod]:
        return (
            self.db.query(PaymentMethod)
            .filter(
                PaymentMethod.customer_id == customer_id,
                PaymentMethod.organization_id == organization_id,
            )
            .all()
        )

    def get_default(
        self, customer_id: UUID, organization_id: UUID
    ) -> PaymentMethod | None:
        return (
            self.db.query(PaymentMethod)
            .filter(
                PaymentMethod.customer_id == customer_id,
                PaymentMethod.organization_id == organization_id,
                PaymentMethod.is_default == True,  # noqa: E712
            )
            .first()
        )

    def set_default(self, payment_method_id: UUID) -> PaymentMethod | None:
        payment_method = (
            self.db.query(PaymentMethod).filter(PaymentMethod.id == payment_method_id).first()
        )
        if not payment_method:
            return None
        # Unset other defaults for the same customer and organization
        self.db.query(PaymentMethod).filter(
            PaymentMethod.customer_id == payment_method.customer_id,
            PaymentMethod.organization_id == payment_method.organization_id,
            PaymentMethod.is_default == True,  # noqa: E712
        ).update({"is_default": False})
        payment_method.is_default = True  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(payment_method)
        return payment_method

    def create(self, data: PaymentMethodCreate, organization_id: UUID) -> PaymentMethod:
        payment_method = PaymentMethod(
            customer_id=data.customer_id,
            provider=data.provider,
            provider_payment_method_id=data.provider_payment_method_id,
            type=data.type,
            is_default=data.is_default,
            details=data.details,
            organization_id=organization_id,
        )
        self.db.add(payment_method)
        self.db.commit()
        self.db.refresh(payment_method)
        return payment_method

    def update(
        self,
        payment_method_id: UUID,
        data: PaymentMethodUpdate,
        organization_id: UUID,
    ) -> PaymentMethod | None:
        payment_method = self.get_by_id(payment_method_id, organization_id)
        if not payment_method:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(payment_method, key, value)
        self.db.commit()
        self.db.refresh(payment_method)
        return payment_method

    def delete(self, payment_method_id: UUID, organization_id: UUID) -> bool:
        payment_method = self.get_by_id(payment_method_id, organization_id)
        if not payment_method:
            return False
        self.db.delete(payment_method)
        self.db.commit()
        return True
