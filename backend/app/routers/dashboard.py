from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import Message

router = APIRouter()


@router.get("/", response_model=Message)
async def get_statistics(
    db: Session = Depends(get_db),
):
    return Message(message="Hello World")
