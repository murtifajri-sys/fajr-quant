# Telegram

Notifikasi via Bot API (HTTP `sendMessage`). Bot token global dari env
`TELEGRAM_BOT_TOKEN`; `chat_id` per-user via UI Settings → Telegram.

## Setup
1. Buat bot via @BotFather, salin `TELEGRAM_BOT_TOKEN` ke `.env`.
2. UI Settings → Telegram → isi Chat ID (dapatkan dari @userinfobot).
3. Klik "Test Send" untuk verifikasi.

## Pesan
- **Daily digest** (17:30 WIB weekday via Celery beat): top 10 screener +
  10 recommendation terbaru. Format Markdown, satu blok per ticker.
- Struktur pesan: header → Top Screener → Recommendations.

## Endpoint
- `GET /api/v1/telegram`
- `POST /api/v1/telegram` (upsert)
- `POST /api/v1/telegram/{id}/test`

## Task Celery
- `send_daily_digest`: dikirim oleh `run_daily_pipeline` (delay 15 menit
  agar scoring selesai).
- `app/workers/tasks.py`: beat schedule `daily-pipeline` 17:30 WIB.

## Roadmap
v3: email + WhatsApp notifier (interface sudah siap di
`app/services/notifier/`).
