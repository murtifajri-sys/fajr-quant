from datetime import date
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.ipo_screener import _flow_features, _phase_for_sessions


class FlowRow:
    def __init__(self, day: date, broker: str, net_value: float):
        self.date = day
        self.broker = broker
        self.net_value = net_value


def test_ipo_phase_allows_early_entry_window_before_41_sessions():
    assert _phase_for_sessions(5) == "price_discovery"
    assert _phase_for_sessions(6) == "early_watch"
    assert _phase_for_sessions(20) == "early_watch"
    assert _phase_for_sessions(21) == "base_forming"
    assert _phase_for_sessions(41) == "setup_ready"


def test_flow_features_tracks_top_broker_accumulation():
    days = [date(2026, 7, day) for day in range(1, 7)]
    flows = [
        FlowRow(days[0], "YP", 10_000_000),
        FlowRow(days[1], "YP", 12_000_000),
        FlowRow(days[2], "YP", -2_000_000),
        FlowRow(days[3], "YP", 15_000_000),
        FlowRow(days[4], "YP", 9_000_000),
        FlowRow(days[5], "YP", 8_000_000),
        FlowRow(days[0], "CC", 5_000_000),
    ]

    result = _flow_features(flows, days)

    assert result["coverage_ratio"] == 1.0
    assert result["top_broker"] == "YP"
    assert result["top_broker_positive_days"] == 5
    assert result["recent_5_net"] == 42_000_000
