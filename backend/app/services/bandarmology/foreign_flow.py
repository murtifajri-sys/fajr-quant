"""Foreign flow scoring.

Computes a 0-100 score from net foreign flow relative to average |flow|.
"""
import pandas as pd


def score_foreign_flow(foreign_flows: list[dict], window: int = 20) -> list[dict]:
    if not foreign_flows:
        return []
    df = pd.DataFrame(foreign_flows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["abs_net"] = df["net_foreign"].abs()
    df["avg_abs"] = df["abs_net"].rolling(window).mean()

    out = []
    for i in range(len(df)):
        row = df.iloc[i]
        avg = row["avg_abs"] if not pd.isna(row["avg_abs"]) else 0
        if avg == 0:
            score = 50.0
        else:
            score = 50.0 + 50.0 * (row["net_foreign"] / (2 * avg))
            score = max(0.0, min(100.0, float(score)))
        out.append(
            {
                "date": row["date"].date(),
                "net_foreign": None if pd.isna(row["net_foreign"]) else float(row["net_foreign"]),
                "score": score,
            }
        )
    return out
