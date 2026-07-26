"""Market regime detection from benchmark (IHSG / ^JKSE).

Regime: trending_up | trending_down | range | volatile
"""
import pandas as pd

from app.utils.indicators import atr, ema, sma


def detect_regime(benchmark_df: pd.DataFrame) -> dict:
    """Return latest regime + meta for the most recent date."""
    if benchmark_df is None or benchmark_df.empty or len(benchmark_df) < 60:
        return {"regime": "unknown", "meta": {}}
    df = benchmark_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["sma200"] = sma(df["close"], 200)
    df["atr"] = atr(df, 14)
    df["atr_pct"] = df["atr"] / df["close"]
    df["atr_pct_ma"] = df["atr_pct"].rolling(20).mean()

    last = df.iloc[-1]
    above_200 = (not pd.isna(last["sma200"])) and last["close"] > last["sma200"]
    bull_stack = last["ema20"] > last["ema50"]
    volatility = last["atr_pct"]
    avg_vol = last["atr_pct_ma"] if not pd.isna(last["atr_pct_ma"]) else volatility
    high_vol = volatility > 1.5 * avg_vol if avg_vol else False

    slope50 = (df["ema50"].iloc[-1] - df["ema50"].iloc[-6]) / df["ema50"].iloc[-6] if len(df) > 6 else 0
    if high_vol:
        regime = "volatile"
    elif bull_stack and above_200 and slope50 > 0:
        regime = "trending_up"
    elif (not bull_stack) and (not above_200) and slope50 < 0:
        regime = "trending_down"
    else:
        regime = "range"

    def _clean(val):
        if val is None or pd.isna(val):
            return None
        if isinstance(val, bool):
            return val
        return float(val)

    return {
        "regime": regime,
        "meta": {
            "date": last["date"].date().isoformat(),
            "close": _clean(last["close"]),
            "atr_pct": _clean(volatility),
            "above_200sma": _clean(above_200),
            "ema20_gt_ema50": bool(bull_stack),
            "slope50": _clean(slope50),
        },
    }


# Regime-based weight adjustments for scoring
REGIME_WEIGHT_ADJUST = {
    "trending_up": {"technical": 1.1, "bandarmology": 0.9, "foreign_flow": 1.0, "regime": 1.2},
    "trending_down": {"technical": 1.0, "bandarmology": 1.1, "foreign_flow": 1.1, "regime": 1.2},
    "range": {"technical": 0.8, "bandarmology": 1.3, "foreign_flow": 1.0, "regime": 1.0},
    "volatile": {"technical": 0.9, "bandarmology": 1.2, "foreign_flow": 1.1, "regime": 0.9},
}
