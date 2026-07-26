from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class DailyPrice(TimestampMixin, Base):
    __tablename__ = "daily_prices"

    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.ticker"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    adj_close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16), default="stockbit")  # stockbit | yfinance

    __table_args__ = (Index("ix_daily_prices_ticker_date", "ticker", "date"),)
