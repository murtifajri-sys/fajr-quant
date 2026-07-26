# AI Prompt

Provider: DeepSeek (OpenAI-compatible). Interface di
`app/services/ai/base.py`, implementasi `deepseek.py`. Switch via
`AI_PROVIDER` env.

## Input yang diberikan ke AI
1. Composite score, fase, confidence.
2. Sub-score per metode (technical + bandar + foreign + regime).
3. Dominant factors.
4. Market regime hari ini.
5. Stock profile (bobot adaptif + dominant_method + notes).
6. Latest close price.

## System prompt (ringkas)
Anda adalah Fajr Quant, asisten analisa saham IDX. Output HARUS JSON dengan
field:
- `action`: BUY | ACCUMULATE | HOLD | REDUCE | SELL
- `entry`, `stop`, `target`: angka atau null
- `rationale`: ≤ 300 karakter, dalam Bahasa Indonesia, dan manusiawi (bukan cuma angka teknis). Jelaskan arti dan alasan mengapa saham layak diperhatikan.
- `dominant_factors`: array string
- `risks`: array string

Aturan: hanya BUY jika fase `Siap Entry`/`Hold` dengan struktur positif.
Selalu hormati fase dan composite score.
Respons HANYA dalam Bahasa Indonesia.

`response_format: json_object` diaktifkan agar output dapat di-parse langsung.

## Penyimpanan
`recommendations(ticker, date, action, entry, stop, target, rationale,
dominant_factors JSON, risks JSON, provider, raw_response JSON)`.

## Cost control
Recommendation dijalankan per ticker dalam pipeline harian (watchlist atau
top-N IDX), bukan seluruh universe, untuk menghemat pemakaian API.

## Fallback model (gratis)
Bila AI utama (`deepseek-v4-pro`) kehabisan token / kuota (error 402 atau 429
dengan kata kunci *insufficient/quota/balance/exhausted*), sistem otomatis
beralih ke model gratis `deepseek-v4-flash` di endpoint yang sama. Field
`provider` di tabel `recommendations` mencatat model mana yang digunakan
(`deepseek` vs `fallback:deepseek-v4-flash`) sehingga mudah dilacak.

Konfigurasi (`.env` / `config.py`):
- `AI_FALLBACK_MODEL` (default `deepseek-v4-flash`)
- `AI_FALLBACK_BASE_URL` & `AI_FALLBACK_API_KEY` — bila kosong, mencontek
  nilai `AI_BASE_URL` / `AI_API_KEY` (primary). Bisa diganti ke endpoint
  OpenAI-compatible gratis lain (Ollama, Groq, OpenRouter).

Error selain kuota (mis. 500, timeout, parse error) **tidak** memicu fallback
agar model gratis tidak terbuang sia-sia.

## Filter rekomendasi
Sebelum masuk ke AI, ticker juga difilter berdasarkan kualitas data harga:
- **Likuiditas**: rata-rata nilai transaksi harian (close × volume) minimal
  `RECOMMENDATION_MIN_AVG_DAILY_VALUE` (default 500 juta IDR, 20 hari).
- **Wick/volatilitas**: rata-rata total wick (upper + lower) sebagai persen
  dari harga penutupan maksimal `RECOMMENDATION_MAX_AVG_WICK_PCT`
  (default 5%). Saham dengan shadow panjang atau sangat volatile tidak
  direkomendasikan.

Filter ini menghemat token AI dan memastikan rekomendasi hanya untuk saham
cukup likuid dengan candlestick yang relatif "bersih".
