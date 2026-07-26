import json
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base
from app.models._mixins import TimestampMixin


class TechnicalIndicator(TimestampMixin, Base):
    """Computed technical indicator / pattern result for a ticker on a date.

    method: trend_structure | price_action | volume_breakout | harmonic |
            relative_strength | candlestick | elliott_wave | indicator
    payload: JSON details (pattern type, levels, scores, etc.)
    score: 0-100 sub-score for this method on this date.
    """
    __tablename__ = "technical_indicators"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.ticker"))
    date: Mapped[date] = mapped_column(Date)
    method: Mapped[str] = mapped_column(String(32))
    name: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    score: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("ix_tech_ticker_date_method", "ticker", "date", "method"),
    )
