"""Silent accumulation: small consistent net buying by specific brokers, price drifts up.

Uses flow_df grouped by party. Detects brokers with consistent positive net flow
over a rolling window while price is stable/rising.
"""
from datetime import date, timedelta

import pandas as pd

from app.services.bandarmology._base import as_of_filter_df, clamp_score, make_result


def run(prices_df: pd.DataFrame, flow_df: pd.DataFrame | None = None, *, as_of=None, window: int = 15) -> list[dict]:
    prices_df = as_of_filter_df(prices_df, as_of)
    if flow_df is None or flow_df.empty or len(prices_df) < window + 5:
        return []
    flow = flow_df.copy()
    flow["date"] = pd.to_datetime(flow["date"])
    prices = prices_df.copy()
    prices["date"] = pd.to_datetime(prices["date"])

    results = []
    for i in range(window, len(prices)):
        d = prices.iloc[i]["date"]
        start = prices.iloc[i - window]["date"]
        window_flow = flow[(flow["date"] > start) & (flow["date"] <= d)]
        if window_flow.empty:
            continue
        broker_net = window_flow.groupby("party")["net_value"].sum()
        consistent_brokers = broker_net[(broker_net > 0) & (broker_net.index != "")]
        if consistent_brokers.empty:
            continue
        # Consistency: fraction of days each top broker had positive net
        top_broker = consistent_brokers.idxmax()
        broker_daily = window_flow[window_flow["party"] == top_broker]
        consistent_days = (broker_daily["net_value"] > 0).sum()
        consistency_ratio = consistent_days / window
        price_drift = (prices.iloc[i]["close"] - prices.iloc[i - window]["close"]) / prices.iloc[i - window]["close"]
        score = clamp_score(40 + 40 * consistency_ratio + 20 * (1 if price_drift > 0 else 0))
        detected = score >= 60
        payload = {
            "top_broker": str(top_broker),
            "net_value": float(consistent_brokers.max()),
            "consistency_ratio": float(consistency_ratio),
            "price_drift": float(price_drift),
        }
        results.append(make_result(d, "silent_accumulation", detected, consistency_ratio, score, payload))
    return results
