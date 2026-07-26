"""Absorption: large net buy by big brokers on a down day (bid absorbs supply)."""
import pandas as pd

from app.services.bandarmology._base import as_of_filter_df, clamp_score, make_result


def run(prices_df: pd.DataFrame, flow_df: pd.DataFrame | None = None, *, as_of=None) -> list[dict]:
    prices_df = as_of_filter_df(prices_df, as_of)
    if flow_df is None or flow_df.empty or len(prices_df) < 10:
        return []
    flow = flow_df.copy()
    flow["date"] = pd.to_datetime(flow["date"])
    prices = prices_df.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices["chg"] = prices["close"].pct_change()

    results = []
    for i in range(1, len(prices)):
        d = prices.iloc[i]["date"]
        day_flow = flow[flow["date"] == d]
        if day_flow.empty:
            continue
        # Top brokers net buy on a down day
        chg = prices.iloc[i]["chg"]
        broker_net = day_flow.groupby("party")["net_value"].sum()
        top_buyers = broker_net[broker_net > 0].sort_values(ascending=False)
        big_net = float(top_buyers.sum()) if not top_buyers.empty else 0.0
        down_day = chg < 0
        detected = down_day and big_net > 0 and len(top_buyers) >= 1
        score = clamp_score(
            30 + 40 * (1 if down_day else 0) + 30 * (1 if big_net > 1e9 else (big_net / 1e9 if big_net > 0 else 0))
        )
        if detected:
            score = clamp_score(score + 10)
        payload = {
            "day_change_pct": float(chg),
            "big_broker_net": big_net,
            "n_buyers": int(len(top_buyers)),
            "top_buyer": str(top_buyers.index[0]) if not top_buyers.empty else None,
        }
        results.append(make_result(d, "absorption", detected, big_net, score, payload))
    return results
