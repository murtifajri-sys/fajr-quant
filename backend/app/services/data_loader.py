"""Data loader: fetch + persist daily prices, bandar flow, foreign flow.

Orchestrates Stockbit client with yfinance fallback for prices.
"""
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.stockbit import StockbitClient
from app.clients.yfinance import YFinanceClient
from app.core.config import settings
from app.core.logging import log
from app.models.bandar import BandarmologySignal
from app.models.broker_flow import BrokerFlow
from app.models.foreign_flow import ForeignFlow
from app.models.price import DailyPrice
from app.models.setting import WatchlistItem
from app.models.stock import Stock
from app.services.bandarmology.foreign_flow import score_foreign_flow


def _ensure_stock(db: Session, ticker: str, name: str | None = None):
    stock = db.get(Stock, ticker)
    if not stock:
        stock = Stock(ticker=ticker, name=name)
        db.add(stock)
        db.commit()


def _latest_price_date(db: Session, ticker: str) -> date | None:
    latest = db.execute(
        select(func.max(DailyPrice.date)).where(DailyPrice.ticker == ticker)
    ).scalar()
    return latest


def load_prices(db: Session, ticker: str, days: int | None = None, incremental: bool = False) -> list[DailyPrice]:
    _ensure_stock(db, ticker)
    end = date.today()

    if incremental:
        latest = _latest_price_date(db, ticker)
        if latest and latest >= end:
            log.info("prices_up_to_date", ticker=ticker, latest=latest.isoformat())
            return []
        # Fetch enough to cover missing days plus a small overlap for corrections.
        if latest:
            start = min(
                latest - timedelta(days=settings.DAILY_INCREMENTAL_OVERLAP_DAYS),
                end - timedelta(days=settings.DAILY_INCREMENTAL_MAX_DAYS),
            )
        else:
            # No existing data: fall back to full lookback
            start = end - timedelta(days=(days or settings.TECHNICAL_LOOKBACK_DAYS))
    else:
        start = end - timedelta(days=(days or settings.TECHNICAL_LOOKBACK_DAYS))

    rows: list[dict] = []
    stockbit_data: Any = None
    source = "stockbit"
    try:
        with StockbitClient(db=db) as client:
            data = client.get_daily_prices(ticker, start, end)
        stockbit_data = data
        rows = _parse_stockbit_prices(data)
    except Exception as e:
        log.warning("stockbit_price_failed_fallback_yfinance", ticker=ticker, error=str(e))
        source = "yfinance"
        rows = YFinanceClient().get_daily_prices(
            _yf_symbol(ticker), start=start, end=end + timedelta(days=1)
        )

    if not rows:
        log.warning("no_prices", ticker=ticker)
        return []

    persisted = []
    for r in rows:
        existing = db.execute(
            select(DailyPrice).where(
                DailyPrice.ticker == ticker, DailyPrice.date == r["date"]
            )
        ).scalar_one_or_none()
        if existing:
            existing.open = r.get("open")
            existing.high = r.get("high")
            existing.low = r.get("low")
            existing.close = r.get("close")
            existing.adj_close = r.get("adj_close")
            existing.volume = r.get("volume")
            existing.source = source
            row_obj = existing
        else:
            row_obj = DailyPrice(
                ticker=ticker,
                date=r["date"],
                open=r.get("open"),
                high=r.get("high"),
                low=r.get("low"),
                close=r.get("close"),
                adj_close=r.get("adj_close"),
                volume=r.get("volume"),
                source=source,
            )
            db.add(row_obj)
        persisted.append(row_obj)
    db.commit()
    if stockbit_data:
        foreign_rows = _parse_stockbit_foreign_flows(stockbit_data)
        _persist_foreign_flow_rows(db, ticker, foreign_rows)
    log.info("prices_loaded", ticker=ticker, count=len(persisted), source=source, incremental=incremental)
    return persisted


def _yf_symbol(ticker: str) -> str:
    return f"{ticker}.JK" if not ticker.startswith("^") else ticker


def _parse_stockbit_prices(data: Any) -> list[dict]:
    """Stockbit historical summary returns data in various shapes; best-effort parse."""
    if not data:
        return []
    payload = data if isinstance(data, list) else data.get("data") or data.get("payload") or []
    if isinstance(payload, dict):
        payload = (
            payload.get("chartbit")
            or payload.get("result")
            or payload.get("data")
            or payload.get("prices")
            or []
        )
    rows = []
    for item in payload:
        try:
            d = item.get("date") or item.get("trading_date") or item.get("tgl")
            if not d:
                continue
            d = pd.to_datetime(d).date()
            rows.append(
                {
                    "date": d,
                    "open": _f(item, "open"),
                    "high": _f(item, "high"),
                    "low": _f(item, "low"),
                    "close": _f(item, "close"),
                    "adj_close": _f(item, "adj_close") or _f(item, "adjusted_close"),
                    "volume": _f(item, "volume") or _f(item, "vol"),
                }
            )
        except Exception:
            continue
    return rows


def _parse_stockbit_foreign_flows(data: Any) -> list[dict]:
    """Extract daily foreign buy/sell values from Stockbit chartbit data."""
    if not data:
        return []
    payload = data if isinstance(data, list) else data.get("data") or {}
    if isinstance(payload, dict):
        payload = payload.get("chartbit") or payload.get("result") or []

    rows = []
    for item in payload:
        try:
            raw_date = item.get("date") or item.get("trading_date")
            if not raw_date:
                continue
            foreign_buy = _f(item, "foreignbuy")
            if foreign_buy is None:
                foreign_buy = _f(item, "foreign_buy")
            foreign_sell = _f(item, "foreignsell")
            if foreign_sell is None:
                foreign_sell = _f(item, "foreign_sell")
            if foreign_buy is None and foreign_sell is None:
                continue
            foreign_buy = foreign_buy or 0.0
            foreign_sell = foreign_sell or 0.0
            rows.append(
                {
                    "date": pd.to_datetime(raw_date).date(),
                    "foreign_buy": foreign_buy,
                    "foreign_sell": foreign_sell,
                    "net_foreign": foreign_buy - foreign_sell,
                }
            )
        except Exception:
            continue
    return rows


def _f(item: dict, key: str) -> float | None:
    v = item.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(item: dict, key: str) -> int | None:
    v = item.get(key)
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def load_bandar_flow(db: Session, ticker: str, days: int | None = None) -> list[dict]:
    """Fetch broker/investor flow from marketdetectors and persist as flow_df-like rows."""
    days = days or settings.BANDARMOLOGY_LOOKBACK_DAYS
    end = date.today()
    start = end - timedelta(days=days)
    try:
        with StockbitClient(db=db) as client:
            data = client.get_market_detectors(ticker, start, end)
    except Exception as e:
        log.warning("bandar_flow_failed", ticker=ticker, error=str(e))
        return []
    rows = _parse_market_detectors(data)
    save_broker_flows(db, ticker, rows)
    return rows


def save_broker_flows(db: Session, ticker: str, rows: list[dict]) -> None:
    if not rows:
        return
    grouped: dict[tuple, dict] = {}
    for row in rows:
        broker = str(row.get("party") or "").strip()
        d = row.get("date")
        if not broker or not d:
            continue
        key = (ticker.upper(), d, broker)
        current = grouped.setdefault(
            key,
            {"buy_value": 0.0, "sell_value": 0.0, "net_value": 0.0, "buy_freq": 0, "sell_freq": 0},
        )
        current["buy_value"] += float(row.get("buy_value") or 0.0)
        current["sell_value"] += float(row.get("sell_value") or 0.0)
        current["net_value"] += float(row.get("net_value") or 0.0)
        current["buy_freq"] += int(row.get("buy_freq") or 0)
        current["sell_freq"] += int(row.get("sell_freq") or 0)

    for (t, d, broker), values in grouped.items():
        existing = db.get(BrokerFlow, {"ticker": t, "date": d, "broker": broker})
        if not existing:
            existing = BrokerFlow(ticker=t, date=d, broker=broker)
            db.add(existing)
        existing.buy_value = values["buy_value"]
        existing.sell_value = values["sell_value"]
        existing.net_value = values["net_value"]
        existing.buy_freq = values["buy_freq"] or None
        existing.sell_freq = values["sell_freq"] or None
        existing.source = "stockbit"
    db.commit()


def backfill_broker_flow_for_ticker(
    db: Session,
    ticker: str,
    period_days: int = 30,
    target_dates: list[date] | None = None,
) -> dict:
    empty_source_marker = "__NO_DATA__"
    t = ticker.upper()
    latest_price = db.execute(
        select(DailyPrice.date)
        .where(DailyPrice.ticker == t)
        .order_by(DailyPrice.date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not latest_price:
        return {
            "ticker": t,
            "ok": False,
            "reason": "no_price_data",
            "fetched_dates": 0,
            "missing_dates": [],
            "fetched_date_list": [],
            "failed_dates": [],
        }

    start = latest_price - timedelta(days=period_days)
    trading_dates = [
        r[0]
        for r in db.execute(
            select(DailyPrice.date)
            .where(DailyPrice.ticker == t, DailyPrice.date >= start, DailyPrice.date <= latest_price)
            .order_by(DailyPrice.date.asc())
        ).all()
    ]
    if not trading_dates:
        return {
            "ticker": t,
            "ok": False,
            "reason": "no_trading_dates",
            "fetched_dates": 0,
            "missing_dates": [],
            "fetched_date_list": [],
            "failed_dates": [],
        }

    existing_dates = {
        r[0]
        for r in db.execute(
            select(BrokerFlow.date)
            .where(BrokerFlow.ticker == t, BrokerFlow.date.in_(trading_dates))
            .distinct()
        ).all()
    }
    if target_dates:
        requested_dates = sorted({d for d in target_dates if d in trading_dates})
        missing_dates = [d for d in requested_dates if d not in existing_dates]
    else:
        missing_dates = [d for d in trading_dates if d not in existing_dates]
    if not missing_dates:
        return {
            "ticker": t,
            "ok": True,
            "reason": "already_complete",
            "fetched_dates": 0,
            "trading_dates": len(trading_dates),
            "missing_dates": [],
            "fetched_date_list": [],
            "failed_dates": [],
        }

    fetched = 0
    fetched_date_list: list[str] = []
    failed_dates: list[dict[str, str]] = []
    empty_source_dates: list[str] = []
    with StockbitClient(db=db) as client:
        for d in missing_dates:
            try:
                data = client.get_market_detectors(t, d, d, limit=300)
                parsed_rows = _parse_market_detectors(data)
                if parsed_rows:
                    save_broker_flows(db, t, parsed_rows)
                else:
                    marker = db.get(BrokerFlow, {"ticker": t, "date": d, "broker": empty_source_marker})
                    if not marker:
                        marker = BrokerFlow(
                            ticker=t,
                            date=d,
                            broker=empty_source_marker,
                            buy_value=0.0,
                            sell_value=0.0,
                            net_value=0.0,
                            source="stockbit_empty",
                        )
                        db.add(marker)
                        db.commit()
                    empty_source_dates.append(d.isoformat())
                fetched += 1
                fetched_date_list.append(d.isoformat())
            except Exception as exc:
                db.rollback()
                failed_dates.append({"date": d.isoformat(), "error": str(exc)[:300]})

    if failed_dates and fetched:
        reason = "partial_backfill"
    elif failed_dates:
        reason = "backfill_failed"
    elif empty_source_dates:
        reason = "empty_source_marked"
    else:
        reason = "backfilled"
    return {
        "ticker": t,
        "ok": len(failed_dates) == 0,
        "reason": reason,
        "fetched_dates": fetched,
        "trading_dates": len(trading_dates),
        "missing_dates": [d.isoformat() for d in missing_dates],
        "fetched_date_list": fetched_date_list,
        "empty_source_dates": empty_source_dates,
        "failed_dates": failed_dates,
    }


def broker_flow_coverage_summary(
    db: Session,
    period_days: int = 30,
    universe: str = "idx",
    tickers: list[str] | None = None,
    limit: int = 25,
) -> dict:
    period_days = max(1, int(period_days or 30))
    latest_market_date = db.execute(select(func.max(DailyPrice.date))).scalar()
    if not latest_market_date:
        return {
            "as_of_date": None,
            "period_days": period_days,
            "universe": universe,
            "total_tickers": 0,
            "complete_tickers": 0,
            "partial_tickers": 0,
            "missing_tickers": 0,
            "average_coverage_ratio": 0.0,
            "items": [],
        }

    selected_tickers = [t.upper() for t in (tickers or []) if t]
    start_date = latest_market_date - timedelta(days=period_days)
    trading_counts = (
        select(DailyPrice.ticker, func.count(func.distinct(DailyPrice.date)).label("trading_days"))
        .where(DailyPrice.date >= start_date, DailyPrice.date <= latest_market_date)
    )
    if selected_tickers:
        trading_counts = trading_counts.where(DailyPrice.ticker.in_(selected_tickers))
    trading_counts = trading_counts.group_by(DailyPrice.ticker).subquery()

    flow_counts = (
        select(BrokerFlow.ticker, func.count(func.distinct(BrokerFlow.date)).label("flow_days"))
        .where(BrokerFlow.date >= start_date, BrokerFlow.date <= latest_market_date)
    )
    if selected_tickers:
        flow_counts = flow_counts.where(BrokerFlow.ticker.in_(selected_tickers))
    flow_counts = flow_counts.group_by(BrokerFlow.ticker).subquery()

    stmt = (
        select(
            Stock.ticker,
            func.coalesce(flow_counts.c.flow_days, 0).label("flow_days"),
            trading_counts.c.trading_days,
        )
        .join(trading_counts, Stock.ticker == trading_counts.c.ticker)
        .outerjoin(flow_counts, Stock.ticker == flow_counts.c.ticker)
    )
    if selected_tickers:
        stmt = stmt.where(Stock.ticker.in_(selected_tickers))
    elif universe == "watchlist":
        watch = select(WatchlistItem.ticker).subquery()
        stmt = stmt.where(Stock.ticker.in_(select(watch.c.ticker)))

    rows = db.execute(stmt.order_by(Stock.ticker.asc())).all()
    items: list[dict] = []
    complete_tickers = 0
    partial_tickers = 0
    missing_tickers = 0
    coverage_sum = 0.0

    for ticker, flow_days, trading_days in rows:
        trading_days = int(trading_days or 0)
        flow_days = int(flow_days or 0)
        coverage_ratio = float(flow_days / trading_days) if trading_days else 0.0
        missing_days = max(trading_days - flow_days, 0)
        if trading_days and flow_days >= trading_days:
            status = "complete"
            complete_tickers += 1
        elif flow_days <= 0:
            status = "missing"
            missing_tickers += 1
        else:
            status = "partial"
            partial_tickers += 1
        coverage_sum += coverage_ratio
        items.append(
            {
                "ticker": ticker,
                "trading_days": trading_days,
                "flow_days": flow_days,
                "missing_days": missing_days,
                "coverage_ratio": round(coverage_ratio, 4),
                "status": status,
            }
        )

    items.sort(key=lambda row: (row["coverage_ratio"], -row["missing_days"], row["ticker"]))
    total_tickers = len(rows)
    return {
        "as_of_date": latest_market_date,
        "period_days": period_days,
        "universe": universe,
        "total_tickers": total_tickers,
        "complete_tickers": complete_tickers,
        "partial_tickers": partial_tickers,
        "missing_tickers": missing_tickers,
        "average_coverage_ratio": round((coverage_sum / total_tickers) if total_tickers else 0.0, 4),
        "items": items[:limit],
    }


def _parse_market_detectors(data: Any) -> list[dict]:
    if not data:
        return []
    payload = data if isinstance(data, list) else data.get("data") or []
    if isinstance(payload, dict):
        broker_summary = payload.get("broker_summary")
        if isinstance(broker_summary, dict):
            rows = []
            for item in broker_summary.get("brokers_buy") or []:
                d = item.get("netbs_date")
                if not d:
                    continue
                rows.append(
                    {
                        "date": pd.to_datetime(d).date(),
                        "party": str(item.get("netbs_broker_code") or ""),
                        "buy_value": _f(item, "bval") or 0.0,
                        "sell_value": 0.0,
                        "net_value": _f(item, "bval") or 0.0,
                        "buy_freq": _i(item, "freq"),
                        "sell_freq": 0,
                    }
                )
            for item in broker_summary.get("brokers_sell") or []:
                d = item.get("netbs_date")
                if not d:
                    continue
                sell = abs(_f(item, "sval") or 0.0)
                rows.append(
                    {
                        "date": pd.to_datetime(d).date(),
                        "party": str(item.get("netbs_broker_code") or ""),
                        "buy_value": 0.0,
                        "sell_value": sell,
                        "net_value": -sell,
                        "buy_freq": 0,
                        "sell_freq": _i(item, "freq"),
                    }
                )
            return rows
        payload = payload.get("result") or payload.get("data") or payload.get("rows") or []
    rows = []
    for item in payload:
        try:
            d = item.get("date") or item.get("trading_date")
            if not d:
                continue
            d = pd.to_datetime(d).date()
            # party could be broker/investor
            party = item.get("broker") or item.get("broker_id") or item.get("investor") or item.get("party") or ""
            buy = _f(item, "buy_value") or _f(item, "buy") or _f(item, "buyVal")
            sell = _f(item, "sell_value") or _f(item, "sell") or _f(item, "sellVal")
            net = _f(item, "net_value") or _f(item, "net") or _f(item, "netVal")
            if net is None and buy is not None and sell is not None:
                net = buy - sell
            rows.append(
                {
                    "date": d,
                    "party": str(party),
                    "buy_value": buy,
                    "sell_value": sell,
                    "net_value": net,
                    "buy_freq": _i(item, "buy_freq") or _i(item, "bfreq") or _i(item, "freq_buy"),
                    "sell_freq": _i(item, "sell_freq") or _i(item, "sfreq") or _i(item, "freq_sell"),
                }
            )
        except Exception:
            continue
    return rows


def load_foreign_flow(db: Session, ticker: str, days: int | None = None) -> list[ForeignFlow]:
    days = days or settings.BANDARMOLOGY_LOOKBACK_DAYS
    end = date.today()
    start = end - timedelta(days=days)
    existing = db.execute(
        select(ForeignFlow)
        .where(ForeignFlow.ticker == ticker, ForeignFlow.date >= start)
        .order_by(ForeignFlow.date.asc())
    ).scalars().all()
    if existing:
        return existing

    # Fallback when chartbit daily data was unavailable: marketdetectors still
    # provides an aggregate foreign broker snapshot for the requested range.
    try:
        with StockbitClient(db=db) as client:
            data = client.get_market_detectors(
                ticker, start, end, investor_type="INVESTOR_TYPE_FOREIGN"
            )
    except Exception as e:
        log.warning("foreign_flow_failed", ticker=ticker, error=str(e))
        return []
    rows = _parse_market_detectors(data)
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    df["date"] = pd.to_datetime(df["date"])
    agg = df.groupby("date").agg(
        foreign_buy=("buy_value", "sum"),
        foreign_sell=("sell_value", "sum"),
        net_foreign=("net_value", "sum"),
    ).reset_index()
    return _persist_foreign_flow_rows(db, ticker, agg.to_dict(orient="records"))


def _persist_foreign_flow_rows(
    db: Session, ticker: str, rows: list[dict]
) -> list[ForeignFlow]:
    if not rows:
        return []
    scored = score_foreign_flow(rows, window=min(20, len(rows)))
    score_map = {s["date"]: s["score"] for s in scored}
    persisted = []
    for r in rows:
        d = pd.to_datetime(r["date"]).date()
        foreign_buy = _safe(r.get("foreign_buy")) or 0.0
        foreign_sell = _safe(r.get("foreign_sell")) or 0.0
        net_foreign = _safe(r.get("net_foreign"))
        if net_foreign is None:
            net_foreign = foreign_buy - foreign_sell
        total = foreign_buy + foreign_sell
        existing = db.execute(
            select(ForeignFlow).where(ForeignFlow.ticker == ticker, ForeignFlow.date == d)
        ).scalar_one_or_none()
        score_val = score_map.get(d)
        if existing:
            existing.foreign_buy = foreign_buy
            existing.foreign_sell = foreign_sell
            existing.net_foreign = net_foreign
            existing.net_foreign_pct = net_foreign / total if total else None
            existing.score = score_val
            obj = existing
        else:
            obj = ForeignFlow(
                ticker=ticker,
                date=d,
                foreign_buy=foreign_buy,
                foreign_sell=foreign_sell,
                net_foreign=net_foreign,
                net_foreign_pct=net_foreign / total if total else None,
                score=score_val,
            )
            db.add(obj)
        persisted.append(obj)
    db.commit()
    log.info("foreign_flow_loaded", ticker=ticker, count=len(persisted))
    return persisted


def _safe(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_company_profile(db: Session, ticker: str) -> dict | None:
    try:
        with StockbitClient(db=db) as client:
            data = client.get_company_profile(ticker)
    except Exception as e:
        log.warning("profile_failed", ticker=ticker, error=str(e))
        return None
    payload = data.get("data") or data if isinstance(data, dict) else {}
    stock = db.get(Stock, ticker)
    if stock:
        stock.name = stock.name or payload.get("company_name") or payload.get("name")
        stock.sector = payload.get("sector") or stock.sector
        stock.industry = payload.get("industry") or stock.industry
        stock.board = payload.get("board") or stock.board
        db.commit()
    return payload
