from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import SignalOut
from app.core.db import get_db
from app.models.bandar import BandarmologySignal
from app.models.foreign_flow import ForeignFlow

router = APIRouter(prefix="/bandarmology", tags=["bandarmology"])


@router.get("/{ticker}/signals", response_model=list[SignalOut])
def get_signals(
    ticker: str,
    days: int = Query(90, ge=10, le=400),
    db: Session = Depends(get_db),
):
    end = date.today()
    start = end - timedelta(days=days)
    stmt = (
        select(BandarmologySignal)
        .where(
            BandarmologySignal.ticker == ticker.upper(),
            BandarmologySignal.date >= start,
        )
        .order_by(BandarmologySignal.date.asc(), BandarmologySignal.label.asc())
    )
    return db.execute(stmt).scalars().all()


@router.get("/{ticker}/foreign-flow", response_model=list[dict])
def get_foreign(
    ticker: str,
    days: int = Query(90, ge=10, le=400),
    db: Session = Depends(get_db),
):
    end = date.today()
    start = end - timedelta(days=days)
    stmt = (
        select(ForeignFlow)
        .where(ForeignFlow.ticker == ticker.upper(), ForeignFlow.date >= start)
        .order_by(ForeignFlow.date.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "ticker": r.ticker,
            "date": r.date.isoformat(),
            "foreign_buy": r.foreign_buy,
            "foreign_sell": r.foreign_sell,
            "net_foreign": r.net_foreign,
            "net_foreign_pct": r.net_foreign_pct,
            "score": r.score,
        }
        for r in rows
    ]
