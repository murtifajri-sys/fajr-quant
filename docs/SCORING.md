# Scoring

Engine adaptif di `backend/app/services/scoring/`. Inti: menggabungkan
sub-score dari technical + bandarmology + foreign flow + regime alignment
menjadi **composite score (0-100)** + **fase** + **dominant factors**.

## Sub-score per metode (0-100)
- Technical: `trend_structure, price_action, volume_breakout, harmonic,
  relative_strength, candlestick, elliott_wave`.
- Bandarmology: `hidden_accumulation, silent_accumulation, shakeout,
  absorption, bandar_positioning, consistency`.
- Foreign flow: dari `foreign_flows.score`.
- Regime alignment: dihitung dari kesesuaian trend_structure dengan regime
  (trend → skor tinggi jika |trend-50| besar; range → skor tinggi jika trend
  flat; volatile → ambil consistency).

## Bobot default (sum 1.0)
- Technical: 45% (trend 20, price_action 10, volume/breakout 10, harmonic 5,
  RS 5, candlestick 5, elliot 5 — di-normalize internal).
- Bandarmology: 40%.
- Foreign flow: 10%.
- Regime: 5%.

## Regime adjustment
`REGIME_WEIGHT_ADJUST` mengalikan bobot per grup berdasar regime:
- trending_up: technical ↑, bandar ↓
- trending_down: technical =, bandar ↑, foreign ↑
- range: technical ↓, bandar ↑↑
- volatile: technical ↓, bandar ↑, foreign ↑

Setelah adjust, bobot di-normalize ulang.

## Adaptive weights (per ticker)
`learn_adaptive_weights` menghitung korelasi tiap sub-score dengan forward
return (window 60 hari). Bobot ∝ |korelasi|, dengan penalti untuk korelasi
negatif. Hasil disimpan di `stock_profiles.weights` (flat, `tech:<m>` /
`bandar:<m>` / `foreign_flow` / `regime`) dan `dominant_method`.

Sistem belajar: saham A mungkin bandarmology-dominan, saham B breakout-dominan.
Profil ini dipakai scoring engine untuk ticker tersebut.

## Fase (state machine)
| Fase | Kondisi singkat |
|---|---|
| Awal | accumulation/consistency terdeteksi, composite < 50 |
| Tunggu Konfirmasi | accumulation + composite ≥ 50, belum ada breakout |
| Siap Entry | composite ≥ 70 + (breakout/absorption) + RS positif + trend up |
| Hold | composite ≥ 60 + trend up + (accumulation/consistency) |
| Siap Jual | distribution/weakness atau composite < 45 + weak trend |
| Exit | weak trend + no accumulation + composite < 40 |

Confidence = `min(100, 50 + 0.5×|composite-50|)`.

## Dominant factors
Top-3 kontributor (`sub_score × weight`) disimpan di `scores.dominant_factors`
untuk dipakai AI prompt dan UI.

## Penyimpanan
- `scores(ticker, date, composite, sub_scores JSON, weights JSON, phase,
  confidence, dominant_factors JSON)`.
- `stock_profiles(ticker, weights JSON, dominant_method, notes,
  sample_window_days)`.

## Tuning
Bobot default di `app/services/scoring/weights.py`. Threshold fase di
`app/services/scoring/phase.py`. Akan dipindah ke config (lihat CHANGELOG).
