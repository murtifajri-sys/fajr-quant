"""Chart data routes: aggregated series for frontend visualization."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.data import _avg_daily_value, _market_cap, _pct
from app.core.db import get_db
from app.models.bandar import BandarmologySignal
from app.models.broker_flow import BrokerFlow
from app.models.foreign_flow import ForeignFlow
from app.models.indicator import TechnicalIndicator
from app.models.price import DailyPrice
from app.models.score import Score
from app.models.stock import Stock
from app.services.broker_accumulation import summarize_broker_window

router = APIRouter(prefix="/charts", tags=["charts"])


def _top_brokers(db: Session, ticker: str, broker_days: int) -> list[dict]:
    """Get accumulated top broker buy/sell over the requested calendar period.

    Stockbit's marketdetectors endpoint returns broker_summary for the requested
    `from` date, not an already-aggregated range. Query each trading date in the
    period and aggregate locally so "1 week" and "1 month" mean those periods.
    """
    latest_price = db.execute(
        select(DailyPrice.date)
        .where(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    end = latest_price or date.today()
    start = end - timedelta(days=broker_days)
    trading_dates = [
        r[0]
        for r in db.execute(
            select(DailyPrice.date)
            .where(DailyPrice.ticker == ticker, DailyPrice.date >= start, DailyPrice.date <= end)
            .order_by(DailyPrice.date.asc())
        ).all()
    ]
    if not trading_dates:
        trading_dates = [end]

    existing_dates = {
        r[0]
        for r in db.execute(
            select(BrokerFlow.date)
            .where(BrokerFlow.ticker == ticker, BrokerFlow.date.in_(trading_dates))
            .distinct()
        ).all()
    }
    missing_dates = [d for d in trading_dates if d not in existing_dates]

    if missing_dates:
        try:
            from app.clients.stockbit import StockbitClient
            from app.services.data_loader import _parse_market_detectors, save_broker_flows

            with StockbitClient(db=db) as client:
                for d in missing_dates:
                    data = client.get_market_detectors(ticker, d, d, limit=300)
                    save_broker_flows(db, ticker, _parse_market_detectors(data))
        except Exception:
            pass

    summary = summarize_broker_window(db, ticker, broker_days, top_limit=15)
    if not summary:
        return []
    return summary["top_brokers"]


@router.get("/{ticker}/overview")
def chart_overview(
    ticker: str,
    days: int = Query(180, ge=30, le=2000),
    broker_days: int = Query(30, ge=7, le=60),
    db: Session = Depends(get_db),
):
    t = ticker.upper()
    end = date.today()
    start = end - timedelta(days=days)

    prices = db.execute(
        select(DailyPrice)
        .where(DailyPrice.ticker == t, DailyPrice.date >= start)
        .order_by(DailyPrice.date.asc())
    ).scalars().all()

    technical = db.execute(
        select(TechnicalIndicator)
        .where(TechnicalIndicator.ticker == t, TechnicalIndicator.date >= start)
        .order_by(TechnicalIndicator.date.asc())
    ).scalars().all()

    bandar = db.execute(
        select(BandarmologySignal)
        .where(BandarmologySignal.ticker == t, BandarmologySignal.date >= start)
        .order_by(BandarmologySignal.date.asc())
    ).scalars().all()

    foreign = db.execute(
        select(ForeignFlow)
        .where(ForeignFlow.ticker == t, ForeignFlow.date >= start)
        .order_by(ForeignFlow.date.asc())
    ).scalars().all()
    mcap = _market_cap(db, t)
    adv = _avg_daily_value(db, t)

    scores = db.execute(
        select(Score)
        .where(Score.ticker == t, Score.date >= start)
        .order_by(Score.date.asc())
    ).scalars().all()

    return {
        "ticker": t,
        "brokers": _top_brokers(db, t, broker_days),
        "prices": [
            {
                "date": p.date.isoformat(),
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume,
                "source": p.source,
            }
            for p in prices
        ],
        "technical": [
            {
                "date": x.date.isoformat(),
                "method": x.method,
                "name": x.name,
                "score": x.score,
                "payload": x.payload,
            }
            for x in technical
        ],
        "bandarmology": [
            {
                "date": x.date.isoformat(),
                "label": x.label,
                "detected": x.detected,
                "value": x.value,
                "score": x.score,
                "payload": x.payload,
            }
            for x in bandar
        ],
        "foreign_flow": [
            {
                "date": x.date.isoformat(),
                "net_foreign": x.net_foreign,
                "foreign_buy": x.foreign_buy,
                "foreign_sell": x.foreign_sell,
                "net_foreign_pct": x.net_foreign_pct,
                "score": x.score,
                "pct_market_cap": _pct(x.net_foreign, mcap),
                "pct_avg_daily_value": _pct(x.net_foreign, adv),
            }
            for x in foreign
        ],
        "scores": [
            {
                "date": x.date.isoformat(),
                "composite": x.composite,
                "phase": x.phase,
                "sub_scores": x.sub_scores,
                "weights": x.weights,
                "dominant_factors": x.dominant_factors,
            }
            for x in scores
        ],
    }
