"""Liquidity and volatility filters for AI recommendations."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import log
from app.models.price import DailyPrice


def get_recommendation_metrics(
    db: Session,
    ticker: str,
    lookback_days: int | None = None,
) -> dict | None:
    """Return average daily value and wick ratio for the last N days.

    Metrics:
    - avg_daily_value: average daily transaction value (close * volume) in IDR.
    - avg_wick_pct: average total wick length as percentage of close price.
      Total wick = upper_wick + lower_wick, where upper_wick = high - max(open, close)
      and lower_wick = min(open, close) - low.
    """
    lookback = lookback_days or settings.RECOMMENDATION_LOOKBACK_DAYS
    start = date.today() - timedelta(days=lookback + 5)  # buffer for weekends/holidays
    rows = db.execute(
        select(DailyPrice)
        .where(
            DailyPrice.ticker == ticker,
            DailyPrice.date >= start,
            DailyPrice.open.isnot(None),
            DailyPrice.high.isnot(None),
            DailyPrice.low.isnot(None),
            DailyPrice.close.isnot(None),
            DailyPrice.volume.isnot(None),
        )
        .order_by(DailyPrice.date.desc())
        .limit(lookback)
    ).scalars().all()

    if len(rows) < max(lookback // 2, 5):
        return None

    values = []
    wick_pcts = []
    for r in rows:
        if r.close <= 0 or r.volume <= 0:
            continue
        values.append(r.close * r.volume)
        body_high = max(r.open, r.close)
        body_low = min(r.open, r.close)
        upper_wick = r.high - body_high
        lower_wick = body_low - r.low
        total_wick = max(0, upper_wick) + max(0, lower_wick)
        wick_pcts.append(total_wick / r.close)

    if not values:
        return None

    return {
        "avg_daily_value": sum(values) / len(values),
        "avg_wick_pct": sum(wick_pcts) / len(wick_pcts),
    }


def is_recommendation_eligible(
    db: Session,
    ticker: str,
    min_avg_daily_value: float | None = None,
    max_avg_wick_pct: float | None = None,
    lookback_days: int | None = None,
) -> tuple[bool, dict | None]:
    """Return (eligible, metrics) for a ticker.

    A ticker is eligible if it has enough liquidity (average daily value)
    and is not too wicky/volatile (average wick percentage below threshold).
    """
    min_adv = min_avg_daily_value if min_avg_daily_value is not None else settings.RECOMMENDATION_MIN_AVG_DAILY_VALUE
    max_wick = max_avg_wick_pct if max_avg_wick_pct is not None else settings.RECOMMENDATION_MAX_AVG_WICK_PCT

    metrics = get_recommendation_metrics(db, ticker, lookback_days=lookback_days)
    if not metrics:
        log.info("recommendation_filter_skip", ticker=ticker, reason="insufficient_price_data")
        return False, None

    avg_value = metrics["avg_daily_value"]
    avg_wick = metrics["avg_wick_pct"]
    eligible = avg_value >= min_adv and avg_wick <= max_wick

    log.info(
        "recommendation_filter_check",
        ticker=ticker,
        eligible=eligible,
        avg_daily_value=avg_value,
        avg_wick_pct=avg_wick,
        min_avg_daily_value=min_adv,
        max_avg_wick_pct=max_wick,
    )
    return eligible, metrics
