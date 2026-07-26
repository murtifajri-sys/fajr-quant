"""Shared helpers for technical modules.

A technical module `run(df, *, benchmark_df=None, as_of=None)` returns a list of
dicts: [{date, name, payload, score}] for each date where the method is active.

We keep helpers here so each module only implements its domain logic.
"""
from datetime import date, timedelta
from typing import Any

import pandas as pd


def clamp_score(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(x)))


def as_of_filter(df: pd.DataFrame, as_of: date | None, lookback_days: int | None = None) -> pd.DataFrame:
    if as_of is not None:
        df = df[df["date"].dt.date <= as_of]
    if lookback_days is not None and not df.empty:
        start = df["date"].iloc[-1].date() - timedelta(days=lookback_days)
        df = df[df["date"].dt.date >= start]
    return df


def make_result(d, name: str, payload: dict, score: float) -> dict[str, Any]:
    return {
        "date": d if isinstance(d, date) else pd.Timestamp(d).date(),
        "name": name,
        "payload": payload,
        "score": score,
    }
