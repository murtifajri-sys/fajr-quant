from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base
from app.models._mixins import TimestampMixin


class Score(TimestampMixin, Base):
    """Composite score + sub-scores + phase per ticker per date."""
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.ticker"))
    date: Mapped[date] = mapped_column(Date)
    composite: Mapped[float] = mapped_column(Float)
    sub_scores: Mapped[dict] = mapped_column(JSON)  # {method: score}
    weights: Mapped[dict] = mapped_column(JSON)  # weights used (adaptive)
    phase: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    dominant_factors: Mapped[dict] = mapped_column(JSON)

    __table_args__ = (Index("ix_score_ticker_date", "ticker", "date"),)


class StockProfile(TimestampMixin, Base):
    """Adaptive character profile of a stock (learned from history)."""
    __tablename__ = "stock_profiles"

    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.ticker"), primary_key=True)
    weights: Mapped[dict] = mapped_column(JSON)  # adaptive weights per method
    dominant_method: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(String(512))
    sample_window_days: Mapped[int | None] = mapped_column()
