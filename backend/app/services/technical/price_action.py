"""Price action: swing pivots, recent candle range, support/resistance proximity."""
import pandas as pd

from app.services.technical._base import as_of_filter, clamp_score, make_result
from app.utils.indicators import atr, swing_points


def run(df: pd.DataFrame, *, benchmark_df=None, as_of=None) -> list[dict]:
    df = as_of_filter(df, as_of)
    if len(df) < 30:
        return []
    df = df.copy()
    df["atr"] = atr(df, 14)
    swing_hi_idx, swing_lo_idx = swing_points(df["high"], df["low"], window=3)

    # Build dynamic S/R from last N swings
    recent_hi = df.loc[swing_hi_idx, "high"].tail(10).tolist() if len(swing_hi_idx) else []
    recent_lo = df.loc[swing_lo_idx, "low"].tail(10).tolist() if len(swing_lo_idx) else []

    results = []
    for i in range(20, len(df)):
        row = df.iloc[i]
        close = row["close"]
        atr_v = row["atr"] if not pd.isna(row["atr"]) else 0
        # distance to nearest S/R
        upper = min(recent_hi, key=lambda x: abs(x - close)) if recent_hi else close
        lower = min(recent_lo, key=lambda x: abs(x - close)) if recent_lo else close
        dist_upper = abs(close - upper)
        dist_lower = abs(close - lower)
        near_sr = min(dist_upper, dist_lower) < (1.0 * atr_v) if atr_v else False

        body = abs(row["close"] - row["open"])
        rng = (row["high"] - row["low"]) or 1e-9
        body_ratio = body / rng

        # bullish price action: close near high, body > 0.5
        bullish = (row["close"] - row["low"]) / rng
        score = clamp_score(40 + 30 * bullish + 20 * body_ratio + (10 if near_sr else 0))
        payload = {
            "nearest_resistance": upper,
            "nearest_support": lower,
            "atr": None if pd.isna(atr_v) else float(atr_v),
            "body_ratio": float(body_ratio),
            "close_position": float(bullish),
            "near_sr": bool(near_sr),
        }
        results.append(make_result(df.iloc[i]["date"].date(), "price_action", payload, score))
    return results
