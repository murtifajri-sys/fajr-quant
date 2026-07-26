"""Screener routes: run filters, fetch results."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    BrokerLabelBacktestOut,
    BrokerLabelWalkforwardOut,
    BrokerTickerDetailOut,
    ScreenerFilter,
    ScreenerResultRow,
    ScreenerRunOut,
    TradeCandidateAnalysisOut,
    TradeCandidatePromptOut,
    TradeCandidatePromptRequest,
)
from app.core.logging import log
from app.core.db import get_db
from app.services.ai.deepseek import get_provider
from app.services.ai.trade_candidate_prompt import (
    TRADE_CANDIDATE_SYSTEM_PROMPT,
    build_trade_candidate_prompt,
)
from app.services.screener.runner import (
    DEFAULT_SCREENER_SNAPSHOT_NAME,
    build_broker_ticker_detail,
    build_trade_monitor_candidates,
    latest_screener_run,
    run_screener,
)
from app.services.screener.backtest import run_broker_label_backtest, run_broker_label_walkforward

router = APIRouter(prefix="/screener", tags=["screener"])


@router.post("/run", response_model=ScreenerRunOut)
def run(filt: ScreenerFilter, db: Session = Depends(get_db)):
    result = run_screener(db, filt)
    return result


@router.get("/latest", response_model=ScreenerRunOut | None)
def latest(db: Session = Depends(get_db)):
    from app.models.screener import ScreenerResult

    run_row = latest_screener_run(db, DEFAULT_SCREENER_SNAPSHOT_NAME)
    if not run_row:
        return None
    results = (
        db.execute(
            select(ScreenerResult)
            .where(ScreenerResult.run_id == run_row.id)
            .order_by(ScreenerResult.rank.asc())
        )
        .scalars()
        .all()
    )
    result_meta = (run_row.filter_json or {}).get("result_meta") or {}
    return ScreenerRunOut(
        run_id=run_row.id,
        created_at=run_row.created_at,
        filter=run_row.filter_json,
        total=run_row.total,
        limit=int(result_meta.get("limit") or len(results)),
        offset=int(result_meta.get("offset") or 0),
        has_more=bool(result_meta.get("has_more") or False),
        coverage_summary=(run_row.filter_json or {}).get("coverage_summary"),
        results=[ScreenerResultRow(**r.as_dict()) for r in results],
    )


@router.get("/trade-monitor", response_model=list[ScreenerResultRow])
def trade_monitor(
    limit: int = Query(12, ge=1, le=50),
    universe: str = Query("idx", pattern="^(idx|watchlist)$"),
    max_scan: int = Query(300, ge=50, le=1000),
    broker_period_days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
):
    return [
        ScreenerResultRow(**row)
        for row in build_trade_monitor_candidates(
            db,
            limit=limit,
            universe=universe,
            max_scan=max_scan,
            broker_period_days=broker_period_days,
        )
    ]


@router.post("/trade-candidates-prompt", response_model=TradeCandidatePromptOut)
def trade_candidates_prompt(payload: TradeCandidatePromptRequest):
    candidates = payload.candidates[: payload.max_candidates]
    return TradeCandidatePromptOut(
        prompt=build_trade_candidate_prompt(candidates, max_candidates=payload.max_candidates),
        candidate_count=len(candidates),
    )


@router.post("/trade-candidates-analysis", response_model=TradeCandidateAnalysisOut)
def trade_candidates_analysis(payload: TradeCandidatePromptRequest):
    candidates = payload.candidates[: payload.max_candidates]
    prompt = build_trade_candidate_prompt(candidates, max_candidates=payload.max_candidates)
    provider = get_provider()
    try:
        result = provider.complete(TRADE_CANDIDATE_SYSTEM_PROMPT, prompt)
    except Exception as e:
        log.error("trade_candidate_ai_error", error=str(e)[:300])
        raise HTTPException(502, "AI analysis failed")
    used_provider = getattr(provider, "active_provider", provider) or provider
    return TradeCandidateAnalysisOut(
        content=result.get("content") or {},
        provider=used_provider.name,
        candidate_count=len(candidates),
    )


@router.get("/broker/{ticker}", response_model=BrokerTickerDetailOut)
def broker_detail(
    ticker: str,
    accumulation_min_score: float | None = Query(None, ge=0, le=100),
    big_accumulation_min_score: float | None = Query(None, ge=0, le=100),
    aggressive_accumulation_min_score: float | None = Query(None, ge=0, le=100),
    broker_rank_weight: float = Query(0.7, ge=0, le=1),
    entry_rank_weight: float = Query(0.3, ge=0, le=1),
    db: Session = Depends(get_db),
):
    detail = build_broker_ticker_detail(
        db,
        ticker,
        score_config={
            "accumulation_min_score": accumulation_min_score,
            "big_accumulation_min_score": big_accumulation_min_score,
            "aggressive_accumulation_min_score": aggressive_accumulation_min_score,
        },
        broker_rank_weight=broker_rank_weight,
        entry_rank_weight=entry_rank_weight,
    )
    if not detail:
        raise HTTPException(404, "Broker detail not found")
    return BrokerTickerDetailOut(**detail)


@router.get("/backtest/broker-accumulation", response_model=BrokerLabelBacktestOut)
def broker_backtest(
    period_days: int = Query(30, ge=7, le=90),
    lookback_days: int = Query(120, ge=30, le=365),
    universe: str = Query("idx", pattern="^(idx|watchlist)$"),
    min_label_score: float | None = Query(None, ge=0, le=100),
    sample_limit: int = Query(50, ge=0, le=200),
    db: Session = Depends(get_db),
):
    result = run_broker_label_backtest(
        db,
        period_days=period_days,
        lookback_days=lookback_days,
        universe=universe,
        min_label_score=min_label_score,
        sample_limit=sample_limit,
    )
    return BrokerLabelBacktestOut(**result)


@router.get("/backtest/broker-accumulation/walk-forward", response_model=BrokerLabelWalkforwardOut)
def broker_walkforward(
    period_days: int = Query(30, ge=7, le=90),
    lookback_days: int = Query(180, ge=30, le=540),
    fold_size_days: int = Query(30, ge=5, le=120),
    num_folds: int = Query(3, ge=2, le=12),
    universe: str = Query("idx", pattern="^(idx|watchlist)$"),
    min_label_score: float | None = Query(None, ge=0, le=100),
    sample_limit_per_fold: int = Query(5, ge=0, le=50),
    db: Session = Depends(get_db),
):
    result = run_broker_label_walkforward(
        db,
        period_days=period_days,
        lookback_days=lookback_days,
        fold_size_days=fold_size_days,
        num_folds=num_folds,
        universe=universe,
        min_label_score=min_label_score,
        sample_limit_per_fold=sample_limit_per_fold,
    )
    return BrokerLabelWalkforwardOut(**result)


@router.get("/{run_id}", response_model=ScreenerRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    from app.models.screener import ScreenerResult, ScreenerRun

    run_row = db.get(ScreenerRun, run_id)
    if not run_row:
        raise HTTPException(404, "Run not found")
    results = (
        db.execute(
            select(ScreenerResult)
            .where(ScreenerResult.run_id == run_id)
            .order_by(ScreenerResult.rank.asc())
        )
        .scalars()
        .all()
    )
    result_meta = (run_row.filter_json or {}).get("result_meta") or {}
    return ScreenerRunOut(
        run_id=run_row.id,
        created_at=run_row.created_at,
        filter=run_row.filter_json,
        total=run_row.total,
        limit=int(result_meta.get("limit") or len(results)),
        offset=int(result_meta.get("offset") or 0),
        has_more=bool(result_meta.get("has_more") or False),
        coverage_summary=(run_row.filter_json or {}).get("coverage_summary"),
        results=[ScreenerResultRow(**r.as_dict()) for r in results],
    )
