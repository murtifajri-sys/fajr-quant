"""Hidden accumulation: high volume but narrow range, price stable.

Signal: volume > 1.5x avg AND daily range < 0.8 ATR AND price change small.
"""
import pandas as pd

from app.services.bandarmology._base import (
    aggregate_flow_by_date,
    as_of_filter_df,
    clamp_score,
    make_result,
)
from app.utils.indicators import atr, sma


def run(prices_df: pd.DataFrame, flow_df: pd.DataFrame | None = None, *, as_of=None) -> list[dict]:
    prices_df = as_of_filter_df(prices_df, as_of)
    if len(prices_df) < 30:
        return []
    df = prices_df.copy()
    df["range"] = df["high"] - df["low"]
    df["atr"] = atr(df, 14)
    df["vol_ma20"] = sma(df["volume"], 20)
    df["chg"] = df["close"].pct_change().abs()

    results = []
    for i in range(20, len(df)):
        row = df.iloc[i]
        vol_ma = row["vol_ma20"] if not pd.isna(row["vol_ma20"]) else 0
        spike = (row["volume"] / vol_ma) if vol_ma else 1.0
        atr_v = row["atr"] if not pd.isna(row["atr"]) else 0
        narrow = atr_v > 0 and row["range"] < 0.8 * atr_v
        flat = row["chg"] < 0.01
        net = None
        if flow_df is not None and not flow_df.empty:
            agg = aggregate_flow_by_date(flow_df)
            d = row["date"].date() if hasattr(row["date"], "date") else row["date"]
            matches = agg[agg["date"].dt.date == d]
            if not matches.empty:
                net = float(matches.iloc[0]["net_value"])
        score = clamp_score(
            40 + 30 * min(spike / 3, 1) + 20 * (1 if narrow else 0) + 10 * (1 if flat else 0)
        )
        detected = score >= 60
        if detected:
            score = clamp_score(score + 5)
        payload = {"volume_spike": float(spike), "narrow_range": bool(narrow), "flat": bool(flat), "net_flow": net}
        results.append(make_result(row["date"], "hidden_accumulation", detected, spike, score, payload))
    return results
