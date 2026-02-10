from sqlalchemy.orm import Session

from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate


class ItemRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Item]:
        return self.db.query(Item).offset(skip).limit(limit).all()

    def get_by_id(self, item_id: int) -> Item | None:
        return self.db.query(Item).filter(Item.id == item_id).first()

    def create(self, data: ItemCreate) -> Item:
        item = Item(**data.model_dump())
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(self, item_id: int, data: ItemUpdate) -> Item | None:
        item = self.get_by_id(item_id)
        if not item:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item_id: int) -> bool:
        item = self.get_by_id(item_id)
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def apply_bulk_discount(self, min_quantity: int, discount: float) -> int:
        items = self.db.query(Item).filter(Item.quantity > min_quantity).all()
        for item in items:
            item.price = round(item.price * (1 - discount), 2)
        self.db.commit()
        return len(items)
