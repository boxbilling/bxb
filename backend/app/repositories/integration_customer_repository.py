"""IntegrationCustomer repository for data access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.integration_customer import IntegrationCustomer
from app.schemas.integration_customer import IntegrationCustomerCreate, IntegrationCustomerUpdate


class IntegrationCustomerRepository:
    """Repository for IntegrationCustomer model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        integration_id: UUID,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[IntegrationCustomer]:
        """Get all integration customers for an integration."""
        query = (
            self.db.query(IntegrationCustomer)
            .filter(IntegrationCustomer.integration_id == integration_id)
        )
        query = apply_order_by(query, IntegrationCustomer, order_by)
        return query.offset(skip).limit(limit).all()

    def get_by_id(self, integration_customer_id: UUID) -> IntegrationCustomer | None:
        """Get an integration customer by ID."""
        return (
            self.db.query(IntegrationCustomer)
            .filter(IntegrationCustomer.id == integration_customer_id)
            .first()
        )

    def get_by_customer(
        self,
        integration_id: UUID,
        customer_id: UUID,
    ) -> IntegrationCustomer | None:
        """Get an integration customer by integration and customer ID."""
        return (
            self.db.query(IntegrationCustomer)
            .filter(
                IntegrationCustomer.integration_id == integration_id,
                IntegrationCustomer.customer_id == customer_id,
            )
            .first()
        )

    def get_by_external_customer_id(
        self,
        integration_id: UUID,
        external_customer_id: str,
    ) -> IntegrationCustomer | None:
        """Get an integration customer by external customer ID."""
        return (
            self.db.query(IntegrationCustomer)
            .filter(
                IntegrationCustomer.integration_id == integration_id,
                IntegrationCustomer.external_customer_id == external_customer_id,
            )
            .first()
        )

    def create(self, data: IntegrationCustomerCreate) -> IntegrationCustomer:
        """Create a new integration customer link."""
        ic = IntegrationCustomer(
            integration_id=data.integration_id,
            customer_id=data.customer_id,
            external_customer_id=data.external_customer_id,
            settings=data.settings,
        )
        self.db.add(ic)
        self.db.commit()
        self.db.refresh(ic)
        return ic

    def update(
        self,
        integration_customer_id: UUID,
        data: IntegrationCustomerUpdate,
    ) -> IntegrationCustomer | None:
        """Update an integration customer."""
        ic = self.get_by_id(integration_customer_id)
        if not ic:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(ic, key, value)
        self.db.commit()
        self.db.refresh(ic)
        return ic

    def delete(self, integration_customer_id: UUID) -> bool:
        """Delete an integration customer link."""
        ic = self.get_by_id(integration_customer_id)
        if not ic:
            return False
        self.db.delete(ic)
        self.db.commit()
        return True
