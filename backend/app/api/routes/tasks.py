"""Task-triggering routes (kick off data load, scoring, etc.)."""
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import BrokerFlowCoverageOut, PipelineRunOut, TaskOut
from app.core.db import get_db
from app.models.pipeline_run import PipelineRun
from app.services.data_loader import broker_flow_coverage_summary
from app.workers.tasks import (
    celery_app,
    run_daily_screener,
    run_broker_flow_backfill,
    run_daily_pipeline,
    run_full_data_load,
    run_recommendations_batch,
    run_recompute_signals,
    run_scoring_for_ticker,
    seed_stocks_task,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _enqueue(db: Session, task, task_name: str, args: list | None = None) -> TaskOut:
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
    return TaskOut(task_id=task_id, status="QUEUED")


@router.post("/data-load", response_model=TaskOut)
def trigger_data_load(
    ticker: str | None = None,
    incremental: bool = False,
    db: Session = Depends(get_db),
):
    return _enqueue(db, run_full_data_load, "data_load", [ticker, incremental])


@router.post("/scoring", response_model=TaskOut)
def trigger_scoring(ticker: str, db: Session = Depends(get_db)):
    return _enqueue(db, run_scoring_for_ticker, "scoring", [ticker])


@router.post("/daily-pipeline", response_model=TaskOut)
def trigger_pipeline(db: Session = Depends(get_db)):
    return _enqueue(db, run_daily_pipeline, "daily_pipeline")


@router.post("/seed-stocks", response_model=TaskOut)
def trigger_seed_stocks(db: Session = Depends(get_db)):
    return _enqueue(db, seed_stocks_task, "seed_stocks")


@router.post("/recommendations-batch", response_model=TaskOut)
def trigger_recommendations_batch(db: Session = Depends(get_db)):
    return _enqueue(db, run_recommendations_batch, "recommendations")


@router.post("/broker-flow-backfill", response_model=TaskOut)
def trigger_broker_flow_backfill(
    limit: int = Query(50, ge=1, le=200),
    period_days: int = Query(30, ge=7, le=120),
    universe: str = Query("idx"),
    db: Session = Depends(get_db),
):
    return _enqueue(db, run_broker_flow_backfill, "broker_flow_backfill", [limit, period_days, universe])


@router.get("/broker-flow-backfill/coverage", response_model=BrokerFlowCoverageOut)
def get_broker_flow_coverage(
    period_days: int = Query(30, ge=7, le=120),
    universe: str = Query("idx"),
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    summary = broker_flow_coverage_summary(db, period_days=period_days, universe=universe, limit=limit)
    return BrokerFlowCoverageOut(**summary)


@router.post("/broker-flow-backfill/{task_id}/retry", response_model=TaskOut)
def retry_broker_flow_backfill(task_id: str, db: Session = Depends(get_db)):
    run = db.execute(
        select(PipelineRun).where(PipelineRun.task_id == task_id)
    ).scalar_one_or_none()
    if not run or run.task_name != "broker_flow_backfill":
        raise HTTPException(404, "Broker flow backfill task not found")
    result = run.result or {}
    failed_tickers = sorted((result.get("errors") or {}).keys())
    if not failed_tickers:
        raise HTTPException(400, "Task has no failed tickers to retry")
    period_days = int(result.get("period_days") or 30)
    universe = str(result.get("universe") or "idx")
    failed_dates_by_ticker = {
        ticker: [item["date"] for item in (items or []) if item.get("date")]
        for ticker, items in (result.get("failed_dates_by_ticker") or {}).items()
    }
    return _enqueue(
        db,
        run_broker_flow_backfill,
        "broker_flow_backfill",
        [len(failed_tickers), period_days, universe, failed_tickers, failed_dates_by_ticker],
    )


@router.post("/daily-screener-snapshot", response_model=TaskOut)
def trigger_daily_screener_snapshot(db: Session = Depends(get_db)):
    return _enqueue(db, run_daily_screener, "daily_screener_snapshot")


@router.post("/recompute-signals", response_model=TaskOut)
def trigger_recompute(db: Session = Depends(get_db)):
    return _enqueue(db, run_recompute_signals, "recompute")


@router.get("/runs", response_model=list[PipelineRunOut])
def list_runs(
    limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)
):
    return (
        db.execute(select(PipelineRun).order_by(PipelineRun.id.desc()).limit(limit))
        .scalars()
        .all()
    )


@router.get("/{task_id}", response_model=PipelineRunOut)
def get_task_status(task_id: str, db: Session = Depends(get_db)):
    run = db.execute(
        select(PipelineRun).where(PipelineRun.task_id == task_id)
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Task not found")
    return run


@router.post("/{task_id}/cancel", response_model=TaskOut)
def cancel_task(task_id: str, db: Session = Depends(get_db)):
    run = db.execute(
        select(PipelineRun).where(PipelineRun.task_id == task_id)
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Task not found")
    if run.status not in ("QUEUED", "STARTED", "PROGRESS"):
        raise HTTPException(400, f"Task status '{run.status}' tidak bisa dibatalkan")
    celery_app.control.revoke(task_id, terminate=True)
    run.status = "CANCELLED"
    run.stage = "cancelled"
    run.finished_at = datetime.utcnow()
    db.commit()
    return TaskOut(task_id=task_id, status="CANCELLED")
