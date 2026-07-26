"""Harmonic pattern detection (Gartley/Bat/Butterfly/Crab/Shark) using Fibonacci.

Simplified pivot-based detection: find last 4 pivots (X,A,B,C) and test whether
the current candidate D satisfies the Fibonacci ratios for any known pattern.
"""
import pandas as pd

from app.services.technical._base import as_of_filter, clamp_score, make_result
from app.utils.indicators import swing_points

# Tolerance for ratio matching
TOL = 0.08

# Pattern definitions: {name: {xab, abc, bcd, xad}}
PATTERNS = {
    "Gartley":    {"xab": 0.618, "abc": 0.382, "bcd": 1.13, "xad": 0.786},
    "Bat":        {"xab": 0.382, "abc": 0.382, "bcd": 1.618, "xad": 0.886},
    "Butterfly":  {"xab": 0.786, "abc": 0.382, "bcd": 1.618, "xad": 1.272},
    "Crab":       {"xab": 0.382, "abc": 0.382, "bcd": 2.618, "xad": 1.618},
    "Shark":      {"xab": 0.382, "abc": 1.13,  "bcd": 1.618, "xad": 0.886},
}


def _ratio(a: float, b: float) -> float | None:
    if b == 0:
        return None
    return abs(a / b)


def _match(actual: float | None, target: float) -> bool:
    if actual is None:
        return False
    return abs(actual - target) <= TOL


def detect_pattern(X, A, B, C, D) -> tuple[str | None, dict]:
    xab = _ratio(B - A, X - A)
    abc = _ratio(C - B, A - B)
    bcd = _ratio(D - C, B - C)
    xad = _ratio(D - A, X - A)
    for name, ratios in PATTERNS.items():
        if (
            _match(xab, ratios["xab"])
            and _match(abc, ratios["abc"])
            and _match(bcd, ratios["bcd"])
            and _match(xad, ratios["xad"])
        ):
            return name, {"xab": xab, "abc": abc, "bcd": bcd, "xad": xad}
    return None, {"xab": xab, "abc": abc, "bcd": bcd, "xad": xad}


def run(df: pd.DataFrame, *, benchmark_df=None, as_of=None) -> list[dict]:
    df = as_of_filter(df, as_of)
    if len(df) < 60:
        return []
    swing_hi_idx, swing_lo_idx = swing_points(df["high"], df["low"], window=3)
    pivots = []
    for idx in swing_hi_idx:
        pivots.append((idx, "H", df.loc[idx, "high"]))
    for idx in swing_lo_idx:
        pivots.append((idx, "L", df.loc[idx, "low"]))
    pivots.sort(key=lambda p: p[0])

    results = []
    if len(pivots) < 5:
        return results

    # Check last 5 pivots forming X,A,B,C,D
    last = pivots[-5:]
    X = last[0][2]; A = last[1][2]; B = last[2][2]; C = last[3][2]; D = last[4][2]
    name, ratios = detect_pattern(X, A, B, C, D)
    d_idx = last[4][0]
    d_date = df.loc[d_idx, "date"]
    if name:
        # Bullish if last pivot is low (potential reversal up)
        bullish = last[4][1] == "L"
        score = clamp_score(80 if bullish else 70)
    else:
        score = clamp_score(30)
    payload = {
        "pattern": name,
        "pivots": [
            {"date": str(df.loc[p[0], "date"].date()), "type": p[1], "price": float(p[2])}
            for p in last
        ],
        "ratios": {k: (None if v is None else float(v)) for k, v in ratios.items()},
    }
    results.append(make_result(d_date, "harmonic", payload, score))
    return results
