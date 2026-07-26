# Plan: NeoBDM Columns & Screener Integration

> Status: DRAFT (belum dieksekusi). Dibuat 2026-07-18.
> Sumber: `NeoBDM _ Referensi Kolom Market Summary.pdf` + `Neobdm Screener.pdf` (ChatGPT racikan).
> Tujuan: bawa kolom & preset screener NeoBDM ke Fajr-Quant yang sudah punya
> engine bandarmology + foreign flow dari data Stockbit.

---

## 1. Konteks — apa yang SUDAH ada di Fajr-Quant

- `DailyPrice` (OHLCV) dari Stockbit `chartbit` / yfinance fallback.
- `ForeignFlow` (foreign_buy/sell/net + score) — sumber F langsung ada.
- `BandarmologySignal` (label: hidden/silent_accumulation/shakeout/absorption/
  bandar_positioning/consistency) + `SmartMoneySignal` — bahan M ada.
- `marketdetectors` Stockbit support param `investor_type`:
  `INVESTOR_TYPE_ALL | _FOREIGN | _INSTITUTION | _RETAIL`.
  Response: `broker_summary.brokers_buy[]` / `brokers_sell[]`
  field `netbs_broker_code, netbs_date, bval/sval, freq`.
- Screener engine saat ini berbasis **composite score** (`ScreenerFilter`),
  BELUM rule-based per kolom NeoBDM.

## 2. Pemetaan 6 Metode NeoBDM -> data Stockbit

| Metode | Arti | Sumber di Fajr-Quant | Cara derive |
|---|---|---|---|
| **F** | Foreign Flow | `ForeignFlow` (sudah ada) | net foreign per hari |
| **I** | Institution | `marketdetectors` `INVESTOR_TYPE_INSTITUTION` | sum net institusi |
| **R** | Retail | `marketdetectors` `INVESTOR_TYPE_RETAIL` | sum net retail |
| **NR** | NonRetail | `ALL − R` | net ALL dikurangi net retail |
| **M** | Bandarmologi | `BandarmologySignal` / `SmartMoneySignal.bandar_score` | akumulasi broker (engine sudah jalan) |
| **S** | Sultanmologi | `marketdetectors` ALL, exclude set broker I + MM | whale pribadi (lihat def §4) |
| **Z** | Zombiemologi | `marketdetectors` ALL, exclude (I ∪ R) | broker abu-abu (lihat def §4) |

**Kesimpulan:** ke-6 metode DAPAT di-derive dari data yang sudah di-fetch.
Hanya perlu tambah fetch `INVESTOR_TYPE_INSTITUTION` & `_RETAIL` (belum
dilakukan `data_loader` saat ini — cuma `_FOREIGN` yg dipakai di fallback).

Nilai metode = Σ net_value (Miliar Rupiah) per periode.
Versi `%` = net / total transaksi periode tersebut × 100.

### Periode (sudah didefinisikan NeoBDM)
- `d0` = hari ini, `d1` = kemarin
- `w0` = Senin–Jumat minggu ini (cumulative)
- `cN` = N candle terakhir (cumulative), mis. `c5`

## 3. Definisi Sultan (S) & Zombie (Z) — hasil diskusi

**Sultanmologi (S):** trader pribadi / akun whale yang beli banyak,
BUKAN institusi dan BUKAN market maker.
- Ambil `marketdetectors` `INVESTOR_TYPE_ALL`.
- Exclude broker code yang masuk **set institusi (I)** DAN **daftar MM statis**.
- Sisa = whale pribadi. Akumulasi = Σ net buy broker sisa per periode.
- Proxy "sultan" = top-N net-buy broker non-institusi non-MM dengan nilai
  jauh di atas median (1 transaksi raksasa atau konsisten besar).

**Zombiemologi (Z):** broker yang TIDAK dipakai institusi maupun retail
(bukan di set I, bukan di set R), sering muncul di saham gorengan,
berpengaruh ke pergerakan harga tapi BUKAN dari emiten (bukan insider/major holder).
- Z = broker yang muncul di `ALL` TAPI tidak ada di set `I` DAN tidak ada di set `R`.
- Akumulasi = Σ net_value broker Z per periode.
- Ini paling gampang dihitung: `ALL − (I ∪ R)`.

## 4. Rencana Implementasi (urutan eksekusi besok)

### Step 1 — `app/models/neobdm.py`
Definisi kolom & enum terstruktur (konstanta, belum perlu DB):
- `enum Period {D0, D1, W0, C5}`
- `enum Method {M, NR, F, S, I, Z}`
- `enum RotStrength {WEAK, STRONG, ABNORMAL}`
- `enum RotPhase {UNDERPERFORM, IMPROVING, OUTPERFORM, WEAKENING}`
- `enum RotDir {U, UR, R, BR, B, BL, L, UL}` (8 arah)
- `enum Liquidity {LOW, MEDIUM, HIGH, EXTREME}`
- Registry kolom -> field name, mis:
  `"M c5"` -> `m_c5`, `"%NR c5"` -> `pct_nr_c5`,
  `"RotDir D"` -> `rot_dir_d`, dst.

### Step 2 — `app/services/neobdm/derive.py`
Fungsi mengisi nilai kolom dari data existing:
- Teknikal (Close, Chg1/5/20, MA20, EMA20, RSI, MACD Hist, RVol20,
  Unusual, VolChg, MAVol) -> dihitung dari `DailyPrice` (pakai
  `app/utils/indicators.py` yang sudah ada: `ema, sma, rsi`).
- F, I, R, NR, S, Z -> derive dari `marketdetectors` dgn kombinasi
  `investor_type` + filter broker code (butuh tambah fetch I & R di
  `data_loader.load_bandar_flow` / fungsi baru).
- M -> ambil dari `SmartMoneySignal.bandar_score` / `BandarmologySignal`.
- Rot*, Clean, Cross, Likuiditas, Pinky, Suspended, FCA, Syariah, Mcap,
  Tval -> nullable / placeholder (belum ada data sumber; diisi bila ada).

### Step 3 — `app/models/neobdm_snapshot.py` + alembic migration
Tabel `neobdm_snapshots` (ticker, date, lalu kolom numerik & kategori
yang dipakai screener). Menyimpan hasil derive per hari per saham.
- `ScreenerRun` / `ScreenerResult` existing tetap dipakai untuk output.

### Step 4 — Preset NeoBDM di screener
Tambah field `preset: str | None` ke `ScreenerFilter` (schemas.py).
File `app/services/screener/presets_neobdm.py` berisi racikan dari PDF:
1. `pre_flight_balanced` (utama)
2. `aggressive_gorengan`
3. `silent_accumulation`
4. `early_breakout`
5. `scalping_1_2d` (+ `scalping_aggressive`, `buy_on_weakness`)
6. `anti_pucuk` (filter pengecualian)
Plus sistem **ranking** (RotDir UR > U > R; Clean tertinggi; %NR/%M c5
tertinggi; RVol 1.5–2.5; Chg5 < 8%).

### Step 5 — Tampilan kolom hasil
Sesuai PDF "Kolom yang perlu ditampilkan": Close, Chg1/5/20, MA20,
EMA20, RSI, MACD Hist, Volume, RVol20, Unusual, M d0/c5/%M c5,
NR d0/c5/%NR c5, S c5, Z c5, Clean, Cross, Pinky, Tektoker, Rot*,
Top3 Buy/Sell, Mcap, Tval, Likuiditas.

## 5. Catatan / Risiko
- Zombie butuh fetch `INVESTOR_TYPE_RETAIL` & `_INSTITUTION` yang belum
  dijalankan `data_loader` saat ini -> perlu tambah.
- Clean / Cross / Likuiditas / Rot* / Pinky adalah fitur "AI/rahasia"
  NeoBDM yang TIDAK ada di data Stockbit -> tetap nullable, screener
  jalan tanpa itu (pakai F + M + teknikal sebagai pengganti).
- Semua threshold di-hardcode dulu (kayak bandarmology existing), rencana
  dipindah ke config nanti.

## 5b. Dampak ke flow screener yang SUDAH ada

- `ScreenerFilter` existing TIDAK diubah bentuknya — cuma **ditambah**
  field opsional `preset: str | None`. Filter lama (methods, bandar_labels,
  phases, min_composite, dll) tetap jalan & backward-compatible.
- `run_screener` existing tetap dipakai untuk filter lama. Preset NeoBDM
  jalan lewat **branch baru** (jika `filt.preset` diisi) yg baca
  `neobdm_snapshots`, bukan mengganti logika lama.
- `ScreenerRun` / `ScreenerResult` (tabel output) dipakai bersama —
  tidak bikin tabel hasil baru.
- Model baru (`neobdm.py`, `neobdm_snapshot.py`) ADDITIVE — tidak
  mengubah `DailyPrice` / `ForeignFlow` / `BandarmologySignal` yg sudah
  dipakai pipeline harian.
- Alembic migration baru (add table), tidak alter tabel existing.

> Inti: ini penambahan fitur, bukan refactor. Flow & endpoint screener
> yang sudah berjalan tidak akan terganggu.

## TODO Checklist
- [ ] Step1: `app/models/neobdm.py` (enum + registry kolom)
- [ ] Step2: `app/services/neobdm/derive.py` (F/I/R/NR/S/Z + teknikal)
- [ ] Step2b: tambah fetch `INVESTOR_TYPE_INSTITUTION` & `_RETAIL` di data_loader
- [ ] Step3: `app/models/neobdm_snapshot.py` + alembic migration
- [ ] Step4: field `preset` di `ScreenerFilter` + `presets_neobdm.py`
- [ ] Step4b: branch preset di `run_screener`
- [ ] Step5: kolom tampilan hasil (schema `ScreenerResultRow`)
- [ ] Step6: tes manual 1 preset (Balanced) vs data existing

## 6. Bahan referensi (dari PDF, ringkas)
- Pre-Flight Balanced inti: Comp Any=T, Cross=F, Clean>=2, M c5>0,
  NR c5>0, %M c5>=5, %NR c5>=5, Chg1 -2..5, Chg5 -3..10,
  Chg20 -10..20, RVol20 1.2..3.5, Close ∈ [MA20, MA20*1.08],
  RSI 48..68, MACD Hist>=0, RotPhase=IMPROVING, RotStrength=STRONG,
  RotDir=UR, Suspend=F, FCA=F, Pinky=F.
- Scalping 1–2d inti: M d0>0, NR d0>0, %M d0>=5, %NR d0>=5,
  M c5>0, NR c5>0, Chg1 0..5, RVol20 1.5..3.5, Close ∈ [EMA20, EMA20*1.07],
  RSI 50..68, MACD Hist>0, SMACD GC=T, SAR Trend=BULL,
  RotPhase=IMPROVING, RotStrength=STRONG, RotDir ∈ {U,UR,R},
  Suspend=F, FCA=F, Pinky=F.
- Anti-Pucuk: Chg1<=7, Chg5<=15, Chg20<=30, Close<=MA20*1.12,
  RSI<=72, RotStrength!=ABNORMAL, excl 3WhiteSoldiers/ShootingStar/
  HangingMan/GravestoneDoji/BearEngulfing=FALSE.
