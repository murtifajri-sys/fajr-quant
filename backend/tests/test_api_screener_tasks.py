from datetime import date, datetime, timedelta
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401 - registers SQLAlchemy models
from app.api.routes import screener as screener_routes
from app.api.routes import tasks as tasks_routes
from app.core.db import Base
from app.models.broker_flow import BrokerFlow
from app.models.pipeline_run import PipelineRun
from app.models.price import DailyPrice
from app.models.screener import ScreenerResult, ScreenerRun
from app.models.stock import Stock
from app.services.screener.runner import DEFAULT_SCREENER_SNAPSHOT_NAME
from app.workers import tasks as worker_tasks


def _make_session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def test_tasks_broker_flow_coverage_route_returns_summary():
    db = _make_session()
    for ticker in ("CMP", "PAR", "MIS"):
        db.add(Stock(ticker=ticker, name=ticker))

    dates = [date(2026, 7, 20), date(2026, 7, 21), date(2026, 7, 22)]
    for ticker in ("CMP", "PAR", "MIS"):
        for d in dates:
            db.add(
                DailyPrice(
                    ticker=ticker,
                    date=d,
                    open=10,
                    high=10,
                    low=10,
                    close=10,
                    adj_close=10,
                    volume=1_000,
                    source="stockbit",
                )
            )
    for d in dates:
        db.add(BrokerFlow(ticker="CMP", date=d, broker="AA", buy_value=100, sell_value=0, net_value=100))
    for d in dates[:2]:
        db.add(BrokerFlow(ticker="PAR", date=d, broker="BB", buy_value=100, sell_value=0, net_value=100))
    db.commit()

    result = tasks_routes.get_broker_flow_coverage(period_days=30, universe="idx", limit=10, db=db)

    assert result.total_tickers == 3
    assert result.complete_tickers == 1
    assert result.partial_tickers == 1
    assert result.missing_tickers == 1
    assert result.items[0].ticker == "MIS"
    assert result.items[1].ticker == "PAR"


def test_tasks_retry_broker_flow_backfill_route_creates_follow_up_run(monkeypatch):
    db = _make_session()
    db.add(
        PipelineRun(
            task_id="failed-broker-backfill",
            task_name="broker_flow_backfill",
            status="FAILURE",
            stage="completed",
            result={
                "period_days": 30,
                "universe": "idx",
                "errors": {"BBRI": "timeout", "BBCA": "401"},
                "failed_dates_by_ticker": {
                    "BBRI": [{"date": "2026-07-21", "error": "timeout"}],
                    "BBCA": [{"date": "2026-07-20", "error": "401"}],
                },
            },
        )
    )
    db.commit()

    calls = []

    def fake_apply_async(*, args=None, task_id=None, **_kwargs):
        calls.append({"args": args, "task_id": task_id})

    monkeypatch.setattr(tasks_routes.run_broker_flow_backfill, "apply_async", fake_apply_async)

    result = tasks_routes.retry_broker_flow_backfill("failed-broker-backfill", db=db)

    assert result.status == "QUEUED"
    assert calls
    assert calls[0]["args"] == [
        2,
        30,
        "idx",
        ["BBCA", "BBRI"],
        {"BBRI": ["2026-07-21"], "BBCA": ["2026-07-20"]},
    ]

    queued = db.query(PipelineRun).filter(PipelineRun.task_id == result.task_id).one()
    assert queued.task_name == "broker_flow_backfill"
    assert queued.status == "QUEUED"


def test_recover_orphaned_runs_skips_queued_dependencies():
    db = _make_session()
    stale_started = PipelineRun(
        task_id="stale-started",
        task_name="data_load",
        status="PROGRESS",
        stage="processing",
    )
    stale_queued = PipelineRun(
        task_id="stale-queued",
        task_name="recommendations",
        status="QUEUED",
        stage="waiting_for_worker",
    )
    db.add(stale_started)
    db.add(stale_queued)
    db.commit()

    stale_time = datetime.utcnow() - timedelta(minutes=worker_tasks.ORPHAN_STALE_MINUTES + 1)
    stale_started.updated_at = stale_time
    stale_queued.updated_at = stale_time
    db.commit()

    original_db = worker_tasks._db
    worker_tasks._db = lambda: db
    try:
        worker_tasks.recover_orphaned_runs()
    finally:
        worker_tasks._db = original_db

    started = db.query(PipelineRun).filter(PipelineRun.task_id == "stale-started").one()
    queued = db.query(PipelineRun).filter(PipelineRun.task_id == "stale-queued").one()

    assert started.status == "ORPHANED"
    assert started.stage == "orphaned"
    assert queued.status == "QUEUED"
    assert queued.stage == "waiting_for_worker"


def test_worker_json_safe_serializes_dates_for_backfill_results():
    payload = {
        "coverage_before": {"as_of_date": date(2026, 7, 23), "items": [{"date": date(2026, 7, 22)}]},
        "coverage_after": {"as_of_date": date(2026, 7, 23)},
        "failed_dates_by_ticker": {"BBCA": [{"date": "2026-07-21", "error": "timeout"}]},
    }

    result = worker_tasks._json_safe(payload)

    assert result["coverage_before"]["as_of_date"] == "2026-07-23"
    assert result["coverage_before"]["items"][0]["date"] == "2026-07-22"
    assert result["coverage_after"]["as_of_date"] == "2026-07-23"
    assert result["failed_dates_by_ticker"]["BBCA"][0]["date"] == "2026-07-21"


def test_screener_latest_route_prefers_named_daily_snapshot():
    db = _make_session()
    db.add(Stock(ticker="SNAP", name="Snapshot"))
    db.add(Stock(ticker="MANL", name="Manual"))
    db.commit()

    manual_run = ScreenerRun(filter_json={"top_n": 20}, total=1)
    snapshot_run = ScreenerRun(
        filter_json={
            "snapshot_name": DEFAULT_SCREENER_SNAPSHOT_NAME,
            "snapshot_label": "Broker Accumulation Daily",
        },
        total=1,
    )
    db.add(manual_run)
    db.add(snapshot_run)
    db.commit()

    db.add(
        ScreenerResult(
            run_id=manual_run.id,
            ticker="MANL",
            name="Manual",
            composite=70.0,
            phase="Awal",
            dominant_factors={},
            rank=1,
        )
    )
    db.add(
        ScreenerResult(
            run_id=snapshot_run.id,
            ticker="SNAP",
            name="Snapshot",
            composite=85.0,
            phase="Siap Entry",
            dominant_factors={"broker_accumulation": {"status": "active"}},
            rank=1,
        )
    )
    db.commit()

    result = screener_routes.latest(db=db)

    assert result is not None
    assert result.filter["snapshot_name"] == DEFAULT_SCREENER_SNAPSHOT_NAME
    assert result.total == 1
    assert result.limit == 1
    assert result.results[0].ticker == "SNAP"


def test_screener_broker_backtest_route_returns_typed_payload():
    db = _make_session()
    ticker = "BTRO"
    db.add(Stock(ticker=ticker, name="Backtest Route", shares_outstanding=1_000_000_000))

    base_date = date(2026, 6, 1)
    for idx in range(26):
        close = 100 + idx
        current_date = base_date + timedelta(days=idx)
        db.add(
            DailyPrice(
                ticker=ticker,
                date=current_date,
                open=close,
                high=close,
                low=close,
                close=close,
                adj_close=close,
                volume=2_000_000_000,
                source="stockbit",
            )
        )
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=current_date,
                broker="AA",
                buy_value=300_000_000_000,
                sell_value=0,
                net_value=300_000_000_000,
            )
        )
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=current_date,
                broker="BB",
                buy_value=100_000_000_000,
                sell_value=0,
                net_value=100_000_000_000,
            )
        )
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=current_date,
                broker="CC",
                buy_value=0,
                sell_value=400_000_000_000,
                net_value=-400_000_000_000,
            )
        )
    db.commit()

    result = screener_routes.broker_backtest(
        period_days=30,
        lookback_days=40,
        universe="idx",
        min_label_score=0,
        sample_limit=1,
        db=db,
    )

    assert result.as_of_date == base_date + timedelta(days=25)
    assert result.horizons == [5, 10, 20]
    label = result.samples[0].label
    bucket = result.samples[0].liquidity_bucket
    assert label in result.summary_by_label
    assert result.summary_by_label[label]["5"].count >= 1
    assert result.samples[0].ticker == ticker
    assert bucket == "medium"
    assert result.samples[0].forward_returns_pct == {"5": 5.0, "10": 10.0, "20": 20.0}


def test_screener_broker_walkforward_route_returns_folded_payload():
    db = _make_session()
    ticker = "WFRO"
    db.add(Stock(ticker=ticker, name="Walkforward Route", shares_outstanding=1_000_000_000))

    base_date = date(2026, 4, 1)
    for idx in range(60):
        close = 100 + idx
        current_date = base_date + timedelta(days=idx)
        db.add(
            DailyPrice(
                ticker=ticker,
                date=current_date,
                open=close,
                high=close,
                low=close,
                close=close,
                adj_close=close,
                volume=2_000_000_000,
                source="stockbit",
            )
        )
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=current_date,
                broker="AA",
                buy_value=300_000_000_000,
                sell_value=0,
                net_value=300_000_000_000,
            )
        )
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=current_date,
                broker="BB",
                buy_value=100_000_000_000,
                sell_value=0,
                net_value=100_000_000_000,
            )
        )
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=current_date,
                broker="CC",
                buy_value=0,
                sell_value=400_000_000_000,
                net_value=-400_000_000_000,
            )
        )
    db.commit()

    result = screener_routes.broker_walkforward(
        period_days=30,
        lookback_days=50,
        fold_size_days=10,
        num_folds=3,
        universe="idx",
        min_label_score=0,
        sample_limit_per_fold=1,
        db=db,
    )

    assert result.as_of_date == base_date + timedelta(days=59)
    assert result.fold_size_days == 10
    assert result.num_folds == 3
    assert len(result.folds) == 3
    assert result.folds[0].signal_count >= 1
    assert result.folds[0].samples
    label = result.folds[0].samples[0].label
    assert label in result.folds[0].summary_by_label
