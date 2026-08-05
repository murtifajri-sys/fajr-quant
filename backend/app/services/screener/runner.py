"""Screener filters and runner.

Filter semantics:
- methods: list of technical methods that must be present with score >= 60 (OR within)
- bandar_labels: bandarmology labels that must be detected=True
- phases: latest score phase must be in set
- min_composite: minimum composite score
- require_foreign_inflow: latest foreign net > 0
- regime: market regime constraint
- universe: idx | watchlist
- breakout_filter: filter by breakout conditions (EMA cross, RSI, volume)
"""
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ScreenerFilter, ScreenerRunOut, ScreenerResultRow
from app.core.logging import log
from app.models.foreign_flow import ForeignFlow
from app.models.market_regime import MarketRegime
from app.models.price import DailyPrice
from app.models.score import Score
from app.models.screener import ScreenerResult, ScreenerRun
from app.models.setting import WatchlistItem
from app.models.stock import Stock
from app.services.broker_accumulation import summarize_broker_window
from app.services.data_loader import broker_flow_coverage_summary
from app.services.trade_setup import build_trade_setup
from app.utils.indicators import ema, rsi, sma

DEFAULT_SCREENER_SNAPSHOT_NAME = "broker_accumulation_daily"


def _json_safe(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _latest_scores_subquery():
    from sqlalchemy import func

    sub = (
        select(Score.ticker, func.max(Score.date).label("max_date"))
        .group_by(Score.ticker)
    ).subquery()
    return sub


def _check_breakout(prices: pd.DataFrame) -> dict | None:
    """Check breakout conditions on latest candle. Returns payload dict if passed, else None."""
    df = prices.copy()
    if len(df) < 25:
        return None

    df = df.sort_values("date")
    df["ema5"] = ema(df["close"], 5)
    df["ema20"] = ema(df["close"], 20)
    df["rsi14"] = rsi(df["close"], 14)
    df["vol_sma20"] = sma(df["volume"], 20)
    df["high_3"] = df["high"].rolling(3).max().shift(1)

    row = df.iloc[-1]
    prev = df.iloc[-2]

    if pd.isna(row["ema20"]) or pd.isna(row["rsi14"]):
        return None

    cond_close = row["close"] > row["ema20"]
    cond_ema5 = row["ema5"] > row["ema20"]
    cond_ema20_up = row["ema20"] > prev["ema20"]
    cond_rsi = row["rsi14"] > 45
    cond_rsi_up = row["rsi14"] > prev["rsi14"]
    cond_break = row["close"] > row["high_3"] if not pd.isna(row["high_3"]) else False
    cond_vol = row["volume"] >= 0.8 * row["vol_sma20"] if not pd.isna(row["vol_sma20"]) and row["vol_sma20"] > 0 else False

    passed = sum([cond_close, cond_ema5, cond_ema20_up, cond_rsi, cond_rsi_up, cond_break, cond_vol])

    # Require ALL 7 conditions (or at most 1 missing for borderline)
    if passed < 6:
        return None
    if not cond_break:  # breakout is mandatory
        return None

    prev_break = prev["close"] > prev["high_3"] if not pd.isna(prev["high_3"]) else False

    return {
        "close": float(row["close"]),
        "ema5": float(row["ema5"]),
        "ema20": float(row["ema20"]),
        "rsi14": float(row["rsi14"]),
        "vol_ratio": float(row["volume"] / row["vol_sma20"]) if row["vol_sma20"] > 0 else None,
        "high_3": float(row["high_3"]) if not pd.isna(row["high_3"]) else None,
        "is_fresh": not prev_break,
        "passed": passed,
    }


def _entry_readiness_from_score(score: Score, breakout_payload: dict | None) -> dict:
    phase_bonus = {
        "Awal": 45.0,
        "Tunggu Konfirmasi": 55.0,
        "Siap Entry": 80.0,
        "Hold": 68.0,
        "Siap Jual": 32.0,
        "Exit": 15.0,
    }
    sub_scores = score.sub_scores or {}
    trend = float(sub_scores.get("tech:trend_structure", 50.0))
    rs = float(sub_scores.get("tech:relative_strength", 50.0))
    breakout = float(sub_scores.get("tech:volume_breakout", 50.0))
    base = phase_bonus.get(score.phase, 50.0)
    readiness = (base * 0.35) + (float(score.composite) * 0.25) + (trend * 0.20) + (rs * 0.10) + (breakout * 0.10)
    tags: list[str] = []
    if breakout_payload:
        if breakout_payload.get("is_fresh"):
            readiness += 5.0
            tags.append("fresh_breakout")
        elif (breakout_payload.get("passed") or 0) >= 6:
            tags.append("breakout_extended")
    if score.phase in {"Siap Jual", "Exit"}:
        tags.append("weak_phase")
    readiness = round(max(0.0, min(100.0, readiness)), 2)
    return {
        "score": readiness,
        "phase": score.phase,
        "composite": float(score.composite),
        "trend_structure": trend,
        "relative_strength": rs,
        "volume_breakout": breakout,
        "tags": tags,
    }


def _closest_to_smart_score(summary: dict | None) -> float | None:
    if not summary:
        return None
    flow_quality = float(summary.get("flow_quality_score") or 0.0)
    retention = float(summary.get("retention") or 0.0) * 15.0
    cluster = float(summary.get("cluster_ratio") or 0.0) * 10.0
    low_freq_bonus = 8.0 if summary.get("low_freq_high_value") else 0.0
    high_freq_penalty = 25.0 if summary.get("high_freq_low_value") else 0.0
    risk_penalty = 15.0 if summary.get("retail_distribution_risk") else 0.0
    status_penalty = 0.0 if summary.get("status") == "active" else 20.0
    return round(flow_quality + retention + cluster + low_freq_bonus - high_freq_penalty - risk_penalty - status_penalty, 2)


def _annotate_closest_to_smart(results: list[dict]) -> None:
    candidates: list[tuple[float, dict, dict]] = []
    for row in results:
        broker = (row.get("dominant_factors") or {}).get("broker_accumulation") or {}
        if not broker:
            continue
        if broker.get("flow_quality_label") == "smart_like_accumulation":
            continue
        if broker.get("broker_conviction_label") not in {"accumulation", "big_accumulation", "aggressive_accumulation"}:
            continue
        score = _closest_to_smart_score(broker)
        if score is None:
            continue
        candidates.append((score, row, broker))

    candidates.sort(key=lambda item: item[0], reverse=True)
    for idx, (score, row, broker) in enumerate(candidates[:5], start=1):
        broker["closest_to_smart_rank"] = idx
        broker["closest_to_smart_score"] = score
        row["closest_to_smart_rank"] = idx
        row["closest_to_smart_score"] = score


def _price_rows_by_ticker(db: Session, tickers: list[str], lookback_days: int = 180) -> dict[str, list[dict]]:
    if not tickers:
        return {}
    latest_price_date = db.execute(
        select(DailyPrice.date).order_by(DailyPrice.date.desc()).limit(1)
    ).scalar_one_or_none()
    lookback_anchor = latest_price_date or date.today()
    lookback = lookback_anchor - timedelta(days=lookback_days)
    price_rows = db.execute(
        select(DailyPrice)
        .where(DailyPrice.ticker.in_(tickers), DailyPrice.date >= lookback)
        .order_by(DailyPrice.ticker.asc(), DailyPrice.date.asc())
    ).scalars().all()
    grouped: dict[str, list[dict]] = {}
    for pr in price_rows:
        grouped.setdefault(pr.ticker, []).append(
            {
                "date": pr.date,
                "open": pr.open,
                "high": pr.high,
                "low": pr.low,
                "close": pr.close,
                "volume": pr.volume or 0,
            }
        )
    return grouped


def _attach_setup_details(db: Session, rows: list[dict]) -> None:
    broker_rows = [row for row in rows if (row.get("dominant_factors") or {}).get("broker_accumulation")]
    price_map = _price_rows_by_ticker(db, [row["ticker"] for row in broker_rows])
    for row in broker_rows:
        dominant_factors = row.get("dominant_factors") or {}
        broker = dominant_factors.get("broker_accumulation") or {}
        entry = {
            "score": row.get("entry_readiness_score"),
            "phase": row.get("phase"),
            "tags": [],
        }
        setup_detail = build_trade_setup(price_map.get(row["ticker"], []), broker, entry)
        row["setup_detail"] = setup_detail
        row["dominant_factors"] = {
            **dominant_factors,
            "broker_accumulation": {
                **broker,
                "setup_detail": setup_detail,
            },
        }


def build_trade_monitor_candidates(
    db: Session,
    limit: int = 12,
    universe: str = "idx",
    max_scan: int = 300,
    broker_period_days: int = 30,
) -> list[dict]:
    """Build dashboard trade radar without persisting a screener run."""
    sub = _latest_scores_subquery()
    stmt = (
        select(Score)
        .join(sub, (Score.ticker == sub.c.ticker) & (Score.date == sub.c.max_date))
        .order_by(Score.composite.desc())
        .limit(max(20, max_scan))
    )
    scores = db.execute(stmt).scalars().all()
    if universe == "watchlist":
        watch = {w.ticker for w in db.execute(select(WatchlistItem)).scalars()}
        scores = [s for s in scores if s.ticker in watch]

    results: list[dict] = []
    for score in scores:
        broker = summarize_broker_window(db, score.ticker, broker_period_days)
        if not broker:
            continue
        if broker.get("status") in {"no_accumulation", "insufficient_data", "reversal_risk", "stale"}:
            continue
        if (broker.get("coverage_ratio") or 0) < 0.8 or (broker.get("broker_coverage_ratio") or 0) < 0.8:
            continue
        if (broker.get("recency_sessions") or 99) > 2:
            continue
        if (broker.get("recent_5_session_net") or 0) <= 0:
            continue
        if broker.get("retail_distribution_risk") or broker.get("flow_quality_label") == "retail_like_accumulation":
            continue
        if broker.get("broker_conviction_label") not in {"accumulation", "big_accumulation", "aggressive_accumulation"}:
            continue

        entry = _entry_readiness_from_score(score, None)
        if (broker.get("broker_conviction_score") or 0) < 55 or entry["score"] < 45:
            continue
        combined_rank_score = round(
            (broker["broker_conviction_score"] * 0.7) + (entry["score"] * 0.3),
            2,
        )
        stock = db.get(Stock, score.ticker)
        broker_payload = {
            **broker,
            "entry_readiness_score": entry["score"],
            "combined_rank_score": combined_rank_score,
        }
        results.append(
            {
                "ticker": score.ticker,
                "name": stock.name if stock else None,
                "composite": float(score.composite),
                "phase": score.phase,
                "dominant_factors": {
                    **(score.dominant_factors or {}),
                    "broker_accumulation": broker_payload,
                },
                "broker_conviction_score": broker.get("broker_conviction_score"),
                "broker_conviction_label": broker.get("broker_conviction_label"),
                "flow_quality_score": broker.get("flow_quality_score"),
                "flow_quality_label": broker.get("flow_quality_label"),
                "entry_readiness_score": entry["score"],
                "combined_rank_score": combined_rank_score,
                "broker_status": broker.get("status"),
                "closest_to_smart_rank": None,
                "closest_to_smart_score": _closest_to_smart_score(broker),
            }
        )

    results.sort(key=lambda row: -(row.get("combined_rank_score") or 0))
    selected = results[: max(1, limit)]
    for idx, row in enumerate(selected, start=1):
        row["rank"] = idx
    _attach_setup_details(db, selected)
    return selected


def run_screener(db: Session, filt: ScreenerFilter) -> ScreenerRunOut:
    return run_screener_with_metadata(db, filt, run_metadata=None)


def run_screener_with_metadata(
    db: Session,
    filt: ScreenerFilter,
    run_metadata: dict | None = None,
) -> ScreenerRunOut:
    sub = _latest_scores_subquery()
    stmt = (
        select(Score)
        .join(sub, (Score.ticker == sub.c.ticker) & (Score.date == sub.c.max_date))
    )
    scores = db.execute(stmt).scalars().all()

    # Universe filter
    if filt.universe == "watchlist":
        watch = {w.ticker for w in db.execute(select(WatchlistItem)).scalars()}
        scores = [s for s in scores if s.ticker in watch]

    # Market regime constraint
    regime_today = db.execute(
        select(MarketRegime).order_by(MarketRegime.date.desc()).limit(1)
    ).scalar_one_or_none()
    regime_name = regime_today.regime if regime_today else "unknown"
    if filt.regime and regime_name != filt.regime:
        scores = []

    # Breakout filter — compute on-the-fly from prices
    breakout_results = {}
    if filt.breakout_filter:
        tickers = [s.ticker for s in scores]
        if tickers:
            latest_price_date = db.execute(
                select(DailyPrice.date).order_by(DailyPrice.date.desc()).limit(1)
            ).scalar_one_or_none()
            lookback_anchor = latest_price_date or date.today()
            lookback = lookback_anchor - timedelta(days=40)
            price_rows = db.execute(
                select(DailyPrice)
                .where(DailyPrice.ticker.in_(tickers), DailyPrice.date >= lookback)
                .order_by(DailyPrice.ticker.asc(), DailyPrice.date.asc())
            ).scalars().all()
            # Group by ticker
            ticker_prices: dict[str, list] = {}
            for pr in price_rows:
                ticker_prices.setdefault(pr.ticker, []).append({
                    "date": pr.date,
                    "open": pr.open,
                    "high": pr.high,
                    "low": pr.low,
                    "close": pr.close,
                    "volume": pr.volume or 0,
                })
            for t, rows in ticker_prices.items():
                df = pd.DataFrame(rows)
                result = _check_breakout(df)
                if result:
                    breakout_results[t] = result

    results = []
    for s in scores:
        # phase filter
        if filt.phases and s.phase not in filt.phases:
            continue
        if filt.min_composite is not None and s.composite < filt.min_composite:
            continue
        # technical methods filter
        if filt.methods:
            sub_scores = s.sub_scores or {}
            ok = all(
                sub_scores.get(f"tech:{m}", 0) >= 60 for m in filt.methods
            )
            if not ok:
                continue
        # bandar labels filter
        if filt.bandar_labels:
            from app.models.bandar import BandarmologySignal

            latest_date = db.execute(
                select(BandarmologySignal.date)
                .where(BandarmologySignal.ticker == s.ticker)
                .order_by(BandarmologySignal.date.desc())
                .limit(1)
            ).scalar()
            if not latest_date:
                continue
            sigs = db.execute(
                select(BandarmologySignal).where(
                    BandarmologySignal.ticker == s.ticker,
                    BandarmologySignal.date == latest_date,
                    BandarmologySignal.label.in_(filt.bandar_labels),
                )
            ).scalars().all()
            detected_labels = {x.label for x in sigs if x.detected}
            if not set(filt.bandar_labels).issubset(detected_labels):
                continue
        # foreign inflow filter
        if filt.require_foreign_inflow:
            ff = db.execute(
                select(ForeignFlow)
                .where(ForeignFlow.ticker == s.ticker)
                .order_by(ForeignFlow.date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not ff or not ff.net_foreign or ff.net_foreign <= 0:
                continue
        # breakout filter
        if filt.breakout_filter and s.ticker not in breakout_results:
            continue
        broker_accumulation = None
        entry_readiness = None
        if filt.require_broker_accumulation:
            broker_accumulation = summarize_broker_window(
                db,
                s.ticker,
                filt.broker_period_days,
                score_config=filt.broker_score_config,
            )
            if not broker_accumulation:
                continue
            status = broker_accumulation.get("status")
            if status == "no_accumulation":
                continue
            if filt.exclude_insufficient_data and status == "insufficient_data":
                continue
            if filt.exclude_reversal_risk and status == "reversal_risk":
                continue
            if filt.exclude_stale and status == "stale":
                continue
            min_coverage = filt.min_broker_coverage_ratio
            if min_coverage is not None and (broker_accumulation.get("coverage_ratio") or 0) < min_coverage:
                continue
            max_balance = filt.max_broker_balance_ratio
            if max_balance is not None and (broker_accumulation.get("balance_abs_net_ratio") or 0) > max_balance:
                continue
            min_days = filt.min_broker_active_days
            if min_days is not None and broker_accumulation["positive_days"] < min_days:
                continue
            min_positive_ratio = filt.min_broker_positive_ratio
            if min_positive_ratio is not None and (broker_accumulation.get("positive_ratio") or 0) < min_positive_ratio:
                continue
            if filt.require_recent and (broker_accumulation.get("recency_sessions") or 99) > 2:
                continue
            if filt.require_acceleration and (broker_accumulation.get("acceleration") or 0) <= 0:
                continue
            if filt.require_cluster_confirmation:
                if (broker_accumulation.get("top_3_net") or 0) <= 0:
                    continue
                if (broker_accumulation.get("cluster_ratio") or 0) < 0.5:
                    continue
            min_mcap = filt.min_broker_net_pct_mcap
            pct_mcap = broker_accumulation.get("pct_market_cap")
            if min_mcap is not None and (pct_mcap is None or pct_mcap < min_mcap):
                continue
            min_adv = filt.min_broker_net_pct_adv
            pct_adv = broker_accumulation.get("pct_avg_daily_value")
            if min_adv is not None and (pct_adv is None or pct_adv < min_adv):
                continue
            min_conviction = filt.min_broker_conviction_score
            if min_conviction is not None and (broker_accumulation.get("broker_conviction_score") or 0) < min_conviction:
                continue
            entry_readiness = _entry_readiness_from_score(
                s,
                breakout_results.get(s.ticker),
            )
            min_entry = filt.min_entry_readiness_score
            if min_entry is not None and entry_readiness["score"] < min_entry:
                continue

        stock = db.get(Stock, s.ticker)
        combined_rank_score = None
        if broker_accumulation and entry_readiness:
            combined_rank_score = round(
                (broker_accumulation["broker_conviction_score"] * filt.broker_rank_weight)
                + (entry_readiness["score"] * filt.entry_rank_weight),
                2,
            )
        sub_scores = s.sub_scores or {}
        trend_score = float(sub_scores.get("tech:trend_structure", 0.0) or 0.0)
        relative_strength_score = float(sub_scores.get("tech:relative_strength", 0.0) or 0.0)
        volume_breakout_score = float(sub_scores.get("tech:volume_breakout", 0.0) or 0.0)
        technical_score = round(
            (trend_score * 0.45) + (relative_strength_score * 0.30) + (volume_breakout_score * 0.25),
            2,
        )
        dominant_factors = {
            **(s.dominant_factors or {}),
            "technical_summary": {
                "score": technical_score,
                "trend_structure": trend_score,
                "relative_strength": relative_strength_score,
                "volume_breakout": volume_breakout_score,
            },
        }
        if broker_accumulation:
            broker_payload = {
                **broker_accumulation,
                "entry_readiness_score": entry_readiness["score"] if entry_readiness else None,
                "combined_rank_score": combined_rank_score,
            }
            dominant_factors = {
                **dominant_factors,
                "broker_accumulation": broker_payload,
            }
            broker_accumulation = broker_payload
        results.append(
            {
                "ticker": s.ticker,
                "name": stock.name if stock else None,
                "composite": float(s.composite),
                "phase": s.phase,
                "dominant_factors": dominant_factors,
                "broker_conviction_score": broker_accumulation.get("broker_conviction_score") if broker_accumulation else None,
                "broker_conviction_label": broker_accumulation.get("broker_conviction_label") if broker_accumulation else None,
                "flow_quality_score": broker_accumulation.get("flow_quality_score") if broker_accumulation else None,
                "flow_quality_label": broker_accumulation.get("flow_quality_label") if broker_accumulation else None,
                "entry_readiness_score": entry_readiness["score"] if entry_readiness else None,
                "combined_rank_score": combined_rank_score,
                "broker_status": broker_accumulation.get("status") if broker_accumulation else None,
                "closest_to_smart_rank": broker_accumulation.get("closest_to_smart_rank") if broker_accumulation else None,
                "closest_to_smart_score": broker_accumulation.get("closest_to_smart_score") if broker_accumulation else None,
            }
        )

    if filt.require_broker_accumulation:
        if filt.sort_by == "broker_conviction":
            results.sort(key=lambda r: -(r.get("broker_conviction_score") or 0))
        elif filt.sort_by == "entry_readiness":
            results.sort(key=lambda r: -(r.get("entry_readiness_score") or 0))
        elif filt.sort_by == "composite":
            results.sort(key=lambda r: -r["composite"])
        else:
            results.sort(key=lambda r: -(r.get("combined_rank_score") or 0))
    else:
        results.sort(key=lambda r: -r["composite"])
    if filt.require_broker_accumulation:
        _annotate_closest_to_smart(results)
    total_results = len(results)
    offset = max(0, int(filt.offset or 0))
    limit = max(1, int(filt.top_n or 20))
    paged_results = results[offset : offset + limit]
    for i, r in enumerate(paged_results, start=offset + 1):
        r["rank"] = i
    if filt.require_broker_accumulation:
        _attach_setup_details(db, paged_results)

    coverage_summary = None
    if filt.require_broker_accumulation:
        coverage_summary = broker_flow_coverage_summary(
            db,
            period_days=filt.broker_period_days,
            universe=filt.universe,
            limit=min(25, max(5, limit)),
        )
        coverage_summary = _json_safe(coverage_summary)

    filter_payload = filt.model_dump()
    filter_payload["result_meta"] = {
        "total": total_results,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(paged_results)) < total_results,
    }
    if coverage_summary:
        filter_payload["coverage_summary"] = coverage_summary
    if run_metadata:
        filter_payload = {**filter_payload, **run_metadata}

    run = ScreenerRun(
        filter_json=filter_payload,
        total=total_results,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    for r in paged_results:
        db.add(
            ScreenerResult(
                run_id=run.id,
                ticker=r["ticker"],
                name=r["name"],
                composite=r["composite"],
                phase=r["phase"],
                dominant_factors=r["dominant_factors"],
                rank=r["rank"],
            )
        )
    db.commit()

    return ScreenerRunOut(
        run_id=run.id,
        created_at=run.created_at,
        filter=filter_payload,
        total=total_results,
        limit=limit,
        offset=offset,
        has_more=(offset + len(paged_results)) < total_results,
        coverage_summary=coverage_summary,
        results=[ScreenerResultRow(**r) for r in paged_results],
    )


def latest_screener_run(
    db: Session,
    snapshot_name: str | None = DEFAULT_SCREENER_SNAPSHOT_NAME,
    limit: int = 50,
) -> ScreenerRun | None:
    runs = db.execute(
        select(ScreenerRun).order_by(ScreenerRun.id.desc()).limit(limit)
    ).scalars().all()
    if not runs:
        return None
    if snapshot_name:
        for run in runs:
            if (run.filter_json or {}).get("snapshot_name") == snapshot_name:
                return run
    return runs[0]


def build_broker_ticker_detail(
    db: Session,
    ticker: str,
    score_config: dict | None = None,
    broker_rank_weight: float = 0.7,
    entry_rank_weight: float = 0.3,
) -> dict | None:
    t = ticker.upper()
    one_week = summarize_broker_window(db, t, 7, top_limit=15, score_config=score_config)
    one_month = summarize_broker_window(db, t, 30, top_limit=15, score_config=score_config)
    primary = one_month or one_week
    if not primary:
        return None

    latest_score = db.execute(
        select(Score)
        .where(Score.ticker == t)
        .order_by(Score.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    entry_readiness = (
        _entry_readiness_from_score(latest_score, None)
        if latest_score
        else {
            "score": None,
            "phase": None,
            "composite": None,
            "trend_structure": None,
            "relative_strength": None,
            "volume_breakout": None,
            "tags": ["missing_score"],
        }
    )
    conviction = {
        "score": primary.get("broker_conviction_score"),
        "label": primary.get("broker_conviction_label"),
        "status": primary.get("status"),
        "components": primary.get("score_components"),
        "config": primary.get("score_config"),
        "closest_to_smart_score": _closest_to_smart_score(primary),
    }
    combined_rank_score = None
    if conviction["score"] is not None and entry_readiness["score"] is not None:
        combined_rank_score = round(
            (conviction["score"] * broker_rank_weight) + (entry_readiness["score"] * entry_rank_weight),
            2,
        )
    price_map = _price_rows_by_ticker(db, [t])
    setup_detail = build_trade_setup(price_map.get(t, []), primary, entry_readiness)

    return {
        "ticker": t,
        "as_of_date": primary["date_to"],
        "latest_score_date": latest_score.date if latest_score else None,
        "broker_conviction": {
            **conviction,
            "combined_rank_score": combined_rank_score,
        },
        "flow_quality": {
            "score": primary.get("flow_quality_score"),
            "label": primary.get("flow_quality_label"),
            "closest_to_smart_score": _closest_to_smart_score(primary),
            "retail_distribution_risk": primary.get("retail_distribution_risk"),
            "high_freq_low_value": primary.get("high_freq_low_value"),
            "low_freq_high_value": primary.get("low_freq_high_value"),
            "avg_buy_ticket": primary.get("avg_buy_ticket"),
            "avg_sell_ticket": primary.get("avg_sell_ticket"),
            "net_per_trade": primary.get("net_per_trade"),
            "frequency_consistency": primary.get("frequency_consistency"),
            "components": primary.get("flow_quality_components"),
        },
        "entry_readiness": entry_readiness,
        "setup_detail": setup_detail,
        "one_week": one_week or {},
        "one_month": one_month or {},
        "comparison": {
            "net_delta": ((one_week or {}).get("net") or 0.0) - ((one_month or {}).get("net") or 0.0),
            "positive_ratio_delta": ((one_week or {}).get("positive_ratio") or 0.0) - ((one_month or {}).get("positive_ratio") or 0.0),
            "recency_delta": ((one_week or {}).get("recency_sessions") or 0) - ((one_month or {}).get("recency_sessions") or 0),
            "acceleration_delta": ((one_week or {}).get("acceleration") or 0.0) - ((one_month or {}).get("acceleration") or 0.0),
            "conviction_delta": ((one_week or {}).get("broker_conviction_score") or 0.0) - ((one_month or {}).get("broker_conviction_score") or 0.0),
        },
    }
