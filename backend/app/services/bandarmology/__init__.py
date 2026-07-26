"""Bandarmology detection package."""
from app.services.bandarmology.absorption import run as absorption_run
from app.services.bandarmology.bandar_positioning import run as bandar_positioning_run
from app.services.bandarmology.consistency import run as consistency_run
from app.services.bandarmology.hidden_accumulation import run as hidden_accumulation_run
from app.services.bandarmology.shakeout import run as shakeout_run
from app.services.bandarmology.silent_accumulation import run as silent_accumulation_run

REGISTRY = {
    "hidden_accumulation": hidden_accumulation_run,
    "silent_accumulation": silent_accumulation_run,
    "shakeout": shakeout_run,
    "absorption": absorption_run,
    "bandar_positioning": bandar_positioning_run,
    "consistency": consistency_run,
}

__all__ = ["REGISTRY"]
