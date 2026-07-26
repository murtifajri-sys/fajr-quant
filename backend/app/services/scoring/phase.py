"""Phase state machine.

Fase:
  - Awal              : early accumulation detected, no confirmation
  - Tunggu Konfirmasi : signal formed but needs trigger
  - Siap Entry        : confirmation (breakout/absorption + RS positive)
  - Hold              : healthy trend, no distribution
  - Siap Jual         : distribution/weakness detected
  - Exit              : strong sell signal
"""

PHASES = ["Awal", "Tunggu Konfirmasi", "Siap Entry", "Hold", "Siap Jual", "Exit"]


def determine_phase(
    composite: float,
    sub_scores: dict,
    bandar_detected: dict[str, bool],
    technical_signals: dict[str, float | None],
    regime: str,
) -> tuple[str, float]:
    """Return (phase, confidence)."""
    accumulation = bandar_detected.get("hidden_accumulation") or bandar_detected.get("silent_accumulation") or bandar_detected.get("absorption")
    consistency = bandar_detected.get("consistency", False)
    shakeout = bandar_detected.get("shakeout", False)
    bandar_pos = bandar_detected.get("bandar_positioning", False)
    rs_score = technical_signals.get("relative_strength")
    rs_positive = rs_score is not None and rs_score > 55
    trend_up = (technical_signals.get("trend_structure") or 50) > 55
    breakout = (technical_signals.get("volume_breakout") or 50) > 65
    distribution = bandar_pos is False and consistency is False and (technical_signals.get("volume_breakout") or 50) < 35
    weak_trend = (technical_signals.get("trend_structure") or 50) < 40

    confidence = min(100.0, 50.0 + 0.5 * abs(composite - 50))

    if weak_trend and not accumulation and composite < 40:
        return "Exit", confidence
    if distribution or (shakeout is False and composite < 45 and weak_trend):
        return "Siap Jual", confidence
    if composite >= 70 and (breakout or accumulation) and rs_positive and trend_up:
        return "Siap Entry", confidence
    if composite >= 60 and trend_up and (accumulation or consistency):
        return "Hold", confidence
    if accumulation and composite >= 50:
        return "Tunggu Konfirmasi", confidence
    if accumulation or consistency:
        return "Awal", confidence
    return "Tunggu Konfirmasi", confidence
