# Fajr Quant

Aplikasi analisa saham untuk pasar Indonesia (IDX) yang menggabungkan **analisis
teknikal**, **bandarmology**, dan **AI recommendation** dengan scoring adaptif.

## Fitur (v1)
- Data harga harian dari Stockbit (Exodus API) dengan fallback yfinance.
- Analisis teknikal: trend structure, price action, volume/breakout, harmonic
  pattern, relative strength, candlestick, Elliott Wave.
- Bandarmology: hidden/silent accumulation, shakeout, absorption, bandar
  positioning, consistency, foreign flow.
- Market regime (trend up/down, range, volatile) dari IHSG.
- Scoring engine adaptif yang belajar karakter tiap saham + fase state machine.
- AI recommendation (DeepSeek, pluggable).
- Screener multi-metode + chart visualisasi per ticker.
- Notifikasi Telegram (digest harian).

## Tech stack
- Backend: Python 3.11, FastAPI, SQLAlchemy, Celery, Redis.
- Frontend: Next.js 14, TypeScript, Tailwind, Recharts.
- Database: MySQL / MariaDB.
- AI: DeepSeek (OpenAI-compatible API).

## Quick start
1. Salin env: `cp backend/.env.example backend/.env` dan isi `ENCRYPTION_KEY`,
   `AI_API_KEY`, `TELEGRAM_BOT_TOKEN`.
2. Jalankan: `docker compose up --build`.
3. Buka UI: http://localhost:3000 → Settings → masukkan Stockbit token.
4. Trigger pipeline: `POST /api/v1/tasks/daily-pipeline` atau tunggu beat
   harian 17:30 WIB.

## Struktur
Lihat [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) untuk arsitektur lengkap.

## Dokumentasi
- [Architecture](docs/ARCHITECTURE.md)
- [Data Sources](docs/DATA_SOURCES.md)
- [Technical Analysis](docs/TECHNICAL.md)
- [Bandarmology](docs/BANDARMOLOGY.md)
- [Scoring](docs/SCORING.md)
- [AI Prompt](docs/AI_PROMPT.md)
- [Telegram](docs/TELEGRAM.md)
- [API](docs/API.md)
- [Operations](docs/OPERATIONS.md)
- [Changelog](docs/CHANGELOG.md)

## Catatan
Endpoint Stockbit Exodus bersifat internal (tidak resmi). Semua akses
dilewatkan via `backend/app/clients/stockbit.py` agar mudah beradaptasi saat
endpoint berubah. Token disimpan terenkripsi (Fernet) di database.

## Daftar ticker IDX
File `Stock List - 20260713.xlsx` (963 ticker IDX) disalin ke
`backend/data/stock_list.xlsx`. Seed ke tabel `stocks` via:
```bash
docker compose exec backend python -m app.scripts.seed_stocks
# atau
curl -X POST http://localhost:8000/api/v1/tasks/seed-stocks
```
Kolom: `Code`, `Company Name`, `Listing Date`, `Shares`, `Listing Board`
(Main/Development/Watchlist/Acceleration/Ekonomi Baru). Saat file update,
ganti `stock_list.xlsx` dan jalankan ulang seed (upsert by ticker).
