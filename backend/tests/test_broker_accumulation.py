from datetime import date, timedelta
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: F401 - registers SQLAlchemy models
from app.core.db import Base
from app.models.broker_flow import BrokerFlow
from app.models.price import DailyPrice
from app.models.score import Score
from app.models.screener import ScreenerRun
from app.models.stock import Stock
from app.api.schemas import ScreenerFilter
from app.services.broker_accumulation import _broker_metrics_for_series, _window_start, summarize_broker_accumulation
from app.services.data_loader import backfill_broker_flow_for_ticker, broker_flow_coverage_summary
from app.services.screener.backtest import run_broker_label_backtest, run_broker_label_walkforward
from app.services.screener.runner import DEFAULT_SCREENER_SNAPSHOT_NAME, build_broker_ticker_detail, latest_screener_run, run_screener


def _make_session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed_backtest_fixture(db, ticker: str, start: date, days: int = 60):
    db.add(Stock(ticker=ticker, name=ticker, shares_outstanding=1_000_000_000))
    for idx in range(days):
        close = 100 + idx
        current_date = start + timedelta(days=idx)
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


def test_window_start_uses_calendar_periods():
    end = date(2026, 7, 8)
    start_1w, label_1w = _window_start(end, 7)
    start_1m, label_1m = _window_start(end, 30)

    assert start_1w == date(2026, 7, 1)
    assert label_1w == "1W"
    assert start_1m == date(2026, 6, 8)
    assert label_1m == "1M"


def test_broker_series_metrics_track_positive_days_and_streak():
    import pandas as pd

    series = pd.Series(
        [10.0, 20.0, -5.0, 15.0],
        index=[date(2026, 7, 2), date(2026, 7, 3), date(2026, 7, 4), date(2026, 7, 5)],
    )
    metrics = _broker_metrics_for_series(series)

    assert metrics["positive_days"] == 3
    assert metrics["negative_days"] == 1
    assert metrics["consecutive_buy_days"] == 1
    assert metrics["recency_sessions"] == 0
    assert metrics["coverage_ratio"] == 1.0


def test_summarize_broker_accumulation_returns_latest_window_metrics():
    db = _make_session()
    ticker = "TST"
    db.add(Stock(ticker=ticker, name="Test Stock", shares_outstanding=100_000_000))

    dates = [date(2026, 7, 2) + timedelta(days=i) for i in range(7)]
    for d in dates:
        db.add(
            DailyPrice(
                ticker=ticker,
                date=d,
                open=10,
                high=11,
                low=9,
                close=10,
                adj_close=10,
                volume=1_000,
                source="stockbit",
            )
        )
        db.add(BrokerFlow(ticker=ticker, date=d, broker="A", buy_value=1000, sell_value=0, net_value=1000))
        db.add(BrokerFlow(ticker=ticker, date=d, broker="B", buy_value=500, sell_value=0, net_value=500))
        db.add(BrokerFlow(ticker=ticker, date=d, broker="C", buy_value=0, sell_value=1500, net_value=-1500))

    db.commit()

    summary = summarize_broker_accumulation(db, ticker, 30, top_limit=15)

    assert summary is not None
    assert summary["date_to"] == date(2026, 7, 8).isoformat()
    assert summary["date_from"] == date(2026, 6, 8).isoformat()
    assert summary["coverage_ratio"] == 1.0
    assert summary["balance_abs_net_ratio"] == 0.0
    assert summary["status"] == "active"
    assert summary["top_broker"] == "A"
    assert summary["positive_days"] == 7
    assert summary["negative_days"] == 0
    assert summary["broker_coverage_ratio"] == 1.0
    assert summary["days_of_adv"] == 0.7
    assert summary["top_3_net"] == 10500.0
    assert summary["cluster_ratio"] == 1.0
    assert summary["top_brokers"][0]["period"] == "1M"
    assert summary["top_brokers"][0]["trading_days"] == 7
    assert summary["top_brokers"][0]["pct_market_cap"] == 0.0007
    assert summary["top_brokers"][1]["pct_market_cap"] == 0.0003
    assert summary["top_brokers"][2]["pct_market_cap"] == -0.001
    assert summary["top_brokers"][0]["pct_avg_daily_value"] == 70.0
    assert summary["top_brokers"][1]["pct_avg_daily_value"] == 35.0
    assert summary["top_brokers"][2]["pct_avg_daily_value"] == -105.0
    assert 0 <= summary["broker_conviction_score"] <= 100
    assert summary["broker_conviction_label"] in {"none", "accumulation", "big_accumulation", "aggressive_accumulation"}


def test_build_broker_ticker_detail_combines_conviction_and_entry_readiness():
    db = _make_session()
    ticker = "BDTL"
    db.add(Stock(ticker=ticker, name="Broker Detail", shares_outstanding=100_000_000))

    dates = [date(2026, 7, 16) + timedelta(days=i) for i in range(6)]
    for idx, d in enumerate(dates):
        db.add(
            DailyPrice(
                ticker=ticker,
                date=d,
                open=100,
                high=105,
                low=99,
                close=102 + idx,
                adj_close=102 + idx,
                volume=10_000,
                source="stockbit",
            )
        )
        db.add(BrokerFlow(ticker=ticker, date=d, broker="XL", buy_value=5000, sell_value=1000, net_value=4000))
        db.add(BrokerFlow(ticker=ticker, date=d, broker="YB", buy_value=3000, sell_value=500, net_value=2500))
        db.add(BrokerFlow(ticker=ticker, date=d, broker="ZZ", buy_value=0, sell_value=6500, net_value=-6500))

    db.add(
        Score(
            ticker=ticker,
            date=dates[-1],
            composite=78.0,
            sub_scores={
                "tech:trend_structure": 72.0,
                "tech:relative_strength": 70.0,
                "tech:volume_breakout": 68.0,
            },
            weights={},
            phase="Siap Entry",
            confidence=80.0,
            dominant_factors={},
        )
    )
    db.commit()

    detail = build_broker_ticker_detail(db, ticker)

    assert detail is not None
    assert detail["ticker"] == ticker
    assert detail["one_week"]["top_broker"] == "XL"
    assert detail["one_month"]["top_broker"] == "XL"
    assert detail["broker_conviction"]["score"] is not None
    assert detail["flow_quality"]["score"] is not None
    assert detail["entry_readiness"]["score"] is not None
    assert detail["broker_conviction"]["combined_rank_score"] is not None


def test_flow_quality_flags_smart_like_accumulation_for_large_low_freq_trades():
    db = _make_session()
    ticker = "SMRT"
    db.add(Stock(ticker=ticker, name="Smart Like", shares_outstanding=100_000_000))

    dates = [date(2026, 7, 16) + timedelta(days=i) for i in range(6)]
    for idx, d in enumerate(dates):
        db.add(
            DailyPrice(
                ticker=ticker,
                date=d,
                open=100,
                high=101,
                low=99,
                close=100,
                adj_close=100,
                volume=1_000,
                source="stockbit",
            )
        )
        aa_net = 0
        aa_buy = 0
        aa_freq = 0
        bb_net = 0
        bb_buy = 0
        bb_freq = 0
        if idx >= 4:
            aa_net = 220_000
            aa_buy = 220_000
            aa_freq = 1
            bb_net = 180_000
            bb_buy = 180_000
            bb_freq = 1
        db.add(BrokerFlow(ticker=ticker, date=d, broker="AA", buy_value=aa_buy, sell_value=0, net_value=aa_net, buy_freq=aa_freq, sell_freq=0))
        db.add(BrokerFlow(ticker=ticker, date=d, broker="BB", buy_value=bb_buy, sell_value=0, net_value=bb_net, buy_freq=bb_freq, sell_freq=0))
        db.add(BrokerFlow(ticker=ticker, date=d, broker="ZZ", buy_value=0, sell_value=aa_net + bb_net, net_value=-(aa_net + bb_net), buy_freq=0, sell_freq=aa_freq + bb_freq))
    db.commit()

    summary = summarize_broker_accumulation(db, ticker, 30, top_limit=15)

    assert summary is not None
    assert summary["low_freq_high_value"] is True
    assert summary["high_freq_low_value"] is False
    assert summary["flow_quality_label"] == "smart_like_accumulation"
    assert summary["flow_quality_score"] >= 60


def test_flow_quality_flags_retail_distribution_risk_for_high_freq_recent_distribution():
    db = _make_session()
    ticker = "RTLR"
    db.add(Stock(ticker=ticker, name="Retail Risk", shares_outstanding=100_000_000))

    dates = [date(2026, 7, 10) + timedelta(days=i) for i in range(8)]
    aa_pattern = [35_000, 30_000, 25_000, 20_000, -8_000, -10_000, -12_000, -14_000]
    other_buyers = [("B1", 8_000), ("B2", 8_000), ("B3", 8_000), ("B4", 8_000), ("B5", 8_000), ("B6", 8_000), ("B7", 8_000)]
    for d, aa_net in zip(dates, aa_pattern):
        db.add(
            DailyPrice(
                ticker=ticker,
                date=d,
                open=50,
                high=51,
                low=49,
                close=50,
                adj_close=50,
                volume=10_000,
                source="stockbit",
            )
        )
        total_positive = 0
        for broker, net in other_buyers:
            total_positive += net
            db.add(BrokerFlow(ticker=ticker, date=d, broker=broker, buy_value=net, sell_value=0, net_value=net, buy_freq=1, sell_freq=0))
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=d,
                broker="AA",
                buy_value=max(aa_net, 0),
                sell_value=abs(min(aa_net, 0)),
                net_value=aa_net,
                buy_freq=4,
                sell_freq=1 if aa_net < 0 else 0,
            )
        )
        total_negative = total_positive + aa_net
        db.add(BrokerFlow(ticker=ticker, date=d, broker="ZZ", buy_value=max(-total_negative, 0), sell_value=max(total_negative, 0), net_value=-total_negative, buy_freq=0, sell_freq=8))
    db.commit()

    summary = summarize_broker_accumulation(db, ticker, 30, top_limit=15)

    assert summary is not None
    assert summary["top_broker"] == "AA"
    assert summary["buy_freq"] >= 8
    assert summary["recent_5_session_net"] < 0
    assert summary["cluster_ratio"] < 0.5
    assert summary["retail_distribution_risk"] is True
    assert summary["flow_quality_label"] == "retail_distribution_risk"


def test_flow_quality_exposes_frequency_metrics_for_top_broker():
    db = _make_session()
    ticker = "FREQ"
    db.add(Stock(ticker=ticker, name="Frequency Metrics", shares_outstanding=100_000_000))

    dates = [date(2026, 7, 13) + timedelta(days=i) for i in range(5)]
    aa_buy_values = [40_000, 45_000, 60_000, 55_000, 50_000]
    aa_buy_freqs = [2, 4, 3, 5, 6]
    aa_sell_values = [5_000, 10_000, 5_000, 10_000, 10_000]
    aa_sell_freqs = [1, 2, 1, 2, 1]

    for d, buy_value, buy_freq, sell_value, sell_freq in zip(
        dates, aa_buy_values, aa_buy_freqs, aa_sell_values, aa_sell_freqs
    ):
        db.add(
            DailyPrice(
                ticker=ticker,
                date=d,
                open=100,
                high=101,
                low=99,
                close=100,
                adj_close=100,
                volume=1_000,
                source="stockbit",
            )
        )
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=d,
                broker="AA",
                buy_value=buy_value,
                sell_value=sell_value,
                net_value=buy_value - sell_value,
                buy_freq=buy_freq,
                sell_freq=sell_freq,
            )
        )
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=d,
                broker="ZZ",
                buy_value=sell_value,
                sell_value=buy_value,
                net_value=sell_value - buy_value,
                buy_freq=sell_freq,
                sell_freq=buy_freq,
            )
        )
    db.commit()

    summary = summarize_broker_accumulation(db, ticker, 30, top_limit=15)

    assert summary is not None
    assert summary["top_broker"] == "AA"
    assert summary["avg_buy_ticket"] == 12_500.0
    assert round(summary["avg_sell_ticket"], 2) == 5_714.29
    assert round(summary["net_per_trade"], 2) == 7_777.78
    assert summary["frequency_consistency"] == 0.6464
    assert summary["high_freq_low_value"] is False


def test_flow_quality_does_not_mark_noisy_high_frequency_flow_as_smart_like():
    db = _make_session()
    ticker = "NOIS"
    db.add(Stock(ticker=ticker, name="Noisy Flow", shares_outstanding=100_000_000))

    dates = [date(2026, 7, 13) + timedelta(days=i) for i in range(6)]
    aa_buy_values = [5_000, 5_000, 4_500, 5_000, 4_500, 5_000]
    aa_buy_freqs = [6, 6, 6, 6, 6, 6]

    for d, buy_value, buy_freq in zip(dates, aa_buy_values, aa_buy_freqs):
        db.add(
            DailyPrice(
                ticker=ticker,
                date=d,
                open=100,
                high=101,
                low=99,
                close=100,
                adj_close=100,
                volume=1_000,
                source="stockbit",
            )
        )
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=d,
                broker="AA",
                buy_value=buy_value,
                sell_value=0,
                net_value=buy_value,
                buy_freq=buy_freq,
                sell_freq=0,
            )
        )
        for idx in range(8):
            db.add(
                BrokerFlow(
                    ticker=ticker,
                    date=d,
                    broker=f"B{idx}",
                    buy_value=4_000,
                    sell_value=0,
                    net_value=4_000,
                    buy_freq=1,
                    sell_freq=0,
                )
            )
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=d,
                broker="ZZ",
                buy_value=0,
                sell_value=buy_value + (8 * 4_000),
                net_value=-(buy_value + (8 * 4_000)),
                buy_freq=0,
                sell_freq=buy_freq + 8,
            )
        )
    db.commit()

    summary = summarize_broker_accumulation(db, ticker, 30, top_limit=15)

    assert summary is not None
    assert summary["top_broker"] == "AA"
    assert summary["cluster_ratio"] < 0.5
    assert summary["high_freq_low_value"] is True
    assert summary["flow_quality_score"] < 45.0
    assert summary["flow_quality_label"] == "retail_like_accumulation"


def test_broker_flow_coverage_summary_counts_complete_partial_and_missing():
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

    summary = broker_flow_coverage_summary(db, period_days=7, universe="idx", limit=10)

    assert summary["total_tickers"] == 3
    assert summary["complete_tickers"] == 1
    assert summary["partial_tickers"] == 1
    assert summary["missing_tickers"] == 1
    assert summary["items"][0]["ticker"] == "MIS"
    assert summary["items"][0]["status"] == "missing"
    assert summary["items"][1]["ticker"] == "PAR"
    assert summary["items"][1]["status"] == "partial"


def test_broker_flow_coverage_summary_respects_requested_period_days():
    db = _make_session()
    ticker = "COV60"
    db.add(Stock(ticker=ticker, name=ticker))

    dates = [date(2026, 5, 1) + timedelta(days=i) for i in range(60)]
    for idx, d in enumerate(dates):
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
        if idx >= 15:
            db.add(BrokerFlow(ticker=ticker, date=d, broker="AA", buy_value=1_000, sell_value=0, net_value=1_000))
            db.add(BrokerFlow(ticker=ticker, date=d, broker="ZZ", buy_value=0, sell_value=1_000, net_value=-1_000))
    db.commit()

    summary = broker_flow_coverage_summary(db, period_days=60, tickers=[ticker], limit=5)

    assert summary["period_days"] == 60
    assert summary["items"][0]["trading_days"] == 60
    assert summary["items"][0]["flow_days"] == 45


def test_latest_screener_run_prefers_named_snapshot():
    db = _make_session()
    db.add(ScreenerRun(filter_json={"snapshot_name": "custom_manual"}, total=1))
    db.add(ScreenerRun(filter_json={"snapshot_name": DEFAULT_SCREENER_SNAPSHOT_NAME}, total=2))
    db.add(ScreenerRun(filter_json={"top_n": 20}, total=3))
    db.commit()

    run = latest_screener_run(db, DEFAULT_SCREENER_SNAPSHOT_NAME)

    assert run is not None
    assert run.filter_json["snapshot_name"] == DEFAULT_SCREENER_SNAPSHOT_NAME


def test_broker_label_backtest_summarizes_forward_returns():
    db = _make_session()
    ticker = "BTST"
    start = date(2026, 6, 1)
    _seed_backtest_fixture(db, ticker, start, days=26)
    db.commit()

    result = run_broker_label_backtest(
        db,
        period_days=30,
        lookback_days=40,
        universe="idx",
        min_label_score=0,
        sample_limit=2,
    )

    label = result["samples"][0]["label"]
    bucket = result["samples"][0]["liquidity_bucket"]

    assert result["as_of_date"] == (start + timedelta(days=25)).isoformat()
    assert label in result["summary_by_label"]
    assert result["summary_by_label"][label]["5"]["count"] >= 1
    assert result["summary_by_label"][label]["10"]["count"] >= 1
    assert result["summary_by_label"][label]["20"]["count"] >= 1
    assert result["summary_by_label_and_liquidity"][label][bucket]["5"]["count"] >= 1
    assert len(result["samples"]) == 2
    assert bucket == "medium"
    assert result["samples"][0]["forward_returns_pct"] == {"5": 5.0, "10": 10.0, "20": 20.0}


def test_broker_label_walkforward_builds_sequential_folds():
    db = _make_session()
    ticker = "WFTS"
    start = date(2026, 4, 1)
    _seed_backtest_fixture(db, ticker, start, days=60)
    db.commit()

    result = run_broker_label_walkforward(
        db,
        period_days=30,
        lookback_days=50,
        fold_size_days=10,
        num_folds=3,
        universe="idx",
        min_label_score=0,
        sample_limit_per_fold=2,
    )

    assert result["as_of_date"] == (start + timedelta(days=59)).isoformat()
    assert result["fold_size_days"] == 10
    assert result["num_folds"] == 3
    assert len(result["folds"]) == 3
    assert result["folds"][0]["fold_index"] == 1
    assert result["folds"][0]["signal_count"] >= 1
    assert result["folds"][0]["samples"]
    label = result["folds"][0]["samples"][0]["label"]
    assert label in result["folds"][0]["summary_by_label"]
    assert result["folds"][0]["summary_by_label"][label]["5"]["count"] >= 1
    assert label in result["summary_by_label"]


def test_one_month_positive_but_recent_five_negative_is_not_active_or_aggressive():
    db = _make_session()
    ticker = "REV"
    db.add(Stock(ticker=ticker, name="Reversal", shares_outstanding=100_000_000))

    dates = [date(2026, 6, 25) + timedelta(days=i) for i in range(10)]
    for idx, d in enumerate(dates):
        db.add(
            DailyPrice(
                ticker=ticker,
                date=d,
                open=100,
                high=102,
                low=99,
                close=101,
                adj_close=101,
                volume=10_000,
                source="stockbit",
            )
        )
        if idx < 5:
            a_net = 5_000
            b_net = 2_000
        else:
            a_net = -2_000
            b_net = 500
        total_positive = max(a_net, 0) + max(b_net, 0)
        total_negative = abs(min(a_net, 0)) + abs(min(b_net, 0))
        c_net = -(a_net + b_net)
        db.add(BrokerFlow(ticker=ticker, date=d, broker="AA", buy_value=max(a_net, 0), sell_value=abs(min(a_net, 0)), net_value=a_net))
        db.add(BrokerFlow(ticker=ticker, date=d, broker="BB", buy_value=max(b_net, 0), sell_value=abs(min(b_net, 0)), net_value=b_net))
        db.add(
            BrokerFlow(
                ticker=ticker,
                date=d,
                broker="CC",
                buy_value=total_negative,
                sell_value=total_positive,
                net_value=c_net,
            )
        )

    db.add(
        Score(
            ticker=ticker,
            date=dates[-1],
            composite=82.0,
            sub_scores={
                "tech:trend_structure": 75.0,
                "tech:relative_strength": 72.0,
                "tech:volume_breakout": 70.0,
            },
            weights={},
            phase="Siap Entry",
            confidence=80.0,
            dominant_factors={},
        )
    )
    db.commit()

    summary = summarize_broker_accumulation(db, ticker, 30, top_limit=15)

    assert summary is not None
    assert summary["net"] > 0
    assert summary["recent_5_session_net"] < 0
    assert summary["status"] in {"stale", "reversal_risk"}
    assert summary["broker_conviction_label"] == "none"

    result = run_screener(
        db,
        ScreenerFilter(
            require_broker_accumulation=True,
            exclude_stale=True,
            exclude_reversal_risk=True,
            require_recent=True,
            top_n=20,
        ),
    )
    assert ticker not in [row.ticker for row in result.results]


def test_broker_frequent_but_mostly_net_sell_fails_minimum_positive_days():
    db = _make_session()
    ticker = "SELL"
    db.add(Stock(ticker=ticker, name="Mostly Sell", shares_outstanding=100_000_000))

    dates = [date(2026, 7, 10) + timedelta(days=i) for i in range(8)]
    sell_pattern = [10_000, -2_000, -2_000, -2_000, 8_000, -2_000, -2_000, -2_000]
    for d, a_net in zip(dates, sell_pattern):
        db.add(
            DailyPrice(
                ticker=ticker,
                date=d,
                open=50,
                high=51,
                low=49,
                close=50,
                adj_close=50,
                volume=8_000,
                source="stockbit",
            )
        )
        db.add(BrokerFlow(ticker=ticker, date=d, broker="AA", buy_value=max(a_net, 0), sell_value=abs(min(a_net, 0)), net_value=a_net))
        db.add(BrokerFlow(ticker=ticker, date=d, broker="BB", buy_value=abs(min(a_net, 0)), sell_value=max(a_net, 0), net_value=-a_net))

    db.add(
        Score(
            ticker=ticker,
            date=dates[-1],
            composite=68.0,
            sub_scores={
                "tech:trend_structure": 60.0,
                "tech:relative_strength": 58.0,
                "tech:volume_breakout": 55.0,
            },
            weights={},
            phase="Awal",
            confidence=65.0,
            dominant_factors={},
        )
    )
    db.commit()

    summary = summarize_broker_accumulation(db, ticker, 30, top_limit=15)

    assert summary is not None
    assert summary["top_broker"] == "AA"
    assert summary["positive_days"] == 2
    assert summary["negative_days"] == 6
    assert summary["positive_ratio"] < 0.4

    result = run_screener(
        db,
        ScreenerFilter(
            require_broker_accumulation=True,
            min_broker_active_days=3,
            top_n=20,
        ),
    )
    assert ticker not in [row.ticker for row in result.results]


def test_run_screener_excludes_stale_when_requested():
    db = _make_session()
    ticker = "STAL"
    db.add(Stock(ticker=ticker, name="Stale Broker", shares_outstanding=100_000_000))

    dates = [date(2026, 7, 1) + timedelta(days=i) for i in range(8)]
    pattern = [4_000, 4_000, 3_000, 2_000, 0, 0, 0, 0]
    for d, a_net in zip(dates, pattern):
        db.add(
            DailyPrice(
                ticker=ticker,
                date=d,
                open=100,
                high=101,
                low=99,
                close=100,
                adj_close=100,
                volume=10_000,
                source="stockbit",
            )
        )
        db.add(BrokerFlow(ticker=ticker, date=d, broker="AA", buy_value=max(a_net, 0), sell_value=abs(min(a_net, 0)), net_value=a_net))
        db.add(BrokerFlow(ticker=ticker, date=d, broker="BB", buy_value=0, sell_value=max(a_net, 0), net_value=-a_net))

    db.add(
        Score(
            ticker=ticker,
            date=dates[-1],
            composite=72.0,
            sub_scores={
                "tech:trend_structure": 65.0,
                "tech:relative_strength": 60.0,
                "tech:volume_breakout": 58.0,
            },
            weights={},
            phase="Tunggu Konfirmasi",
            confidence=70.0,
            dominant_factors={},
        )
    )
    db.commit()

    summary = summarize_broker_accumulation(db, ticker, 30, top_limit=15)
    assert summary is not None
    assert summary["status"] == "stale"

    included = run_screener(
        db,
        ScreenerFilter(
            require_broker_accumulation=True,
            exclude_stale=False,
            top_n=20,
        ),
    )
    assert ticker in [row.ticker for row in included.results]

    excluded = run_screener(
        db,
        ScreenerFilter(
            require_broker_accumulation=True,
            exclude_stale=True,
            top_n=20,
        ),
    )
    assert ticker not in [row.ticker for row in excluded.results]


def test_run_screener_requires_cluster_confirmation():
    db = _make_session()

    clustered = "CLUS"
    db.add(Stock(ticker=clustered, name="Clustered", shares_outstanding=100_000_000))
    broad = "BROAD"
    db.add(Stock(ticker=broad, name="Broad Buyers", shares_outstanding=100_000_000))

    dates = [date(2026, 7, 14) + timedelta(days=i) for i in range(6)]
    for ticker in (clustered, broad):
        for d in dates:
            db.add(
                DailyPrice(
                    ticker=ticker,
                    date=d,
                    open=100,
                    high=103,
                    low=99,
                    close=102,
                    adj_close=102,
                    volume=15_000,
                    source="stockbit",
                )
            )

    for d in dates:
        db.add(BrokerFlow(ticker=clustered, date=d, broker="A1", buy_value=6_000, sell_value=0, net_value=6_000))
        db.add(BrokerFlow(ticker=clustered, date=d, broker="A2", buy_value=5_000, sell_value=0, net_value=5_000))
        db.add(BrokerFlow(ticker=clustered, date=d, broker="A3", buy_value=4_000, sell_value=0, net_value=4_000))
        db.add(BrokerFlow(ticker=clustered, date=d, broker="ZZ", buy_value=0, sell_value=15_000, net_value=-15_000))

    for d in dates:
        positive_total = 0
        for idx in range(10):
            broker = f"B{idx}"
            db.add(BrokerFlow(ticker=broad, date=d, broker=broker, buy_value=1_000, sell_value=0, net_value=1_000))
            positive_total += 1_000
        db.add(BrokerFlow(ticker=broad, date=d, broker="ZX", buy_value=0, sell_value=positive_total, net_value=-positive_total))

    for ticker in (clustered, broad):
        db.add(
            Score(
                ticker=ticker,
                date=dates[-1],
                composite=76.0,
                sub_scores={
                    "tech:trend_structure": 68.0,
                    "tech:relative_strength": 66.0,
                    "tech:volume_breakout": 62.0,
                },
                weights={},
                phase="Siap Entry",
                confidence=78.0,
                dominant_factors={},
            )
        )
    db.commit()

    broad_summary = summarize_broker_accumulation(db, broad, 30, top_limit=15)
    clustered_summary = summarize_broker_accumulation(db, clustered, 30, top_limit=15)
    assert broad_summary is not None
    assert clustered_summary is not None
    assert broad_summary["cluster_ratio"] < 0.5
    assert clustered_summary["cluster_ratio"] >= 0.5

    result = run_screener(
        db,
        ScreenerFilter(
            require_broker_accumulation=True,
            require_cluster_confirmation=True,
            top_n=20,
        ),
    )

    tickers = [row.ticker for row in result.results]
    assert clustered in tickers
    assert broad not in tickers


def test_run_screener_returns_pagination_and_coverage_metadata():
    db = _make_session()
    tickers = ["META1", "META2", "META3"]
    dates = [date(2026, 7, 14) + timedelta(days=i) for i in range(6)]

    for ticker in tickers:
        db.add(Stock(ticker=ticker, name=ticker, shares_outstanding=100_000_000))
        for d in dates:
            db.add(
                DailyPrice(
                    ticker=ticker,
                    date=d,
                    open=100,
                    high=101,
                    low=99,
                    close=100,
                    adj_close=100,
                    volume=2_000_000,
                    source="stockbit",
                )
            )
            db.add(BrokerFlow(ticker=ticker, date=d, broker="AA", buy_value=9_000_000, sell_value=0, net_value=9_000_000))
            db.add(BrokerFlow(ticker=ticker, date=d, broker="BB", buy_value=4_000_000, sell_value=0, net_value=4_000_000))
            db.add(BrokerFlow(ticker=ticker, date=d, broker="CC", buy_value=0, sell_value=13_000_000, net_value=-13_000_000))
        db.add(
            Score(
                ticker=ticker,
                date=dates[-1],
                composite=70.0 + tickers.index(ticker),
                sub_scores={
                    "tech:trend_structure": 66.0,
                    "tech:relative_strength": 64.0,
                    "tech:volume_breakout": 61.0,
                },
                weights={},
                phase="Siap Entry",
                confidence=75.0,
                dominant_factors={},
            )
        )
    db.commit()

    result = run_screener(
        db,
        ScreenerFilter(
            require_broker_accumulation=True,
            min_broker_conviction_score=0,
            top_n=1,
            offset=1,
        ),
    )

    assert result.total == 3
    assert result.limit == 1
    assert result.offset == 1
    assert result.has_more is True
    assert result.coverage_summary is not None
    assert result.coverage_summary["total_tickers"] == 3
    assert len(result.results) == 1
    assert result.results[0].rank == 2


def test_backfill_broker_flow_for_ticker_reports_failed_dates(monkeypatch):
    db = _make_session()
    ticker = "BFDT"
    db.add(Stock(ticker=ticker, name="Backfill Detail"))

    dates = [date(2026, 7, 20), date(2026, 7, 21)]
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
    db.commit()

    class FakeStockbitClient:
        def __init__(self, db=None):
            self.db = db

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_market_detectors(self, current_ticker, start, end, limit=300):
            if start == dates[1]:
                raise RuntimeError("upstream timeout")
            return {
                "data": {
                    "broker_summary": {
                        "brokers_buy": [
                            {
                                "netbs_date": start.isoformat(),
                                "netbs_broker_code": "YP",
                                "bval": 1000,
                                "freq": 3,
                            }
                        ],
                        "brokers_sell": [
                            {
                                "netbs_date": start.isoformat(),
                                "netbs_broker_code": "CC",
                                "sval": 1000,
                                "freq": 2,
                            }
                        ],
                    }
                }
            }

    monkeypatch.setattr("app.services.data_loader.StockbitClient", FakeStockbitClient)

    result = backfill_broker_flow_for_ticker(db, ticker, period_days=7)

    assert result["ok"] is False
    assert result["reason"] == "partial_backfill"
    assert result["fetched_dates"] == 1
    assert result["fetched_date_list"] == [dates[0].isoformat()]
    assert result["failed_dates"] == [{"date": dates[1].isoformat(), "error": "upstream timeout"}]


def test_backfill_broker_flow_for_ticker_limits_fetch_to_target_dates(monkeypatch):
    db = _make_session()
    ticker = "TGDT"
    db.add(Stock(ticker=ticker, name="Target Date Retry"))

    dates = [date(2026, 7, 20), date(2026, 7, 21), date(2026, 7, 22)]
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
    db.commit()

    requested = []

    class FakeStockbitClient:
        def __init__(self, db=None):
            self.db = db

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_market_detectors(self, current_ticker, start, end, limit=300):
            requested.append(start.isoformat())
            return {
                "data": {
                    "broker_summary": {
                        "brokers_buy": [
                            {
                                "netbs_date": start.isoformat(),
                                "netbs_broker_code": "YP",
                                "bval": 1000,
                                "freq": 5,
                            }
                        ],
                        "brokers_sell": [
                            {
                                "netbs_date": start.isoformat(),
                                "netbs_broker_code": "CC",
                                "sval": 1000,
                                "freq": 1,
                            }
                        ],
                    }
                }
            }

    monkeypatch.setattr("app.services.data_loader.StockbitClient", FakeStockbitClient)

    result = backfill_broker_flow_for_ticker(db, ticker, period_days=7, target_dates=[dates[1]])

    assert result["ok"] is True
    assert requested == [dates[1].isoformat()]
    assert result["missing_dates"] == [dates[1].isoformat()]
    assert result["fetched_date_list"] == [dates[1].isoformat()]

    stored = db.query(BrokerFlow).filter(BrokerFlow.ticker == ticker, BrokerFlow.date == dates[1], BrokerFlow.broker == "YP").one()
    assert stored.buy_freq == 5
    assert stored.sell_freq is None


def test_backfill_broker_flow_for_ticker_marks_empty_source_dates(monkeypatch):
    db = _make_session()
    ticker = "EMPT"
    db.add(Stock(ticker=ticker, name="Empty Source"))

    dates = [date(2026, 7, 20), date(2026, 7, 21)]
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
    db.commit()

    class FakeStockbitClient:
        def __init__(self, db=None):
            self.db = db

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_market_detectors(self, current_ticker, start, end, limit=300):
            return {"data": {"broker_summary": {"brokers_buy": [], "brokers_sell": []}}}

    monkeypatch.setattr("app.services.data_loader.StockbitClient", FakeStockbitClient)

    result = backfill_broker_flow_for_ticker(db, ticker, period_days=7)

    assert result["ok"] is True
    assert result["reason"] == "empty_source_marked"
    assert result["empty_source_dates"] == [dates[0].isoformat(), dates[1].isoformat()]

    markers = db.query(BrokerFlow).filter(BrokerFlow.ticker == ticker, BrokerFlow.source == "stockbit_empty").all()
    assert len(markers) == 2

    summary = broker_flow_coverage_summary(db, period_days=7, tickers=[ticker], limit=5)
    assert summary["complete_tickers"] == 1
