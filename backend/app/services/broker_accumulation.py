"""Broker accumulation analysis helpers.

This module provides a reusable engine for broker-flow window analysis so the
same logic can be consumed by screener, charting, API detail, and tests.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.broker_flow import BrokerFlow
from app.models.price import DailyPrice
from app.models.stock import Stock

MIN_COVERAGE_RATIO = 0.8
DEFAULT_BROKER_SCORE_CONFIG = {
    "accumulation_min_score": 55.0,
    "big_accumulation_min_score": 70.0,
    "aggressive_accumulation_min_score": 85.0,
    "big_accumulation_min_pct_mcap": 0.25,
    "big_accumulation_min_days_of_adv": 1.5,
    "minimum_positive_ratio": 0.4,
    "maximum_recent_stale_sessions": 2,
    "minimum_directional_purity": 0.2,
    "minimum_cluster_ratio": 0.5,
}


def _score_clip(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return max(0.0, min(100.0, (value / max_value) * 100.0))


def _merge_score_config(overrides: dict[str, Any] | None = None) -> dict[str, float]:
    merged = dict(DEFAULT_BROKER_SCORE_CONFIG)
    if overrides:
        for key, value in overrides.items():
            if key in merged and value is not None:
                merged[key] = float(value)
    return merged


def _latest_price_date(db: Session, ticker: str, as_of_date: date | None = None) -> date | None:
    stmt = (
        select(DailyPrice.date)
        .where(DailyPrice.ticker == ticker.upper())
        .order_by(DailyPrice.date.desc())
        .limit(1)
    )
    if as_of_date is not None:
        stmt = stmt.where(DailyPrice.date <= as_of_date)
    return db.execute(stmt).scalar_one_or_none()


def _pct(value: float | None, base: float | None) -> float | None:
    if value is None or not base or base == 0:
        return None
    return round((value / base) * 100, 4)


def _market_cap_as_of(db: Session, ticker: str, as_of_date: date) -> float | None:
    stock = db.execute(select(Stock).where(Stock.ticker == ticker.upper())).scalar_one_or_none()
    if not stock or not stock.shares_outstanding:
        return None
    price = db.execute(
        select(DailyPrice)
        .where(DailyPrice.ticker == ticker.upper(), DailyPrice.date <= as_of_date)
        .order_by(DailyPrice.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not price or price.close is None:
        return None
    return float(stock.shares_outstanding) * float(price.close)


def _avg_daily_value_as_of(db: Session, ticker: str, as_of_date: date, days: int = 20) -> float | None:
    start = as_of_date - timedelta(days=days + 10)
    rows = db.execute(
        select(DailyPrice)
        .where(
            DailyPrice.ticker == ticker.upper(),
            DailyPrice.date >= start,
            DailyPrice.date <= as_of_date,
        )
        .order_by(DailyPrice.date.desc())
        .limit(days)
    ).scalars().all()
    if not rows:
        return None
    values = [float(r.close) * float(r.volume) for r in rows if r.close is not None and r.volume is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _window_start(end: date, period_days: int) -> tuple[date, str]:
    """Return the exclusive left boundary and a human readable period label."""
    if period_days <= 7:
        return end - timedelta(days=7), "1W"
    return (pd.Timestamp(end) - pd.DateOffset(months=1)).date(), "1M"


def _load_trading_dates(db: Session, ticker: str, start: date, end: date) -> list[date]:
    rows = db.execute(
        select(DailyPrice.date)
        .where(
            DailyPrice.ticker == ticker.upper(),
            DailyPrice.date > start,
            DailyPrice.date <= end,
        )
        .order_by(DailyPrice.date.asc())
    ).all()
    return [r[0] for r in rows]


def _load_flow_rows(db: Session, ticker: str, start: date, end: date) -> pd.DataFrame:
    rows = db.execute(
        select(BrokerFlow)
        .where(
            BrokerFlow.ticker == ticker.upper(),
            BrokerFlow.date > start,
            BrokerFlow.date <= end,
            BrokerFlow.source != "stockbit_empty",
        )
        .order_by(BrokerFlow.date.asc(), BrokerFlow.broker.asc())
    ).scalars().all()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        [
            {
                "date": r.date,
                "broker": r.broker,
                "buy_value": float(r.buy_value or 0.0),
                "sell_value": float(r.sell_value or 0.0),
                "net_value": float(r.net_value or 0.0),
                "buy_freq": int(r.buy_freq or 0),
                "sell_freq": int(r.sell_freq or 0),
            }
            for r in rows
        ]
    )
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _load_price_rows(db: Session, ticker: str, start: date, end: date) -> list[dict[str, Any]]:
    rows = db.execute(
        select(DailyPrice)
        .where(
            DailyPrice.ticker == ticker.upper(),
            DailyPrice.date > start,
            DailyPrice.date <= end,
        )
        .order_by(DailyPrice.date.asc())
    ).scalars().all()
    return [
        {
            "date": r.date.isoformat(),
            "open": float(r.open) if r.open is not None else None,
            "high": float(r.high) if r.high is not None else None,
            "low": float(r.low) if r.low is not None else None,
            "close": float(r.close) if r.close is not None else None,
            "volume": float(r.volume) if r.volume is not None else None,
        }
        for r in rows
    ]


def _streak_from_end(series: pd.Series) -> int:
    streak = 0
    for value in reversed(series.tolist()):
        if pd.isna(value) or float(value) <= 0:
            break
        streak += 1
    return streak


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def _frequency_consistency(values: list[float]) -> float:
    cleaned = [float(v) for v in values if v is not None and float(v) > 0]
    if not cleaned:
        return 0.0
    if len(cleaned) == 1:
        return 1.0
    series = pd.Series(cleaned, dtype=float)
    mean = float(series.mean())
    if mean <= 0:
        return 0.0
    variation = float(series.std(ddof=0)) / mean
    return max(0.0, min(1.0, 1.0 - min(1.0, variation)))


def _broker_metrics_for_series(series: pd.Series) -> dict[str, Any]:
    """Return metrics for a broker daily net series indexed by trading date."""
    observed = series.dropna()
    buy_days = int((observed > 0).sum())
    negative_days = int((observed < 0).sum())
    zero_days = int((observed == 0).sum())
    total_days = int(series.shape[0])
    observed_days = int(observed.shape[0])
    coverage_ratio = observed_days / total_days if total_days else 0.0
    positive_ratio = buy_days / total_days if total_days else 0.0
    observed_positive_ratio = buy_days / observed_days if observed_days else 0.0
    positive_days = buy_days
    cumulative = observed.fillna(0).cumsum()
    cumulative_now = float(cumulative.iloc[-1]) if not cumulative.empty else 0.0
    cumulative_peak = float(cumulative.max()) if not cumulative.empty else 0.0
    retention = cumulative_now / cumulative_peak if cumulative_peak > 0 else 0.0
    last_positive_index = None
    for idx in range(len(series) - 1, -1, -1):
        value = series.iloc[idx]
        if pd.notna(value) and float(value) > 0:
            last_positive_index = idx
            break
    recency_sessions = (len(series) - 1 - last_positive_index) if last_positive_index is not None else len(series)
    recent_5 = float(observed.tail(5).sum()) if not observed.empty else 0.0
    prior_5 = float(observed.iloc[:-5].tail(5).sum()) if len(observed) > 5 else 0.0
    recent_5_avg = recent_5 / min(5, max(1, len(observed.tail(5)))) if not observed.empty else 0.0
    prior_5_avg = prior_5 / min(5, max(1, len(observed.iloc[:-5].tail(5)))) if len(observed) > 5 else 0.0
    acceleration = recent_5_avg - prior_5_avg
    directional_purity = None
    return {
        "positive_days": positive_days,
        "negative_days": negative_days,
        "zero_days": zero_days,
        "observed_days": observed_days,
        "total_days": total_days,
        "coverage_ratio": coverage_ratio,
        "positive_ratio": positive_ratio,
        "observed_positive_ratio": observed_positive_ratio,
        "consecutive_buy_days": _streak_from_end(series),
        "recency_sessions": recency_sessions,
        "recent_5_session_net": recent_5,
        "previous_5_session_net": prior_5,
        "acceleration": acceleration,
        "retention": retention,
        "cumulative_now": cumulative_now,
        "cumulative_peak": cumulative_peak,
        "directional_purity": directional_purity,
        "last_positive_date": (
            series.index[last_positive_index].isoformat()
            if last_positive_index is not None and hasattr(series.index[last_positive_index], "isoformat")
            else None
        ),
    }


def _daily_top_cluster(df: pd.DataFrame, trading_dates: list[date], top_brokers: list[str]) -> pd.Series:
    if df.empty or not top_brokers:
        return pd.Series(dtype=float)
    subset = df[df["broker"].isin(top_brokers)]
    if subset.empty:
        return pd.Series(dtype=float)
    daily = (
        subset.groupby("date")["net_value"].sum()
        .reindex(trading_dates)
    )
    return daily


def _series_points(series: pd.Series, scale_reference: float | None = None) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    running = 0.0
    for idx, value in series.items():
        has_data = pd.notna(value)
        raw_value = float(value) if has_data else None
        if has_data:
            running += float(value)
        pct_value = None
        if raw_value is not None and scale_reference not in (None, 0):
            pct_value = round((raw_value / float(scale_reference)) * 100.0, 4)
        points.append(
            {
                "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                "net_value": raw_value,
                "cumulative_net": round(running, 2) if has_data else None,
                "pct_reference": pct_value,
                "has_data": has_data,
            }
        )
    return points


def _build_heatmap_rows(pivot: pd.DataFrame, brokers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for broker in brokers[:5]:
        code = broker["broker"]
        series = pivot[code] if code in pivot.columns else pd.Series(index=pivot.index, dtype=float)
        rows.append(
            {
                "broker": code,
                "total_net": broker["net"],
                "positive_days": broker["positive_days"],
                "positive_ratio": broker["positive_ratio"],
                "last_buy_date": broker["last_positive_date"],
                "retention": broker["retention"],
                "cells": [
                    {
                        "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                        "net_value": (float(value) if pd.notna(value) else None),
                        "has_data": pd.notna(value),
                    }
                    for idx, value in series.items()
                ],
            }
        )
    return rows


def summarize_broker_accumulation(
    db: Session,
    ticker: str,
    period_days: int = 30,
    top_limit: int = 5,
    score_config: dict[str, Any] | None = None,
    as_of_date: date | None = None,
) -> dict[str, Any] | None:
    ticker = ticker.upper()
    end = _latest_price_date(db, ticker, as_of_date=as_of_date)
    if end is None:
        return None

    start, period_label = _window_start(end, period_days)
    trading_dates = _load_trading_dates(db, ticker, start, end)
    if not trading_dates:
        return None

    flow_df = _load_flow_rows(db, ticker, start, end)
    if flow_df.empty:
        return None

    for col in ("buy_freq", "sell_freq"):
        if col not in flow_df.columns:
            flow_df[col] = 0

    daily = (
        flow_df.groupby(["broker", "date"], as_index=False)
        .agg(
            buy_value=("buy_value", "sum"),
            sell_value=("sell_value", "sum"),
            net_value=("net_value", "sum"),
            buy_freq=("buy_freq", "sum"),
            sell_freq=("sell_freq", "sum"),
        )
    )
    daily["date"] = pd.to_datetime(daily["date"]).dt.date

    broker_agg = (
        daily.groupby("broker", as_index=False)
        .agg(
            buy=("buy_value", "sum"),
            sell=("sell_value", "sum"),
            net=("net_value", "sum"),
            buy_freq=("buy_freq", "sum"),
            sell_freq=("sell_freq", "sum"),
            active_days=("date", "nunique"),
            positive_days=("net_value", lambda s: int((s > 0).sum())),
            negative_days=("net_value", lambda s: int((s < 0).sum())),
        )
        .sort_values("net", ascending=False)
    )
    broker_agg = broker_agg[broker_agg["broker"].astype(str).str.strip() != ""]
    if broker_agg.empty:
        return None

    pivot = (
        daily.pivot_table(index="date", columns="broker", values="net_value", aggfunc="sum")
        .reindex(trading_dates)
    )
    pivot.index = pd.Index(trading_dates, name="date")

    flow_dates = sorted(pd.Series(flow_df["date"]).dropna().unique().tolist())
    coverage_ratio = len(flow_dates) / len(trading_dates) if trading_dates else 0.0

    total_buy = float(flow_df["buy_value"].sum())
    total_sell = float(flow_df["sell_value"].sum())
    total_abs_flow = float((flow_df["buy_value"].abs() + flow_df["sell_value"].abs()).sum())
    total_net = float(flow_df["net_value"].sum())
    balance_abs_net_ratio = abs(total_net) / total_abs_flow if total_abs_flow > 0 else 0.0

    enriched_brokers: list[dict[str, Any]] = []
    for _, row in broker_agg.iterrows():
        broker = str(row["broker"])
        series = pivot[broker] if broker in pivot.columns else pd.Series(index=pivot.index, dtype=float)
        metrics = _broker_metrics_for_series(series)
        buy = float(row["buy"])
        sell = float(row["sell"])
        net = float(row["net"])
        directional_purity = abs(net) / (buy + sell) if (buy + sell) > 0 else 0.0
        metrics["directional_purity"] = directional_purity
        metrics["broker"] = broker
        metrics["buy"] = buy
        metrics["sell"] = sell
        metrics["net"] = net
        metrics["active_days"] = int(row["active_days"])
        metrics["buy_freq"] = int(row["buy_freq"] or 0)
        metrics["sell_freq"] = int(row["sell_freq"] or 0)
        metrics["total_freq"] = int((row["buy_freq"] or 0) + (row["sell_freq"] or 0))
        metrics["buy_sell_ratio"] = buy / sell if sell > 0 else None
        enriched_brokers.append(metrics)

    top_limit = max(1, int(top_limit))
    top_brokers = enriched_brokers[:top_limit]
    top_broker = enriched_brokers[0]
    positive_brokers = [b for b in enriched_brokers if b["net"] > 0]
    top_3 = positive_brokers[:3]
    top_5 = positive_brokers[:5]
    top_3_net = float(sum(b["net"] for b in top_3))
    top_5_net = float(sum(b["net"] for b in top_5))
    positive_cluster_net = float(sum(b["net"] for b in positive_brokers))
    cluster_ratio = top_3_net / positive_cluster_net if positive_cluster_net > 0 else 0.0
    cluster_positive_days = 0
    cluster_daily = _daily_top_cluster(daily, trading_dates, [b["broker"] for b in top_3])
    if not cluster_daily.empty:
        cluster_positive_days = int((cluster_daily.fillna(0) > 0).sum())
    selected_daily = pivot[top_broker["broker"]] if top_broker["broker"] in pivot.columns else pd.Series(index=pivot.index, dtype=float)
    top_broker_daily = daily[daily["broker"] == top_broker["broker"]].copy()

    mcap = _market_cap_as_of(db, ticker, end)
    adv = _avg_daily_value_as_of(db, ticker, end)
    latest_net = float(top_broker["net"])
    days_of_adv = _safe_ratio(latest_net, adv)
    broker_meta = {
        "period_days": period_days,
        "period": period_label,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "trading_days": len(trading_dates),
        "pct_market_cap": _pct(latest_net, mcap),
        "pct_avg_daily_value": _pct(latest_net, adv),
    }

    status = "active"
    broker_coverage_ratio = float(top_broker["coverage_ratio"])
    if coverage_ratio < MIN_COVERAGE_RATIO or broker_coverage_ratio < MIN_COVERAGE_RATIO:
        status = "insufficient_data"
    elif top_broker["positive_days"] == 0 or latest_net <= 0:
        status = "no_accumulation"
    elif top_broker["recency_sessions"] > 2:
        status = "stale"
    elif top_broker["recent_5_session_net"] < 0:
        status = "reversal_risk"

    config = _merge_score_config(score_config)

    magnitude_score = (_score_clip(abs(latest_net if latest_net else 0.0), adv or 1.0) + _score_clip(pct := abs((_pct(latest_net, mcap) or 0.0)), 0.5)) / 2.0
    persistence_score = top_broker["positive_ratio"] * 100.0
    recency_score = max(0.0, 100.0 - (top_broker["recency_sessions"] * 25.0))
    acceleration_score = 50.0
    if top_broker["recent_5_session_net"] > 0:
        acceleration_score = min(100.0, 50.0 + _score_clip(max(0.0, top_broker["acceleration"]), abs(top_broker["recent_5_session_net"]) or 1.0) / 2.0)
    elif top_broker["recent_5_session_net"] < 0:
        acceleration_score = max(0.0, 50.0 - _score_clip(abs(top_broker["recent_5_session_net"]), abs(top_broker["net"]) or 1.0) / 2.0)
    retention_score = top_broker["retention"] * 100.0
    cluster_score = ((cluster_ratio * 100.0) + (((sum(b["positive_ratio"] for b in top_3) / len(top_3)) if top_3 else 0.0) * 100.0)) / 2.0
    purity_score = top_broker["directional_purity"] * 100.0
    quality_score = max(0.0, 100.0 - (balance_abs_net_ratio * 10000.0))
    avg_buy_ticket = _safe_ratio(top_broker["buy"], top_broker["buy_freq"])
    avg_sell_ticket = _safe_ratio(top_broker["sell"], top_broker["sell_freq"])
    net_per_trade = _safe_ratio(top_broker["net"], top_broker["total_freq"])
    buy_freq_series = top_broker_daily["buy_freq"].tolist() if not top_broker_daily.empty else []
    frequency_consistency = _frequency_consistency(buy_freq_series)
    buy_freq_dominance = _safe_ratio(top_broker["buy_freq"], max(top_broker["sell_freq"], 1))
    trade_magnitude_score = _score_clip(abs(net_per_trade or 0.0), adv or 1.0) if adv else _score_clip(abs(net_per_trade or 0.0), abs(latest_net) or 1.0)
    frequency_score = frequency_consistency * 100.0
    retail_noise_penalty = 0.0
    high_freq_low_value = bool(
        top_broker["buy_freq"] >= max(5, len(trading_dates))
        and (days_of_adv or 0.0) < 0.75
        and (trade_magnitude_score < 15.0)
    )
    low_freq_high_value = bool(
        top_broker["buy_freq"] > 0
        and top_broker["buy_freq"] <= max(2, len(trading_dates) // 3)
        and ((days_of_adv or 0.0) >= 1.0 or ((_pct(latest_net, mcap) or 0.0) >= 0.2))
    )
    if high_freq_low_value:
        retail_noise_penalty += 20.0
    if top_broker["retention"] < 0.6:
        retail_noise_penalty += 10.0
    if cluster_ratio < config["minimum_cluster_ratio"]:
        retail_noise_penalty += 10.0
    if top_broker["recent_5_session_net"] < 0:
        retail_noise_penalty += 10.0
    flow_quality_score = (
        (trade_magnitude_score * 0.25)
        + (frequency_score * 0.20)
        + (retention_score * 0.20)
        + (cluster_score * 0.15)
        + (recency_score * 0.10)
        + (purity_score * 0.10)
    )
    if low_freq_high_value:
        flow_quality_score += 10.0
    flow_quality_score = round(max(0.0, min(100.0, flow_quality_score - retail_noise_penalty)), 2)
    retail_distribution_risk = bool(
        top_broker["positive_ratio"] >= config["minimum_positive_ratio"]
        and top_broker["recent_5_session_net"] < 0
        and top_broker["buy_freq"] >= max(5, len(trading_dates))
        and cluster_ratio < config["minimum_cluster_ratio"]
    )

    conviction_score = (
        (magnitude_score * 0.20)
        + (persistence_score * 0.20)
        + (recency_score * 0.15)
        + (acceleration_score * 0.15)
        + (retention_score * 0.10)
        + (cluster_score * 0.10)
        + (purity_score * 0.05)
        + (quality_score * 0.05)
    )

    if coverage_ratio < MIN_COVERAGE_RATIO or broker_coverage_ratio < MIN_COVERAGE_RATIO:
        conviction_score = min(conviction_score, 35.0)
    elif top_broker["recency_sessions"] > config["maximum_recent_stale_sessions"]:
        conviction_score -= 15.0
    if top_broker["recent_5_session_net"] < 0:
        conviction_score -= 20.0
    conviction_score = round(max(0.0, min(100.0, conviction_score)), 2)

    conviction_label = "none"
    if status not in {"insufficient_data", "no_accumulation", "reversal_risk"}:
        meets_common_gate = (
            top_broker["positive_ratio"] >= config["minimum_positive_ratio"]
            and top_broker["recency_sessions"] <= config["maximum_recent_stale_sessions"]
            and top_broker["directional_purity"] >= config["minimum_directional_purity"]
            and cluster_ratio >= config["minimum_cluster_ratio"]
        )
        if meets_common_gate and conviction_score >= config["aggressive_accumulation_min_score"] and top_broker["recent_5_session_net"] > 0 and top_broker["acceleration"] > 0:
            conviction_label = "aggressive_accumulation"
        elif meets_common_gate and conviction_score >= config["big_accumulation_min_score"] and (((_pct(latest_net, mcap) or 0.0) >= config["big_accumulation_min_pct_mcap"]) or ((days_of_adv or 0.0) >= config["big_accumulation_min_days_of_adv"])):
            conviction_label = "big_accumulation"
        elif meets_common_gate and conviction_score >= config["accumulation_min_score"]:
            conviction_label = "accumulation"

    flow_quality_label = "mixed_accumulation"
    if status in {"insufficient_data", "no_accumulation"}:
        flow_quality_label = "insufficient_flow_quality"
    elif retail_distribution_risk:
        flow_quality_label = "retail_distribution_risk"
    elif high_freq_low_value and flow_quality_score < 45.0:
        flow_quality_label = "retail_like_accumulation"
    elif low_freq_high_value and top_broker["retention"] >= 0.7 and cluster_ratio >= config["minimum_cluster_ratio"] and flow_quality_score >= 60.0:
        flow_quality_label = "smart_like_accumulation"
    elif flow_quality_score >= 70.0 and top_broker["retention"] >= 0.75 and cluster_ratio >= config["minimum_cluster_ratio"]:
        flow_quality_label = "smart_like_accumulation"

    result = {
        "ticker": ticker,
        "period": period_label,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "trading_days": len(trading_dates),
        "coverage_ratio": round(coverage_ratio, 4),
        "balance_abs_net_ratio": round(balance_abs_net_ratio, 6),
        "status": status,
        "top_broker": top_broker["broker"],
        "buy": top_broker["buy"],
        "sell": top_broker["sell"],
        "net": latest_net,
        "buy_freq": top_broker["buy_freq"],
        "sell_freq": top_broker["sell_freq"],
        "total_freq": top_broker["total_freq"],
        "positive_days": top_broker["positive_days"],
        "negative_days": top_broker["negative_days"],
        "positive_ratio": round(top_broker["positive_ratio"], 4),
        "observed_positive_ratio": round(top_broker["observed_positive_ratio"], 4),
        "broker_coverage_ratio": round(broker_coverage_ratio, 4),
        "consecutive_buy_days": top_broker["consecutive_buy_days"],
        "recency_sessions": top_broker["recency_sessions"],
        "recent_5_session_net": round(top_broker["recent_5_session_net"], 2),
        "previous_5_session_net": round(top_broker["previous_5_session_net"], 2),
        "acceleration": round(top_broker["acceleration"], 2),
        "retention": round(top_broker["retention"], 4),
        "directional_purity": round(top_broker["directional_purity"], 4),
        "active_days": top_broker["positive_days"],
        "last_buy_date": top_broker["last_positive_date"],
        "pct_market_cap": _pct(latest_net, mcap),
        "pct_avg_daily_value": _pct(latest_net, adv),
        "days_of_adv": days_of_adv,
        "broker_conviction_score": conviction_score,
        "broker_conviction_label": conviction_label,
        "flow_quality_score": flow_quality_score,
        "flow_quality_label": flow_quality_label,
        "retail_distribution_risk": retail_distribution_risk,
        "high_freq_low_value": high_freq_low_value,
        "low_freq_high_value": low_freq_high_value,
        "avg_buy_ticket": avg_buy_ticket,
        "avg_sell_ticket": avg_sell_ticket,
        "net_per_trade": net_per_trade,
        "frequency_consistency": round(frequency_consistency, 4),
        "buy_sell_freq_ratio": round(buy_freq_dominance, 4) if buy_freq_dominance is not None else None,
        "score_components": {
            "magnitude": round(magnitude_score, 2),
            "persistence": round(persistence_score, 2),
            "recency": round(recency_score, 2),
            "acceleration": round(acceleration_score, 2),
            "retention": round(retention_score, 2),
            "cluster": round(cluster_score, 2),
            "purity": round(purity_score, 2),
            "quality": round(quality_score, 2),
        },
        "flow_quality_components": {
            "trade_magnitude": round(trade_magnitude_score, 2),
            "frequency": round(frequency_score, 2),
            "retention": round(retention_score, 2),
            "cluster": round(cluster_score, 2),
            "recency": round(recency_score, 2),
            "purity": round(purity_score, 2),
            "retail_noise_penalty": round(retail_noise_penalty, 2),
        },
        "score_config": config,
        "top_3_net": round(top_3_net, 2),
        "top_5_net": round(top_5_net, 2),
        "cluster_ratio": round(cluster_ratio, 4),
        "cluster_positive_days": cluster_positive_days,
        "cluster_stability": round(
            sum(b["positive_ratio"] for b in top_3) / len(top_3) if top_3 else 0.0,
            4,
        ),
        "top_brokers": top_brokers,
        "cluster_brokers": [b["broker"] for b in top_3],
        "chart": {
            "price_series": _load_price_rows(db, ticker, start, end),
            "selected_broker_daily": _series_points(selected_daily, mcap),
            "broker_daily_series": {
                broker["broker"]: _series_points(
                    pivot[broker["broker"]] if broker["broker"] in pivot.columns else pd.Series(index=pivot.index, dtype=float),
                    mcap,
                )
                for broker in top_brokers[:5]
            },
            "cluster_daily": _series_points(cluster_daily, mcap) if not cluster_daily.empty else [],
            "heatmap_rows": _build_heatmap_rows(pivot, top_brokers),
        },
        "quality": {
            "total_buy": total_buy,
            "total_sell": total_sell,
            "total_net": total_net,
            "balance_abs_net_ratio": round(balance_abs_net_ratio, 6),
        },
    }
    for broker in top_brokers:
        broker["days"] = broker["active_days"]
        broker["period_days"] = period_days
        broker["period"] = period_label
        broker["start_date"] = start.isoformat()
        broker["end_date"] = end.isoformat()
        broker["trading_days"] = len(trading_dates)
        broker["pct_market_cap"] = _pct(broker["net"], mcap)
        broker["pct_avg_daily_value"] = _pct(broker["net"], adv)
        broker["days_of_adv"] = _safe_ratio(broker["net"], adv)
    return result


def summarize_broker_window(
    db: Session,
    ticker: str,
    period_days: int = 30,
    top_limit: int = 5,
    score_config: dict[str, Any] | None = None,
    as_of_date: date | None = None,
) -> dict[str, Any] | None:
    """Compatibility wrapper for callers that want a named summary helper."""
    return summarize_broker_accumulation(
        db,
        ticker,
        period_days,
        top_limit=top_limit,
        score_config=score_config,
        as_of_date=as_of_date,
    )
