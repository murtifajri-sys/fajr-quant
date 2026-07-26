"""Watchlist CRUD routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import MessageOut, WatchlistItemCreate, WatchlistItemOut
from app.core.db import get_db
from app.models.setting import WatchlistItem
from app.models.stock import Stock

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(name: str = "default", db: Session = Depends(get_db)):
    return db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.name == name)
        .order_by(WatchlistItem.sort_order.asc(), WatchlistItem.ticker.asc())
    ).scalars().all()


@router.post("", response_model=WatchlistItemOut)
def add_watchlist_item(payload: WatchlistItemCreate, db: Session = Depends(get_db)):
    ticker = payload.ticker.strip().upper()
    stock = db.get(Stock, ticker)
    if not stock:
        raise HTTPException(404, "Ticker not found")

    existing = db.execute(
        select(WatchlistItem).where(
            WatchlistItem.name == payload.name,
            WatchlistItem.ticker == ticker,
        )
    ).scalar_one_or_none()
    if existing:
        existing.sort_order = payload.sort_order
        db.commit()
        db.refresh(existing)
        return existing

    row = WatchlistItem(
        name=payload.name,
        ticker=ticker,
        sort_order=payload.sort_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{item_id}", response_model=MessageOut)
def delete_watchlist_item(item_id: int, db: Session = Depends(get_db)):
    row = db.get(WatchlistItem, item_id)
    if not row:
        raise HTTPException(404, "Watchlist item not found")
    db.delete(row)
    db.commit()
    return MessageOut(message="Deleted")
