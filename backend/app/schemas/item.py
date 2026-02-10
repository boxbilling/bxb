from datetime import datetime

from pydantic import BaseModel


class ItemCreate(BaseModel):
    name: str
    description: str | None = None
    price: float
    quantity: int = 0


class ItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    quantity: int | None = None


class ItemResponse(BaseModel):
    id: int
    name: str
    description: str | None
    price: float
    quantity: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
