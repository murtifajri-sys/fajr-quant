from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ScoreOut
from app.core.db import get_db
from app.models.score import Score, StockProfile

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.get("/{ticker}/scores", response_model=list[ScoreOut])
def get_scores(
    ticker: str,
    days: int = Query(120, ge=10, le=1000),
    db: Session = Depends(get_db),
):
    end = date.today()
    start = end - timedelta(days=days)
    stmt = (
        select(Score)
        .where(Score.ticker == ticker.upper(), Score.date >= start)
        .order_by(Score.date.asc())
    )
    return db.execute(stmt).scalars().all()


@router.get("/{ticker}/profile", response_model=dict | None)
def get_profile(ticker: str, db: Session = Depends(get_db)):
    stmt = select(StockProfile).where(StockProfile.ticker == ticker.upper())
    prof = db.execute(stmt).scalar_one_or_none()
    if not prof:
        return None
    return {
        "ticker": prof.ticker,
        "weights": prof.weights,
        "dominant_method": prof.dominant_method,
        "notes": prof.notes,
        "sample_window_days": prof.sample_window_days,
    }
