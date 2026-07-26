"""Analysis pipeline: compute technical + bandarmology signals, persist them,
compute scores, and generate AI recommendation for a single ticker.
"""
from datetime import date, datetime, timedelta
import math
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.yfinance import YFinanceClient
from app.core.logging import log
from app.models.bandar import BandarmologySignal
from app.models.foreign_flow import ForeignFlow
from app.models.indicator import TechnicalIndicator
from app.models.market_regime import MarketRegime
from app.models.price import DailyPrice
from app.models.score import Score, StockProfile
from app.services.bandarmology import REGISTRY as BANDAR_REGISTRY
from app.services.market_regime import detect_regime
from app.services.scoring.engine import compute_score_for_date, save_score
from app.services.scoring.weights import BANDAR_LABELS, TECHNICAL_METHODS
from app.services.smart_money import detect_smart_money
from app.services.technical import REGISTRY as TECH_REGISTRY

_benchmark_cache: pd.DataFrame | None = None
_benchmark_cache_time: datetime | None = None
_BM_CACHE_TTL = 1800


def _json_safe(value: Any) -> Any:
    """Convert analysis output to values accepted by MySQL JSON columns."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _prices_df(db: Session, ticker: str) -> pd.DataFrame:
    rows = db.execute(
        select(DailyPrice).where(DailyPrice.ticker == ticker).order_by(DailyPrice.date.asc())
    ).scalars().all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(
        [
            {
                "date": r.date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in rows
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def _flow_df_from_bandar(db: Session, ticker: str) -> pd.DataFrame:
    # We reconstruct a flow_df from the marketdetectors payload if stored.
    # For simplicity, we re-derive a daily aggregate from bandar signals payload
    # which carries top broker info; but for silent_accumulation/absorption we need
    # per-party flow. We store that in the BandarmologySignal payload of the latest
    # day via the data_loader. Here we use foreign_flow + an aggregate.
    return pd.DataFrame()  # per-party flow handled in compute_bandar via stored payloads


def _benchmark_df(db: Session) -> pd.DataFrame:
    global _benchmark_cache, _benchmark_cache_time
    now = datetime.utcnow()
    if _benchmark_cache is not None and _benchmark_cache_time is not None:
        if (now - _benchmark_cache_time).total_seconds() < _BM_CACHE_TTL:
            return _benchmark_cache.copy()

    rows = db.execute(
        select(DailyPrice).where(DailyPrice.ticker == "^JKSE").order_by(DailyPrice.date.asc())
    ).scalars().all()
    if rows:
        df = pd.DataFrame(
            [{"date": r.date, "close": r.close, "high": r.high, "low": r.low, "open": r.open, "volume": r.volume} for r in rows]
        )
        df["date"] = pd.to_datetime(df["date"])
        _benchmark_cache = df.copy()
        _benchmark_cache_time = now
        return df
    # fallback yfinance
    bm = YFinanceClient().get_benchmark_prices("^JKSE", start=date.today() - timedelta(days=1500))
    if not bm:
        return pd.DataFrame()
    df = pd.DataFrame(bm)
    df["date"] = pd.to_datetime(df["date"])
    _benchmark_cache = df.copy()
    _benchmark_cache_time = now
    return df


def compute_technical(db: Session, ticker: str, as_of: date | None = None) -> None:
    df = _prices_df(db, ticker)
    if df.empty or len(df) < 60:
        log.info("skip_technical_insufficient_data", ticker=ticker, rows=len(df))
        return
    bm = _benchmark_df(db)
    bm_df = bm[["date", "close"]] if not bm.empty else None

    for method, fn in TECH_REGISTRY.items():
        try:
            results = fn(df, benchmark_df=bm_df, as_of=as_of)
        except Exception as e:
            log.warning("technical_method_error", ticker=ticker, method=method, error=str(e))
            continue
        for r in results:
            d = r["date"]
            payload = _json_safe(r["payload"])
            existing = db.execute(
                select(TechnicalIndicator).where(
                    TechnicalIndicator.ticker == ticker,
                    TechnicalIndicator.date == d,
                    TechnicalIndicator.method == method,
                    TechnicalIndicator.name == (r.get("name") or method),
                )
            ).scalar_one_or_none()
            if existing:
                existing.payload = payload
                existing.score = r["score"]
            else:
                db.add(
                    TechnicalIndicator(
                        ticker=ticker,
                        date=d,
                        method=method,
                        name=r.get("name") or method,
                        payload=payload,
                        score=r["score"],
                    )
                )
    db.commit()
    log.info("technical_computed", ticker=ticker)


def compute_bandar(db: Session, ticker: str, flow_rows: list[dict], as_of: date | None = None) -> None:
    df = _prices_df(db, ticker)
    if df.empty or len(df) < 30:
        return
    flow_df = pd.DataFrame(flow_rows) if flow_rows else pd.DataFrame()
    if not flow_df.empty:
        flow_df["date"] = pd.to_datetime(flow_df["date"])

    for label, fn in BANDAR_REGISTRY.items():
        try:
            results = fn(df, flow_df, as_of=as_of)
        except Exception as e:
            log.warning("bandar_method_error", ticker=ticker, label=label, error=str(e))
            continue
        for r in results:
            d = r["date"]
            payload = _json_safe(r["payload"])
            existing = db.execute(
                select(BandarmologySignal).where(
                    BandarmologySignal.ticker == ticker,
                    BandarmologySignal.date == d,
                    BandarmologySignal.label == label,
                )
            ).scalar_one_or_none()
            if existing:
                existing.detected = r["detected"]
                existing.value = r["value"]
                existing.score = r["score"]
                existing.payload = payload
            else:
                db.add(
                    BandarmologySignal(
                        ticker=ticker,
                        date=d,
                        label=label,
                        detected=r["detected"],
                        value=r["value"],
                        score=r["score"],
                        payload=payload,
                    )
                )
    db.commit()
    log.info("bandar_computed", ticker=ticker)


def compute_score(db: Session, ticker: str, as_of: date | None = None) -> Score | None:
    d = as_of or date.today()
    # Latest technical scores on date d (or latest <= d)
    tech_rows = db.execute(
        select(TechnicalIndicator).where(
            TechnicalIndicator.ticker == ticker, TechnicalIndicator.date <= d
        ).order_by(TechnicalIndicator.date.desc())
    ).scalars().all()
    tech_scores: dict[str, float] = {}
    seen_methods = set()
    for r in tech_rows:
        if r.method in seen_methods:
            continue
        tech_scores[r.method] = r.score or 50.0
        seen_methods.add(r.method)

    bandar_rows = db.execute(
        select(BandarmologySignal).where(
            BandarmologySignal.ticker == ticker, BandarmologySignal.date <= d
        ).order_by(BandarmologySignal.date.desc())
    ).scalars().all()
    bandar_scores: dict[str, float] = {}
    bandar_detected: dict[str, bool] = {}
    seen_labels = set()
    for r in bandar_rows:
        if r.label in seen_labels:
            continue
        bandar_scores[r.label] = r.score or 50.0
        bandar_detected[r.label] = bool(r.detected)
        seen_labels.add(r.label)

    ff = db.execute(
        select(ForeignFlow).where(
            ForeignFlow.ticker == ticker, ForeignFlow.date <= d
        ).order_by(ForeignFlow.date.desc()).limit(1)
    ).scalar_one_or_none()
    foreign_score = ff.score if ff else None

    regime_row = db.execute(
        select(MarketRegime).where(MarketRegime.date <= d).order_by(MarketRegime.date.desc()).limit(1)
    ).scalar_one_or_none()
    regime = regime_row.regime if regime_row else "unknown"

    prof = db.get(StockProfile, ticker)
    weights = None
    if prof and prof.weights:
        # Reuse stored adaptive weights flattened form
        weights = {
            "technical": {m: prof.weights.get(f"tech:{m}", 1.0) for m in TECHNICAL_METHODS},
            "bandarmology": {m: prof.weights.get(f"bandar:{m}", 1.0) for m in BANDAR_LABELS},
            "_technical_share": 0.45,
            "_bandar_share": 0.40,
            "_foreign_share": 0.10,
            "_regime_share": 0.05,
        }

    score = compute_score_for_date(
        ticker=ticker,
        d=d,
        tech_scores=tech_scores,
        bandar_scores=bandar_scores,
        bandar_detected=bandar_detected,
        foreign_score=foreign_score,
        regime=regime,
        weights=weights,
    )
    save_score(db, score)
    return db.execute(
        select(Score).where(Score.ticker == ticker, Score.date == d)
    ).scalar_one_or_none()


def run_full_analysis(db: Session, ticker: str, incremental: bool = False) -> None:
    from app.services.ai.orchestrator import generate_recommendation
    from app.services.data_loader import (
        load_bandar_flow,
        load_foreign_flow,
        load_prices,
    )
    from app.services.recommendation_filter import is_recommendation_eligible

    load_prices(db, ticker, incremental=incremental)
    flow_rows = load_bandar_flow(db, ticker)
    load_foreign_flow(db, ticker)
    compute_technical(db, ticker)
    compute_bandar(db, ticker, flow_rows)
    compute_score(db, ticker)
    detect_smart_money(db, ticker)
    eligible, metrics = is_recommendation_eligible(db, ticker)
    if eligible:
        generate_recommendation(db, ticker)
    else:
        log.info(
            "full_analysis_recommendation_skipped",
            ticker=ticker,
            reason="liquidity_or_volatility_filter",
            metrics=metrics,
        )
    log.info("full_analysis_done", ticker=ticker, incremental=incremental)
