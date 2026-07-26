# Signal Detail Enhancement Plan

## Tujuan
Setiap signal (bandarmology, technical, breakout, dll) harus punya penjelasan detail yang bisa dipahami user: kenapa terdeteksi, parameternya apa, dan siapa pelakunya.

---

## 1. Bandarmology — Penjelasan per Signal

### 1.1 Hidden Accumulation
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `volume_spike` | Seberapa besar volume vs rata-rata | ✅ |
| `narrow_range` | Range harga sempit (akumulasi senyap) | ✅ |
| `flat` | Harga flat/menyamping | ✅ |
| **`brokers_buy`** | Broker mana yang beli terbanyak | ❌ |
| **`brokers_sell`** | Broker mana yang jual terbanyak | ❌ |
| **`net_flow`** | Net buy/sell value dari broker | Setengah (null) |

**Backend fix**: `load_bandar_flow` di `data_loader.py` sudah fetch marketdetectors, tapi `hidden_accumulation.py` hanya baca hasil parse tanpa mapping broker detail. Perlu:
- Simpan top 3 broker buy + sell di payload `hidden_accumulation`
- Ambil dari `brokers_buy` / `brokers_sell` di `market_detectors` response

### 1.2 Silent Accumulation
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `range_ratio` | Range / ATR ratio | ✅ |
| `volume_spike` | Volume spike ratio | ✅ |
| `broker_flow` | Broker net flow | ❌ |

### 1.3 Shakeout
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `drop_pct` | % penurunan | ✅ |
| `recover_pct` | % pemulihan | ✅ |
| `volume_spike` | Volume saat drop | ✅ |
| `candle_pattern` | Pola candle (hammer, engulfing) | ❌ |

### 1.4 Absorption
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `net_flow` | Net broker flow | ✅ |
| `pressure` | Buy/sell pressure | ✅ |
| `accumulation_days` | Berapa hari akumulasi berturut-turut | ❌ |

### 1.5 Bandar Positioning
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `buy_value` / `sell_value` | Total buy/sell value | ✅ |
| **`top_brokers`** | Top 3 broker + value | ❌ |
| `position_change` | Perubahan posisi vs hari sebelumnya | ❌ |

### 1.6 Consistency
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `consistent_days` | Hari berturut-turut | ✅ |
| `trend_strength` | Kekuatan tren akumulasi/distribusi | ❌ |

### Frontend
- **Kolom "Details"** di `/data/bandarmology` → sudah ada formatter basic, perlu di-expand
- **Halaman detail per ticker** → `/charts/[ticker]` tampilkan bandar panel dengan popover/tooltip yang jelasin tiap signal
- **Broker table** di bawah bandar chart, list top 5 broker + net value

---

## 2. Technical — Penjelasan per Method

### 2.1 Trend Structure
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `ema20`, `ema50`, `sma200` | Nilai EMA/SMA | ✅ |
| `slope50` | Kemiringan EMA50 | ✅ |
| `structure` | uptrend/downtrend/range | ✅ |
| `above_200sma` | Di atas SMA200? | ✅ |
| **`ema20_cross_ema50`** | EMA20 vs EMA50 posisi | ❌ |
| **`hh_hl_sequence`** | Higher high / higher low | ❌ |

### 2.2 Price Action
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `atr` | Average True Range | ✅ |
| `nearest_resistance` / `nearest_support` | S/R terdekat | ✅ |
| `body_ratio` | Rasio body candle | ✅ |
| `close_position` | Posisi close vs range | ✅ |
| `near_sr` | Dekat S/R? | ✅ |
| **`swing_high` / `swing_low`** | Pivot level | ❌ |
| **`breakout_sr`** | Break S/R? | ❌ |

### 2.3 Volume Breakout
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `spike_ratio` | Volume / MA20 | ✅ |
| `obv_rising` / `adl_rising` | OBV/ADL naik? | ✅ |
| `breakout` | Breakout terdeteksi? | ✅ |
| `move_pct` | % pergerakan harga | ✅ |
| `bullish_break` | Bullish atau bearish? | ✅ |
| **`consecutive_spikes`** | Berapa candle volume naik berturut-turut | ❌ |

### 2.4 Candlestick
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `pattern` | Nama pola | ✅ |
| `body` | Body size | ✅ |
| `range` | High-low range | ✅ |
| `upper_wick` / `lower_wick` | Wick size | ✅ |
| **`confirmation`** | Pola terkonfirmasi candle berikutnya? | ❌ |

### 2.5 Relative Strength
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `rs` | RS ratio vs IHSG | ✅ |
| `rs_ma20` | RS moving average | ✅ |
| `rs_mom_20d` | RS momentum 20 hari | ✅ |
| `outperforming` | Outperform IHSG? | ✅ |

### 2.6 Harmonic
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `pattern` | Nama pola (Gartley, Bat, dll) | ✅ |
| `pivots` | 5 titik pivot (harga + tanggal) | ✅ |
| `ratios` | Fibonacci ratios (XAB, ABC, BCD, XAD) | ✅ |

### 2.7 Elliott Wave
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `label` | impulse_up/down, corrective | ✅ |
| `pivots` | Swing pivot points | ✅ |
| **`wave_count`** | Posisi wave saat ini | ❌ |

### 2.8 Breakout (baru)
| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `close` vs `ema20` | Posisi vs EMA20 | ✅ |
| `ema5` vs `ema20` | EMA5 cross EMA20 | ✅ |
| `rsi14` | Nilai RSI | ✅ |
| `vol_ratio` | Volume / MA20 | ✅ |
| `high_3` | High 3 candle sebelumnya | ✅ |
| `is_fresh` | Breakout baru? | ✅ |
| `passed` | Jumlah kondisi terpenuhi (0-7) | ✅ |

### Frontend
- **Kolom "Details"** di `/data/technical` → sudah ada formatter, perlu di-expand untuk semua field
- **Chart overlay** di `/charts/[ticker]` → tampilkan EMA, RSI, volume spike di chart harga
- **Indicator panel** → list semua technical signal dengan deskripsi singkat

---

## 3. Scores — Penjelasan Composite

| Parameter | Deskripsi | Sudah ada di UI? |
|---|---|---|
| `composite` | Skor gabungan | ✅ Dashboard |
| `phase` | Fase market | ✅ |
| `sub_scores` | Skor per komponen | ✅ Radar chart |
| `dominant_factors` | Faktor dominan | ✅ |
| `weights` | Bobot adaptif | ❌ (tidak ditampilkan) |
| **`phase_reason`** | Kenapa dapat fase ini? | ❌ |

### Frontend
- Tambah **tooltip** di radar chart yang jelasin tiap sub-score
- Tampilkan **weights** di panel terpisah

---

## 4. Foreign Flow — Penjelasan

| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `foreign_buy` / `foreign_sell` | Buy/sell value | ✅ |
| `net_foreign` | Net flow | ✅ |
| `net_foreign_pct` | Net % dari total | ✅ |
| `score` | Skor foreign flow | ✅ |
| **`consecutive_inflow`** | Berapa hari net inflow berturut-turut | ❌ |
| **`net_20d`** | Akumulasi net 20 hari | ❌ |

---

## 5. Market Regime — Penjelasan

| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `regime` | trending_up/down/range/volatile | ✅ |
| `meta` | Metadata (ADX, volatility, dll) | ✅ (API) |

### Frontend
- Tampilkan **regime info** di dashboard header
- Tampilkan **meta detail** di halaman terpisah

---

## 6. Recommendations — Penjelasan

| Parameter | Deskripsi | Sudah ada? |
|---|---|---|
| `action` | BUY/ACCUMULATE/HOLD/REDUCE/SELL | ✅ Dashboard |
| `entry` / `stop` / `target` | Level harga | ✅ |
| `rationale` | Alasan AI | ✅ |
| `dominant_factors` | Faktor dominan | ✅ |
| `risks` | Risiko | ✅ |
| **`confidence`** | Confidence dari AI | ❌ |

---

## 7. Implementation Tasks

### Backend
- [ ] **Bandarmology modules**: Tambah broker detail (top 3 buy/sell) ke payload hidden_accumulation, silent_accumulation, bandar_positioning
- [ ] **Bandarmology modules**: Tambah `consecutive_days`, `candle_pattern` ke absorption, shakeout
- [ ] **Technical modules**: Tambah `hh_hl_sequence` ke trend_structure, `swing_high/low` ke price_action, `consecutive_spikes` ke volume_breakout, `confirmation` ke candlestick, `wave_count` ke elliott_wave
- [ ] **Foreign Flow**: Tambah `consecutive_inflow`, `net_20d` ke foreign flow scorer
- [ ] **Scores**: Tambah `phase_reason` ke compute_score
- [ ] **Recommendations**: Tambah `confidence` field ke RecommendationOut schema

### Frontend
- [ ] **Chart page** `/charts/[ticker]`: 
  - Indicator overlay di candlestick chart (EMA20, high_3)
  - Broker table di bawah bandar panel
  - Tooltip di radar chart
- [ ] **Data explorer**: Expand semua "Details" column formatter
- [ ] **Dashboard**: Tampilkan market regime di header

---

## 8. Priority

| Priority | Task | Impact |
|---|---|---|
| **High** | Broker detail di bandarmology | User bisa lihat siapa yang akumulasi |
| **High** | Indicator overlay di chart | Chart lebih informatif |
| **Medium** | Expand Details formatter | Semua signal ada penjelasan |
| **Medium** | Foreign flow consecutive days | Konteks inflow/outflow |
| **Low** | Phase reason, wave count | Nice to have |
