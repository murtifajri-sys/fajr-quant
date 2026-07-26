"""Pydantic schemas for API request/response."""
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---- Token ----
class TokenCreate(BaseModel):
    label: str = "default"
    token: str
    expires_at: Optional[datetime] = None


class TokenOut(BaseModel):
    id: int
    label: str
    expires_at: Optional[datetime]
    active: bool
    last_used_at: Optional[datetime]
    last_error: Optional[str]
    token_preview: str  # last 12 chars only
    status: str
    is_expired: bool
    warning: Optional[str] = None

    class Config:
        from_attributes = True


# ---- Telegram ----
class TelegramSettingCreate(BaseModel):
    label: str = "default"
    chat_id: str
    enabled: bool = True
    daily_digest_time: str = "17:30"


class TelegramSettingOut(TelegramSettingCreate):
    id: int
    class Config:
        from_attributes = True


# ---- Stock ----
class StockOut(BaseModel):
    ticker: str
    name: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    board: Optional[str]
    exchange: Optional[str] = "IDX"
    listing_date: Optional[date] = None
    class Config:
        from_attributes = True


class WatchlistItemCreate(BaseModel):
    name: str = "default"
    ticker: str
    sort_order: int = 0


class WatchlistItemOut(BaseModel):
    id: int
    name: str
    ticker: str
    sort_order: int

    class Config:
        from_attributes = True


# ---- Price ----
class PriceOut(BaseModel):
    ticker: str
    date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[float]
    source: str
    class Config:
        from_attributes = True


# ---- Smart Money ----
class SmartMoneySignalOut(BaseModel):
    ticker: str
    date: date
    detected: bool
    score: Optional[float]
    bandar_score: Optional[float]
    foreign_score: Optional[float]
    bandar_lookback: Optional[int]
    foreign_lookback: Optional[int]
    reasons: Optional[Any] = None
    class Config:
        from_attributes = True


# ---- Foreign Flow ----
class ForeignFlowOut(BaseModel):
    ticker: str
    date: date
    foreign_buy: Optional[float]
    foreign_sell: Optional[float]
    net_foreign: Optional[float]
    net_foreign_pct: Optional[float]
    score: Optional[float]
    pct_market_cap: Optional[float] = None
    pct_avg_daily_value: Optional[float] = None
    class Config:
        from_attributes = True


# ---- Technical / Bandar ----
class SignalOut(BaseModel):
    ticker: str
    date: date
    method: Optional[str] = None
    label: Optional[str] = None
    name: Optional[str] = None
    detected: Optional[bool] = None
    value: Optional[float] = None
    score: Optional[float] = None
    payload: Optional[Any] = None
    flow_value: Optional[float] = None
    pct_market_cap: Optional[float] = None
    pct_avg_daily_value: Optional[float] = None
    class Config:
        from_attributes = True


# ---- Score ----
class ScoreOut(BaseModel):
    id: int
    ticker: str
    date: date
    composite: float
    sub_scores: dict
    weights: dict
    phase: str
    confidence: float
    dominant_factors: dict
    class Config:
        from_attributes = True


# ---- Data Explorer ----
class PaginatedResponse(BaseModel):
    items: list
    total: int
    limit: int
    offset: int


# ---- Recommendation ----
class RecommendationOut(BaseModel):
    ticker: str
    date: date
    action: str
    entry: Optional[float]
    stop: Optional[float]
    target: Optional[float]
    rationale: Optional[str]
    dominant_factors: Optional[Any] = None
    risks: Optional[Any] = None
    provider: str
    class Config:
        from_attributes = True


# ---- Screener ----
class ScreenerFilter(BaseModel):
    methods: list[str] = Field(default_factory=list)  # technical methods to require
    bandar_labels: list[str] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)
    min_composite: Optional[float] = None
    require_foreign_inflow: bool = False
    require_smart_money: bool = False
    min_smart_money_score: Optional[float] = None
    regime: Optional[str] = None
    universe: str = "idx"  # idx | watchlist
    top_n: int = 20
    offset: int = 0
    breakout_filter: bool = False  # filter by breakout conditions (EMA x RSI x volume)
    require_broker_accumulation: bool = False
    broker_period_days: int = 30
    min_broker_net_pct_mcap: Optional[float] = None
    min_broker_net_pct_adv: Optional[float] = None
    min_broker_active_days: Optional[int] = None
    min_broker_positive_ratio: Optional[float] = None
    min_broker_coverage_ratio: Optional[float] = None
    max_broker_balance_ratio: Optional[float] = None
    min_broker_conviction_score: Optional[float] = None
    min_entry_readiness_score: Optional[float] = None
    exclude_stale: bool = False
    exclude_reversal_risk: bool = True
    exclude_insufficient_data: bool = True
    require_recent: bool = False
    require_acceleration: bool = False
    require_cluster_confirmation: bool = False
    sort_by: str = "combined_rank"  # combined_rank | broker_conviction | entry_readiness | composite
    broker_rank_weight: float = 0.7
    entry_rank_weight: float = 0.3
    broker_score_config: Optional[dict] = None


class ScreenerResultRow(BaseModel):
    ticker: str
    name: Optional[str]
    composite: float
    phase: str
    dominant_factors: dict
    broker_conviction_score: Optional[float] = None
    broker_conviction_label: Optional[str] = None
    flow_quality_score: Optional[float] = None
    flow_quality_label: Optional[str] = None
    entry_readiness_score: Optional[float] = None
    combined_rank_score: Optional[float] = None
    broker_status: Optional[str] = None
    setup_detail: Optional[dict] = None
    closest_to_smart_rank: Optional[int] = None
    closest_to_smart_score: Optional[float] = None
    rank: int


class ScreenerRunOut(BaseModel):
    run_id: int
    created_at: datetime
    filter: dict
    total: int = 0
    limit: int = 0
    offset: int = 0
    has_more: bool = False
    coverage_summary: Optional[dict] = None
    results: list[ScreenerResultRow]


class IpoScreenerRowOut(BaseModel):
    ticker: str
    name: Optional[str] = None
    board: Optional[str] = None
    listing_date: date
    calendar_age_days: int
    trading_session_age: int
    phase: str
    status: str
    setup_type: str
    ipo_setup_score: float
    last_price: Optional[float] = None
    last_price_date: Optional[date] = None
    avg_value_5: float
    opening_range_high: Optional[float] = None
    opening_range_low: Optional[float] = None
    anchored_vwap: Optional[float] = None
    base_high: Optional[float] = None
    base_low: Optional[float] = None
    base_width_pct: Optional[float] = None
    volume_ratio: Optional[float] = None
    broker_flow: dict
    holder_risk: Optional[dict] = None
    levels: dict
    blockers: list[str]


class IpoScreenerOut(BaseModel):
    as_of_date: date
    max_calendar_age_days: int
    total: int
    results: list[IpoScreenerRowOut]


class IpoScreenerDetailOut(IpoScreenerRowOut):
    recent_prices: list[dict]
    watchlist_names: list[str] = Field(default_factory=list)


class IpoScreenerPromptRequest(BaseModel):
    candidates: list[dict]
    max_candidates: int = Field(default=10, ge=1, le=10)


class TradeCandidatePromptRequest(BaseModel):
    candidates: list[dict]
    max_candidates: int = Field(default=10, ge=1, le=10)


class TradeCandidatePromptOut(BaseModel):
    prompt: str
    candidate_count: int


class TradeCandidateAnalysisOut(BaseModel):
    content: dict
    provider: str
    candidate_count: int


class BrokerTickerDetailOut(BaseModel):
    ticker: str
    as_of_date: date
    latest_score_date: Optional[date] = None
    broker_conviction: dict
    flow_quality: dict
    entry_readiness: dict
    setup_detail: dict
    one_week: dict
    one_month: dict
    comparison: dict


class BrokerFlowCoverageItemOut(BaseModel):
    ticker: str
    trading_days: int
    flow_days: int
    missing_days: int
    coverage_ratio: float
    status: str


class BrokerFlowCoverageOut(BaseModel):
    as_of_date: Optional[date] = None
    period_days: int
    universe: str
    total_tickers: int
    complete_tickers: int
    partial_tickers: int
    missing_tickers: int
    average_coverage_ratio: float
    items: list[BrokerFlowCoverageItemOut]


class BacktestReturnSummaryOut(BaseModel):
    count: int
    avg_return_pct: Optional[float] = None
    median_return_pct: Optional[float] = None
    win_rate: Optional[float] = None


class BrokerBacktestSampleOut(BaseModel):
    ticker: str
    date: date
    label: str
    score: Optional[float] = None
    status: Optional[str] = None
    liquidity_bucket: str
    forward_returns_pct: dict[str, Optional[float]]


class BrokerLabelBacktestOut(BaseModel):
    as_of_date: Optional[date] = None
    period_days: int
    lookback_days: int
    universe: str
    horizons: list[int]
    summary_by_label: dict[str, dict[str, BacktestReturnSummaryOut]]
    summary_by_label_and_liquidity: dict[str, dict[str, dict[str, BacktestReturnSummaryOut]]]
    samples: list[BrokerBacktestSampleOut]


class BrokerWalkforwardFoldOut(BaseModel):
    fold_index: int
    date_from: date
    date_to: date
    signal_count: int
    summary_by_label: dict[str, dict[str, BacktestReturnSummaryOut]]
    summary_by_label_and_liquidity: dict[str, dict[str, dict[str, BacktestReturnSummaryOut]]]
    samples: list[BrokerBacktestSampleOut]


class BrokerLabelWalkforwardOut(BaseModel):
    as_of_date: Optional[date] = None
    period_days: int
    lookback_days: int
    fold_size_days: int
    num_folds: int
    universe: str
    min_label_score: Optional[float] = None
    horizons: list[int]
    summary_by_label: dict[str, dict[str, BacktestReturnSummaryOut]]
    summary_by_label_and_liquidity: dict[str, dict[str, dict[str, BacktestReturnSummaryOut]]]
    samples: list[BrokerBacktestSampleOut]
    folds: list[BrokerWalkforwardFoldOut]


# ---- Misc ----
class MessageOut(BaseModel):
    message: str
    detail: Optional[Any] = None


class TaskOut(BaseModel):
    task_id: str
    status: str


class PipelineRunOut(BaseModel):
    task_id: str
    task_name: str
    status: str
    stage: Optional[str]
    progress: int
    total_tickers: int
    processed_tickers: int
    succeeded_tickers: int
    failed_tickers: int
    result: Optional[dict]
    error: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
