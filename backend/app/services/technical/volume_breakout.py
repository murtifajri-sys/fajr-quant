"""Volume + breakout: OBV, ADL, volume spike, breakout vs ATR."""
import pandas as pd

from app.services.technical._base import as_of_filter, clamp_score, make_result
from app.utils.indicators import adl, atr, obv, sma


def run(df: pd.DataFrame, *, benchmark_df=None, as_of=None) -> list[dict]:
    df = as_of_filter(df, as_of)
    if len(df) < 30:
        return []
    df = df.copy()
    df["obv"] = obv(df["close"], df["volume"])
    df["adl"] = adl(df["high"], df["low"], df["close"], df["volume"])
    df["vol_ma20"] = sma(df["volume"], 20)
    df["atr"] = atr(df, 14)

    results = []
    for i in range(20, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        vol_ma = row["vol_ma20"] if not pd.isna(row["vol_ma20"]) else 0
        spike = (row["volume"] / vol_ma) if vol_ma else 1.0
        obv_rising = row["obv"] > prev["obv"]
        adl_rising = row["adl"] > prev["adl"]
        move = (row["close"] - prev["close"]) / (prev["close"] or 1e-9)
        breakout = abs(row["close"] - prev["close"]) > (1.5 * (row["atr"] if not pd.isna(row["atr"]) else 0))
        bullish_break = breakout and move > 0
        score = clamp_score(
            35
            + 20 * (1 if obv_rising else 0)
            + 15 * (1 if adl_rising else 0)
            + 15 * min(spike, 3) / 3
            + 15 * (1 if bullish_break else (-10 if breakout and move < 0 else 0))
        )
        payload = {
            "volume": float(row["volume"]),
            "vol_ma20": None if pd.isna(vol_ma) else float(vol_ma),
            "spike_ratio": float(spike),
            "obv_rising": bool(obv_rising),
            "adl_rising": bool(adl_rising),
            "breakout": bool(breakout),
            "bullish_break": bool(bullish_break),
            "move_pct": float(move),
        }
        results.append(make_result(df.iloc[i]["date"].date(), "volume_breakout", payload, score))
    return results
