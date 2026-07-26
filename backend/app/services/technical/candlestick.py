"""Candlestick pattern detection: doji, engulfing, hammer, shooting star, morning/evening star."""
import pandas as pd

from app.services.technical._base import as_of_filter, clamp_score, make_result

PATTERNS_BULLISH = {"hammer", "morning_star", "bullish_engulfing", "piercing"}
PATTERNS_BEARISH = {"shooting_star", "evening_star", "bearish_engulfing", "dark_cloud"}


def _detect(df: pd.DataFrame, i: int) -> tuple[str | None, dict]:
    o = df.iloc[i]["open"]; c = df.iloc[i]["close"]
    h = df.iloc[i]["high"]; l = df.iloc[i]["low"]
    body = abs(c - o)
    rng = (h - l) or 1e-9
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    info = {"body": float(body), "range": float(rng), "upper_wick": float(upper_wick), "lower_wick": float(lower_wick)}

    if body / rng < 0.1:
        return "doji", info
    if i >= 1:
        prev = df.iloc[i - 1]
        # Engulfing
        if c > o and prev["close"] < prev["open"] and c >= prev["open"] and o <= prev["close"]:
            return "bullish_engulfing", info
        if c < o and prev["close"] > prev["open"] and o >= prev["close"] and c <= prev["open"]:
            return "bearish_engulfing", info
    if lower_wick > 2 * body and upper_wick < body:
        return "hammer", info
    if upper_wick > 2 * body and lower_wick < body:
        return "shooting_star", info
    if i >= 2:
        a = df.iloc[i - 2]; b = df.iloc[i - 1]
        if a["close"] < a["open"] and b["close"] < b["open"] and c > o and c > (a["open"] + a["close"]) / 2:
            return "morning_star", info
        if a["close"] > a["open"] and b["close"] > b["open"] and c < o and c < (a["open"] + a["close"]) / 2:
            return "evening_star", info
    return None, info


def run(df: pd.DataFrame, *, benchmark_df=None, as_of=None) -> list[dict]:
    df = as_of_filter(df, as_of)
    if len(df) < 5:
        return []
    results = []
    for i in range(2, len(df)):
        name, info = _detect(df, i)
        if not name:
            continue
        bullish = name in PATTERNS_BULLISH
        bearish = name in PATTERNS_BEARISH
        if bullish:
            score = clamp_score(75)
        elif bearish:
            score = clamp_score(25)
        else:
            score = 50  # doji neutral
        payload = {"pattern": name, **info}
        results.append(make_result(df.iloc[i]["date"].date(), "candlestick", payload, score))
    return results
