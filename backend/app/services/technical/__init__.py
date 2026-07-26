"""Technical analysis package: each module computes results for a date range."""
from app.services.technical.breakout import run as breakout_run
from app.services.technical.candlestick import run as candlestick_run
from app.services.technical.elliott_wave import run as elliott_run
from app.services.technical.harmonic import run as harmonic_run
from app.services.technical.price_action import run as price_action_run
from app.services.technical.relative_strength import run as relative_strength_run
from app.services.technical.trend_structure import run as trend_run
from app.services.technical.volume_breakout import run as volume_breakout_run

REGISTRY = {
    "trend_structure": trend_run,
    "price_action": price_action_run,
    "volume_breakout": volume_breakout_run,
    "harmonic": harmonic_run,
    "relative_strength": relative_strength_run,
    "candlestick": candlestick_run,
    "elliott_wave": elliott_run,
    "breakout": breakout_run,
}

__all__ = ["REGISTRY"]
