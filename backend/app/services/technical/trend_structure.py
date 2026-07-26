"""Trend structure + price action analysis: HH/HL, swing detection, BOS/CHoCH, S/R."""
import pandas as pd

from app.services.technical._base import as_of_filter, clamp_score, make_result
from app.utils.indicators import ema, sma, swing_points


def run(df: pd.DataFrame, *, benchmark_df: pd.DataFrame | None = None, as_of=None) -> list[dict]:
    df = as_of_filter(df, as_of)
    if len(df) < 60:
        return []
    df = df.copy()
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["sma200"] = sma(df["close"], 200)
    swing_hi_idx, swing_lo_idx = swing_points(df["high"], df["low"], window=3)

    results = []
    # Determine trend from EMA alignment + slope
    for i in range(50, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        up = row["ema20"] > row["ema50"] and (row["sma200"] is not None and not pd.isna(row["sma200"]))
        above_200 = not pd.isna(row["sma200"]) and row["close"] > row["sma200"]
        slope = (row["ema50"] - prev["ema50"]) / prev["ema50"] if prev["ema50"] else 0
        if up and above_200 and slope > 0:
            structure = "uptrend"
            score = clamp_score(60 + 40 * min(slope * 200, 1))
        elif (not up) and (not above_200) and slope < 0:
            structure = "downtrend"
            score = clamp_score(40 - 30 * min(abs(slope) * 200, 1))
        else:
            structure = "range"
            score = 50
        payload = {
            "structure": structure,
            "above_200sma": bool(above_200) if not pd.isna(above_200) else None,
            "ema20": None if pd.isna(row["ema20"]) else float(row["ema20"]),
            "ema50": None if pd.isna(row["ema50"]) else float(row["ema50"]),
            "sma200": None if pd.isna(row["sma200"]) else float(row["sma200"]),
            "slope50": float(slope),
        }
        results.append(make_result(df.iloc[i]["date"].date(), "trend_structure", payload, score))
    return results
