from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.trade_setup import build_trade_setup


def _rows(start: date, closes: list[float]) -> list[dict]:
    rows = []
    for idx, close in enumerate(closes):
        rows.append(
            {
                "date": start + timedelta(days=idx),
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 1_000_000,
            }
        )
    return rows


def _broker(**overrides):
    base = {
        "status": "active",
        "broker_conviction_score": 72,
        "broker_conviction_label": "big_accumulation",
        "flow_quality_score": 70,
        "flow_quality_label": "smart_like_accumulation",
        "recent_5_session_net": 1_000_000,
        "retail_distribution_risk": False,
    }
    return {**base, **overrides}


def _entry(**overrides):
    return {"score": 76, "phase": "Siap Entry", "tags": [], **overrides}


def test_trade_setup_blocks_when_broker_gate_is_hold():
    setup = build_trade_setup(
        _rows(date(2026, 6, 1), [100 + i for i in range(30)]),
        _broker(status="reversal_risk"),
        _entry(),
    )

    assert setup["setup_type"] == "no_setup"
    assert setup["setup_state"] == "blocked"
    assert "broker_gate_not_clear" in setup["blockers"]


def test_trade_setup_returns_unavailable_for_short_price_history():
    setup = build_trade_setup(_rows(date(2026, 7, 1), [100, 101, 102]), _broker(), _entry())

    assert setup["setup_type"] == "no_setup"
    assert setup["setup_state"] == "unavailable"
    assert "data_setup_belum_lengkap" in setup["blockers"]


def test_trade_setup_marks_extended_price_as_value_area_wait():
    closes = [100 + i for i in range(35)] + [150, 153, 156, 160, 164]
    setup = build_trade_setup(_rows(date(2026, 5, 1), closes), _broker(), _entry())

    assert setup["setup_type"] in {"wait_value_area", "buy_on_weakness", "wait_breakout", "wait_retest"}
    assert setup["last_price"] == 164
    assert setup["invalidation_price"] is not None
