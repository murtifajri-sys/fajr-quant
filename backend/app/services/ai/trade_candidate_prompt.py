"""Prompt builder for near-entry screener candidates."""
from __future__ import annotations

import json
from typing import Any


TRADE_CANDIDATE_SYSTEM_PROMPT = """Kamu adalah Fajr Quant, asisten analisis saham IDX.
Tugasmu memilih kandidat yang benar-benar siap entry atau paling mendekati siap entry dari output screener.
Utamakan disiplin risiko: jangan menyarankan entry agresif bila broker flow retail-like, label broker none, reversal risk, recent flow negatif, atau coverage buruk.
Respons HANYA dalam Bahasa Indonesia dan HANYA dalam format JSON."""


def _round(value: Any, digits: int = 2) -> Any:
    if isinstance(value, int | float):
        return round(float(value), digits)
    return value


def _compact_broker(broker: dict[str, Any] | None) -> dict[str, Any]:
    broker = broker or {}
    return {
        "status": broker.get("status"),
        "top_broker": broker.get("top_broker"),
        "cluster_brokers": broker.get("cluster_brokers"),
        "net": _round(broker.get("net"), 0),
        "pct_market_cap": _round(broker.get("pct_market_cap"), 4),
        "days_of_adv": _round(broker.get("days_of_adv"), 2),
        "coverage_ratio": _round(broker.get("coverage_ratio"), 4),
        "broker_coverage_ratio": _round(broker.get("broker_coverage_ratio"), 4),
        "positive_ratio": _round(broker.get("positive_ratio"), 4),
        "recency_sessions": broker.get("recency_sessions"),
        "recent_5_session_net": _round(broker.get("recent_5_session_net"), 0),
        "retention": _round(broker.get("retention"), 4),
        "cluster_ratio": _round(broker.get("cluster_ratio"), 4),
        "directional_purity": _round(broker.get("directional_purity"), 4),
        "retail_distribution_risk": broker.get("retail_distribution_risk"),
        "high_freq_low_value": broker.get("high_freq_low_value"),
        "low_freq_high_value": broker.get("low_freq_high_value"),
        "last_buy_date": broker.get("last_buy_date"),
    }


def _compact_setup(setup: dict[str, Any] | None) -> dict[str, Any]:
    setup = setup or {}
    return {
        "setup_type": setup.get("setup_type") or "no_setup",
        "setup_state": setup.get("setup_state"),
        "label": setup.get("label"),
        "last_price": _round(setup.get("last_price"), 2),
        "trigger_price": _round(setup.get("trigger_price"), 2),
        "zone_low": _round(setup.get("zone_low"), 2),
        "zone_high": _round(setup.get("zone_high"), 2),
        "invalidation_price": _round(setup.get("invalidation_price"), 2),
        "distance_pct": _round(setup.get("distance_pct"), 2),
        "risk_reward": _round(setup.get("risk_reward"), 2),
        "confirmations": setup.get("confirmations") or [],
        "confluences": setup.get("confluences") or [],
        "blockers": setup.get("blockers") or ["data_setup_belum_lengkap"],
        "warnings": setup.get("warnings") or [],
        "as_of_date": setup.get("as_of_date"),
    }


def build_trade_candidate_prompt(candidates: list[dict[str, Any]], max_candidates: int = 10) -> str:
    selected = candidates[:max(1, min(max_candidates, 10))]
    payload = []
    for item in selected:
        broker = item.get("broker") or {}
        trade_status = item.get("trade_status") or {}
        payload.append(
            {
                "rank": item.get("rank"),
                "ticker": item.get("ticker"),
                "name": item.get("name"),
                "trade_status": {
                    "label": trade_status.get("label"),
                    "code": trade_status.get("code"),
                    "summary": trade_status.get("summary"),
                    "blockers": trade_status.get("blockers") or [],
                    "warnings": trade_status.get("warnings") or [],
                    "passed": trade_status.get("passed") or [],
                },
                "setup_detail": _compact_setup(item.get("setup_detail")),
                "score": {
                    "composite": _round(item.get("composite"), 2),
                    "tech_phase": item.get("phase"),
                    "broker_conviction_score": _round(item.get("broker_conviction_score"), 2),
                    "broker_conviction_label": item.get("broker_conviction_label"),
                    "flow_quality_score": _round(item.get("flow_quality_score"), 2),
                    "flow_quality_label": item.get("flow_quality_label"),
                    "entry_readiness_score": _round(item.get("entry_readiness_score"), 2),
                    "combined_rank_score": _round(item.get("combined_rank_score"), 2),
                },
                "broker": _compact_broker(broker),
            }
        )

    return (
        "Kamu adalah analis trading IDX untuk Fajr Quant.\n"
        "Tugas: cari kandidat yang benar-benar siap entry atau paling mendekati siap entry dari data screener berikut.\n\n"
        "Aturan analisis:\n"
        "1. Prioritaskan trade_status Siap Entry, lalu Tunggu Konfirmasi yang blocker-nya paling ringan.\n"
        "2. Jangan rekomendasikan entry agresif jika flow_quality_label retail_like_accumulation, broker label none, reversal risk, recent flow negatif, atau coverage buruk.\n"
        "3. Gunakan setup_detail sebagai sumber tunggal level harga. Jangan mengarang trigger, zona, atau invalidasi di luar setup_detail.\n"
        "4. Jika setup_detail kosong/no_setup atau blocker berisi data_setup_belum_lengkap, tulis risiko data_setup_belum_lengkap dan turunkan confidence.\n"
        "5. Decision harus mengikuti setup_detail: ready -> entry_now hanya jika setup_state confirmed; wait_breakout; wait_retest; buy_on_weakness; wait_value_area; no_setup/blocked -> skip.\n"
        "6. Jelaskan alasan dengan bahasa manusia, bukan sekadar mengulang skor.\n"
        "7. Output dalam Bahasa Indonesia.\n\n"
        "Format output yang diminta:\n"
        "{\n"
        '  "top_candidates": [\n'
        "    {\n"
        '      "ticker": "...",\n'
        '      "decision": "entry_now | wait_breakout | wait_pullback | skip",\n'
        '      "priority": 1,\n'
        '      "setup_label": "...",\n'
        '      "trigger_or_zone": "...",\n'
        '      "invalidation": "...",\n'
        '      "reason": "...",\n'
        '      "confirmation_needed": "...",\n'
        '      "main_risks": ["..."]\n'
        "    }\n"
        "  ],\n"
        '  "summary": "..."\n'
        "}\n\n"
        "Data kandidat:\n"
        + json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    )
