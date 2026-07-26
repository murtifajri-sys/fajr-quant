"""IPO major-holder refresh and supply-risk summaries."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.stockbit import StockbitClient
from app.core.logging import log
from app.models.ipo_holder import IpoMajorHolderSnapshot
from app.models.price import DailyPrice
from app.models.stock import Stock

IPO_HOLDER_MAX_CALENDAR_AGE_DAYS = 120


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace("%", "").replace(",", "").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    candidates: list[Any] = [
        payload.get("data"),
        payload.get("result"),
        payload.get("rows"),
        payload.get("items"),
    ]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.extend(
            [
                data.get("result"),
                data.get("rows"),
                data.get("items"),
                data.get("major_holders"),
                data.get("majorholders"),
                data.get("company_major_holders"),
            ]
        )
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
        if isinstance(candidate, dict):
            nested = _find_rows(candidate)
            if nested:
                return nested
    return []


def _holder_name(row: dict[str, Any]) -> str | None:
    for key in ("name", "holder_name", "shareholder_name", "insider_name", "investor_name"):
        value = row.get(key)
        if value:
            return str(value).strip()
    insider = row.get("insider")
    if isinstance(insider, dict):
        for key in ("name", "full_name"):
            value = insider.get(key)
            if value:
                return str(value).strip()
    return None


def _holder_pct(row: dict[str, Any]) -> float | None:
    for key in (
        "ownership_percentage",
        "percentage",
        "ownership_pct",
        "share_percentage",
        "total_percentage",
        "pct",
    ):
        value = _as_float(row.get(key))
        if value is not None:
            return value
    return None


def summarize_major_holder_payload(payload: dict[str, Any]) -> dict[str, Any]:
    rows = _find_rows(payload)
    holders = [
        {"name": _holder_name(row), "percentage": _holder_pct(row), "raw": row}
        for row in rows
    ]
    holders = [holder for holder in holders if holder["name"] or holder["percentage"] is not None]
    holders.sort(key=lambda item: item["percentage"] or 0.0, reverse=True)

    pct_values = [holder["percentage"] for holder in holders if holder["percentage"] is not None]
    total_pct = min(100.0, sum(pct_values)) if pct_values else None
    free_float = round(max(0.0, 100.0 - total_pct), 2) if total_pct is not None else None
    top = holders[0] if holders else {}
    top_pct = top.get("percentage")

    if not holders:
        label = "unknown_majorholder"
    elif total_pct is not None and total_pct >= 80:
        label = "float_tight"
    elif total_pct is not None and total_pct < 50:
        label = "supply_overhang"
    elif top_pct is not None and top_pct < 25:
        label = "fragmented_holder"
    else:
        label = "majorholder_stable"

    return {
        "holder_count": len(holders),
        "top_holder_name": top.get("name"),
        "top_holder_pct": round(top_pct, 4) if top_pct is not None else None,
        "total_major_holder_pct": round(total_pct, 4) if total_pct is not None else None,
        "free_float_estimate_pct": free_float,
        "holder_risk_label": label,
        "holders": [
            {"name": holder.get("name"), "percentage": holder.get("percentage")}
            for holder in holders[:10]
        ],
    }


def latest_major_holder_snapshot(db: Session, ticker: str) -> IpoMajorHolderSnapshot | None:
    return db.execute(
        select(IpoMajorHolderSnapshot)
        .where(IpoMajorHolderSnapshot.ticker == ticker.upper())
        .order_by(IpoMajorHolderSnapshot.fetched_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def latest_major_holder_summary(db: Session, ticker: str) -> dict[str, Any] | None:
    row = latest_major_holder_snapshot(db, ticker)
    if not row:
        return None
    return {
        "as_of_date": row.as_of_date,
        "fetched_at": row.fetched_at,
        "holder_count": row.holder_count,
        "top_holder_name": row.top_holder_name,
        "top_holder_pct": row.top_holder_pct,
        "total_major_holder_pct": row.total_major_holder_pct,
        "free_float_estimate_pct": row.free_float_estimate_pct,
        "holder_risk_label": row.holder_risk_label,
        "summary": row.summary or {},
    }


def ipo_universe_tickers(db: Session, as_of_date: date | None = None, max_age_days: int = IPO_HOLDER_MAX_CALENDAR_AGE_DAYS) -> list[str]:
    as_of_date = as_of_date or db.execute(select(DailyPrice.date).order_by(DailyPrice.date.desc()).limit(1)).scalar_one_or_none() or date.today()
    start = as_of_date - timedelta(days=max_age_days)
    return [
        row[0]
        for row in db.execute(
            select(Stock.ticker)
            .where(Stock.listing_date >= start, Stock.listing_date <= as_of_date)
            .order_by(Stock.listing_date.desc(), Stock.ticker.asc())
        ).all()
    ]


def refresh_major_holder_for_ticker(db: Session, ticker: str, as_of_date: date | None = None) -> dict[str, Any]:
    ticker = ticker.upper()
    as_of_date = as_of_date or date.today()
    with StockbitClient(db=db) as client:
        payload = client.get_major_holders(ticker)
    summary = summarize_major_holder_payload(payload)
    row = db.get(IpoMajorHolderSnapshot, {"ticker": ticker, "as_of_date": as_of_date})
    if not row:
        row = IpoMajorHolderSnapshot(ticker=ticker, as_of_date=as_of_date, fetched_at=datetime.utcnow())
        db.add(row)
    row.fetched_at = datetime.utcnow()
    row.holder_count = int(summary.get("holder_count") or 0)
    row.top_holder_name = summary.get("top_holder_name")
    row.top_holder_pct = summary.get("top_holder_pct")
    row.total_major_holder_pct = summary.get("total_major_holder_pct")
    row.free_float_estimate_pct = summary.get("free_float_estimate_pct")
    row.holder_risk_label = summary.get("holder_risk_label") or "unknown_majorholder"
    row.summary = summary
    row.raw_payload = payload
    db.commit()
    return {"ticker": ticker, "ok": True, "holder_risk_label": row.holder_risk_label, "holder_count": row.holder_count}


def refresh_ipo_major_holders(db: Session, limit: int = 50, tickers: list[str] | None = None) -> dict[str, Any]:
    selected = sorted({ticker.upper() for ticker in (tickers or [])}) if tickers else ipo_universe_tickers(db)
    selected = selected[: max(1, min(limit, 200))]
    succeeded = 0
    failed = 0
    errors: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    as_of_date = db.execute(select(DailyPrice.date).order_by(DailyPrice.date.desc()).limit(1)).scalar_one_or_none() or date.today()
    for ticker in selected:
        try:
            result = refresh_major_holder_for_ticker(db, ticker, as_of_date=as_of_date)
            results.append(result)
            succeeded += 1
        except Exception as exc:
            db.rollback()
            failed += 1
            errors[ticker] = str(exc)[:500]
            log.warning("ipo_major_holder_refresh_failed", ticker=ticker, error=str(exc)[:300])
    return {
        "processed": len(selected),
        "succeeded": succeeded,
        "failed": failed,
        "errors": errors,
        "results": results,
        "as_of_date": as_of_date,
    }
