# Technical Analysis

Modul di `backend/app/services/technical/`, masing-masing menghasilkan list
`{date, name, payload, score}` (0-100) yang dipersist ke `technical_indicators`.

Indikator dasar (`app/utils/indicators.py`): SMA, EMA, RSI, MACD, ATR,
Bollinger, OBV, ADL, VWAP, Stochastic, swing points.

## 1. Trend Structure (`trend_structure.py`)
- EMA20/EMA50/SMA200 alignment + slope EMA50.
- Output `structure`: `uptrend` / `downtrend` / `range`, plus `above_200sma`.
- Skor: uptrend kuat → 80-90; downtrend → rendah; range → 50.

## 2. Price Action (`price_action.py`)
- Swing pivots → support/resistance dinamis (10 swing terakhir).
- Body ratio, close position dalam range, kedekatan ke S/R (vs ATR).
- Skor: bullish close-position + body + dekat SR → naik.

## 3. Volume + Breakout (`volume_breakout.py`)
- OBV, ADL, volume MA20, volume spike ratio, breakout vs ATR.
- Bullish breakout (close change > 1.5×ATR) → skor tinggi.

## 4. Harmonic Pattern (`harmonic.py`)
- Pivot-based: cari 5 pivot terakhir (X,A,B,C,D) lalu cek rasio Fibonacci.
- Pola: Gartley, Bat, Butterfly, Crab, Shark (toleransi 8%).
- Bullish reversal (pivot D rendah) → skor tinggi.

## 5. Relative Strength (`relative_strength.py`)
- RS ratio = close_saham / close_benchmark (`^JKSE`).
- RS MA20, RS momentum 20 hari.
- Outperforming (RS > RS-MA, momentum > 0) → skor tinggi.

## 6. Candlestick (`candlestick.py`)
- Deteksi: doji, bullish/bearish engulfing, hammer, shooting star,
  morning/evening star.
- Bullish pattern → 75; bearish → 25; doji → 50.

## 7. Elliott Wave (`elliott_wave.py`)
- Heuristik: label 5 pivot terakhir sebagai impulse up/down atau corrective.
- Wave 3 terpanjang → konfirmasi impulse up.

## Penyimpanan
- Tabel `technical_indicators(ticker, date, method, name, payload JSON, score)`.
- Index `(ticker, date, method)`.
- Payload berisi detail (levels, ratios, pivots) untuk visualisasi chart.
