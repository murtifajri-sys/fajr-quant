from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base
from app.models._mixins import TimestampMixin


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.ticker"))
    date: Mapped[date] = mapped_column(Date)
    action: Mapped[str] = mapped_column(String(16))  # BUY | WAIT | SELL | HOLD | EXIT
    entry: Mapped[float | None] = mapped_column(Float)
    stop: Mapped[float | None] = mapped_column(Float)
    target: Mapped[float | None] = mapped_column(Float)
    rationale: Mapped[str | None] = mapped_column(Text)
    dominant_factors: Mapped[dict] = mapped_column(JSON)
    risks: Mapped[dict] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(32), default="deepseek")
    raw_response: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (Index("ix_rec_ticker_date", "ticker", "date"),)
