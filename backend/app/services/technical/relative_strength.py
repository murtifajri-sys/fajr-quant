"""Relative strength vs benchmark (IHSG / ^JKSE)."""
import pandas as pd

from app.services.technical._base import as_of_filter, clamp_score, make_result


def run(df: pd.DataFrame, *, benchmark_df: pd.DataFrame | None = None, as_of=None) -> list[dict]:
    df = as_of_filter(df, as_of)
    if benchmark_df is None or benchmark_df.empty or len(df) < 30:
        return []
    bm = benchmark_df.copy()
    bm["date"] = pd.to_datetime(bm["date"])
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    merged = pd.merge(df[["date", "close"]], bm[["date", "close"]], on="date", suffixes=("_s", "_b"))
    merged = merged.sort_values("date").reset_index(drop=True)
    merged["rs"] = merged["close_s"] / merged["close_b"]
    merged["rs_ma20"] = merged["rs"].rolling(20).mean()
    merged["rs_mom"] = merged["rs"].pct_change(20)

    results = []
    for i in range(20, len(merged)):
        row = merged.iloc[i]
        rs = row["rs"]
        rs_ma = row["rs_ma20"]
        mom = row["rs_mom"] if not pd.isna(row["rs_mom"]) else 0
        outperform = (not pd.isna(rs_ma)) and rs > rs_ma
        score = clamp_score(50 + 25 * (1 if outperform else -1) + 25 * (1 if mom > 0 else -1))
        payload = {
            "rs": float(rs),
            "rs_ma20": None if pd.isna(rs_ma) else float(rs_ma),
            "rs_mom_20d": float(mom),
            "outperforming": bool(outperform),
        }
        results.append(make_result(row["date"].date(), "relative_strength", payload, score))
    return results
