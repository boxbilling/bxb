from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.item_repository import ItemRepository
from app.schemas.item import ItemCreate, ItemResponse, ItemUpdate
from app.tasks import enqueue_task

router = APIRouter()


@router.post(
    "/update-prices",
    status_code=202,
    summary="Enqueue price update",
    description="Enqueue a background task to update all item prices.",
)
async def enqueue_update_prices() -> dict[str, str]:
    job = await enqueue_task("update_item_prices")
    return {"job_id": job.job_id}


@router.get(
    "/",
    response_model=list[ItemResponse],
    summary="List items",
    description="List all items with pagination.",
)
async def list_items(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[ItemResponse]:
    repo = ItemRepository(db)
    return [ItemResponse.model_validate(item) for item in repo.get_all(skip=skip, limit=limit)]


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Get item",
    description="Get an item by ID.",
    responses={404: {"description": "Item not found"}},
)
async def get_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> ItemResponse:
    repo = ItemRepository(db)
    item = repo.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemResponse.model_validate(item)


@router.post(
    "/",
    response_model=ItemResponse,
    status_code=201,
    summary="Create item",
    description="Create a new item.",
    responses={422: {"description": "Validation error"}},
)
async def create_item(
    data: ItemCreate,
    db: Session = Depends(get_db),
) -> ItemResponse:
    repo = ItemRepository(db)
    return ItemResponse.model_validate(repo.create(data))


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Update item",
    description="Update an existing item.",
    responses={404: {"description": "Item not found"}},
)
async def update_item(
    item_id: int,
    data: ItemUpdate,
    db: Session = Depends(get_db),
) -> ItemResponse:
    repo = ItemRepository(db)
    item = repo.update(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemResponse.model_validate(item)


@router.delete(
    "/{item_id}",
    status_code=204,
    summary="Delete item",
    description="Delete an item by ID.",
    responses={404: {"description": "Item not found"}},
)
async def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> Response:
    repo = ItemRepository(db)
    if not repo.delete(item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return Response(status_code=204)
