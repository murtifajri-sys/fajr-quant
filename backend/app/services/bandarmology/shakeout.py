"""Shakeout: sharp drop then quick recovery, volume spike, retail distribution."""
import pandas as pd

from app.services.bandarmology._base import as_of_filter_df, clamp_score, make_result
from app.utils.indicators import atr, sma


def run(prices_df: pd.DataFrame, flow_df: pd.DataFrame | None = None, *, as_of=None) -> list[dict]:
    prices_df = as_of_filter_df(prices_df, as_of)
    if len(prices_df) < 30:
        return []
    df = prices_df.copy()
    df["atr"] = atr(df, 14)
    df["vol_ma20"] = sma(df["volume"], 20)

    results = []
    for i in range(5, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        drop = (row["low"] - prev["close"]) / (prev["close"] or 1e-9)
        recover = (row["close"] - row["low"]) / (row["low"] or 1e-9)
        vol_ma = row["vol_ma20"] if not pd.isna(row["vol_ma20"]) else 0
        spike = (row["volume"] / vol_ma) if vol_ma else 1.0
        atr_v = row["atr"] if not pd.isna(row["atr"]) else 0
        sharp_drop = drop < -0.02 and abs(drop) > 1.5 * (atr_v / prev["close"] if prev["close"] else 0)
        quick_recover = recover > abs(drop) * 0.7
        detected = sharp_drop and quick_recover and spike > 1.3
        # Better score: drop severity + recovery quality + volume confirmation
        base = 30
        if sharp_drop: base += 25
        if quick_recover: base += 20
        if spike > 1.0: base += 15 * min(spike / 2, 1)
        if spike > 1.5: base += 10
        score = clamp_score(base)
        payload = {
            "drop_pct": float(drop),
            "recover_pct": float(recover),
            "volume_spike": float(spike),
        }
        results.append(make_result(row["date"], "shakeout", detected, drop, score, payload))
    return results
