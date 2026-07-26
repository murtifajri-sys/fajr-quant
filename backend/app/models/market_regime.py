from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base
from app.models._mixins import TimestampMixin


class MarketRegime(TimestampMixin, Base):
    __tablename__ = "market_regimes"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    benchmark: Mapped[str] = mapped_column(String(16), default="^JKSE")
    regime: Mapped[str] = mapped_column(String(32))  # trending_up | trending_down | range | volatile
    meta: Mapped[dict] = mapped_column(JSON)
