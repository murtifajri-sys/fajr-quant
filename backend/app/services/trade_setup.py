"""Deterministic trade setup classification from OHLCV and broker gates."""
from __future__ import annotations

from datetime import date
from typing import Any


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric == numeric else None


def _avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return (sum(clean) / len(clean)) if clean else None


def _pct_distance(last_price: float | None, target: float | None) -> float | None:
    if not last_price or target is None:
        return None
    return round(((target - last_price) / last_price) * 100.0, 2)


def _within_pct_or_atr(distance_pct: float | None, atr_value: float, last_price: float, pct_threshold: float = 8.0) -> bool:
    if distance_pct is None:
        return False
    atr_threshold = (atr_value / last_price) * 100.0 * 1.5
    return abs(distance_pct) <= max(atr_threshold, pct_threshold)


def _price(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _atr(rows: list[dict[str, Any]], period: int = 14) -> float | None:
    ranges: list[float] = []
    previous_close: float | None = None
    for row in rows:
        high = _num(row.get("high"))
        low = _num(row.get("low"))
        close = _num(row.get("close"))
        if high is None or low is None:
            previous_close = close
            continue
        if previous_close is None:
            true_range = high - low
        else:
            true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
        if true_range >= 0:
            ranges.append(true_range)
        previous_close = close
    if len(ranges) < period:
        return None
    return _avg(ranges[-period:])


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    current = _avg(values[:period])
    if current is None:
        return None
    for value in values[period:]:
        current = (value * k) + (current * (1 - k))
    return current


def _swings(rows: list[dict[str, Any]], window: int = 3) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    highs: list[dict[str, Any]] = []
    lows: list[dict[str, Any]] = []
    for idx in range(window, len(rows) - window):
        row = rows[idx]
        high = _num(row.get("high"))
        low = _num(row.get("low"))
        if high is None or low is None:
            continue
        left = rows[idx - window : idx]
        right = rows[idx + 1 : idx + window + 1]
        if all(high >= (_num(item.get("high")) or high) for item in left + right):
            highs.append({"price": high, "date": row.get("date"), "index": idx})
        if all(low <= (_num(item.get("low")) or low) for item in left + right):
            lows.append({"price": low, "date": row.get("date"), "index": idx})
    return highs, lows


def _cluster_level(levels: list[dict[str, Any]], atr: float | None, prefer_high: bool) -> dict[str, Any] | None:
    if not levels:
        return None
    tolerance = (atr or 0) * 0.5
    best: dict[str, Any] | None = None
    for level in levels:
        members = [item for item in levels if tolerance <= 0 or abs(item["price"] - level["price"]) <= tolerance]
        price = _avg([item["price"] for item in members])
        if price is None:
            continue
        candidate = {
            "price": price,
            "touches": len(members),
            "date": max((item.get("date") for item in members if item.get("date")), default=level.get("date")),
            "index": max(item.get("index", 0) for item in members),
        }
        if best is None:
            best = candidate
            continue
        if candidate["touches"] > best["touches"]:
            best = candidate
        elif candidate["touches"] == best["touches"]:
            best = max([best, candidate], key=lambda item: (item["index"], item["price"] if prefer_high else -item["price"]))
    return best


def _latest_volume_ratio(rows: list[dict[str, Any]]) -> float | None:
    if len(rows) < 20:
        return None
    volume = _num(rows[-1].get("volume"))
    ma20 = _avg([_num(row.get("volume")) or 0.0 for row in rows[-20:]])
    if volume is None or not ma20:
        return None
    return round(volume / ma20, 2)


def _trade_status_code(broker: dict[str, Any] | None, entry: dict[str, Any] | None) -> str:
    broker = broker or {}
    entry = entry or {}
    conviction = _num(broker.get("broker_conviction_score"))
    flow = _num(broker.get("flow_quality_score"))
    entry_score = _num(entry.get("score"))
    if conviction is None or flow is None or entry_score is None:
        return "unavailable"
    if broker.get("status") in {"no_accumulation", "stale", "reversal_risk", "insufficient_data"}:
        return "hold" if broker.get("status") != "insufficient_data" else "unavailable"
    if broker.get("broker_conviction_label") == "none":
        return "hold"
    if (_num(broker.get("recent_5_session_net")) or 0) <= 0:
        return "hold"
    if broker.get("retail_distribution_risk") or broker.get("flow_quality_label") == "retail_like_accumulation":
        return "hold"
    phase = str(entry.get("phase") or "")
    if phase in {"Siap Jual", "Exit"}:
        return "hold"
    if (
        conviction >= 70
        and flow >= 60
        and entry_score >= 75
        and broker.get("flow_quality_label") in {"smart_like_accumulation", "mixed_accumulation"}
        and phase in {"Siap Entry", "Hold"}
    ):
        return "ready"
    if conviction >= 55 and entry_score >= 50:
        return "waiting"
    return "hold"


def _base_payload(
    *,
    setup_type: str,
    setup_state: str,
    label: str,
    last_price: float | None,
    trigger_price: float | None = None,
    zone_low: float | None = None,
    zone_high: float | None = None,
    invalidation_price: float | None = None,
    distance_pct: float | None = None,
    risk_reward: float | None = None,
    confirmations: list[str] | None = None,
    confluences: list[str] | None = None,
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
    as_of_date: date | str | None = None,
) -> dict[str, Any]:
    return {
        "setup_type": setup_type,
        "setup_state": setup_state,
        "label": label,
        "last_price": _price(last_price),
        "trigger_price": _price(trigger_price),
        "zone_low": _price(zone_low),
        "zone_high": _price(zone_high),
        "invalidation_price": _price(invalidation_price),
        "distance_pct": distance_pct,
        "risk_reward": round(risk_reward, 2) if risk_reward is not None else None,
        "confirmations": confirmations or [],
        "confluences": confluences or [],
        "blockers": blockers or [],
        "warnings": warnings or [],
        "as_of_date": as_of_date.isoformat() if hasattr(as_of_date, "isoformat") else as_of_date,
    }


def build_trade_setup(
    price_rows: list[dict[str, Any]],
    broker: dict[str, Any] | None,
    entry_readiness: dict[str, Any] | None,
    trade_status_code: str | None = None,
) -> dict[str, Any]:
    """Build one actionable setup detail. This is derivative and does not rescore history."""
    rows = sorted(price_rows, key=lambda item: item.get("date") or date.min)
    rows = [row for row in rows if _num(row.get("close")) is not None]
    last = rows[-1] if rows else {}
    last_price = _num(last.get("close"))
    as_of_date = last.get("date")
    status_code = trade_status_code or _trade_status_code(broker, entry_readiness)

    if len(rows) < 25 or last_price is None:
        return _base_payload(
            setup_type="no_setup",
            setup_state="unavailable",
            label="Data setup belum lengkap",
            last_price=last_price,
            blockers=["data_setup_belum_lengkap"],
            as_of_date=as_of_date,
        )
    if status_code in {"hold", "unavailable"}:
        return _base_payload(
            setup_type="no_setup",
            setup_state="blocked",
            label="Hold",
            last_price=last_price,
            blockers=["broker_gate_not_clear" if status_code == "hold" else "data_setup_belum_lengkap"],
            as_of_date=as_of_date,
        )

    atr = _atr(rows)
    closes = [_num(row.get("close")) or 0.0 for row in rows]
    ema20 = _ema(closes, 20)
    vol_ratio = _latest_volume_ratio(rows)
    swing_highs, swing_lows = _swings(rows)
    resistance = _cluster_level([item for item in swing_highs if item["price"] > last_price], atr, prefer_high=False)
    support = _cluster_level([item for item in swing_lows if item["price"] < last_price], atr, prefer_high=True)
    recent_high = max((_num(row.get("high")) or last_price) for row in rows[-20:-1])
    recent_low = min((_num(row.get("low")) or last_price) for row in rows[-20:-1])
    resistance_price = (resistance or {}).get("price") or (recent_high if recent_high > last_price else None)
    support_price = (support or {}).get("price") or (recent_low if recent_low < last_price else None)
    atr_value = atr or max(last_price * 0.025, 1.0)
    confirmations = ["broker_flow_positive"]
    if vol_ratio is not None:
        confirmations.append("volume_ratio_available")

    if resistance_price:
        distance_to_resistance = _pct_distance(last_price, resistance_price)
        near_resistance = distance_to_resistance is not None and distance_to_resistance >= 0 and min(atr_value / last_price * 100, 5.0) >= distance_to_resistance
        breakout_confirmed = last_price > resistance_price + (0.1 * atr_value) and (vol_ratio or 0) >= 1.2
        if breakout_confirmed:
            zone_low = resistance_price - (0.5 * atr_value)
            zone_high = resistance_price + (0.25 * atr_value)
            distance = 0.0 if zone_low <= last_price <= zone_high else _pct_distance(last_price, zone_high if last_price < zone_low else zone_low)
            return _base_payload(
                setup_type="wait_retest",
                setup_state="confirmed" if zone_low <= last_price <= zone_high else "watch",
                label=f"Tunggu Retest {round(zone_low)}-{round(zone_high)}",
                last_price=last_price,
                trigger_price=resistance_price,
                zone_low=zone_low,
                zone_high=zone_high,
                invalidation_price=zone_low,
                distance_pct=distance,
                confirmations=["dry_pullback_volume", "bullish_reclaim", "broker_flow_positive"],
                confluences=["breakout_level", "broker_flow_positive"],
                blockers=[] if zone_low <= last_price <= zone_high else ["waiting_retest_zone"],
                warnings=[] if (vol_ratio or 0) >= 1.2 else ["breakout_without_volume"],
                as_of_date=as_of_date,
            )
        if near_resistance:
            invalidation = support_price or (last_price - atr_value)
            reward = (resistance_price - last_price)
            risk = max(last_price - invalidation, atr_value * 0.5)
            return _base_payload(
                setup_type="wait_breakout",
                setup_state="watch",
                label=f"Tunggu Breakout > {round(resistance_price)}",
                last_price=last_price,
                trigger_price=resistance_price,
                invalidation_price=invalidation,
                distance_pct=distance_to_resistance,
                risk_reward=(reward / risk) if risk > 0 else None,
                confirmations=["close_above_trigger", "volume_1_2x_ma20", "broker_flow_positive"],
                confluences=["near_resistance", "broker_flow_positive"],
                blockers=["waiting_breakout_confirmation"],
                as_of_date=as_of_date,
            )

    impulse_low = support_price or recent_low
    impulse_high = max((_num(row.get("high")) or last_price) for row in rows[-30:])
    fib_low = impulse_high - ((impulse_high - impulse_low) * 0.705)
    fib_high = impulse_high - ((impulse_high - impulse_low) * 0.50)
    confluences = ["broker_flow_positive"]
    if support_price and abs(last_price - support_price) <= atr_value:
        confluences.append("swing_support")
    if ema20 and abs(last_price - ema20) <= atr_value:
        confluences.append("ema20")
    bow_zone_low = min(fib_low, support_price or fib_low)
    bow_zone_high = max(min(fib_high, (support_price or fib_high) + (0.5 * atr_value)), bow_zone_low)
    distance_to_bow = 0.0 if bow_zone_low <= last_price <= bow_zone_high else _pct_distance(last_price, bow_zone_high)
    near_bow_zone = _within_pct_or_atr(distance_to_bow, atr_value, last_price)
    price_in_bow_zone = bow_zone_low <= last_price <= bow_zone_high
    if price_in_bow_zone or near_bow_zone:
        confluences.append("fib_value_area")
    dry_pullback = vol_ratio is not None and vol_ratio <= 0.9
    has_bow_confluence = len(set(confluences)) >= 2 and impulse_high - impulse_low >= 2 * atr_value
    if has_bow_confluence and (price_in_bow_zone or near_bow_zone):
        bow_confirmed = price_in_bow_zone and dry_pullback
        bow_confirmations = ["broker_flow_positive"]
        if dry_pullback:
            bow_confirmations.append("volume_pullback_dry")
        if price_in_bow_zone:
            bow_confirmations.append("price_in_value_zone")
        return _base_payload(
            setup_type="buy_on_weakness",
            setup_state="confirmed" if bow_confirmed else "watch",
            label=f"BOW {'Confirmed' if bow_confirmed else 'Watch'} {round(bow_zone_low)}-{round(bow_zone_high)}",
            last_price=last_price,
            zone_low=bow_zone_low,
            zone_high=bow_zone_high,
            invalidation_price=bow_zone_low - (0.25 * atr_value),
            distance_pct=distance_to_bow,
            confirmations=bow_confirmations,
            confluences=[*dict.fromkeys(confluences)],
            blockers=[] if bow_confirmed else ["waiting_price_in_zone"],
            warnings=[] if dry_pullback else ["pullback_volume_not_dry"],
            as_of_date=as_of_date,
        )
    if has_bow_confluence and last_price > bow_zone_high:
        return _base_payload(
            setup_type="wait_value_area",
            setup_state="watch",
            label=f"Tunggu area value {round(bow_zone_low)}-{round(bow_zone_high)}",
            last_price=last_price,
            zone_low=bow_zone_low,
            zone_high=bow_zone_high,
            invalidation_price=bow_zone_low - (0.25 * atr_value),
            distance_pct=distance_to_bow,
            confirmations=["structure_holds", "broker_flow_positive"],
            confluences=[*dict.fromkeys([*confluences, "anti_chasing"])],
            blockers=["price_extended"],
            warnings=["anti_chasing"],
            as_of_date=as_of_date,
        )

    if ema20 and last_price > ema20 * 1.08:
        zone_high = ema20 + (0.25 * atr_value)
        zone_low = ema20 - (0.5 * atr_value)
        return _base_payload(
            setup_type="wait_value_area",
            setup_state="watch",
            label=f"Tunggu area value {round(zone_low)}-{round(zone_high)}",
            last_price=last_price,
            zone_low=zone_low,
            zone_high=zone_high,
            invalidation_price=zone_low - (0.25 * atr_value),
            distance_pct=_pct_distance(last_price, zone_high),
            confirmations=["structure_holds", "broker_flow_positive"],
            confluences=["ema20", "anti_chasing"],
            blockers=["price_extended"],
            warnings=["anti_chasing"],
            as_of_date=as_of_date,
        )

    return _base_payload(
        setup_type="no_setup",
        setup_state="watch",
        label="Hold",
        last_price=last_price,
        invalidation_price=support_price,
        blockers=["no_clear_trigger_or_value_zone"],
        as_of_date=as_of_date,
    )
