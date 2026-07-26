from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import StockOut
from app.core.db import get_db
from app.models.stock import Stock

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("", response_model=list[StockOut])
def list_stocks(q: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    stmt = select(Stock)
    if q:
        like = f"%{q.upper()}%"
        stmt = stmt.where((Stock.ticker.like(like)) | (Stock.name.like(f"%{q}%")))
    stmt = stmt.limit(limit)
    return db.execute(stmt).scalars().all()
