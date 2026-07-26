"""Default weights and method normalization for scoring engine."""

# Default weights (sum to 1.0). Adaptive engine can override per ticker.
DEFAULT_WEIGHTS = {
    "technical": {
        "trend_structure": 0.20,
        "price_action": 0.10,
        "volume_breakout": 0.10,
        "harmonic": 0.05,
        "relative_strength": 0.05,
        "candlestick": 0.05,
        "elliott_wave": 0.05,
    },
    "bandarmology": {
        "hidden_accumulation": 0.10,
        "silent_accumulation": 0.06,
        "shakeout": 0.05,
        "absorption": 0.08,
        "bandar_positioning": 0.08,
        "consistency": 0.03,
    },
    "foreign_flow": 0.10,
    "regime": 0.05,
}

TECHNICAL_METHODS = list(DEFAULT_WEIGHTS["technical"].keys())
BANDAR_LABELS = list(DEFAULT_WEIGHTS["bandarmology"].keys())
