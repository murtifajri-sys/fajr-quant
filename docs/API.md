# API

Base URL: `/api/v1`. Semua response JSON.

## Health
- `GET /health` → `{status, app}`

## Tokens (Stockbit)
- `GET /tokens` → status, expiry, dan error tanpa mengembalikan plaintext.
- `POST /tokens` body: `{label, token, expires_at?}` → simpan terenkripsi;
  `exp` JWT dibaca otomatis jika `expires_at` kosong.
- `DELETE /tokens/{id}`
- `POST /tokens/{id}/activate`
- `POST /tokens/{id}/test` → verifikasi koneksi nyata ke Stockbit.

## Telegram
- `GET /telegram` | `POST /telegram` body `{label, chat_id, enabled, daily_digest_time}`
- `POST /telegram/{id}/test`

## Stocks
- `GET /stocks?q=&limit=` → list ticker.

## Technical
- `GET /technical/{ticker}/prices?days=500`
- `GET /technical/{ticker}/signals?days=120`
- `GET /technical/{ticker}/indicators/{method}?days=120`

## Bandarmology
- `GET /bandarmology/{ticker}/signals?days=90`
- `GET /bandarmology/{ticker}/foreign-flow?days=90`

## Scoring
- `GET /scoring/{ticker}/scores?days=120`
- `GET /scoring/{ticker}/profile`

## Screener
- `POST /screener/run` body:
  ```json
  {
    "methods": ["volume_breakout"],
    "bandar_labels": ["absorption"],
    "phases": ["Siap Entry"],
    "min_composite": 60,
    "require_foreign_inflow": true,
    "universe": "idx",
    "top_n": 20
  }
  ```
- `GET /screener/latest`
- `GET /screener/{run_id}`

## Charts
- `GET /charts/{ticker}/overview?days=180` → prices, technical, bandarmology,
  foreign_flow, scores (aggregated untuk visualisasi).

## Recommendations
- `GET /recommendations/{ticker}?days=60`
- `GET /recommendations?limit=20`

## Tasks (Celery)
- `POST /tasks/data-load?ticker=` → enqueue `run_full_data_load`.
- `POST /tasks/scoring?ticker=` → enqueue scoring + recommendation.
- `POST /tasks/daily-pipeline` → enqueue full EOD pipeline.
- `POST /tasks/seed-stocks` → load IDX ticker list from `backend/data/stock_list.xlsx` into `stocks`.
- `GET /tasks/runs?limit=20` → recent pipeline status.
- `GET /tasks/{task_id}` → status, progress, result, dan error satu task.
