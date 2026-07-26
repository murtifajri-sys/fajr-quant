from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import PriceOut, SignalOut
from app.core.db import get_db
from app.models.indicator import TechnicalIndicator
from app.models.price import DailyPrice

router = APIRouter(prefix="/technical", tags=["technical"])


@router.get("/{ticker}/prices", response_model=list[PriceOut])
def get_prices(
    ticker: str,
    days: int = Query(500, ge=30, le=2000),
    db: Session = Depends(get_db),
):
    end = date.today()
    start = end - timedelta(days=days)
    stmt = (
        select(DailyPrice)
        .where(DailyPrice.ticker == ticker.upper(), DailyPrice.date >= start)
        .order_by(DailyPrice.date.asc())
    )
    return db.execute(stmt).scalars().all()


@router.get("/{ticker}/signals", response_model=list[SignalOut])
def get_signals(
    ticker: str,
    days: int = Query(120, ge=10, le=1000),
    db: Session = Depends(get_db),
):
    end = date.today()
    start = end - timedelta(days=days)
    stmt = (
        select(TechnicalIndicator)
        .where(
            TechnicalIndicator.ticker == ticker.upper(),
            TechnicalIndicator.date >= start,
        )
        .order_by(TechnicalIndicator.date.asc(), TechnicalIndicator.method.asc())
    )
    return db.execute(stmt).scalars().all()


@router.get("/{ticker}/indicators/{method}", response_model=list[SignalOut])
def get_method(
    ticker: str,
    method: str,
    days: int = Query(120, ge=10, le=2000),
    db: Session = Depends(get_db),
):
    end = date.today()
    start = end - timedelta(days=days)
    stmt = (
        select(TechnicalIndicator)
        .where(
            TechnicalIndicator.ticker == ticker.upper(),
            TechnicalIndicator.method == method,
            TechnicalIndicator.date >= start,
        )
        .order_by(TechnicalIndicator.date.asc())
    )
    return db.execute(stmt).scalars().all()
