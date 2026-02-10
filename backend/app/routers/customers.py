from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import Customer
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter()


@router.get("/", response_model=list[CustomerResponse])
async def list_customers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[Customer]:
    """List all customers with pagination."""
    repo = CustomerRepository(db)
    return repo.get_all(skip=skip, limit=limit)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
) -> Customer:
    """Get a customer by ID."""
    repo = CustomerRepository(db)
    customer = repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("/", response_model=CustomerResponse, status_code=201)
async def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
) -> Customer:
    """Create a new customer."""
    repo = CustomerRepository(db)
    if repo.external_id_exists(data.external_id):
        raise HTTPException(status_code=409, detail="Customer with this external_id already exists")
    return repo.create(data)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
) -> Customer:
    """Update a customer."""
    repo = CustomerRepository(db)
    customer = repo.update(customer_id, data)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a customer."""
    repo = CustomerRepository(db)
    if not repo.delete(customer_id):
        raise HTTPException(status_code=404, detail="Customer not found")
