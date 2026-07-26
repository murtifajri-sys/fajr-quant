from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class ForeignFlow(TimestampMixin, Base):
    __tablename__ = "foreign_flows"

    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.ticker"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    foreign_buy: Mapped[float | None] = mapped_column(Float)
    foreign_sell: Mapped[float | None] = mapped_column(Float)
    net_foreign: Mapped[float | None] = mapped_column(Float)
    net_foreign_pct: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_ff_ticker_date", "ticker", "date"),)
