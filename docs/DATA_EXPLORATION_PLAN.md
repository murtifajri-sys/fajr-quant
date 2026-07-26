# Data Exploration Plan

## Tujuan
Membuat menu Data Explorer di dashboard supaya user bisa melihat, filter, dan inspect data historis yang sudah di-download oleh pipeline.

## Halaman yang Akan Dibuat

| Path | Deskripsi |
|---|---|
| `/data` | Index explorer, link ke semua sub-halaman |
| `/data/prices` | Daily OHLCV price data |
| `/data/bandarmology` | Bandar/broker flow & pattern signals |
| `/data/foreign` | Foreign flow net buy/sell per ticker |
| `/data/technical` | Technical indicator signals |
| `/data/scores` | Composite score history |
| `/data/recommendations` | AI recommendation history |
| `/data/stocks` | Stock universe listing |

---

## 1. Backend API

### 1.1 Prices `/api/v1/data/prices`
- `GET /api/v1/data/prices`
- Query params:
  - `ticker` (string, optional, comma-separated untuk multi)
  - `from` (date, optional)
  - `to` (date, optional)
  - `source` (string, optional: `stockbit` | `yfinance`)
  - `limit` / `offset` (pagination)
- Response: list `{ ticker, date, open, high, low, close, adj_close, volume, source }`

### 1.2 Bandarmology `/api/v1/data/bandarmology`
- `GET /api/v1/data/bandarmology`
- Query params:
  - `ticker`
  - `from`, `to`
  - `label` (multi-select: hidden_accumulation, silent_accumulation, shakeout, absorption, bandar_positioning, consistency)
  - `detected` (true/false)
  - `min_score`, `max_score`
  - `broker` (filter dari payload JSON)
  - `limit` / `offset`
- Response: list `{ id, ticker, date, label, detected, value, score, payload }`

### 1.3 Foreign Flow `/api/v1/data/foreign-flow`
- `GET /api/v1/data/foreign-flow`
- Query params:
  - `ticker`
  - `from`, `to`
  - `min_net`, `max_net`
  - `min_net_pct`, `max_net_pct`
  - `min_score`, `max_score`
- Response: list `{ ticker, date, foreign_buy, foreign_sell, net_foreign, net_foreign_pct, score }`

### 1.4 Technical Indicators `/api/v1/data/technical`
- `GET /api/v1/data/technical`
- Query params:
  - `ticker`
  - `from`, `to`
  - `method` (multi-select: trend_structure, price_action, volume_breakout, harmonic, relative_strength, candlestick, elliott_wave, indicator)
  - `name`
  - `min_score`, `max_score`
- Response: list `{ id, ticker, date, method, name, score, payload }`

### 1.5 Scores `/api/v1/data/scores`
- `GET /api/v1/data/scores`
- Query params:
  - `ticker`
  - `from`, `to`
  - `phase` (multi-select)
  - `min_composite`, `max_composite`
  - `min_confidence`, `max_confidence`
- Response: list `{ id, ticker, date, composite, phase, confidence, sub_scores, weights, dominant_factors }`

### 1.6 Recommendations `/api/v1/data/recommendations`
- `GET /api/v1/data/recommendations`
- Query params:
  - `ticker`
  - `from`, `to`
  - `action` (BUY, SELL, HOLD, WAIT, EXIT)
  - `provider`
  - `min_entry`, `max_entry`
- Response: list `{ id, ticker, date, action, entry, stop, target, rationale, provider }`

### 1.7 Stocks `/api/v1/data/stocks`
- `GET /api/v1/data/stocks`
- Query params:
  - `ticker` (prefix search)
  - `sector`
  - `industry`
  - `board`
  - `exchange`
- Response: list `{ ticker, name, sector, industry, board, exchange, listing_date }`

### 1.8 Filter Metadata `/api/v1/data/filters`
- `GET /api/v1/data/filters`
- Mengembalikan enum/dropdown options: sectors, industries, boards, phases, actions, methods, labels, brokers

---

## 2. Frontend

### 2.1 Layout
- Tambah menu **Data** di navbar /settings menjadi dropdown
- Halaman `/data` jadi index card menu

### 2.2 Shared Components
- `DataFilterPanel.tsx` — reusable filter form
  - Ticker input / multi-select
  - Date range picker (`from`, `to`)
  - Dropdown multi-select
  - Min/Max numeric inputs
- `DataTable.tsx` — reusable paginated table
- `Pagination.tsx`

### 2.3 Page per Section
- Setiap halaman punya filter panel di atas + tabel di bawah
- Pagination default 50 rows per page
- Export CSV (optional phase 2)

---

## 3. Filter yang Disediakan per Halaman

| Halaman | Filter Utama |
|---|---|
| Prices | ticker, date range, source |
| Bandarmology | ticker, date range, label, detected, score range, broker |
| Foreign Flow | ticker, date range, net foreign range, net % range |
| Technical | ticker, date range, method, name, score |
| Scores | ticker, date range, phase, composite range |
| Recommendations | ticker, date range, action, provider |
| Stocks | ticker prefix, sector, industry, board |

---

## 4. Database Considerations

- Existing indexes sudah cukup untuk `(ticker, date)` dan `(ticker, date, label/method)`.
- Tambah index jika sering filter by `phase`, `action`, `sector`, `detected`.
- JSON filtering (`payload`, `sub_scores`) mulai client-side saja; DB JSON operator bisa ditambah nanti.

---

## 5. Implementation Phases

### Phase 1 — Core API + Pages
- Buat 7 backend endpoints (prices, bandarmology, foreign, technical, scores, recommendations, stocks)
- Buat shared filter/table components
- Buat frontend pages untuk masing-masing

### Phase 2 — Polish
- Export CSV
- Tambah chart mini (line price, bar foreign flow)
- Broker autocomplete/filter

### Phase 3 — Advanced
- Full-text search rationale
- Saved filters
- Cross-table join (misal: harga + score + foreign flow dalam satu tabel)
