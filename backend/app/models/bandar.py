from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base
from app.models._mixins import TimestampMixin


class BandarmologySignal(TimestampMixin, Base):
    """Bandarmology detection result per ticker per date.

    label: hidden_accumulation | silent_accumulation | shakeout | absorption |
           bandar_positioning | consistency
    detected: boolean whether the pattern is active
    value: numeric strength (0-100 or raw metric)
    score: normalized 0-100 contribution
    payload: supporting details (top brokers, lots, etc.)
    """
    __tablename__ = "bandarmology_signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), ForeignKey("stocks.ticker"))
    date: Mapped[date] = mapped_column(Date)
    label: Mapped[str] = mapped_column(String(32))
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    value: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON)

    __table_args__ = (
        Index("ix_bandar_ticker_date_label", "ticker", "date", "label"),
    )
