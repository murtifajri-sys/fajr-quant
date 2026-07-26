import pytest


def test_clamp_score():
    from app.services.bandarmology._base import clamp_score

    assert clamp_score(-5) == 0.0
    assert clamp_score(150) == 100.0
    assert clamp_score(50) == 50.0


def test_phase_determination():
    from app.services.scoring.phase import determine_phase

    phase, conf = determine_phase(
        composite=75,
        sub_scores={},
        bandar_detected={"absorption": True, "consistency": True},
        technical_signals={"relative_strength": 60, "trend_structure": 60, "volume_breakout": 70},
        regime="trending_up",
    )
    assert phase == "Siap Entry"
    assert 0 <= conf <= 100


def test_compute_score_basic():
    from app.services.scoring.engine import compute_score_for_date

    tech = {m: 60 for m in ["trend_structure","price_action","volume_breakout","harmonic","relative_strength","candlestick","elliott_wave"]}
    bandar = {m: 55 for m in ["hidden_accumulation","silent_accumulation","shakeout","absorption","bandar_positioning","consistency"]}
    s = compute_score_for_date(
        ticker="TEST", d=__import__("datetime").date(2026,7,13),
        tech_scores=tech, bandar_scores=bandar,
        bandar_detected={"absorption": True}, foreign_score=60,
        regime="trending_up",
    )
    assert 0 <= s["composite"] <= 100
    assert s["phase"] in ["Awal","Tunggu Konfirmasi","Siap Entry","Hold","Siap Jual","Exit"]


def test_harmonic_detect_returns_none_for_flat():
    import pandas as pd
    from app.services.technical.harmonic import run

    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=80),
        "open": [100]*80, "high": [101]*80, "low": [99]*80, "close": [100]*80, "volume": [1000]*80,
    })
    res = run(df)
    assert isinstance(res, list)


def test_analysis_payload_replaces_non_finite_values():
    from app.services.pipeline import _json_safe

    assert _json_safe({"volume": float("nan"), "nested": [float("inf"), 1.0]}) == {
        "volume": None,
        "nested": [None, 1.0],
    }


def test_stockbit_daily_response_parser():
    from app.services.data_loader import (
        _parse_stockbit_foreign_flows,
        _parse_stockbit_prices,
    )

    payload = {
        "message": "success",
        "data": {
            "chartbit": [
                {
                    "date": "2026-07-13",
                    "open": 6100,
                    "high": 6250,
                    "low": 6075,
                    "close": 6225,
                    "volume": 123456,
                    "foreignbuy": 10,
                    "foreignsell": 8,
                }
            ],
        },
    }
    rows = _parse_stockbit_prices(payload)
    assert len(rows) == 1
    assert rows[0]["close"] == 6225.0
    assert str(rows[0]["date"]) == "2026-07-13"
    foreign_rows = _parse_stockbit_foreign_flows(payload)
    assert foreign_rows == [
        {
            "date": rows[0]["date"],
            "foreign_buy": 10.0,
            "foreign_sell": 8.0,
            "net_foreign": 2.0,
        }
    ]


def test_stockbit_broker_response_parser():
    from app.services.data_loader import _parse_market_detectors

    payload = {
        "data": {
            "broker_summary": {
                "brokers_buy": [
                    {
                        "netbs_date": "2026-07-13",
                        "netbs_broker_code": "YP",
                        "bval": 1000,
                        "freq": 7,
                    }
                ],
                "brokers_sell": [
                    {
                        "netbs_date": "2026-07-13",
                        "netbs_broker_code": "CC",
                        "sval": 600,
                        "freq": 4,
                    }
                ],
            }
        }
    }
    rows = _parse_market_detectors(payload)
    assert len(rows) == 2
    assert rows[0]["net_value"] == 1000.0
    assert rows[0]["buy_freq"] == 7
    assert rows[1]["net_value"] == -600.0
    assert rows[1]["sell_freq"] == 4


def test_jwt_expiry_parser():
    import base64
    import json
    from datetime import datetime

    from app.utils.jwt import jwt_expiry

    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": 1783983749}).encode()
    ).decode().rstrip("=")
    assert jwt_expiry(f"header.{payload}.signature") == datetime(2026, 7, 13, 23, 2, 29)
