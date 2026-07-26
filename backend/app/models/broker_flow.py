from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class BrokerFlow(TimestampMixin, Base):
    __tablename__ = "broker_flows"

    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.ticker"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    broker: Mapped[str] = mapped_column(String(16), primary_key=True)
    buy_value: Mapped[float] = mapped_column(Float, default=0.0)
    sell_value: Mapped[float] = mapped_column(Float, default=0.0)
    net_value: Mapped[float] = mapped_column(Float, default=0.0)
    buy_freq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sell_freq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="stockbit")

    __table_args__ = (
        Index("ix_broker_flow_ticker_date", "ticker", "date"),
        Index("ix_broker_flow_ticker_broker_date", "ticker", "broker", "date"),
    )
