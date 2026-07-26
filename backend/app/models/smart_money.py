from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base
from app.models._mixins import TimestampMixin


class SmartMoneySignal(TimestampMixin, Base):
    """Combined smart-money signal from bandarmology + foreign flow.

    Score is a 0-100 composite. Detected is True when the composite score
    crosses the configured threshold and the underlying flows are large enough
    to rule out small retail accumulation.
    """
    __tablename__ = "smart_money_signals"

    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.ticker"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float | None] = mapped_column(Float)
    bandar_score: Mapped[float | None] = mapped_column(Float)
    foreign_score: Mapped[float | None] = mapped_column(Float)
    bandar_lookback: Mapped[int | None] = mapped_column(Integer)
    foreign_lookback: Mapped[int | None] = mapped_column(Integer)
    reasons: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_smart_money_ticker_date", "ticker", "date"),
        Index("ix_smart_money_detected_date", "detected", "date"),
    )
