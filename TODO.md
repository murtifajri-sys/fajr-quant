# TODO — Fajr-Quant Improvement

## 1. Cancel Task ✅
- [ ] **Backend**: Endpoint `POST /api/v1/tasks/{task_id}/cancel`
  - Panggil `celery_app.control.revoke(task_id, terminate=True)`
  - Update `pipeline_runs` status ke `CANCELLED`
  - Return response `{ "task_id": "...", "status": "CANCELLED" }`
- [ ] **Frontend**: Tombol **Cancel** di tabel Pipeline Status
  - Hanya muncul untuk task yang statusnya `PROGRESS` / `QUEUED`
  - Konfirmasi dialog sebelum cancel
  - Refresh tabel setelah cancel

## 2. Token 401 — Jangan Matikan Semua Ticker 🛡️
- [ ] **Backend** (`base.py`): Saat dapat 401, jangan langsung `active=False`
  - Ganti: log warning, retry 1x setelah delay 30 detik
  - Kalau masih gagal → skip ticker itu saja (return empty data)
  - Token tetap aktif, ticker berikutnya tetap bisa coba
- [ ] **Backend** (`data_loader.py`): Graceful fallback
  - `load_bandar_flow` & `load_foreign_flow` sudah ada try/except → return `[]`
  - `load_prices` sudah ada fallback ke yfinance → OK
  - Pastikan tidak ada re-raise yang mematikan loop

## 3. Delay Antar Stockbit API Call ⏱️
- [ ] **Backend** (`stockbit.py` atau `data_loader.py`): Tambah `time.sleep(0.5)` setelah setiap panggilan Stockbit
  - Atau bikin config `STOCKBIT_RATE_LIMIT_DELAY` di `config.py`
  - Default 0.5 detik, bisa di-set ke 0 untuk testing

## 4. Parallel Processing ⚡
- [ ] **Backend** (`tasks.py` — `run_full_data_load`): Ganti `for` loop dengan `ThreadPoolExecutor`
  - Max worker: 3-5 (configurable via `settings.PIPELINE_MAX_WORKERS`)
  - Setiap worker buat DB session sendiri (tidak share `db`)
  - `_progress` tetap update record pipeline yang sama
  - `_progress` harus thread-safe (pakai lock atau DB session terpisah per update)
- [ ] **Config** (`config.py`): Tambah `PIPELINE_MAX_WORKERS: int = 3`

## 5. Cache Benchmark Data 🗂️
- [ ] **Backend** (`pipeline.py`): `_benchmark_df` untuk `^JKSE` di-fetch ulang per ticker
  - Fetch & cache sekali di awal `run_full_data_load`
  - Passing sebagai parameter ke `compute_technical`
  - Atau simpan di module-level cache dengan TTL

## 6. Validasi Token Expiry Saat Input 🕒
- [ ] **Backend** (`tokens.py` — `POST /api/v1/tokens`): Validasi `exp` claim JWT
  - Decode JWT tanpa verifikasi, baca `exp`
  - Kalau < 2 jam dari sekarang → warning di response
  - Kalau sudah expired → tolak dengan error jelas
- [ ] **Frontend** (`settings/tokens`): Tampilkan warning kalau token dekat expired
  - Info bar: "Token akan expired dalam X jam"

## 7. Notifikasi Telegram Saat Token Expired 🔔
- [ ] **Backend** (`telegram.py`): Tambah fungsi `send_alert(chat_id, title, message)`
  - Kirim notifikasi ke semua `TelegramSetting` yang `enabled=True`
  - Contoh pesan: "⚠️ Token Stockbit expired saat proses *data_load* ticker *BBRI* (12/50)"
- [ ] **Backend** (`base.py`): Panggil `send_alert` saat token kena 401
  - Kirim notifikasi sebelum fallback/skip ticker
  - Sertakan info: task_name, ticker saat ini, progress

## 8. Halaman Detail Task 🔍
- [x] **Frontend**: Halaman `/tasks/[task_id]`
  - Tampilkan full detail: stage, progress, total/succeeded/failed tickers
  - List ticker yang gagal + error message (dari `result.errors`)
  - Auto-refresh setiap 3 detik kalau status `PROGRESS`
- [x] **Frontend**: Link task_name di dashboard ke halaman detail

## 9. Auto-refresh Pipeline Table 🔄
- [x] **Frontend** (`PipelineTable.tsx`): Self-fetch `GET /tasks/runs` tiap 3 detik
- [x] **Frontend** (`PipelineActions.tsx`): Hapus tombol "Refresh Status" (redundant)

## 10. Data Explorer (Phase 1) 📊 ✅
Lihat detail lengkap di `docs/DATA_EXPLORATION_PLAN.md`.

### Backend
- [x] `GET /api/v1/data/prices` — filter ticker, date range, source
- [x] `GET /api/v1/data/bandarmology` — filter ticker, date, label, detected, score
- [x] `GET /api/v1/data/foreign-flow` — filter ticker, date, net flow
- [x] `GET /api/v1/data/technical` — filter ticker, date, method, score
- [x] `GET /api/v1/data/scores` — filter ticker, date, phase, composite
- [x] `GET /api/v1/data/recommendations` — filter ticker, date, action
- [x] `GET /api/v1/data/stocks` — filter ticker prefix, sector, industry, board
- [x] `GET /api/v1/data/filters` — metadata dropdown (sectors, phases, actions, dll)

### Frontend
- [x] Menu "Data" di navbar
- [x] Halaman `/data` index card menu
- [x] Shared components: `DataTable.tsx`, `PaginationBar.tsx`
- [x] Halaman `/data/prices`, `/data/bandarmology`, `/data/foreign`, `/data/technical`, `/data/scores`, `/data/recommendations`, `/data/stocks`
- [x] Pagination 50 rows per page

## 11. Data Explorer (Phase 2) 📈
- [ ] Export CSV per halaman
- [ ] Chart mini per halaman
- [ ] Broker autocomplete
- [ ] Full-text search rationale rekomendasi

## 12. Data Explorer (Phase 3) 🔬
- [ ] Saved filters
- [ ] Cross-table view (price + score + foreign flow)
- [ ] DB JSON operator filtering

