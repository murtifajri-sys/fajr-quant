"""Shared helpers for bandarmology modules.

Each module: run(prices_df, flow_df, *, as_of=None) -> list[{date,label,detected,value,score,payload}]

prices_df columns: date, open, high, low, close, volume
flow_df columns: date, party (broker_id or investor_type), buy_value, sell_value, net_value
"""
from datetime import date, timedelta
from typing import Any

import pandas as pd


def clamp_score(x: float) -> float:
    return max(0.0, min(100.0, float(x)))


def as_of_filter_df(df: pd.DataFrame, as_of: date | None) -> pd.DataFrame:
    if as_of is not None and not df.empty and "date" in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df = df.copy()
            df["date"] = pd.to_datetime(df["date"])
        df = df[df["date"].dt.date <= as_of]
    return df


def make_result(d, label: str, detected: bool, value: float | None, score: float, payload: dict) -> dict[str, Any]:
    if hasattr(d, "date"):
        d = d.date()
    elif not isinstance(d, date):
        d = pd.Timestamp(d).date()
    return {
        "date": d,
        "label": label,
        "detected": bool(detected),
        "value": None if value is None else float(value),
        "score": float(score),
        "payload": payload,
    }


def aggregate_flow_by_date(flow_df: pd.DataFrame) -> pd.DataFrame:
    """Sum buy/sell/net across parties per date."""
    if flow_df is None or flow_df.empty:
        return pd.DataFrame(columns=["date", "buy_value", "sell_value", "net_value"])
    g = flow_df.groupby("date").agg(
        buy_value=("buy_value", "sum"),
        sell_value=("sell_value", "sum"),
        net_value=("net_value", "sum"),
    ).reset_index()
    return g
