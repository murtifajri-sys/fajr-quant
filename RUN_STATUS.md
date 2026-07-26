# Status Run - Fajr Quant

> Dibuat: 2026-07-14 21:40 WIB  
> Terakhir update: 2026-07-15 07:20 WIB  
> Penulis: OpenCode Agent

---

## Ringkasan

Semua task besar sudah selesai. Data terbaru dari Stockbit sudah dimuat, rekomendasi AI sudah dibuat untuk top 150 saham, dan semua fitur normalisasi `% MCap` / `% ADV` sudah aktif.

---

## Status Final

| Task | Status | Detail |
|------|--------|--------|
| `recompute` | ✅ SUCCESS | 963/963 ticker, 50 gagal |
| `data_load` | ✅ SUCCESS | 963/963 ticker, 788 ok, 175 gagal |
| `recommendations` | ✅ SUCCESS | 150/150 ticker, 0 gagal |

---

## Timeline

- **2026-07-14 21:38** - Worker di-scale ke 3 container
- **2026-07-14 21:38** - Background monitor script dijalankan
- **2026-07-14 23:11** - `data_load` selesai
- **2026-07-14 23:11** - Worker restart untuk aktifkan kode rekomendasi baru
- **2026-07-14 23:11** - `recommendations` batch (top 150) ditrigger
- **2026-07-14 23:12** - `recommendations` selesai (150/150)

---

## Catatan Penting: 175 Ticker Gagal di data_load

Bukan karena token invalid, melainkan **race condition** saat banyak worker paralel mengupdate `last_used_at` di tabel `stockbit_tokens`.

Contoh error:

```text
(pymysql.err.OperationalError) (1020, "Record has changed since last read in table 'stockbit_tokens'")
```

## Fix Race Condition (Sudah Diterapkan)

Perubahan di `backend/app/clients/base.py`:
- `mark_token_used` sekarang pakai **raw SQL UPDATE** (bukan read-modify-write).
- Ditambahkan **retry 3x** jika terjadi `OperationalError` saat update token.
- Worker sudah di-restart untuk aktifkan kode baru.

Test cepat:
- `BCCA`: ✅ SUCCESS
- `AALI`: ✅ SUCCESS
- `BMRI`: ✅ SUCCESS

Verifikasi penuh dengan full data_load 963 ticker dijadwalkan **15 Juli 2026 jam 18:00 WIB** via screen session `data_load_18wib`.

---

## Daily Load Incremental (Baru)

### Masalah
`load_prices` sebelumnya selalu mengambil `TECHNICAL_LOOKBACK_DAYS = 1000` hari per ticker, bahkan untuk daily run.

### Solusi
Ditambahkan mode **incremental** untuk daily load:
- Kalau ticker sudah punya data hari ini → **skip** (tidak panggil Stockbit).
- Kalau belum → ambil hanya data yang kurang + overlap 5 hari untuk antisipasi revisi.
- Full lookback 1000 hari tetap tersedia untuk backfill manual.

### File yang berubah
- `backend/app/core/config.py` - Tambah `DAILY_INCREMENTAL_OVERLAP_DAYS` dan `DAILY_INCREMENTAL_MAX_DAYS`
- `backend/app/services/data_loader.py` - `load_prices` support `incremental=True`
- `backend/app/services/pipeline.py` - `run_full_analysis` support `incremental`
- `backend/app/workers/tasks.py` - `run_full_data_load` support `incremental`, daily pipeline otomatis incremental
- `backend/app/api/routes/tasks.py` - Endpoint `data-load` support query param `incremental`

### Test Incremental
- `BBCA` incremental: ✅ SUCCESS (~20 detik, sudah up-to-date)
- `TLKM` incremental: ✅ SUCCESS
- `BBRI` incremental: ✅ SUCCESS

### Dampak
Daily pipeline ke depan tidak akan butuh 3 jam lagi. Estimasi **5-15 menit** untuk 963 ticker, karena hanya mengisi data yang belum ada.

---

## Cara Cek Status

```bash
# Cek log monitor
tail -100 /home/fajrirog/Fajr-Quant/monitor_and_recommend.log

# Cek status semua task
curl -s http://localhost:8000/api/v1/tasks/runs | python3 -m json.tool

# Cek screen session (sudah selesai, bisa di-kill)
screen -ls
```

---

## File yang Berubah

- `backend/app/api/routes/charts.py` - Top broker % MCap / % ADV
- `backend/app/api/routes/data.py` - Normalisasi % MCap / % ADV untuk Bandarmology & Foreign Flow
- `backend/app/api/schemas.py` - Field `pct_market_cap`, `pct_avg_daily_value`
- `backend/app/core/config.py` - Tambah `RECOMMENDATION_MAX_TICKERS = 150`, `DAILY_INCREMENTAL_*`
- `backend/app/workers/tasks.py` - Filter recommendations ke top 150 + incremental daily load
- `backend/app/services/data_loader.py` - `load_prices` support incremental
- `backend/app/services/pipeline.py` - `run_full_analysis` support incremental
- `backend/app/api/routes/tasks.py` - Endpoint `data-load` support `incremental` param
- `frontend/components/ChartPanels.tsx` - Top broker detail + sorting % MCap
- `frontend/app/data/bandarmology/page.tsx` - Kolom % MCap / % ADV
- `frontend/app/data/foreign/page.tsx` - Kolom % MCap / % ADV
- `backend/app/clients/base.py` - Fix race condition update token
- `monitor_and_recommend.sh` - Script background monitor
- `run_data_load_18wib.sh` - Script scheduled 18:00 WIB
- `RUN_STATUS.md` - File ini

---

## Rekomendasi AI

- Dibatasi ke **top 10 saham** berdasarkan composite score hari ini.
- Hemat token AI dibanding 963 saham atau top 150 sebelumnya.
- Semua 10 saham berhasil diproses tanpa error.

### Regenerasi 15 Juli 2026

- Konfigurasi `RECOMMENDATION_MAX_TICKERS` diubah dari `150` ke `10`.
- Prompt AI diubah: rationale wajib Bahasa Indonesia, lebih manusiawi, dan menjelaskan artinya bukan cuma angka teknis.
- Timeout AI provider dinaikkan dari 60 detik ke 120 detik untuk menghindari `read operation timed out`.
- **Filter rekomendasi baru** aktif: saham dengan rata-rata nilai transaksi harian di bawah 500 juta IDR atau rata-rata wick > 5% tidak dimasukkan rekomendasi.
- **Fallback model gratis** aktif: bila `deepseek-v4-pro` kehabisan token (402/429), otomatis pakai `deepseek-v4-flash` (gratis).
- Menu Recommendations default hanya hari ini + date picker; data lama 2026-07-14 (844 duplikat) dihapus.
- Worker dan backend di-restart untuk mengaktifkan konfigurasi baru.
- 1.269 rekomendasi lama untuk hari ini dihapus, kemudian di-generate ulang top 10.
- Task `recommendations` status **SUCCESS**: 10/10 ticker, 0 gagal.
