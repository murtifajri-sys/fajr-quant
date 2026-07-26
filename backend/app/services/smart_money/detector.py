"""Smart-money detector.

Combines bandarmology accumulation signals with foreign flow to identify
institutional/smart accumulation while filtering out small retail-driven moves.

The key retail filters are:
- Minimum absolute flow value (default Rp 1 billion per day).
- Minimum flow as % of average daily traded value (default 5 % ADV).
- Foreign flow is institutional by definition, but still filtered by size.
"""
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bandar import BandarmologySignal
from app.models.foreign_flow import ForeignFlow
from app.models.price import DailyPrice
from app.models.smart_money import SmartMoneySignal
from app.models.stock import Stock
from app.services.bandarmology._base import clamp_score


DEFAULT_BANDAR_WINDOW = 20
DEFAULT_FOREIGN_WINDOW = 5
DEFAULT_MIN_BANDAR_FLOW_VALUE = 1.0e9
DEFAULT_MIN_FOREIGN_NET_VALUE = 1.0e9
DEFAULT_MIN_FLOW_PCT_ADV = 0.05
DEFAULT_SCORE_THRESHOLD = 65.0
DEFAULT_BANDAR_WEIGHT = 0.6
DEFAULT_FOREIGN_WEIGHT = 0.4


def _avg_daily_value(db: Session, ticker: str, days: int = 20) -> float | None:
    """Average daily traded value over recent N days."""
    end = date.today()
    start = end - timedelta(days=days + 7)
    rows = db.execute(
        select(DailyPrice)
        .where(
            DailyPrice.ticker == ticker,
            DailyPrice.date >= start,
            DailyPrice.date <= end,
        )
        .order_by(DailyPrice.date.desc())
        .limit(days)
    ).scalars().all()
    if not rows:
        return None
    values = [r.close * r.volume for r in rows if r.close is not None and r.volume is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _market_cap(db: Session, ticker: str) -> float | None:
    stock = db.execute(select(Stock).where(Stock.ticker == ticker)).scalar_one_or_none()
    if not stock or not stock.shares_outstanding:
        return None
    price = db.execute(
        select(DailyPrice)
        .where(DailyPrice.ticker == ticker)
        .order_by(DailyPrice.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not price:
        return None
    return stock.shares_outstanding * price.close


def _is_significant(value: float | None, adv: float | None, min_abs: float, min_pct_adv: float) -> bool:
    """Return True if flow value is large enough to be institutional."""
    if value is None or value <= 0:
        return False
    if value >= min_abs:
        return True
    if adv and adv > 0 and (value / adv) >= min_pct_adv:
        return True
    return False


def _bandar_label_score(row: BandarmologySignal, adv: float | None) -> tuple[float | None, str | None]:
    """Return (score, reason) for a single bandarmology signal if it is significant."""
    if not row.detected:
        return None, None
    p = row.payload or {}
    label = row.label
    value = None
    reason_key = None

    if label == "absorption":
        value = p.get("big_broker_net")
        reason_key = f"absorption net {value:,.0f}" if value else None
    elif label == "bandar_positioning":
        value = p.get("net")
        reason_key = f"bandar positioning net {value:,.0f}" if value else None
    elif label == "consistency":
        value = p.get("net_total")
        reason_key = f"consistency net {value:,.0f}" if value else None
    elif label == "hidden_accumulation":
        value = p.get("net_flow")
        reason_key = f"hidden accumulation net {value:,.0f}" if value else None
    elif label == "silent_accumulation":
        value = p.get("net_value")
        reason_key = f"silent accumulation net {value:,.0f}" if value else None
    else:
        return None, None

    if value is None:
        return None, None
    if not _is_significant(value, adv, DEFAULT_MIN_BANDAR_FLOW_VALUE, DEFAULT_MIN_FLOW_PCT_ADV):
        return None, None

    return clamp_score(row.score or 0.0), reason_key


def _foreign_significant(row: ForeignFlow, adv: float | None) -> bool:
    if row.net_foreign is None or row.net_foreign <= 0:
        return False
    if row.net_foreign >= DEFAULT_MIN_FOREIGN_NET_VALUE:
        return True
    if adv and adv > 0 and row.net_foreign_pct and (row.net_foreign_pct / 100) >= DEFAULT_MIN_FLOW_PCT_ADV:
        return True
    return False


def detect_smart_money(
    db: Session,
    ticker: str,
    as_of: date | None = None,
    *,
    bandar_window: int = DEFAULT_BANDAR_WINDOW,
    foreign_window: int = DEFAULT_FOREIGN_WINDOW,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    bandar_weight: float = DEFAULT_BANDAR_WEIGHT,
    foreign_weight: float = DEFAULT_FOREIGN_WEIGHT,
) -> dict[str, Any]:
    """Compute and persist smart-money signal for a ticker.

    Returns a dict describing the signal (used by tests and the pipeline).
    """
    d = as_of or date.today()
    ticker = ticker.upper()

    start_bandar = d - timedelta(days=bandar_window)
    start_foreign = d - timedelta(days=foreign_window)

    adv = _avg_daily_value(db, ticker)

    # Bandar accumulation signals
    bandar_rows = db.execute(
        select(BandarmologySignal).where(
            BandarmologySignal.ticker == ticker,
            BandarmologySignal.date >= start_bandar,
            BandarmologySignal.date <= d,
        )
    ).scalars().all()

    bandar_daily: dict[date, list[float]] = {}
    bandar_reasons: list[str] = []
    for row in bandar_rows:
        score, reason = _bandar_label_score(row, adv)
        if score is None:
            continue
        bandar_daily.setdefault(row.date, []).append(score)
        if reason:
            bandar_reasons.append(f"{row.date}: {row.label} ({reason})")

    if bandar_daily:
        bandar_score = clamp_score(
            sum(sum(v) / len(v) for v in bandar_daily.values()) / len(bandar_daily)
        )
    else:
        bandar_score = 0.0

    # Foreign flow
    foreign_rows = db.execute(
        select(ForeignFlow).where(
            ForeignFlow.ticker == ticker,
            ForeignFlow.date >= start_foreign,
            ForeignFlow.date <= d,
        )
    ).scalars().all()

    foreign_scores: list[float] = []
    foreign_reasons: list[str] = []
    for row in foreign_rows:
        if not _foreign_significant(row, adv):
            continue
        fs = clamp_score(row.score if row.score is not None else 50.0)
        foreign_scores.append(fs)
        foreign_reasons.append(
            f"{row.date}: foreign net {row.net_foreign:,.0f} ({row.net_foreign_pct or 0:.2f}%)"
        )

    foreign_score = clamp_score(sum(foreign_scores) / len(foreign_scores)) if foreign_scores else 0.0

    composite = clamp_score(bandar_weight * bandar_score + foreign_weight * foreign_score)
    detected = composite >= score_threshold and (bandar_score > 0 or foreign_score > 0)

    reasons: dict[str, Any] = {
        "bandar": bandar_reasons[:10],
        "foreign": foreign_reasons[:10],
        "adv": adv,
        "threshold": score_threshold,
    }

    existing = db.execute(
        select(SmartMoneySignal).where(SmartMoneySignal.ticker == ticker, SmartMoneySignal.date == d)
    ).scalar_one_or_none()
    signal = SmartMoneySignal(
        ticker=ticker,
        date=d,
        detected=detected,
        score=composite,
        bandar_score=bandar_score,
        foreign_score=foreign_score,
        bandar_lookback=bandar_window,
        foreign_lookback=foreign_window,
        reasons=reasons,
    )
    if existing:
        existing.detected = detected
        existing.score = composite
        existing.bandar_score = bandar_score
        existing.foreign_score = foreign_score
        existing.bandar_lookback = bandar_window
        existing.foreign_lookback = foreign_window
        existing.reasons = reasons
    else:
        db.add(signal)
    db.commit()

    return {
        "ticker": ticker,
        "date": d.isoformat(),
        "detected": detected,
        "score": composite,
        "bandar_score": bandar_score,
        "foreign_score": foreign_score,
        "reasons": reasons,
    }
