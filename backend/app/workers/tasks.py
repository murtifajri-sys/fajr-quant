"""Celery application, schedules, and persistently monitored tasks."""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from uuid import uuid4

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import log
from app.models.setting import TelegramSetting, WatchlistItem
from app.models.pipeline_run import PipelineRun
from app.models.price import DailyPrice
from app.models.stock import Stock
from app.services.market_regime import detect_regime
from app.services.notifier.telegram import send_digest
from app.services.recommendation_filter import is_recommendation_eligible
from app.services.screener.runner import (
    DEFAULT_SCREENER_SNAPSHOT_NAME,
    latest_screener_run,
    run_screener,
    run_screener_with_metadata,
)
from app.api.schemas import ScreenerFilter

celery_app = Celery(
    "fajr_quant",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_track_started=True,
    task_time_limit=60 * 60 * 3,
    beat_schedule={
        "recover-orphaned-runs": {
            "task": "recover_orphaned_runs_task",
            "schedule": crontab(minute="*/5"),
        },
        "daily-pipeline": {
            "task": "run_daily_pipeline",
            "schedule": crontab(hour=18, minute=0, day_of_week="1-5"),
        },
        "compute-regime": {
            "task": "compute_market_regime",
            "schedule": crontab(hour=17, minute=0, day_of_week="1-5"),
        },
        "broker-flow-backfill-evening": {
            "task": "run_broker_flow_backfill",
            "schedule": crontab(hour=19, minute=0, day_of_week="1-5"),
            "args": (50, 30, "idx"),
        },
        "broker-flow-backfill-evening-2": {
            "task": "run_broker_flow_backfill",
            "schedule": crontab(hour=19, minute=30, day_of_week="1-5"),
            "args": (50, 30, "idx"),
        },
        "daily-broker-screener-snapshot": {
            "task": "run_daily_screener",
            "schedule": crontab(hour=20, minute=0, day_of_week="1-5"),
        },
    },
    timezone="Asia/Jakarta",
)


@celery_app.task(bind=True, name="recover_orphaned_runs_task")
def recover_orphaned_runs_task(self):
    recover_orphaned_runs()
    return {"recovered": True}


def _on_worker_init(**kwargs):
    try:
        recover_orphaned_runs()
    except Exception as exc:  # never block worker boot
        log.warning("recover_orphaned_runs_failed", error=str(exc))


from celery.signals import worker_process_init

worker_process_init.connect(_on_worker_init)


def _db():
    return SessionLocal()


def _start_run(db, task_id: str, task_name: str) -> PipelineRun:
    run = db.execute(
        select(PipelineRun).where(PipelineRun.task_id == task_id)
    ).scalar_one_or_none()
    if not run:
        run = PipelineRun(task_id=task_id, task_name=task_name)
        db.add(run)
    run.status = "STARTED"
    run.stage = "starting"
    run.started_at = datetime.utcnow()
    run.error = None
    db.commit()
    return run


def _progress(db, run: PipelineRun, stage: str, processed: int, total: int, succeeded: int, failed: int):
    run.status = "PROGRESS"
    run.stage = stage
    run.processed_tickers = processed
    run.total_tickers = total
    run.succeeded_tickers = succeeded
    run.failed_tickers = failed
    run.progress = int(processed * 100 / total) if total else 0
    db.commit()


def _finish(db, run: PipelineRun, result: dict | None = None, error: str | None = None):
    run.status = "FAILURE" if error else "SUCCESS"
    run.stage = "failed" if error else "completed"
    run.progress = 100 if not error else run.progress
    run.result = result
    run.error = error
    run.finished_at = datetime.utcnow()
    db.commit()


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _enqueue_child(db, task, task_name: str, args: list | None = None) -> str:
    task_id = str(uuid4())
    db.add(
        PipelineRun(
            task_id=task_id,
            task_name=task_name,
            status="QUEUED",
            stage="waiting_for_worker",
        )
    )
    db.commit()
    task.apply_async(args=args or [], task_id=task_id)
    return task_id


ORPHAN_STALE_MINUTES = 10


def recover_orphaned_runs():
    """Mark runs stuck in STARTED/PROGRESS as ORPHANED.

    Runs whose worker was restarted mid-execution stay in a non-terminal
    state forever because no worker holds the task anymore. We only recover
    tasks that had already started execution; queued tasks may still be valid
    dependencies waiting on another linked task to finish.
    """
    from datetime import timedelta

    db = _db()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=ORPHAN_STALE_MINUTES)
        stale = db.execute(
            select(PipelineRun).where(
                PipelineRun.status.in_(["STARTED", "PROGRESS"]),
                PipelineRun.updated_at < cutoff,
            )
        ).scalars().all()
        for run in stale:
            run.status = "ORPHANED"
            run.stage = "orphaned"
            run.error = "Recovered: worker likely restarted; run was not terminal."
            run.finished_at = datetime.utcnow()
            log.warning(
                "pipeline_run_recovered",
                run_id=run.id,
                task_name=run.task_name,
                last_update=str(run.updated_at),
            )
        if stale:
            db.commit()
    finally:
        db.close()


@celery_app.task(bind=True, name="run_full_data_load")
def run_full_data_load(
    self,
    ticker: str | None = None,
    incremental: bool = False,
    universe: str = "watchlist",
):
    """Load data + run analysis for a single ticker or all watchlist/stocks."""
    from app.services.data_loader import load_prices
    from app.services.pipeline import run_full_analysis

    db = _db()
    task_id = self.request.id or str(uuid4())
    run = _start_run(db, task_id, "data_load")
    try:
        tickers = _select_data_load_tickers(db, ticker=ticker, universe=universe)
        run.total_tickers = len(tickers)
        db.commit()

        lock = threading.Lock()
        succeeded = 0
        failed = 0
        processed = 0
        errors = {}

        def process_ticker(current_ticker: str):
            local_db = _db()
            try:
                run_full_analysis(local_db, current_ticker, incremental=incremental)
                return (current_ticker, True, None)
            except Exception as exc:
                local_db.rollback()
                return (current_ticker, False, str(exc)[:500])
            finally:
                local_db.close()

        _progress(db, run, "processing", 0, len(tickers), 0, 0)
        with ThreadPoolExecutor(max_workers=settings.PIPELINE_MAX_WORKERS) as executor:
            futures = {executor.submit(process_ticker, t): t for t in tickers}
            for future in as_completed(futures):
                ticker_name, ok, err = future.result()
                with lock:
                    processed += 1
                    if ok:
                        succeeded += 1
                    else:
                        failed += 1
                        if err:
                            errors[ticker_name] = err
                    _progress(
                        db, run, "processing", processed, len(tickers),
                        succeeded, failed,
                    )
                self.update_state(
                    state="PROGRESS",
                    meta={"processed": processed, "total": len(tickers), "ticker": ticker_name},
                )

        result = {
            "processed": len(tickers),
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors,
        }
        _finish(db, run, result=result)
        return result
    except Exception as exc:
        db.rollback()
        _finish(db, run, error=str(exc))
        raise
    finally:
        db.close()


def _select_data_load_tickers(db, ticker: str | None = None, universe: str = "watchlist") -> list[str]:
    if ticker:
        return [ticker.upper()]
    if universe == "idx":
        return [
            s.ticker
            for s in db.execute(
                select(Stock)
                .order_by(Stock.ticker.asc())
                .limit(settings.DAILY_PIPELINE_MAX_TICKERS)
            ).scalars()
        ]

    tickers = [w.ticker for w in db.execute(select(WatchlistItem)).scalars()]
    if tickers:
        return tickers
    return [
        s.ticker
        for s in db.execute(
            select(Stock)
            .order_by(Stock.ticker.asc())
            .limit(settings.DAILY_PIPELINE_MAX_TICKERS)
        ).scalars()
    ]


@celery_app.task(bind=True, name="run_scoring_for_ticker")
def run_scoring_for_ticker(self, ticker: str):
    from app.services.pipeline import compute_score
    from app.services.ai.orchestrator import generate_recommendation
    db = _db()
    run = _start_run(db, self.request.id or str(uuid4()), "scoring")
    try:
        _progress(db, run, f"scoring:{ticker}", 0, 1, 0, 0)
        score = compute_score(db, ticker)
        eligible = False
        if score:
            eligible, metrics = is_recommendation_eligible(db, ticker)
            if eligible:
                generate_recommendation(db, ticker)
            else:
                log.info("scoring_recommendation_skipped", ticker=ticker, reason="liquidity_or_volatility_filter", metrics=metrics)
        result = {
            "ticker": ticker,
            "score": score.composite if score else None,
            "recommendation_generated": eligible,
        }
        _progress(db, run, f"scored:{ticker}", 1, 1, 1, 0)
        _finish(db, run, result=result)
        return result
    except Exception as exc:
        db.rollback()
        _finish(db, run, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="run_recommendations_batch")
def run_recommendations_batch(self):
    """Generate AI recommendations for all tickers that have scores but no recommendations today."""
    from app.models.recommendation import Recommendation
    from app.models.score import Score
    from app.services.ai.orchestrator import generate_recommendation
    from app.services.broker_accumulation import summarize_broker_window

    db = _db()
    run = _start_run(db, self.request.id or str(uuid4()), "recommendations")
    try:
        today = date.today()
        # Find tickers with scores today but no recommendations today,
        # limit to top N by composite score to save AI tokens.
        recd = {
            r[0] for r in db.execute(
                select(Recommendation.ticker).where(Recommendation.date == today).distinct()
            ).all()
        }
        scored_rows = db.execute(
            select(Score.ticker, Score.composite)
            .where(Score.date == today)
            .order_by(Score.composite.desc())
        ).all()

        # Filter by liquidity/volatility before taking top N, to avoid wasting AI tokens
        # on illiquid or very wicky stocks.
        candidate_tickers = [r[0] for r in scored_rows if r[0] not in recd]
        eligible_tickers = []
        skipped = {}
        shortlist_limit = max(settings.RECOMMENDATION_MAX_TICKERS * 5, 25)
        for t in candidate_tickers:
            eligible, metrics = is_recommendation_eligible(db, t)
            if eligible:
                eligible_tickers.append(t)
            else:
                skipped[t] = metrics
            if len(eligible_tickers) >= shortlist_limit:
                break

        ranked_candidates = []
        composite_map = {ticker: float(composite) for ticker, composite in scored_rows}
        for ticker_name in eligible_tickers:
            broker = summarize_broker_window(db, ticker_name, 30, as_of_date=today)
            conviction = float((broker or {}).get("broker_conviction_score") or 0.0)
            flow_quality = float((broker or {}).get("flow_quality_score") or 0.0)
            retail_penalty = 20.0 if (broker or {}).get("high_freq_low_value") else 0.0
            score = (
                (composite_map.get(ticker_name, 0.0) * 0.50)
                + (conviction * 0.35)
                + (flow_quality * 0.15)
                - retail_penalty
            )
            ranked_candidates.append((score, ticker_name))
        ranked_candidates.sort(key=lambda item: item[0], reverse=True)
        tickers = [ticker_name for _, ticker_name in ranked_candidates[: settings.RECOMMENDATION_MAX_TICKERS]]
        if not tickers:
            msg = "No eligible tickers for recommendations (liquidity/volatility filters or all already have recommendations)"
            result = {"ok": True, "message": msg, "skipped": {k: str(v) for k, v in skipped.items()}}
            _finish(db, run, result=result)
            return result

        run.total_tickers = len(tickers)
        db.commit()

        lock = threading.Lock()
        succeeded = 0
        failed = 0
        processed = 0
        errors = {}

        def process_ticker(current_ticker: str):
            local_db = _db()
            try:
                generate_recommendation(local_db, current_ticker)
                return (current_ticker, True, None)
            except Exception as exc:
                local_db.rollback()
                return (current_ticker, False, str(exc)[:500])
            finally:
                local_db.close()

        _progress(db, run, "generating", 0, len(tickers), 0, 0)
        with ThreadPoolExecutor(max_workers=settings.PIPELINE_MAX_WORKERS) as executor:
            futures = {executor.submit(process_ticker, t): t for t in tickers}
            for future in as_completed(futures):
                ticker_name, ok, err = future.result()
                with lock:
                    processed += 1
                    if ok:
                        succeeded += 1
                    else:
                        failed += 1
                        if err:
                            errors[ticker_name] = err
                    _progress(
                        db, run, "generating", processed, len(tickers),
                        succeeded, failed,
                    )

        result = {
            "processed": len(tickers),
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors,
        }
        _finish(db, run, result=result)
        return result
    except Exception as exc:
        db.rollback()
        _finish(db, run, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="run_broker_flow_backfill")
def run_broker_flow_backfill(
    self,
    limit: int = 50,
    period_days: int = 30,
    universe: str = "idx",
    tickers: list[str] | None = None,
    retry_dates_by_ticker: dict[str, list[str]] | None = None,
):
    """Backfill broker flow cache in bounded batches for broker-accumulation screener."""
    from sqlalchemy import func

    from app.models.broker_flow import BrokerFlow
    from app.services.data_loader import backfill_broker_flow_for_ticker, broker_flow_coverage_summary

    db = _db()
    run = _start_run(db, self.request.id or str(uuid4()), "broker_flow_backfill")
    try:
        period_days = max(1, min(int(period_days or 30), 120))
        limit = max(1, min(int(limit or 50), 200))
        selected_tickers = sorted({str(t).upper() for t in (tickers or []) if t})
        retry_dates_by_ticker = {
            str(ticker).upper(): [str(d) for d in (dates or [])]
            for ticker, dates in (retry_dates_by_ticker or {}).items()
            if ticker
        }
        coverage_before = broker_flow_coverage_summary(
            db,
            period_days=period_days,
            universe=universe,
            tickers=selected_tickers or None,
            limit=limit,
        )

        latest_market_date = db.execute(select(func.max(DailyPrice.date))).scalar()
        if not latest_market_date:
            result = {
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "errors": {},
                "message": "no_price_data",
                "period_days": period_days,
                "universe": universe,
                "requested_tickers": selected_tickers,
                "retry_dates_by_ticker": retry_dates_by_ticker,
                "failed_tickers": [],
                "coverage_before": coverage_before,
                "coverage_after": coverage_before,
            }
            _finish(db, run, result=result)
            return result
        start_date = latest_market_date - timedelta(days=period_days)
        trading_counts = (
            select(DailyPrice.ticker, func.count(func.distinct(DailyPrice.date)).label("trading_days"))
            .where(DailyPrice.date >= start_date, DailyPrice.date <= latest_market_date)
            .group_by(DailyPrice.ticker)
            .subquery()
        )
        flow_counts = (
            select(BrokerFlow.ticker, func.count(func.distinct(BrokerFlow.date)).label("flow_days"))
            .where(BrokerFlow.date >= start_date, BrokerFlow.date <= latest_market_date)
            .group_by(BrokerFlow.ticker)
            .subquery()
        )

        if selected_tickers:
            tickers_to_process = selected_tickers
        else:
            stmt = (
                select(
                    Stock.ticker,
                    func.coalesce(flow_counts.c.flow_days, 0).label("flow_days"),
                    trading_counts.c.trading_days,
                )
                .join(trading_counts, Stock.ticker == trading_counts.c.ticker)
                .outerjoin(flow_counts, Stock.ticker == flow_counts.c.ticker)
                .where(func.coalesce(flow_counts.c.flow_days, 0) < trading_counts.c.trading_days)
                .order_by(func.coalesce(flow_counts.c.flow_days, 0).asc(), Stock.ticker.asc())
                .limit(limit)
            )
            if universe == "watchlist":
                watch = select(WatchlistItem.ticker).subquery()
                stmt = stmt.where(Stock.ticker.in_(select(watch.c.ticker)))
            tickers_to_process = [r[0] for r in db.execute(stmt).all()]
        run.total_tickers = len(tickers_to_process)
        db.commit()

        if not tickers_to_process:
            result = {
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "errors": {},
                "message": "broker_flow_cache_complete",
                "period_days": period_days,
                "universe": universe,
                "requested_tickers": [],
                "retry_dates_by_ticker": retry_dates_by_ticker,
                "failed_tickers": [],
                "coverage_before": coverage_before,
                "coverage_after": coverage_before,
            }
            _finish(db, run, result=result)
            return result

        succeeded = 0
        failed = 0
        errors = {}
        fetched_dates = 0
        failed_dates_by_ticker = {}
        empty_source_dates_by_ticker = {}
        _progress(db, run, "backfilling", 0, len(tickers_to_process), 0, 0)

        for processed, ticker in enumerate(tickers_to_process, start=1):
            try:
                target_dates = None
                if ticker in retry_dates_by_ticker:
                    target_dates = [
                        datetime.fromisoformat(value).date()
                        for value in retry_dates_by_ticker[ticker]
                    ]
                info = backfill_broker_flow_for_ticker(
                    db,
                    ticker,
                    period_days=period_days,
                    target_dates=target_dates,
                )
                fetched_dates += int(info.get("fetched_dates") or 0)
                if info.get("failed_dates"):
                    failed_dates_by_ticker[ticker] = info.get("failed_dates")
                if info.get("empty_source_dates"):
                    empty_source_dates_by_ticker[ticker] = info.get("empty_source_dates")
                succeeded += 1 if info.get("ok") else 0
                if not info.get("ok"):
                    failed += 1
                    errors[ticker] = info.get("reason", "unknown")
            except Exception as exc:
                db.rollback()
                failed += 1
                errors[ticker] = str(exc)[:500]
            _progress(db, run, f"backfilled:{ticker}", processed, len(tickers_to_process), succeeded, failed)
            self.update_state(
                state="PROGRESS",
                meta={"processed": processed, "total": len(tickers_to_process), "ticker": ticker},
            )

        coverage_after = broker_flow_coverage_summary(
            db,
            period_days=period_days,
            universe=universe,
            tickers=tickers_to_process,
            limit=max(len(tickers_to_process), limit),
        )

        result = {
            "processed": len(tickers_to_process),
            "succeeded": succeeded,
            "failed": failed,
            "fetched_dates": fetched_dates,
            "period_days": period_days,
            "universe": universe,
            "requested_tickers": tickers_to_process,
            "retry_dates_by_ticker": retry_dates_by_ticker,
            "failed_tickers": sorted(errors.keys()),
            "failed_dates_by_ticker": failed_dates_by_ticker,
            "empty_source_dates_by_ticker": empty_source_dates_by_ticker,
            "errors": errors,
            "coverage_before": coverage_before,
            "coverage_after": coverage_after,
        }
        result = _json_safe(result)
        _finish(db, run, result=result)
        return result
    except Exception as exc:
        db.rollback()
        _finish(db, run, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="run_ipo_majorholder_refresh")
def run_ipo_majorholder_refresh(self, limit: int = 50, tickers: list[str] | None = None):
    """Refresh major-holder cache for IPO/new-listing tickers only."""
    from app.services.ipo_major_holder import refresh_ipo_major_holders

    db = _db()
    run = _start_run(db, self.request.id or str(uuid4()), "ipo_majorholder_refresh")
    try:
        selected_tickers = sorted({str(t).upper() for t in (tickers or []) if t}) if tickers else None
        total = len(selected_tickers) if selected_tickers else 1
        _progress(db, run, "refreshing_ipo_majorholders", 0, total, 0, 0)
        result = refresh_ipo_major_holders(db, limit=limit, tickers=selected_tickers)
        _progress(
            db,
            run,
            "completed_with_ticker_errors" if result.get("failed") else "completed",
            result.get("processed") or 0,
            result.get("processed") or 0,
            result.get("succeeded") or 0,
            result.get("failed") or 0,
        )
        _finish(db, run, result=_json_safe(result))
        return _json_safe(result)
    except Exception as exc:
        db.rollback()
        _finish(db, run, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="run_recompute_signals")
def run_recompute_signals(self):
    """Recompute technical + bandarmology + scores for all tickers (no data download)."""
    from app.models.price import DailyPrice
    from app.services.data_loader import load_bandar_flow
    from app.services.pipeline import compute_bandar, compute_score, compute_technical
    from app.services.smart_money import detect_smart_money

    db = _db()
    run = _start_run(db, self.request.id or str(uuid4()), "recompute")
    try:
        tickers = sorted(
            r[0] for r in db.execute(
                select(DailyPrice.ticker).distinct()
            ).all()
        )
        if not tickers:
            _finish(db, run, result={"ok": True, "message": "No data to recompute"})
            return {"ok": True}

        run.total_tickers = len(tickers)
        db.commit()

        lock = threading.Lock()
        succeeded = 0
        failed = 0
        processed = 0
        errors = {}

        def process_ticker(current_ticker: str):
            local_db = _db()
            try:
                flow = load_bandar_flow(local_db, current_ticker)
                compute_technical(local_db, current_ticker)
                compute_bandar(local_db, current_ticker, flow)
                compute_score(local_db, current_ticker)
                detect_smart_money(local_db, current_ticker)
                return (current_ticker, True, None)
            except Exception as exc:
                local_db.rollback()
                return (current_ticker, False, str(exc)[:500])
            finally:
                local_db.close()

        _progress(db, run, "computing", 0, len(tickers), 0, 0)
        with ThreadPoolExecutor(max_workers=settings.PIPELINE_MAX_WORKERS) as executor:
            futures = {executor.submit(process_ticker, t): t for t in tickers}
            for future in as_completed(futures):
                ticker_name, ok, err = future.result()
                with lock:
                    processed += 1
                    if ok:
                        succeeded += 1
                    else:
                        failed += 1
                        if err:
                            errors[ticker_name] = err
                    _progress(
                        db, run, "computing", processed, len(tickers),
                        succeeded, failed,
                    )

        result = {
            "processed": len(tickers),
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors,
        }
        _finish(db, run, result=result)
        return result
    except Exception as exc:
        db.rollback()
        _finish(db, run, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="run_daily_pipeline")
def run_daily_pipeline(self):
    """End-of-day pipeline: regime, full data load, scoring, telegram digest."""
    from app.clients.yfinance import YFinanceClient
    from app.models.market_regime import MarketRegime

    db = _db()
    run = _start_run(db, self.request.id or str(uuid4()), "daily_pipeline")
    try:
        _progress(db, run, "market_regime", 0, 1, 0, 0)
        # Market regime from benchmark
        bm = YFinanceClient().get_benchmark_prices("^JKSE", start=date(2000, 1, 1))
        regime = {"regime": "unknown"}
        if bm:
            import pandas as pd

            regime = detect_regime(pd.DataFrame(bm))
            existing = db.get(MarketRegime, date.today())
            if existing:
                existing.regime = regime["regime"]
                existing.meta = regime["meta"]
            else:
                db.add(
                    MarketRegime(
                        date=date.today(),
                        benchmark="^JKSE",
                        regime=regime["regime"],
                        meta=regime["meta"],
                    )
                )
            db.commit()

        # Data load (which also produces today's scores) runs first; recommendations
        # are chained to run only after data_load succeeds, so scores exist.
        data_task_id = str(uuid4())
        db.add(
            PipelineRun(
                task_id=data_task_id,
                task_name="data_load",
                status="QUEUED",
                stage="waiting_for_worker",
            )
        )
        rec_task_id = str(uuid4())
        db.add(
            PipelineRun(
                task_id=rec_task_id,
                task_name="recommendations",
                status="QUEUED",
                stage="waiting_for_worker",
            )
        )
        holder_task_id = str(uuid4())
        db.add(
            PipelineRun(
                task_id=holder_task_id,
                task_name="ipo_majorholder_refresh",
                status="QUEUED",
                stage="waiting_for_worker",
            )
        )
        db.commit()
        run_full_data_load.apply_async(
            args=[None, True, "idx"],
            task_id=data_task_id,
            link=run_ipo_majorholder_refresh.si().set(task_id=holder_task_id)
                 .set(link=run_recommendations_batch.si().set(task_id=rec_task_id)
                 .set(link=run_daily_screener.si().set(link=send_daily_digest.si()))),
        )
        result = {
            "ok": True,
            "regime": regime.get("regime"),
            "data_load_task_id": data_task_id,
            "ipo_majorholder_task_id": holder_task_id,
            "recommendations_task_id": rec_task_id,
        }
        _progress(db, run, "data_load_queued", 1, 1, 1, 0)
        _finish(db, run, result=result)
        return result
    except Exception as exc:
        db.rollback()
        _finish(db, run, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(name="run_daily_screener")
def run_daily_screener():
    """Refresh the top-screener snapshot used by the daily Telegram digest."""
    db = _db()
    try:
        snapshot_filter = ScreenerFilter(
            require_broker_accumulation=True,
            broker_period_days=30,
            min_broker_net_pct_mcap=0.05,
            min_broker_net_pct_adv=0.5,
            min_broker_active_days=3,
            min_broker_positive_ratio=0.5,
            min_broker_coverage_ratio=0.8,
            min_broker_conviction_score=55,
            min_entry_readiness_score=45,
            sort_by="combined_rank",
            broker_rank_weight=0.7,
            entry_rank_weight=0.3,
            top_n=20,
        )
        result = run_screener_with_metadata(
            db,
            snapshot_filter,
            run_metadata={
                "snapshot_name": DEFAULT_SCREENER_SNAPSHOT_NAME,
                "snapshot_label": "Broker Accumulation Daily",
            },
        )
        return {"ok": True, "run_id": result.run_id}
    finally:
        db.close()


@celery_app.task(name="send_daily_digest")
def send_daily_digest():
    from app.models.recommendation import Recommendation

    db = _db()
    try:
        settings_rows = db.execute(select(TelegramSetting).where(TelegramSetting.enabled.is_(True))).scalars().all()
        if not settings_rows:
            return {"skipped": "no_telegram_settings"}
        # Latest recommendations
        recs = db.execute(
            select(Recommendation).order_by(Recommendation.date.desc(), Recommendation.id.desc()).limit(10)
        ).scalars().all()
        rec_dicts = [
            {
                "ticker": r.ticker,
                "action": r.action,
                "entry": r.entry,
                "stop": r.stop,
                "target": r.target,
                "rationale": r.rationale,
            }
            for r in recs
        ]
        # Top screener (latest run)
        from app.models.screener import ScreenerResult, ScreenerRun

        run = latest_screener_run(db, DEFAULT_SCREENER_SNAPSHOT_NAME)
        screen_dicts = []
        if run:
            rows = db.execute(
                select(ScreenerResult).where(ScreenerResult.run_id == run.id).order_by(ScreenerResult.rank.asc()).limit(10)
            ).scalars().all()
            screen_dicts = [
                {"ticker": r.ticker, "name": r.name, "composite": r.composite, "phase": r.phase}
                for r in rows
            ]
        ok = []
        for s in settings_rows:
            ok.append(send_digest(s.chat_id, rec_dicts, screen_dicts))
        return {"sent": ok}
    finally:
        db.close()


@celery_app.task(name="compute_market_regime")
def compute_market_regime():
    from app.clients.yfinance import YFinanceClient
    from app.models.market_regime import MarketRegime

    import pandas as pd

    db = _db()
    try:
        bm = YFinanceClient().get_benchmark_prices("^JKSE", start=date(2000, 1, 1))
        if not bm:
            return {"ok": False}
        regime = detect_regime(pd.DataFrame(bm))
        existing = db.get(MarketRegime, date.today())
        if existing:
            existing.regime = regime["regime"]
            existing.meta = regime["meta"]
        else:
            db.add(
                MarketRegime(
                    date=date.today(), benchmark="^JKSE", regime=regime["regime"], meta=regime["meta"]
                )
            )
        db.commit()
        return {"ok": True, "regime": regime["regime"]}
    finally:
        db.close()


@celery_app.task(bind=True, name="seed_stocks_task")
def seed_stocks_task(self):
    from app.scripts.seed_stocks import seed_stocks

    db = _db()
    run = _start_run(db, self.request.id or str(uuid4()), "seed_stocks")
    try:
        _progress(db, run, "importing_stock_list", 0, 1, 0, 0)
        result = seed_stocks(db)
        _progress(db, run, "stock_list_imported", 1, 1, 1, 0)
        _finish(db, run, result=result)
        return result
    except Exception as exc:
        db.rollback()
        _finish(db, run, error=str(exc))
        raise
    finally:
        db.close()
