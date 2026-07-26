"""Prompt builder for deterministic IPO screener output."""
from __future__ import annotations

import json
from typing import Any


IPO_SCREENER_SYSTEM_PROMPT = """Kamu adalah Fajr Quant, asisten analisis saham IPO IDX.
Tugasmu memilih kandidat IPO/new listing yang benar-benar layak entry atau paling dekat entry dari output deterministic IPO Screener.
Jangan mengarang level harga. Gunakan hanya trigger, AVWAP, base, blocker, dan broker flow dari payload.
Respons HANYA dalam Bahasa Indonesia dan HANYA dalam format JSON."""


def _round(value: Any, digits: int = 2) -> Any:
    if isinstance(value, int | float):
        return round(float(value), digits)
    return value


def _compact_candidate(item: dict[str, Any]) -> dict[str, Any]:
    flow = item.get("broker_flow") or {}
    levels = item.get("levels") or {}
    return {
        "ticker": item.get("ticker"),
        "name": item.get("name"),
        "listing_date": item.get("listing_date"),
        "calendar_age_days": item.get("calendar_age_days"),
        "trading_session_age": item.get("trading_session_age"),
        "status": item.get("status"),
        "setup_type": item.get("setup_type"),
        "ipo_setup_score": _round(item.get("ipo_setup_score"), 2),
        "last_price": _round(item.get("last_price"), 2),
        "opening_range_high": _round(item.get("opening_range_high"), 2),
        "opening_range_low": _round(item.get("opening_range_low"), 2),
        "anchored_vwap": _round(item.get("anchored_vwap"), 2),
        "base_high": _round(item.get("base_high"), 2),
        "base_low": _round(item.get("base_low"), 2),
        "base_width_pct": _round(item.get("base_width_pct"), 2),
        "volume_ratio": _round(item.get("volume_ratio"), 2),
        "avg_value_5": _round(item.get("avg_value_5"), 0),
        "levels": {
            "trigger_price": _round(levels.get("trigger_price"), 2),
            "entry_low": _round(levels.get("entry_low"), 2),
            "entry_high": _round(levels.get("entry_high"), 2),
            "bow_zone_low": _round(levels.get("bow_zone_low"), 2),
            "bow_zone_high": _round(levels.get("bow_zone_high"), 2),
            "invalidation_price": _round(levels.get("invalidation_price"), 2),
            "distance_to_trigger_pct": _round(levels.get("distance_to_trigger_pct"), 2),
            "extension_from_avwap_pct": _round(levels.get("extension_from_avwap_pct"), 2),
        },
        "broker_flow": {
            "coverage_ratio": _round(flow.get("coverage_ratio"), 3),
            "top_broker": flow.get("top_broker"),
            "top_broker_net": _round(flow.get("top_broker_net"), 0),
            "top_broker_positive_ratio": _round(flow.get("top_broker_positive_ratio"), 3),
            "recent_5_net": _round(flow.get("recent_5_net"), 0),
            "recent_10_net": _round(flow.get("recent_10_net"), 0),
            "concentration_ratio": _round(flow.get("concentration_ratio"), 3),
            "distribution_reversal": flow.get("distribution_reversal"),
        },
        "blockers": item.get("blockers") or [],
    }


def build_ipo_screener_prompt(candidates: list[dict[str, Any]], max_candidates: int = 10) -> str:
    selected = candidates[: max(1, min(max_candidates, 10))]
    payload = [_compact_candidate(item) for item in selected]
    return (
        "Kamu adalah analis trading IDX untuk saham IPO/new listing.\n"
        "Tugas: ranking kandidat yang layak entry atau paling dekat entry dari data IPO Screener berikut.\n\n"
        "Aturan:\n"
        "1. Prioritaskan status IPO Siap Entry, IPO Early Entry, lalu IPO Mendekati Entry.\n"
        "2. IPO Early Entry boleh dipilih walau sesi 6-20, tetapi sebutkan bahwa risikonya agresif dan harus disiplin invalidasi.\n"
        "3. Jangan rekomendasikan entry jika blocker berisi broker_flow_not_positive, distribution_reversal, liquidity_below_threshold, atau price_extended_from_trigger.\n"
        "4. Jika status IPO Tunggu Retest, keputusan harus wait_pullback/retest, bukan entry_now.\n"
        "5. Gunakan levels sebagai sumber tunggal trigger, zona BOW, dan invalidasi. Jangan membuat level baru.\n"
        "6. Jelaskan alasan status dengan bahasa manusia: akumulasi, jarak harga ke trigger/AVWAP, volume, dan risiko IPO.\n\n"
        "Format output JSON:\n"
        "{\n"
        '  "top_candidates": [\n'
        "    {\n"
        '      "ticker": "...",\n'
        '      "decision": "entry_now | wait_breakout | wait_pullback | watch_only | skip",\n'
        '      "priority": 1,\n'
        '      "status_reason": "...",\n'
        '      "entry_plan": "...",\n'
        '      "invalidation": "...",\n'
        '      "confirmation_needed": "...",\n'
        '      "main_risks": ["..."]\n'
        "    }\n"
        "  ],\n"
        '  "summary": "..."\n'
        "}\n\n"
        "Data kandidat IPO:\n"
        + json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    )
