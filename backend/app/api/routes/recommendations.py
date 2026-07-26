from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import RecommendationOut
from app.core.db import get_db
from app.models.recommendation import Recommendation

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/{ticker}", response_model=list[RecommendationOut])
def get_recommendations(
    ticker: str,
    days: int = Query(60, ge=1, le=400),
    db: Session = Depends(get_db),
):
    end = date.today()
    start = end - timedelta(days=days)
    stmt = (
        select(Recommendation)
        .where(
            Recommendation.ticker == ticker.upper(),
            Recommendation.date >= start,
        )
        .order_by(Recommendation.date.asc())
    )
    return db.execute(stmt).scalars().all()


@router.get("", response_model=list[RecommendationOut])
def latest_recommendations(
    limit: int = 50,
    rec_date: date | None = Query(None, alias="date", description="Filter by date (default: today)"),
    db: Session = Depends(get_db),
):
    target = rec_date or date.today()
    stmt = (
        select(Recommendation)
        .where(Recommendation.date == target)
        .order_by(Recommendation.id.desc())
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()
