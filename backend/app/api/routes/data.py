"""Data Explorer routes — browse downloaded data with filters and pagination."""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import Session

from app.api.schemas import (
    ForeignFlowOut,
    PaginatedResponse,
    PriceOut,
    RecommendationOut,
    ScoreOut,
    SignalOut,
    SmartMoneySignalOut,
    StockOut,
)
from app.core.db import get_db
from app.models.bandar import BandarmologySignal
from app.models.foreign_flow import ForeignFlow
from app.models.indicator import TechnicalIndicator
from app.models.price import DailyPrice
from app.models.recommendation import Recommendation
from app.models.score import Score
from app.models.smart_money import SmartMoneySignal
from app.models.stock import Stock

router = APIRouter(prefix="/data", tags=["data"])

DEFAULT_LIMIT = 50


def _paginate(query, db: Session, limit: int, offset: int, model_class) -> dict:
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    rows = db.execute(query.limit(limit).offset(offset)).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}


def _market_cap(db: Session, ticker: str) -> float | None:
    """Return approximate market cap (shares_outstanding * latest close)."""
    stock = db.execute(select(Stock).where(Stock.ticker == ticker)).scalar_one_or_none()
    if not stock or not stock.shares_outstanding:
        return None
    price = db.execute(
        select(DailyPrice)
        .where(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not price:
        return None
    return stock.shares_outstanding * price.close


def _avg_daily_value(db: Session, ticker: str, days: int = 20) -> float | None:
    """Return average daily traded value (close * volume) over recent N days."""
    end = date.today()
    start = end - timedelta(days=days + 7)
    rows = db.execute(
        select(DailyPrice)
        .where(DailyPrice.ticker == ticker, DailyPrice.date >= start, DailyPrice.date <= end)
        .order_by(DailyPrice.date.desc())
        .limit(days)
    ).scalars().all()
    if not rows:
        return None
    values = [r.close * r.volume for r in rows if r.close is not None and r.volume is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _signal_flow_value(label: str, payload: dict | None) -> float | None:
    """Extract raw broker/foreign flow value from bandarmology signal payload."""
    if not payload:
        return None
    if label == "hidden_accumulation":
        return payload.get("net_flow")
    if label == "silent_accumulation":
        return payload.get("net_value")
    if label == "absorption":
        return payload.get("big_broker_net")
    if label == "bandar_positioning":
        return payload.get("net")
    if label == "consistency":
        return payload.get("net_total")
    return None


def _pct(value: float | None, base: float | None) -> float | None:
    if value is None or not base or base == 0:
        return None
    return round((value / base) * 100, 4)


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------
@router.get("/prices")
def get_prices(
    ticker: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    source: Optional[str] = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = select(DailyPrice)
    if ticker:
        tickers = [t.strip().upper() for t in ticker.split(",") if t.strip()]
        if tickers:
            q = q.where(DailyPrice.ticker.in_(tickers))
    if date_from:
        q = q.where(DailyPrice.date >= date_from)
    if date_to:
        q = q.where(DailyPrice.date <= date_to)
    if source:
        q = q.where(DailyPrice.source == source)
    q = q.order_by(DailyPrice.date.desc(), DailyPrice.ticker.asc())
    result = _paginate(q, db, limit, offset, PriceOut)
    result["items"] = [PriceOut.model_validate(r) for r in result["items"]]
    return result


# ---------------------------------------------------------------------------
# Bandarmology
# ---------------------------------------------------------------------------
@router.get("/bandarmology")
def get_bandarmology(
    ticker: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    label: Optional[str] = None,
    detected: Optional[bool] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = select(BandarmologySignal)
    if ticker:
        tickers = [t.strip().upper() for t in ticker.split(",") if t.strip()]
        if tickers:
            q = q.where(BandarmologySignal.ticker.in_(tickers))
    if date_from:
        q = q.where(BandarmologySignal.date >= date_from)
    if date_to:
        q = q.where(BandarmologySignal.date <= date_to)
    if label:
        labels = [l.strip() for l in label.split(",") if l.strip()]
        if labels:
            q = q.where(BandarmologySignal.label.in_(labels))
    if detected is not None:
        q = q.where(BandarmologySignal.detected == detected)
    if min_score is not None:
        q = q.where(BandarmologySignal.score >= min_score)
    if max_score is not None:
        q = q.where(BandarmologySignal.score <= max_score)
    q = q.order_by(BandarmologySignal.date.desc(), BandarmologySignal.ticker.asc())
    result = _paginate(q, db, limit, offset, SignalOut)

    # cache per-ticker market cap & avg daily value for normalization
    mcap_cache: dict[str, float | None] = {}
    adv_cache: dict[str, float | None] = {}

    def enrich(r):
        ticker = r.ticker
        if ticker not in mcap_cache:
            mcap_cache[ticker] = _market_cap(db, ticker)
        if ticker not in adv_cache:
            adv_cache[ticker] = _avg_daily_value(db, ticker)
        flow_value = _signal_flow_value(r.label, r.payload)
        return SignalOut(
            ticker=r.ticker,
            date=r.date,
            label=r.label,
            detected=r.detected,
            value=r.value,
            score=r.score,
            payload=r.payload,
            flow_value=flow_value,
            pct_market_cap=_pct(flow_value, mcap_cache[ticker]),
            pct_avg_daily_value=_pct(flow_value, adv_cache[ticker]),
        )

    result["items"] = [enrich(r) for r in result["items"]]
    return result


# ---------------------------------------------------------------------------
# Foreign Flow
# ---------------------------------------------------------------------------
@router.get("/foreign-flow")
def get_foreign_flow(
    ticker: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    min_net: Optional[float] = None,
    max_net: Optional[float] = None,
    min_net_pct: Optional[float] = None,
    max_net_pct: Optional[float] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = select(ForeignFlow)
    if ticker:
        tickers = [t.strip().upper() for t in ticker.split(",") if t.strip()]
        if tickers:
            q = q.where(ForeignFlow.ticker.in_(tickers))
    if date_from:
        q = q.where(ForeignFlow.date >= date_from)
    if date_to:
        q = q.where(ForeignFlow.date <= date_to)
    if min_net is not None:
        q = q.where(ForeignFlow.net_foreign >= min_net)
    if max_net is not None:
        q = q.where(ForeignFlow.net_foreign <= max_net)
    if min_net_pct is not None:
        q = q.where(ForeignFlow.net_foreign_pct >= min_net_pct)
    if max_net_pct is not None:
        q = q.where(ForeignFlow.net_foreign_pct <= max_net_pct)
    if min_score is not None:
        q = q.where(ForeignFlow.score >= min_score)
    if max_score is not None:
        q = q.where(ForeignFlow.score <= max_score)
    q = q.order_by(ForeignFlow.date.desc(), ForeignFlow.ticker.asc())
    result = _paginate(q, db, limit, offset, ForeignFlowOut)

    mcap_cache: dict[str, float | None] = {}
    adv_cache: dict[str, float | None] = {}

    def enrich_ff(r):
        ticker = r.ticker
        if ticker not in mcap_cache:
            mcap_cache[ticker] = _market_cap(db, ticker)
        if ticker not in adv_cache:
            adv_cache[ticker] = _avg_daily_value(db, ticker)
        net = r.net_foreign
        return ForeignFlowOut(
            ticker=r.ticker,
            date=r.date,
            foreign_buy=r.foreign_buy,
            foreign_sell=r.foreign_sell,
            net_foreign=net,
            net_foreign_pct=r.net_foreign_pct,
            score=r.score,
            pct_market_cap=_pct(net, mcap_cache[ticker]),
            pct_avg_daily_value=_pct(net, adv_cache[ticker]),
        )

    result["items"] = [enrich_ff(r) for r in result["items"]]
    return result


# ---------------------------------------------------------------------------
# Technical Indicators
# ---------------------------------------------------------------------------
@router.get("/technical")
def get_technical(
    ticker: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    method: Optional[str] = None,
    name: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = select(TechnicalIndicator)
    if ticker:
        tickers = [t.strip().upper() for t in ticker.split(",") if t.strip()]
        if tickers:
            q = q.where(TechnicalIndicator.ticker.in_(tickers))
    if date_from:
        q = q.where(TechnicalIndicator.date >= date_from)
    if date_to:
        q = q.where(TechnicalIndicator.date <= date_to)
    if method:
        methods = [m.strip() for m in method.split(",") if m.strip()]
        if methods:
            q = q.where(TechnicalIndicator.method.in_(methods))
    if name:
        q = q.where(TechnicalIndicator.name.ilike(f"%{name}%"))
    if min_score is not None:
        q = q.where(TechnicalIndicator.score >= min_score)
    if max_score is not None:
        q = q.where(TechnicalIndicator.score <= max_score)
    q = q.order_by(TechnicalIndicator.date.desc(), TechnicalIndicator.ticker.asc())
    result = _paginate(q, db, limit, offset, SignalOut)
    result["items"] = [
        SignalOut(
            ticker=r.ticker,
            date=r.date,
            method=r.method,
            name=r.name,
            score=r.score,
            payload=r.payload,
        )
        for r in result["items"]
    ]
    return result


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------
@router.get("/scores")
def get_scores(
    ticker: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    phase: Optional[str] = None,
    min_composite: Optional[float] = None,
    max_composite: Optional[float] = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = select(Score)
    if ticker:
        tickers = [t.strip().upper() for t in ticker.split(",") if t.strip()]
        if tickers:
            q = q.where(Score.ticker.in_(tickers))
    if date_from:
        q = q.where(Score.date >= date_from)
    if date_to:
        q = q.where(Score.date <= date_to)
    if phase:
        phases = [p.strip() for p in phase.split(",") if p.strip()]
        if phases:
            q = q.where(Score.phase.in_(phases))
    if min_composite is not None:
        q = q.where(Score.composite >= min_composite)
    if max_composite is not None:
        q = q.where(Score.composite <= max_composite)
    q = q.order_by(Score.date.desc(), Score.composite.desc())
    result = _paginate(q, db, limit, offset, ScoreOut)
    result["items"] = [ScoreOut.model_validate(r) for r in result["items"]]
    return result


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------
@router.get("/recommendations")
def get_recommendations(
    ticker: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    action: Optional[str] = None,
    provider: Optional[str] = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = select(Recommendation)
    if ticker:
        tickers = [t.strip().upper() for t in ticker.split(",") if t.strip()]
        if tickers:
            q = q.where(Recommendation.ticker.in_(tickers))
    if date_from:
        q = q.where(Recommendation.date >= date_from)
    if date_to:
        q = q.where(Recommendation.date <= date_to)
    if action:
        actions = [a.strip().upper() for a in action.split(",") if a.strip()]
        if actions:
            q = q.where(Recommendation.action.in_(actions))
    if provider:
        q = q.where(Recommendation.provider == provider)
    q = q.order_by(Recommendation.date.desc(), Recommendation.ticker.asc())
    result = _paginate(q, db, limit, offset, RecommendationOut)
    result["items"] = [RecommendationOut.model_validate(r) for r in result["items"]]
    return result


# ---------------------------------------------------------------------------
# Stocks
# ---------------------------------------------------------------------------
@router.get("/stocks")
def get_stocks(
    ticker: Optional[str] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    board: Optional[str] = None,
    exchange: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = select(Stock)
    if ticker:
        q = q.where(Stock.ticker.ilike(f"%{ticker.upper()}%"))
    if sector:
        q = q.where(Stock.sector == sector)
    if industry:
        q = q.where(Stock.industry == industry)
    if board:
        q = q.where(Stock.board == board)
    if exchange:
        q = q.where(Stock.exchange == exchange)
    q = q.order_by(Stock.ticker.asc())
    result = _paginate(q, db, limit, offset, StockOut)
    result["items"] = [StockOut.model_validate(r) for r in result["items"]]
    return result


# ---------------------------------------------------------------------------
# Filters (metadata)
# ---------------------------------------------------------------------------
@router.get("/filters")
def get_filters(db: Session = Depends(get_db)):
    sectors = [
        r[0] for r in db.execute(
            select(distinct(Stock.sector)).where(Stock.sector.isnot(None)).order_by(Stock.sector)
        ).all()
    ]
    boards = [
        r[0] for r in db.execute(
            select(distinct(Stock.board)).where(Stock.board.isnot(None)).order_by(Stock.board)
        ).all()
    ]
    industries = [
        r[0] for r in db.execute(
            select(distinct(Stock.industry)).where(Stock.industry.isnot(None)).order_by(Stock.industry)
        ).all()
    ]
    phases = [
        r[0] for r in db.execute(
            select(distinct(Score.phase)).where(Score.phase.isnot(None)).order_by(Score.phase)
        ).all()
    ]
    actions = [
        r[0] for r in db.execute(
            select(distinct(Recommendation.action)).where(Recommendation.action.isnot(None)).order_by(Recommendation.action)
        ).all()
    ]
    methods = [
        r[0] for r in db.execute(
            select(distinct(TechnicalIndicator.method)).where(TechnicalIndicator.method.isnot(None)).order_by(TechnicalIndicator.method)
        ).all()
    ]
    labels = [
        r[0] for r in db.execute(
            select(distinct(BandarmologySignal.label)).where(BandarmologySignal.label.isnot(None)).order_by(BandarmologySignal.label)
        ).all()
    ]
    sources = [
        r[0] for r in db.execute(
            select(distinct(DailyPrice.source)).where(DailyPrice.source.isnot(None)).order_by(DailyPrice.source)
        ).all()
    ]
    return {
        "sectors": sectors,
        "boards": boards,
        "industries": industries,
        "phases": phases,
        "actions": actions,
        "methods": methods,
        "labels": labels,
        "sources": sources,
    }
