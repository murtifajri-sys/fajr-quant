"""High-level AI recommendation orchestration."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import log
from app.core.config import settings
from app.models.price import DailyPrice
from app.models.recommendation import Recommendation
from app.models.score import Score, StockProfile
from app.services.broker_accumulation import summarize_broker_window
from app.services.ai.deepseek import get_provider
from app.services.ai.prompt import SYSTEM_PROMPT, build_user_prompt


def generate_recommendation(db: Session, ticker: str, score: Score | None = None) -> Recommendation | None:
    if not settings.AI_API_KEY:
        log.info("ai_recommendation_skipped", reason="AI_API_KEY is not configured")
        return None
    if score is None:
        score = db.execute(
            select(Score).where(Score.ticker == ticker).order_by(Score.date.desc()).limit(1)
        ).scalar_one_or_none()
    if not score:
        log.info("no_score_for_recommendation", ticker=ticker)
        return None

    profile = db.get(StockProfile, ticker)
    profile_dict = None
    if profile:
        profile_dict = {
            "weights": profile.weights,
            "dominant_method": profile.dominant_method,
            "notes": profile.notes,
        }

    latest_price = db.execute(
        select(DailyPrice)
        .where(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    close = latest_price.close if latest_price else None

    regime = (score.dominant_factors or {}).get("regime", "unknown")
    broker_summary = summarize_broker_window(
        db,
        ticker,
        30,
        as_of_date=score.date,
    )
    broker_prompt = None
    if broker_summary:
        broker_prompt = {
            "period": broker_summary.get("period"),
            "status": broker_summary.get("status"),
            "top_broker": broker_summary.get("top_broker"),
            "broker_conviction_score": broker_summary.get("broker_conviction_score"),
            "broker_conviction_label": broker_summary.get("broker_conviction_label"),
            "flow_quality_score": broker_summary.get("flow_quality_score"),
            "flow_quality_label": broker_summary.get("flow_quality_label"),
            "cluster_ratio": broker_summary.get("cluster_ratio"),
            "retention": broker_summary.get("retention"),
            "recency_sessions": broker_summary.get("recency_sessions"),
            "high_freq_low_value": broker_summary.get("high_freq_low_value"),
            "low_freq_high_value": broker_summary.get("low_freq_high_value"),
            "recent_5_session_net": broker_summary.get("recent_5_session_net"),
            "pct_market_cap": broker_summary.get("pct_market_cap"),
            "days_of_adv": broker_summary.get("days_of_adv"),
            "closest_to_smart_score": broker_summary.get("closest_to_smart_score"),
            "closest_to_smart_rank": broker_summary.get("closest_to_smart_rank"),
        }
    user_prompt = build_user_prompt(
        {
            "ticker": score.ticker,
            "date": score.date,
            "composite": score.composite,
            "phase": score.phase,
            "confidence": score.confidence,
            "sub_scores": score.sub_scores,
            "dominant_factors": score.dominant_factors,
        },
        profile_dict,
        close,
        regime,
        broker_prompt,
    )

    provider = get_provider()
    try:
        result = provider.complete(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        log.error("ai_provider_error", error=str(e))
        return None

    used_provider = getattr(provider, "active_provider", provider) or provider

    content = result["content"]
    rec = Recommendation(
        ticker=ticker,
        date=score.date,
        action=str(content.get("action", "WAIT")).upper(),
        entry=content.get("entry"),
        stop=content.get("stop"),
        target=content.get("target"),
        rationale=content.get("rationale"),
        dominant_factors=content.get("dominant_factors", score.dominant_factors),
        risks=content.get("risks", {}),
        provider=used_provider.name,
        raw_response=result["raw"],
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec
