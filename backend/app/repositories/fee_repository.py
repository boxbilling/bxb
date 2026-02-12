"""Fee repository for data access."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.fee import Fee, FeePaymentStatus, FeeType
from app.schemas.fee import FeeCreate, FeeUpdate


class FeeRepository:
    """Repository for Fee model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        invoice_id: UUID | None = None,
        customer_id: UUID | None = None,
        subscription_id: UUID | None = None,
        charge_id: UUID | None = None,
        fee_type: FeeType | None = None,
        payment_status: FeePaymentStatus | None = None,
        organization_id: UUID | None = None,
    ) -> list[Fee]:
        """Get all fees with optional filters."""
        query = self.db.query(Fee)

        if organization_id is not None:
            query = query.filter(Fee.organization_id == organization_id)
        if invoice_id:
            query = query.filter(Fee.invoice_id == invoice_id)
        if customer_id:
            query = query.filter(Fee.customer_id == customer_id)
        if subscription_id:
            query = query.filter(Fee.subscription_id == subscription_id)
        if charge_id:
            query = query.filter(Fee.charge_id == charge_id)
        if fee_type:
            query = query.filter(Fee.fee_type == fee_type.value)
        if payment_status:
            query = query.filter(Fee.payment_status == payment_status.value)

        return query.order_by(Fee.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_id(self, fee_id: UUID, organization_id: UUID | None = None) -> Fee | None:
        """Get a fee by ID."""
        query = self.db.query(Fee).filter(Fee.id == fee_id)
        if organization_id is not None:
            query = query.filter(Fee.organization_id == organization_id)
        return query.first()

    def get_by_invoice_id(self, invoice_id: UUID) -> list[Fee]:
        """Get all fees for an invoice."""
        return (
            self.db.query(Fee)
            .filter(Fee.invoice_id == invoice_id)
            .order_by(Fee.created_at.asc())
            .all()
        )

    def get_by_customer_id(self, customer_id: UUID, skip: int = 0, limit: int = 100) -> list[Fee]:
        """Get all fees for a customer."""
        return (
            self.db.query(Fee)
            .filter(Fee.customer_id == customer_id)
            .order_by(Fee.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_subscription_id(self, subscription_id: UUID) -> list[Fee]:
        """Get all fees for a subscription."""
        return (
            self.db.query(Fee)
            .filter(Fee.subscription_id == subscription_id)
            .order_by(Fee.created_at.desc())
            .all()
        )

    def create(self, data: FeeCreate, organization_id: UUID | None = None) -> Fee:
        """Create a new fee."""
        fee = Fee(
            invoice_id=data.invoice_id,
            charge_id=data.charge_id,
            subscription_id=data.subscription_id,
            customer_id=data.customer_id,
            fee_type=data.fee_type.value,
            amount_cents=data.amount_cents,
            taxes_amount_cents=data.taxes_amount_cents,
            total_amount_cents=data.total_amount_cents,
            units=data.units,
            events_count=data.events_count,
            unit_amount_cents=data.unit_amount_cents,
            payment_status=data.payment_status.value,
            description=data.description,
            metric_code=data.metric_code,
            properties=data.properties,
            organization_id=organization_id,
        )
        self.db.add(fee)
        self.db.commit()
        self.db.refresh(fee)
        return fee

    def create_bulk(
        self, fees_data: list[FeeCreate], organization_id: UUID | None = None,
    ) -> list[Fee]:
        """Create multiple fees at once."""
        fees = []
        for data in fees_data:
            fee = Fee(
                invoice_id=data.invoice_id,
                charge_id=data.charge_id,
                subscription_id=data.subscription_id,
                customer_id=data.customer_id,
                fee_type=data.fee_type.value,
                amount_cents=data.amount_cents,
                taxes_amount_cents=data.taxes_amount_cents,
                total_amount_cents=data.total_amount_cents,
                units=data.units,
                events_count=data.events_count,
                unit_amount_cents=data.unit_amount_cents,
                payment_status=data.payment_status.value,
                description=data.description,
                metric_code=data.metric_code,
                properties=data.properties,
                organization_id=organization_id,
            )
            self.db.add(fee)
            fees.append(fee)

        self.db.commit()
        for fee in fees:
            self.db.refresh(fee)
        return fees

    def update(self, fee_id: UUID, data: FeeUpdate) -> Fee | None:
        """Update a fee."""
        fee = self.get_by_id(fee_id)
        if not fee:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Convert payment_status enum to string value
        if "payment_status" in update_data and update_data["payment_status"]:
            update_data["payment_status"] = update_data["payment_status"].value

        for key, value in update_data.items():
            setattr(fee, key, value)

        self.db.commit()
        self.db.refresh(fee)
        return fee

    def delete(self, fee_id: UUID) -> bool:
        """Delete a fee."""
        fee = self.get_by_id(fee_id)
        if not fee:
            return False

        self.db.delete(fee)
        self.db.commit()
        return True

    def mark_succeeded(self, fee_id: UUID) -> Fee | None:
        """Mark a fee as succeeded."""
        fee = self.get_by_id(fee_id)
        if not fee:
            return None

        fee.payment_status = FeePaymentStatus.SUCCEEDED.value  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(fee)
        return fee

    def mark_failed(self, fee_id: UUID) -> Fee | None:
        """Mark a fee as failed."""
        fee = self.get_by_id(fee_id)
        if not fee:
            return None

        fee.payment_status = FeePaymentStatus.FAILED.value  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(fee)
        return fee
