"""Telegram notifier.

Uses the Bot API directly (sendMessage). Bot token is configured globally via env;
chat_id is configured per-user via the Telegram settings UI.
"""
import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import log


def _send(chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        log.warning("telegram_bot_token_missing")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    with httpx.Client(timeout=15) as client:
        resp = client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
    if resp.status_code >= 400:
        log.error("telegram_send_failed", status=resp.status_code, body=resp.text)
        return False
    return True


def send_test_message(chat_id: str) -> bool:
    return _send(chat_id, "*Fajr Quant*: test message OK.")


def send_token_expired_alert(db, ticker: str = "", task_name: str = "", detail: str = ""):
    from app.models.setting import TelegramSetting

    rows = db.execute(
        select(TelegramSetting).where(TelegramSetting.enabled.is_(True))
    ).scalars().all()
    if not rows:
        return
    lines = [
        "\u26a0\ufe0f *Fajr Quant \u2014 Token Expired*",
        "",
        f"Stockbit token expired saat proses *{task_name or 'data_load'}*.",
    ]
    if ticker:
        lines.append(f"Ticker terakhir: `{ticker}`")
    if detail:
        lines.append(f"Detail: {detail[:200]}")
    lines.append("")
    lines.append("Segera input token baru di Settings \u2192 Tokens.")
    text = "\n".join(lines)
    for row in rows:
        _send(row.chat_id, text)


def send_digest(chat_id: str, recommendations: list[dict], screener_rows: list[dict]) -> bool:
    lines = ["*Fajr Quant - Daily Digest*", ""]
    if screener_rows:
        lines.append("*Top Screener:*")
        for r in screener_rows[:10]:
            lines.append(
                f"- `{r['ticker']}` {r.get('name','')} | score {r['composite']:.0f} | {r['phase']}"
            )
        lines.append("")
    if recommendations:
        lines.append("*Recommendations:*")
        for rec in recommendations:
            lines.append(
                f"*{rec['ticker']}* -> {rec['action']} "
                f"entry {rec.get('entry')} / stop {rec.get('stop')} / target {rec.get('target')}"
            )
            if rec.get("rationale"):
                lines.append(f"  _{rec['rationale']}_")
    if not screener_rows and not recommendations:
        lines.append("_No signals today._")
    return _send(chat_id, "\n".join(lines))
