"""Breakout detection: EMA cross, RSI momentum, price breakout, volume confirmation."""
import pandas as pd

from app.services.technical._base import as_of_filter, clamp_score, make_result
from app.utils.indicators import ema, rsi, sma


def run(df: pd.DataFrame, *, benchmark_df: pd.DataFrame | None = None, as_of=None) -> list[dict]:
    df = as_of_filter(df, as_of)
    if len(df) < 30:
        return []

    df = df.copy()
    df["ema5"] = ema(df["close"], 5)
    df["ema20"] = ema(df["close"], 20)
    df["rsi14"] = rsi(df["close"], 14)
    df["vol_sma20"] = sma(df["volume"], 20)
    df["high_3"] = df["high"].rolling(3).max().shift(1)

    results = []
    for i in range(25, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        prev2 = df.iloc[i - 2]

        cond_close_ema20 = row["close"] > row["ema20"] if not pd.isna(row["ema20"]) else False
        cond_ema5_ema20 = row["ema5"] > row["ema20"] if not pd.isna(row["ema5"]) else False
        cond_ema20_rising = row["ema20"] > prev["ema20"] if not pd.isna(row["ema20"]) else False
        cond_rsi45 = row["rsi14"] > 45 if not pd.isna(row["rsi14"]) else False
        cond_rsi_rising = row["rsi14"] > prev["rsi14"] if not pd.isna(row["rsi14"]) else False
        cond_breakout = row["close"] > row["high_3"] if not pd.isna(row["high_3"]) else False
        cond_vol = row["volume"] >= 0.8 * row["vol_sma20"] if not pd.isna(row["vol_sma20"]) and row["vol_sma20"] > 0 else False

        passed = sum([
            cond_close_ema20, cond_ema5_ema20, cond_ema20_rising,
            cond_rsi45, cond_rsi_rising, cond_breakout, cond_vol,
        ])
        # Check if previous day also had breakout (freshness)
        prev_breakout = prev["close"] > prev["high_3"] if not pd.isna(prev["high_3"]) else False
        prev2_breakout = prev2["close"] > prev2["high_3"] if not pd.isna(prev2["high_3"]) else False
        is_fresh = cond_breakout and (not prev_breakout or not prev2_breakout)

        score = clamp_score(passed * 14.0 + (10 if is_fresh else 0))

        payload = {
            "close": float(row["close"]),
            "ema5": None if pd.isna(row["ema5"]) else float(row["ema5"]),
            "ema20": None if pd.isna(row["ema20"]) else float(row["ema20"]),
            "rsi14": None if pd.isna(row["rsi14"]) else float(row["rsi14"]),
            "vol_ratio": None if pd.isna(row["vol_sma20"]) or row["vol_sma20"] == 0 else float(row["volume"] / row["vol_sma20"]),
            "breakout_high3": None if pd.isna(row["high_3"]) else float(row["high_3"]),
            "is_fresh": is_fresh,
            "conditions": {
                "close_above_ema20": cond_close_ema20,
                "ema5_above_ema20": cond_ema5_ema20,
                "ema20_rising": cond_ema20_rising,
                "rsi_above_45": cond_rsi45,
                "rsi_rising": cond_rsi_rising,
                "breakout_high3": cond_breakout,
                "volume_80pct": cond_vol,
            },
        }
        results.append(make_result(df.iloc[i]["date"].date(), "breakout", payload, score))
    return results
