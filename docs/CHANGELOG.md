# Changelog

Semua perubahan yang memengaruhi data flow, schema, endpoint, scoring, AI
prompt, atau notifikasi WAJIB dicatat di sini.

## [0.1.0] - 2026-07-13
### Added
- Project scaffold: FastAPI backend, Next.js frontend, Docker Compose
  (db, redis, backend, worker, beat, flower, frontend).
- SQLAlchemy models + Alembic untuk: stocks, daily_prices,
  technical_indicators, bandarmology_signals, foreign_flows, market_regimes,
  stock_profiles, scores, recommendations, screener_runs/results,
  stockbit_tokens, telegram_settings, settings, watchlist_items.
- Stockbit client (price, marketdetectors, profile, shareholder, majorholder)
  dengan retry + token encryption (Fernet).
- yfinance client sebagai fallback price + benchmark IHSG.
- Data loader + Celery tasks/beat (daily pipeline 17:30 WIB).
- 6 modul analisis teknikal: trend_structure, price_action, volume_breakout,
  harmonic, relative_strength, candlestick, elliott_wave.
- 6 modul bandarmology: hidden/silent_accumulation, shakeout, absorption,
  bandar_positioning, consistency + foreign flow scoring.
- Market regime detection (trending_up/down, range, volatile).
- Scoring engine adaptif (default + regime-adjusted weights, adaptive
  learning via correlation, fase state machine, dominant factors).
- AI recommendation (DeepSeek, pluggable) dengan structured JSON output.
- Screener multi-metode (technical + bandar + phase + foreign + regime).
- Chart visualisasi: candlestick, score timeline, sub-score radar, bandar
  panel, foreign flow panel.
- Telegram notifier (test send + daily digest).
- Dokumentasi: ARCHITECTURE, DATA_SOURCES, TECHNICAL, BANDARMOLOGY, SCORING,
  AI_PROMPT, TELEGRAM, API.
- Cursor rule: aturan update dokumentasi + isolasi Stockbit client.
- IDX stock list seed: `backend/app/scripts/seed_stocks.py` membaca
  `backend/data/stock_list.xlsx` (963 ticker, 5 board) ke tabel `stocks`.
  Trigger via `POST /api/v1/tasks/seed-stocks` atau `python -m app.scripts.seed_stocks`.
- Initial Alembic revision untuk seluruh schema, termasuk `pipeline_runs`.
- Persistent pipeline monitoring (status, stage, progress, success/failure,
  result/error), API status, dashboard table, manual run button, dan Flower link.
- Celery Beat schedule diperbaiki dengan `crontab`: weekday 17:30 WIB.
- JWT expiry dibaca otomatis; token expired/401 dinonaktifkan dan dashboard
  menampilkan banner. Endpoint test token ditambahkan.
- Stockbit daily-price dan broker-summary parser disesuaikan dengan schema
  respons nyata BBCA. JWT plaintext dihapus dari `data_sources.md`.
- Integration verification: Stockbit BBCA HTTP 200 (9 daily rows), Yahoo BBCA
  20 daily rows, serta fallback pipeline menyimpan 650 prices, 2697 technical
  signals, dan 1 score pada database sementara.

### Known limitations
- Stockbit token JWT memiliki `exp`; refresh otomatis belum tersedia
  (re-input manual via UI).
- Threshold bandarmology & bobot scoring masih di kode; belum dipindah ke
  config table.
- Intraday 30 menit, paper trading, backtest ditunda ke v2.
- Email & WhatsApp notifier ditunda ke v3.
