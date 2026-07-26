"""Bandar positioning: track net position of top brokers across rolling window.

Output: are top brokers accumulating (long build-up) or distributing?
"""
from datetime import timedelta

import pandas as pd

from app.services.bandarmology._base import as_of_filter_df, clamp_score, make_result


def run(prices_df: pd.DataFrame, flow_df: pd.DataFrame | None = None, *, as_of=None, window: int = 20) -> list[dict]:
    prices_df = as_of_filter_df(prices_df, as_of)
    if flow_df is None or flow_df.empty or len(prices_df) < window:
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
        broker_net = window_flow.groupby("party")["net_value"].sum().sort_values(ascending=False)
        broker_net = broker_net[broker_net.index != ""]
        if broker_net.empty:
            continue
        top5 = broker_net.head(5)
        accumulation = float(top5[top5 > 0].sum())
        distribution = float(abs(top5[top5 < 0].sum()))
        net = accumulation - distribution
        detected = net > 0 and (accumulation > distribution * 1.3)
        score = clamp_score(50 + 40 * (net / max(accumulation + distribution, 1)))
        payload = {
            "window_days": window,
            "accumulation": accumulation,
            "distribution": distribution,
            "net": net,
            "top_brokers": [
                {"party": str(idx), "net": float(v)} for idx, v in top5.items()
            ],
        }
        results.append(make_result(d, "bandar_positioning", detected, net, score, payload))
    return results
