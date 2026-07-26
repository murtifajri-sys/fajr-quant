"""Deterministic IPO/new-listing screener.

The regular screener expects mature history. This module keeps new listings in a
separate lane so short history is not mistaken for weak data.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.broker_flow import BrokerFlow
from app.models.price import DailyPrice
from app.models.setting import WatchlistItem
from app.models.stock import Stock

IPO_MAX_CALENDAR_AGE_DAYS = 120
MIN_LIQUIDITY_VALUE = 1_000_000_000.0
MIN_BROKER_COVERAGE_RATIO = 0.8


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _pct(value: float | None, base: float | None) -> float | None:
    if value is None or not base:
        return None
    return round((float(value) / float(base)) * 100.0, 2)


def _price_payload(row: DailyPrice) -> dict[str, Any]:
    return {
        "date": row.date,
        "open": float(row.open) if row.open is not None else None,
        "high": float(row.high) if row.high is not None else None,
        "low": float(row.low) if row.low is not None else None,
        "close": float(row.close) if row.close is not None else None,
        "volume": float(row.volume or 0.0),
    }


def _load_prices(db: Session, ticker: str, start: date, end: date) -> list[dict[str, Any]]:
    rows = db.execute(
        select(DailyPrice)
        .where(
            DailyPrice.ticker == ticker,
            DailyPrice.date >= start,
            DailyPrice.date <= end,
        )
        .order_by(DailyPrice.date.asc())
    ).scalars().all()
    return [_price_payload(row) for row in rows if row.close is not None]


def _load_flows(db: Session, ticker: str, start: date, end: date) -> list[BrokerFlow]:
    return db.execute(
        select(BrokerFlow)
        .where(
            BrokerFlow.ticker == ticker,
            BrokerFlow.date >= start,
            BrokerFlow.date <= end,
            BrokerFlow.source != "stockbit_empty",
        )
        .order_by(BrokerFlow.date.asc(), BrokerFlow.broker.asc())
    ).scalars().all()


def _anchored_vwap(prices: list[dict[str, Any]]) -> float | None:
    value_sum = 0.0
    volume_sum = 0.0
    for row in prices:
        close = row.get("close")
        volume = row.get("volume") or 0.0
        if close is None or volume <= 0:
            continue
        value_sum += float(close) * float(volume)
        volume_sum += float(volume)
    if volume_sum <= 0:
        return None
    return value_sum / volume_sum


def _flow_features(flows: list[BrokerFlow], trading_dates: list[date]) -> dict[str, Any]:
    if not trading_dates:
        return {
            "coverage_ratio": 0.0,
            "flow_days": 0,
            "top_broker": None,
            "top_broker_net": 0.0,
            "top_broker_positive_days": 0,
            "top_broker_positive_ratio": 0.0,
            "recent_5_net": 0.0,
            "recent_10_net": 0.0,
            "top3_net": 0.0,
            "concentration_ratio": None,
            "distribution_reversal": False,
        }

    flow_dates = {row.date for row in flows}
    by_broker: dict[str, dict[date, float]] = {}
    for row in flows:
        by_broker.setdefault(row.broker, {})
        by_broker[row.broker][row.date] = by_broker[row.broker].get(row.date, 0.0) + float(row.net_value or 0.0)

    broker_totals = {
        broker: sum(values.get(day, 0.0) for day in trading_dates)
        for broker, values in by_broker.items()
    }
    top_broker = max(broker_totals, key=broker_totals.get) if broker_totals else None
    top_values = by_broker.get(top_broker or "", {})
    top_series = [float(top_values.get(day, 0.0)) for day in trading_dates]
    top_positive_days = sum(1 for value in top_series if value > 0)
    top3_net = sum(value for value in sorted(broker_totals.values(), reverse=True)[:3] if value > 0)
    top_net = float(broker_totals.get(top_broker or "", 0.0))
    recent_5 = sum(top_series[-5:])
    recent_10 = sum(top_series[-10:])
    recent_3 = sum(top_series[-3:])
    prior_5 = sum(top_series[-8:-3]) if len(top_series) >= 8 else sum(top_series[:-3])

    return {
        "coverage_ratio": round(len(flow_dates) / len(trading_dates), 3),
        "flow_days": len(flow_dates),
        "top_broker": top_broker,
        "top_broker_net": round(top_net, 2),
        "top_broker_positive_days": top_positive_days,
        "top_broker_positive_ratio": round(top_positive_days / len(trading_dates), 3),
        "recent_5_net": round(recent_5, 2),
        "recent_10_net": round(recent_10, 2),
        "top3_net": round(top3_net, 2),
        "concentration_ratio": round(top_net / top3_net, 3) if top3_net > 0 else None,
        "distribution_reversal": recent_3 < 0 and prior_5 > 0,
    }


def _phase_for_sessions(sessions: int) -> str:
    if sessions <= 5:
        return "price_discovery"
    if sessions <= 20:
        return "early_watch"
    if sessions <= 40:
        return "base_forming"
    return "setup_ready"


def _setup_from_levels(
    sessions: int,
    last_price: float | None,
    opening_high: float | None,
    base_high: float | None,
    base_low: float | None,
    avwap: float | None,
    volume_ratio: float | None,
    flow: dict[str, Any],
) -> tuple[str, str, dict[str, Any], list[str]]:
    blockers: list[str] = []
    if last_price is None:
        return "no_setup", "IPO Data Belum Cukup", {}, ["no_last_price"]

    trigger = base_high if sessions > 20 and base_high else opening_high
    invalidation = base_low if sessions > 20 and base_low else avwap
    extension_from_trigger = ((last_price / trigger) - 1.0) if trigger else None
    extension_from_avwap = ((last_price / avwap) - 1.0) if avwap else None
    near_trigger = extension_from_trigger is not None and -0.03 <= extension_from_trigger <= 0.05
    near_avwap = extension_from_avwap is not None and abs(extension_from_avwap) <= 0.08
    breakout_confirmed = bool(trigger and last_price > trigger and (volume_ratio or 0.0) >= 1.2)

    if extension_from_trigger is not None and extension_from_trigger > 0.12:
        blockers.append("price_extended_from_trigger")
    if extension_from_avwap is not None and extension_from_avwap > 0.15:
        blockers.append("price_extended_from_avwap")

    levels = {
        "last_price": _round(last_price),
        "trigger_price": _round(trigger),
        "entry_low": _round(trigger * 0.98) if trigger else None,
        "entry_high": _round(trigger * 1.03) if trigger else None,
        "bow_zone_low": _round(avwap * 0.97) if avwap else None,
        "bow_zone_high": _round(avwap * 1.03) if avwap else None,
        "invalidation_price": _round(invalidation),
        "distance_to_trigger_pct": _pct((trigger - last_price), last_price) if trigger else None,
        "extension_from_avwap_pct": _pct((last_price - avwap), avwap) if avwap else None,
    }

    if sessions <= 5:
        return "observe", "IPO Observasi", levels, blockers
    if flow["top_broker_net"] <= 0 or flow["recent_5_net"] <= 0:
        return "no_setup", "IPO Hindari - Distribusi", levels, blockers + ["broker_flow_not_positive"]
    if flow["distribution_reversal"]:
        return "no_setup", "IPO Hindari - Distribusi", levels, blockers + ["distribution_reversal"]
    if blockers:
        return "wait_retest", "IPO Tunggu Retest", levels, blockers
    if sessions <= 20:
        if breakout_confirmed and near_trigger and near_avwap:
            return "opening_range_breakout", "IPO Early Entry", levels, blockers
        if near_trigger or near_avwap:
            return "watch_accumulation", "IPO Watch - Akumulasi", levels, blockers
        return "watch_accumulation", "IPO Watch - Akumulasi", levels, blockers + ["waiting_opening_range_confirmation"]
    if sessions <= 40:
        if breakout_confirmed and near_trigger:
            return "base_breakout", "IPO Mendekati Entry", levels, blockers
        if near_avwap:
            return "buy_on_weakness", "IPO Mendekati Entry", levels, blockers
        return "base_forming", "IPO Base Forming", levels, blockers + ["base_not_confirmed"]
    if breakout_confirmed and near_trigger:
        return "base_breakout", "IPO Siap Entry", levels, blockers
    if near_avwap:
        return "buy_on_weakness", "IPO Siap Entry", levels, blockers
    return "base_forming", "IPO Base Forming", levels, blockers + ["waiting_setup_confirmation"]


def build_ipo_candidate(
    db: Session,
    stock: Stock,
    as_of_date: date,
    min_liquidity_value: float = MIN_LIQUIDITY_VALUE,
) -> dict[str, Any] | None:
    if not stock.listing_date:
        return None
    calendar_age_days = (as_of_date - stock.listing_date).days
    if calendar_age_days < 0 or calendar_age_days > IPO_MAX_CALENDAR_AGE_DAYS:
        return None

    prices = _load_prices(db, stock.ticker, stock.listing_date, as_of_date)
    trading_dates = [row["date"] for row in prices]
    sessions = len(prices)
    phase = _phase_for_sessions(sessions)
    flows = _load_flows(db, stock.ticker, stock.listing_date, as_of_date)
    flow = _flow_features(flows, trading_dates)

    last = prices[-1] if prices else {}
    last_price = last.get("close")
    opening = prices[:5]
    opening_high = max((row["high"] for row in opening if row.get("high") is not None), default=None)
    opening_low = min((row["low"] for row in opening if row.get("low") is not None), default=None)
    base_rows = prices[-16:-1] if sessions > 20 else prices[5:]
    base_high = max((row["high"] for row in base_rows if row.get("high") is not None), default=None)
    base_low = min((row["low"] for row in base_rows if row.get("low") is not None), default=None)
    avwap = _anchored_vwap(prices)
    values = [
        float(row["close"]) * float(row["volume"] or 0.0)
        for row in prices[-5:]
        if row.get("close") is not None
    ]
    avg_value_5 = sum(values) / len(values) if values else 0.0
    vols = [float(row.get("volume") or 0.0) for row in prices]
    avg_vol_5 = sum(vols[-5:]) / min(5, len(vols)) if vols else 0.0
    baseline_vols = vols[-20:] if len(vols) >= 20 else vols
    baseline_vol = sum(baseline_vols) / len(baseline_vols) if baseline_vols else 0.0
    volume_ratio = avg_vol_5 / baseline_vol if baseline_vol > 0 else None
    base_width_pct = ((base_high - base_low) / ((base_high + base_low) / 2.0)) * 100 if base_high and base_low else None

    setup_type, status, levels, blockers = _setup_from_levels(
        sessions,
        last_price,
        opening_high,
        base_high,
        base_low,
        avwap,
        volume_ratio,
        flow,
    )
    if sessions < 6:
        blockers.append("min_6_sessions_required")
        status = "IPO Data Belum Cukup"
    if avg_value_5 < min_liquidity_value:
        blockers.append("liquidity_below_threshold")
        if status in {"IPO Early Entry", "IPO Mendekati Entry", "IPO Siap Entry"}:
            status = "IPO Risiko Tinggi"
    if flow["coverage_ratio"] < MIN_BROKER_COVERAGE_RATIO:
        blockers.append("broker_coverage_below_threshold")
        if status in {"IPO Early Entry", "IPO Mendekati Entry", "IPO Siap Entry"}:
            status = "IPO Watch - Akumulasi"
    if stock.board and "pemantauan" in stock.board.lower():
        blockers.append("special_monitoring_board")
        if status in {"IPO Early Entry", "IPO Mendekati Entry", "IPO Siap Entry"}:
            status = "IPO Risiko Tinggi"

    accumulation_score = min(100.0, max(0.0, (flow["top_broker_positive_ratio"] * 45.0) + (flow["coverage_ratio"] * 25.0) + (20.0 if flow["recent_5_net"] > 0 else 0.0)))
    structure_score = 30.0
    if setup_type in {"opening_range_breakout", "base_breakout", "buy_on_weakness"}:
        structure_score = 75.0
    elif setup_type in {"watch_accumulation", "base_forming"}:
        structure_score = 55.0
    liquidity_score = min(100.0, (avg_value_5 / max(min_liquidity_value, 1.0)) * 70.0)
    volume_score = min(100.0, (volume_ratio or 0.0) * 50.0)
    penalty = 0.0
    if "price_extended_from_trigger" in blockers:
        penalty += 15.0
    if "distribution_reversal" in blockers:
        penalty += 30.0
    ipo_score = max(0.0, min(100.0, (accumulation_score * 0.3) + (structure_score * 0.3) + (liquidity_score * 0.15) + (volume_score * 0.15) - penalty))

    return {
        "ticker": stock.ticker,
        "name": stock.name,
        "board": stock.board,
        "listing_date": stock.listing_date,
        "calendar_age_days": calendar_age_days,
        "trading_session_age": sessions,
        "phase": phase,
        "status": status,
        "setup_type": setup_type,
        "ipo_setup_score": round(ipo_score, 2),
        "last_price": _round(last_price),
        "last_price_date": last.get("date"),
        "avg_value_5": round(avg_value_5, 2),
        "opening_range_high": _round(opening_high),
        "opening_range_low": _round(opening_low),
        "anchored_vwap": _round(avwap),
        "base_high": _round(base_high),
        "base_low": _round(base_low),
        "base_width_pct": _round(base_width_pct),
        "volume_ratio": _round(volume_ratio),
        "broker_flow": flow,
        "levels": levels,
        "blockers": sorted(set(blockers)),
    }


def build_ipo_screener(
    db: Session,
    limit: int = 50,
    status: str | None = None,
    setup: str | None = None,
    only_actionable: bool = False,
    min_score: float | None = None,
) -> dict[str, Any]:
    as_of_date = db.execute(select(DailyPrice.date).order_by(DailyPrice.date.desc()).limit(1)).scalar_one_or_none() or date.today()
    start = as_of_date - timedelta(days=IPO_MAX_CALENDAR_AGE_DAYS)
    stocks = db.execute(
        select(Stock)
        .where(Stock.listing_date >= start, Stock.listing_date <= as_of_date)
        .order_by(Stock.listing_date.desc(), Stock.ticker.asc())
    ).scalars().all()
    rows = [row for stock in stocks if (row := build_ipo_candidate(db, stock, as_of_date))]
    if status:
        rows = [row for row in rows if row["status"] == status]
    if setup:
        rows = [row for row in rows if row["setup_type"] == setup]
    if only_actionable:
        rows = [row for row in rows if row["status"] in {"IPO Early Entry", "IPO Mendekati Entry", "IPO Siap Entry"}]
    if min_score is not None:
        rows = [row for row in rows if row["ipo_setup_score"] >= min_score]
    rows.sort(key=lambda row: (row["status"] not in {"IPO Early Entry", "IPO Mendekati Entry", "IPO Siap Entry"}, -row["ipo_setup_score"], -row["trading_session_age"]))
    return {
        "as_of_date": as_of_date,
        "max_calendar_age_days": IPO_MAX_CALENDAR_AGE_DAYS,
        "total": len(rows),
        "results": rows[: max(1, limit)],
    }


def build_ipo_detail(db: Session, ticker: str) -> dict[str, Any] | None:
    as_of_date = db.execute(select(DailyPrice.date).order_by(DailyPrice.date.desc()).limit(1)).scalar_one_or_none() or date.today()
    stock = db.get(Stock, ticker.upper())
    if not stock:
        return None
    row = build_ipo_candidate(db, stock, as_of_date)
    if not row:
        return None
    row["recent_prices"] = _load_prices(db, stock.ticker, max(stock.listing_date, as_of_date - timedelta(days=45)), as_of_date)
    row["watchlist_names"] = [
        item.name
        for item in db.execute(select(WatchlistItem).where(WatchlistItem.ticker == stock.ticker)).scalars().all()
    ]
    return row
