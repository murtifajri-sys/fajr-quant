"""Seed the `stocks` table from the IDX stock list xlsx.

Run inside the backend container:
    python -m app.scripts.seed_stocks

Or via API: POST /api/v1/tasks/seed-stocks  (delegates to a Celery task)

Source file: backend/data/stock_list.xlsx
Columns expected: No, Code, Company Name, Listing Date, Shares, Listing Board
"""
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.logging import log
from app.models.stock import Stock

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "stock_list.xlsx"

BOARD_MAP = {
    "Main": "MAIN",
    "Development": "DEV",
    "Watchlist": "WL",
    "Acceleration": "ACC",
    "Ekonomi Baru": "EB",
}


def _parse_shares(v) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_listing_date(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, datetime):
        return v.date()
    for fmt in ("%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    return None


def seed_stocks(db: Session, path: Path | str = DEFAULT_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Stock list not found: {path}")

    df = pd.read_excel(path)
    required = {"Code", "Company Name", "Listing Date", "Shares", "Listing Board"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in xlsx: {missing}")

    created = 0
    updated = 0
    for _, row in df.iterrows():
        ticker = str(row["Code"]).strip().upper()
        if not ticker:
            continue
        name = str(row["Company Name"]).strip()
        board = BOARD_MAP.get(str(row["Listing Board"]).strip(), str(row["Listing Board"]).strip().upper())
        listing_date = _parse_listing_date(row["Listing Date"])
        shares = _parse_shares(row["Shares"])

        existing = db.execute(select(Stock).where(Stock.ticker == ticker)).scalar_one_or_none()
        if existing:
            existing.name = name or existing.name
            existing.board = board or existing.board
            existing.listing_date = listing_date or existing.listing_date
            existing.shares_outstanding = shares or existing.shares_outstanding
            existing.exchange = "IDX"
            updated += 1
        else:
            db.add(
                Stock(
                    ticker=ticker,
                    name=name,
                    board=board,
                    exchange="IDX",
                    listing_date=listing_date,
                    shares_outstanding=shares,
                )
            )
            created += 1
    db.commit()
    log.info("stocks_seeded", created=created, updated=updated, total=len(df))
    return {"created": created, "updated": updated, "total_rows": int(len(df))}


def main():
    db = SessionLocal()
    try:
        result = seed_stocks(db)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
