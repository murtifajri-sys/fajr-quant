from datetime import date

from sqlalchemy import BigInteger, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._mixins import TimestampMixin


class Stock(TimestampMixin, Base):
    __tablename__ = "stocks"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(64))
    industry: Mapped[str | None] = mapped_column(String(128))
    board: Mapped[str | None] = mapped_column(String(32))
    exchange: Mapped[str] = mapped_column(String(16), default="IDX")
    listing_date: Mapped[date | None] = mapped_column(Date)
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    profile_payload: Mapped[str | None] = mapped_column(String(8192))
