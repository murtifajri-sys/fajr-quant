"""Screener run/result persistence models."""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base
from app.models._mixins import TimestampMixin


class ScreenerRun(TimestampMixin, Base):
    __tablename__ = "screener_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filter_json: Mapped[dict] = mapped_column(JSON)
    total: Mapped[int] = mapped_column(Integer, default=0)


class ScreenerResult(TimestampMixin, Base):
    __tablename__ = "screener_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("screener_runs.id", ondelete="CASCADE"))
    ticker: Mapped[str] = mapped_column(String(16))
    name: Mapped[str | None] = mapped_column(String(255))
    composite: Mapped[float] = mapped_column()
    phase: Mapped[str] = mapped_column(String(32))
    dominant_factors: Mapped[dict] = mapped_column(JSON)
    rank: Mapped[int] = mapped_column(Integer)

    def as_dict(self) -> dict:
        broker = (self.dominant_factors or {}).get("broker_accumulation") or {}
        return {
            "ticker": self.ticker,
            "name": self.name,
            "composite": self.composite,
            "phase": self.phase,
            "dominant_factors": self.dominant_factors,
            "broker_conviction_score": broker.get("broker_conviction_score"),
            "broker_conviction_label": broker.get("broker_conviction_label"),
            "flow_quality_score": broker.get("flow_quality_score"),
            "flow_quality_label": broker.get("flow_quality_label"),
            "entry_readiness_score": broker.get("entry_readiness_score"),
            "combined_rank_score": broker.get("combined_rank_score"),
            "broker_status": broker.get("status"),
            "setup_detail": broker.get("setup_detail"),
            "closest_to_smart_rank": broker.get("closest_to_smart_rank"),
            "closest_to_smart_score": broker.get("closest_to_smart_score"),
            "rank": self.rank,
        }
