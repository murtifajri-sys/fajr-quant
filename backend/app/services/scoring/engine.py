"""Adaptive scoring engine.

Computes per-date composite scores from technical + bandarmology + foreign flow
+ regime, using adaptive per-ticker weights learned from history.
"""
from collections import defaultdict
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from app.models.score import Score, StockProfile
from app.services.market_regime import REGIME_WEIGHT_ADJUST
from app.services.scoring.phase import determine_phase
from app.services.scoring.weights import (
    BANDAR_LABELS,
    DEFAULT_WEIGHTS,
    TECHNICAL_METHODS,
)
from app.services.bandarmology._base import clamp_score


def _flatten_weights(weights: dict, regime: str) -> dict[str, float]:
    """Expand grouped weights into method->weight and apply regime adjust."""
    out = {}
    tech_total = sum(weights["technical"].values())
    bandar_total = sum(weights["bandarmology"].values())
    adj = REGIME_WEIGHT_ADJUST.get(regime, {})
    tech_factor = adj.get("technical", 1.0)
    bandar_factor = adj.get("bandarmology", 1.0)
    ff_factor = adj.get("foreign_flow", 1.0)
    reg_factor = adj.get("regime", 1.0)

    for m, w in weights["technical"].items():
        out[f"tech:{m}"] = (w / tech_total) * weights.get("_technical_share", 0.45) * tech_factor
    for m, w in weights["bandarmology"].items():
        out[f"bandar:{m}"] = (w / bandar_total) * weights.get("_bandar_share", 0.40) * bandar_factor
    out["foreign_flow"] = weights.get("_foreign_share", 0.10) * ff_factor
    out["regime"] = weights.get("_regime_share", 0.05) * reg_factor
    # normalize
    total = sum(out.values())
    if total == 0:
        return out
    return {k: v / total for k, v in out.items()}


def _build_weights(weights: dict) -> dict:
    """Convert flat per-method weights (from profile) back to grouped form."""
    return {
        "technical": {m: weights.get(f"tech:{m}", DEFAULT_WEIGHTS["technical"][m]) for m in TECHNICAL_METHODS},
        "bandarmology": {m: weights.get(f"bandar:{m}", DEFAULT_WEIGHTS["bandarmology"][m]) for m in BANDAR_LABELS},
        "_technical_share": 0.45,
        "_bandar_share": 0.40,
        "_foreign_share": 0.10,
        "_regime_share": 0.05,
    }


def compute_score_for_date(
    ticker: str,
    d: date,
    tech_scores: dict[str, float],
    bandar_scores: dict[str, float],
    bandar_detected: dict[str, bool],
    foreign_score: float | None,
    regime: str,
    weights: dict | None = None,
) -> dict:
    base = weights or DEFAULT_WEIGHTS
    flat = _flatten_weights(base, regime)
    sub_scores = {}
    for m in TECHNICAL_METHODS:
        sub_scores[f"tech:{m}"] = tech_scores.get(m, 50.0)
    for m in BANDAR_LABELS:
        sub_scores[f"bandar:{m}"] = bandar_scores.get(m, 50.0)
    sub_scores["foreign_flow"] = foreign_score if foreign_score is not None else 50.0
    # Regime alignment score: how well technical+bandar agree with regime
    if regime in ("trending_up", "trending_down"):
        regime_score = abs(tech_scores.get("trend_structure", 50) - 50) * 2
    elif regime == "range":
        regime_score = 100 - abs(tech_scores.get("trend_structure", 50) - 50) * 2
    else:
        regime_score = bandar_scores.get("consistency", 50)
    sub_scores["regime"] = clamp_score(regime_score)

    composite = sum(sub_scores.get(k, 0) * flat.get(k, 0) for k in sub_scores)
    composite = clamp_score(composite)

    tech_signals = {m: tech_scores.get(m) for m in TECHNICAL_METHODS}
    phase, confidence = determine_phase(composite, sub_scores, bandar_detected, tech_signals, regime)

    # Dominant factors: top 3 weights * score
    contrib = {k: sub_scores.get(k, 0) * flat.get(k, 0) for k in flat}
    dominant = dict(sorted(contrib.items(), key=lambda x: -x[1])[:3])

    return {
        "ticker": ticker,
        "date": d,
        "composite": composite,
        "sub_scores": sub_scores,
        "weights": flat,
        "phase": phase,
        "confidence": confidence,
        "dominant_factors": dominant,
    }


def save_score(db: Session, score: dict) -> None:
    existing = db.query(Score).filter_by(ticker=score["ticker"], date=score["date"]).first()
    if existing:
        for k, v in score.items():
            setattr(existing, k, v)
    else:
        db.add(Score(**score))
    db.commit()


def update_stock_profile(db: Session, ticker: str, weights: dict, dominant_method: str, notes: str | None = None) -> None:
    prof = db.get(StockProfile, ticker)
    if prof:
        prof.weights = weights
        prof.dominant_method = dominant_method
        prof.notes = notes
    else:
        prof = StockProfile(
            ticker=ticker,
            weights=weights,
            dominant_method=dominant_method,
            notes=notes,
        )
        db.add(prof)
    db.commit()


def learn_adaptive_weights(
    ticker: str,
    scores_history: list[dict],
    forward_returns: list[float],
    window: int = 60,
) -> dict:
    """Learn adaptive per-method weights from correlation with forward returns.

    scores_history: list of {date, sub_scores}
    forward_returns: aligned future N-day returns
    Returns flat weights dict keyed by 'tech:<m>' etc.
    """
    if len(scores_history) < 20 or len(forward_returns) < 20:
        return {}
    rows = []
    for s, r in zip(scores_history, forward_returns):
        row = dict(s.get("sub_scores", {}))
        row["ret"] = r
        rows.append(row)
    df = pd.DataFrame(rows)
    cols = [c for c in df.columns if c != "ret"]
    if not cols:
        return {}
    corrs = df[cols + ["ret"]].corr()["ret"].drop("ret")
    # positive correlation -> more weight; negative -> less
    strengths = corrs.abs()
    signs = (corrs > 0).astype(float)
    raw = strengths * (0.5 + 0.5 * signs)  # penalize negative corr
    raw = raw.fillna(0)
    if raw.sum() == 0:
        return {}
    weights = (raw / raw.sum()).to_dict()
    return weights
