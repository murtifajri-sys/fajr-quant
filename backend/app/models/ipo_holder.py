"""IPO major-holder cache models."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base
from app.models._mixins import TimestampMixin


class IpoMajorHolderSnapshot(TimestampMixin, Base):
    __tablename__ = "ipo_major_holder_snapshots"

    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.ticker"), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    holder_count: Mapped[int] = mapped_column(default=0)
    top_holder_name: Mapped[str | None] = mapped_column(String(255))
    top_holder_pct: Mapped[float | None] = mapped_column(Float)
    total_major_holder_pct: Mapped[float | None] = mapped_column(Float)
    free_float_estimate_pct: Mapped[float | None] = mapped_column(Float)
    holder_risk_label: Mapped[str] = mapped_column(String(48), default="unknown_majorholder")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_ipo_major_holder_ticker_fetched", "ticker", "fetched_at"),
        Index("ix_ipo_major_holder_label", "holder_risk_label"),
    )
