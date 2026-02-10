from uuid import UUID

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        return self.db.query(Customer).offset(skip).limit(limit).all()

    def get_by_id(self, customer_id: UUID) -> Customer | None:
        return self.db.query(Customer).filter(Customer.id == customer_id).first()

    def get_by_external_id(self, external_id: str) -> Customer | None:
        return self.db.query(Customer).filter(Customer.external_id == external_id).first()

    def create(self, data: CustomerCreate) -> Customer:
        customer = Customer(**data.model_dump())
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def update(self, customer_id: UUID, data: CustomerUpdate) -> Customer | None:
        customer = self.get_by_id(customer_id)
        if not customer:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(customer, key, value)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def delete(self, customer_id: UUID) -> bool:
        customer = self.get_by_id(customer_id)
        if not customer:
            return False
        self.db.delete(customer)
        self.db.commit()
        return True

    def external_id_exists(self, external_id: str) -> bool:
        """Check if a customer with the given external_id already exists."""
        query = self.db.query(Customer).filter(Customer.external_id == external_id)
        return query.first() is not None
