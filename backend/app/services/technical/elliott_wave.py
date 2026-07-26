"""Elliott Wave heuristic detection (impulse 1-5, corrective A-B-C).

This is a simplified rule-based approach using swing pivots and Fibonacci
guidelines. It is not a full wave-counting engine; it labels the most recent
swing sequence and assigns a confidence.
"""
import pandas as pd

from app.services.technical._base import as_of_filter, clamp_score, make_result
from app.utils.indicators import swing_points


def run(df: pd.DataFrame, *, benchmark_df=None, as_of=None) -> list[dict]:
    df = as_of_filter(df, as_of)
    if len(df) < 80:
        return []
    swing_hi_idx, swing_lo_idx = swing_points(df["high"], df["low"], window=4)
    pivots = []
    for idx in swing_hi_idx:
        pivots.append((idx, "H", df.loc[idx, "high"]))
    for idx in swing_lo_idx:
        pivots.append((idx, "L", df.loc[idx, "low"]))
    pivots.sort(key=lambda p: p[0])
    if len(pivots) < 5:
        return []

    # Try to label the last 5 pivots as impulse (alternating) if trend up
    last5 = pivots[-5:]
    types = [p[1] for p in last5]
    is_impulse_up = types == ["L", "H", "L", "H", "L"] or types == ["L", "H", "L", "H", "H"]
    is_impulse_down = types == ["H", "L", "H", "L", "H"] or types == ["H", "L", "H", "L", "L"]

    d_idx = last5[-1][0]
    d_date = df.loc[d_idx, "date"]
    if is_impulse_up:
        label = "impulse_up"
        # wave 3 longest heuristic: wave3 = pivots[3]-pivots[2] should be largest
        legs = [abs(last5[k + 1][2] - last5[k][2]) for k in range(4)]
        wave3_longest = legs[2] == max(legs)
        score = clamp_score(70 + 15 * (1 if wave3_longest else 0))
    elif is_impulse_down:
        label = "impulse_down"
        score = clamp_score(30)
    else:
        label = "corrective"
        score = clamp_score(50)

    payload = {
        "label": label,
        "pivots": [
            {"date": str(df.loc[p[0], "date"].date()), "type": p[1], "price": float(p[2])}
            for p in last5
        ],
    }
    return [make_result(d_date, "elliott_wave", payload, score)]
