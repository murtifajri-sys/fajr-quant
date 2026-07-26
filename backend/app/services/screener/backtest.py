"""Baseline broker-accumulation backtest utilities."""
from __future__ import annotations

from datetime import date, timedelta
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.price import DailyPrice
from app.models.setting import WatchlistItem
from app.models.stock import Stock
from app.services.broker_accumulation import _avg_daily_value_as_of, summarize_broker_window

FORWARD_HORIZONS = (5, 10, 20)


def _liquidity_bucket(avg_daily_value: float | None) -> str:
    if avg_daily_value is None:
        return "unknown"
    if avg_daily_value < 100_000_000_000:
        return "small"
    if avg_daily_value < 500_000_000_000:
        return "medium"
    return "large"


def _future_return(prices: list[DailyPrice], horizon: int) -> float | None:
    if len(prices) <= horizon:
        return None
    start_close = prices[0].close
    end_close = prices[horizon].close
    if start_close in (None, 0) or end_close is None:
        return None
    return round(((float(end_close) / float(start_close)) - 1.0) * 100.0, 4)


def _summarize_returns(values: list[float]) -> dict:
    if not values:
        return {
            "count": 0,
            "avg_return_pct": None,
            "median_return_pct": None,
            "win_rate": None,
        }
    wins = sum(1 for value in values if value > 0)
    return {
        "count": len(values),
        "avg_return_pct": round(sum(values) / len(values), 4),
        "median_return_pct": round(median(values), 4),
        "win_rate": round(wins / len(values), 4),
    }


def _empty_backtest_result(
    *,
    period_days: int,
    lookback_days: int,
    universe: str,
    as_of_date: date | None = None,
    samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "as_of_date": as_of_date.isoformat() if as_of_date else None,
        "period_days": period_days,
        "lookback_days": lookback_days,
        "universe": universe,
        "horizons": list(FORWARD_HORIZONS),
        "summary_by_label": {},
        "summary_by_label_and_liquidity": {},
        "samples": samples or [],
    }


def _load_universe_tickers(db: Session, universe: str) -> list[str]:
    tickers_stmt = select(Stock.ticker).order_by(Stock.ticker.asc())
    if universe == "watchlist":
        watch = select(WatchlistItem.ticker).subquery()
        tickers_stmt = tickers_stmt.where(Stock.ticker.in_(select(watch.c.ticker)))
    return [row[0] for row in db.execute(tickers_stmt).all()]


def _collect_backtest_events(
    db: Session,
    *,
    period_days: int,
    signal_start_date: date,
    signal_end_date: date,
    latest_date: date,
    universe: str,
    min_label_score: float | None,
) -> list[dict[str, Any]]:
    max_horizon = max(FORWARD_HORIZONS)
    events: list[dict[str, Any]] = []

    for ticker in _load_universe_tickers(db, universe):
        price_rows = db.execute(
            select(DailyPrice)
            .where(
                DailyPrice.ticker == ticker,
                DailyPrice.date >= signal_start_date,
                DailyPrice.date <= latest_date,
            )
            .order_by(DailyPrice.date.asc())
        ).scalars().all()
        if len(price_rows) <= max_horizon:
            continue

        for idx, row in enumerate(price_rows[:-max_horizon]):
            current_date = row.date
            if current_date < signal_start_date or current_date > signal_end_date:
                continue
            summary = summarize_broker_window(db, ticker, period_days=period_days, top_limit=15, as_of_date=current_date)
            if not summary:
                continue
            label = summary.get("broker_conviction_label") or "none"
            score = summary.get("broker_conviction_score")
            if label == "none":
                continue
            if min_label_score is not None and (score or 0) < min_label_score:
                continue

            future_prices = price_rows[idx:]
            liquidity_bucket = _liquidity_bucket(_avg_daily_value_as_of(db, ticker, current_date))

            forward_returns = {}
            for horizon in FORWARD_HORIZONS:
                value = _future_return(future_prices, horizon)
                forward_returns[str(horizon)] = value
            events.append(
                {
                    "ticker": ticker,
                    "date": current_date.isoformat(),
                    "label": label,
                    "score": score,
                    "status": summary.get("status"),
                    "liquidity_bucket": liquidity_bucket,
                    "forward_returns_pct": forward_returns,
                }
            )
    return events


def _summarize_event_rows(events: list[dict[str, Any]], sample_limit: int = 0) -> dict[str, Any]:
    summary_by_label: dict[str, dict[int, list[float]]] = {}
    summary_by_label_and_liquidity: dict[str, dict[str, dict[int, list[float]]]] = {}

    for event in events:
        label = str(event["label"])
        liquidity_bucket = str(event["liquidity_bucket"])
        label_summary = summary_by_label.setdefault(label, {h: [] for h in FORWARD_HORIZONS})
        liquidity_summary = summary_by_label_and_liquidity.setdefault(label, {}).setdefault(
            liquidity_bucket,
            {h: [] for h in FORWARD_HORIZONS},
        )
        forward_returns = event["forward_returns_pct"]
        for horizon in FORWARD_HORIZONS:
            value = forward_returns.get(str(horizon))
            if value is not None:
                label_summary[horizon].append(value)
                liquidity_summary[horizon].append(value)

    samples = events if sample_limit <= 0 else events[:sample_limit]
    return {
        "summary_by_label": {
            label: {str(horizon): _summarize_returns(values) for horizon, values in horizon_map.items()}
            for label, horizon_map in summary_by_label.items()
        },
        "summary_by_label_and_liquidity": {
            label: {
                bucket: {str(horizon): _summarize_returns(values) for horizon, values in horizon_map.items()}
                for bucket, horizon_map in bucket_map.items()
            }
            for label, bucket_map in summary_by_label_and_liquidity.items()
        },
        "samples": samples,
    }


def run_broker_label_backtest(
    db: Session,
    period_days: int = 30,
    lookback_days: int = 120,
    universe: str = "idx",
    min_label_score: float | None = None,
    sample_limit: int = 0,
) -> dict:
    latest_date = db.execute(select(DailyPrice.date).order_by(DailyPrice.date.desc()).limit(1)).scalar_one_or_none()
    if not latest_date:
        return _empty_backtest_result(
            period_days=period_days,
            lookback_days=lookback_days,
            universe=universe,
            samples=[],
        )

    signal_start_date = latest_date - timedelta(days=lookback_days)
    events = _collect_backtest_events(
        db,
        period_days=period_days,
        signal_start_date=signal_start_date,
        signal_end_date=latest_date,
        latest_date=latest_date,
        universe=universe,
        min_label_score=min_label_score,
    )
    summarized = _summarize_event_rows(events, sample_limit=sample_limit)

    return {
        "as_of_date": latest_date.isoformat(),
        "period_days": period_days,
        "lookback_days": lookback_days,
        "universe": universe,
        "horizons": list(FORWARD_HORIZONS),
        **summarized,
    }


def run_broker_label_walkforward(
    db: Session,
    period_days: int = 30,
    lookback_days: int = 180,
    fold_size_days: int = 30,
    num_folds: int = 3,
    universe: str = "idx",
    min_label_score: float | None = None,
    sample_limit_per_fold: int = 5,
) -> dict[str, Any]:
    latest_date = db.execute(select(DailyPrice.date).order_by(DailyPrice.date.desc()).limit(1)).scalar_one_or_none()
    if not latest_date:
        return {
            **_empty_backtest_result(
                period_days=period_days,
                lookback_days=lookback_days,
                universe=universe,
                samples=[],
            ),
            "fold_size_days": fold_size_days,
            "num_folds": num_folds,
            "min_label_score": min_label_score,
            "folds": [],
        }

    signal_start_date = latest_date - timedelta(days=lookback_days)
    all_events = _collect_backtest_events(
        db,
        period_days=period_days,
        signal_start_date=signal_start_date,
        signal_end_date=latest_date,
        latest_date=latest_date,
        universe=universe,
        min_label_score=min_label_score,
    )
    if not all_events:
        return {
            **_empty_backtest_result(
                period_days=period_days,
                lookback_days=lookback_days,
                universe=universe,
                as_of_date=latest_date,
                samples=[],
            ),
            "fold_size_days": fold_size_days,
            "num_folds": num_folds,
            "min_label_score": min_label_score,
            "folds": [],
        }

    anchor_end = max(date.fromisoformat(event["date"]) for event in all_events)
    effective_days = min(lookback_days, max(1, fold_size_days * num_folds))
    first_fold_start = anchor_end - timedelta(days=effective_days - 1)
    folds: list[dict[str, Any]] = []

    for fold_index in range(num_folds):
        fold_start = first_fold_start + timedelta(days=fold_index * fold_size_days)
        fold_end = min(anchor_end, fold_start + timedelta(days=fold_size_days - 1))
        if fold_start > anchor_end:
            break
        fold_events = [
            event
            for event in all_events
            if fold_start <= date.fromisoformat(event["date"]) <= fold_end
        ]
        fold_summary = _summarize_event_rows(fold_events, sample_limit=sample_limit_per_fold)
        folds.append(
            {
                "fold_index": fold_index + 1,
                "date_from": fold_start.isoformat(),
                "date_to": fold_end.isoformat(),
                "signal_count": len(fold_events),
                **fold_summary,
            }
        )

    return {
        "as_of_date": latest_date.isoformat(),
        "period_days": period_days,
        "lookback_days": lookback_days,
        "fold_size_days": fold_size_days,
        "num_folds": num_folds,
        "universe": universe,
        "min_label_score": min_label_score,
        "horizons": list(FORWARD_HORIZONS),
        "summary_by_label": _summarize_event_rows(all_events)["summary_by_label"],
        "summary_by_label_and_liquidity": _summarize_event_rows(all_events)["summary_by_label_and_liquidity"],
        "samples": [],
        "folds": folds,
    }
