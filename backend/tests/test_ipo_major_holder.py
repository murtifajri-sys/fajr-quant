from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.ipo_major_holder import summarize_major_holder_payload


def test_major_holder_summary_labels_tight_float():
    payload = {
        "data": {
            "rows": [
                {"name": "Founder A", "percentage": "70.5"},
                {"name": "Strategic B", "percentage": "15.0"},
            ]
        }
    }

    result = summarize_major_holder_payload(payload)

    assert result["holder_count"] == 2
    assert result["top_holder_name"] == "Founder A"
    assert result["total_major_holder_pct"] == 85.5
    assert result["free_float_estimate_pct"] == 14.5
    assert result["holder_risk_label"] == "float_tight"


def test_major_holder_summary_labels_unknown_payload():
    result = summarize_major_holder_payload({"data": {"rows": []}})

    assert result["holder_count"] == 0
    assert result["holder_risk_label"] == "unknown_majorholder"
