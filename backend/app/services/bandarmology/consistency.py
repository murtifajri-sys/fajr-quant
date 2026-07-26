"""Consistency: how consistent is accumulation over N days (rolling)."""
import pandas as pd

from app.services.bandarmology._base import as_of_filter_df, clamp_score, make_result


def run(prices_df: pd.DataFrame, flow_df: pd.DataFrame | None = None, *, as_of=None, window: int = 20) -> list[dict]:
    prices_df = as_of_filter_df(prices_df, as_of)
    if flow_df is None or flow_df.empty or len(prices_df) < window:
        return []
    flow = flow_df.copy()
    flow["date"] = pd.to_datetime(flow["date"])
    daily = flow.groupby("date")["net_value"].sum().reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    prices = prices_df.copy()
    prices["date"] = pd.to_datetime(prices["date"])

    results = []
    for i in range(window, len(prices)):
        d = prices.iloc[i]["date"]
        start = prices.iloc[i - window]["date"]
        wd = daily[(daily["date"] > start) & (daily["date"] <= d)]
        if wd.empty:
            continue
        pos_days = int((wd["net_value"] > 0).sum())
        ratio = pos_days / len(wd)
        score = clamp_score(50 + 100 * (ratio - 0.5))  # 0.5 -> 50, 1.0 -> 100, 0.0 -> 0
        detected = score >= 60
        payload = {
            "window_days": window,
            "positive_days": pos_days,
            "total_days": int(len(wd)),
            "consistency_ratio": float(ratio),
            "net_total": float(wd["net_value"].sum()),
        }
        results.append(make_result(d, "consistency", detected, ratio, score, payload))
    return results
