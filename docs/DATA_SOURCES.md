# Data Sources

## Stockbit (Exodus) - primary
Base URL: `https://exodus.stockbit.com`
Auth: `Authorization: Bearer <JWT>` (token dari login Stockbit web; memiliki `exp`).

| Endpoint | Path | Digunakan untuk |
|---|---|---|
| Daily prices + foreign flow | `GET /chartbit/{symbol}/price/daily?from&to&limit` | `daily_prices`, `foreign_flows` |
| Market detectors (broker/investor flow) | `GET /marketdetectors/{symbol}?from&to&transaction_type=TRANSACTION_TYPE_NET&market_board=MARKET_BOARD_REGULER&investor_type=INVESTOR_TYPE_ALL&limit` | `bandarmology_signals`, `foreign_flows` |
| Company profile | `GET /emitten/{symbol}/profile` | `stocks` (name, sector, board) |
| Shareholder composition | `GET /insider/shareholding/composition/companies/{symbol}?period_start&period_end` | konteks bandarmology (v2) |
| Major holders | `GET /insider/company/majorholder?symbol={symbol}&page` | konteks bandarmology (v2) |

Parameter `investor_type` untuk foreign flow: `INVESTOR_TYPE_FOREIGN`.
Wrapper: `backend/app/clients/stockbit.py`. Schema daily price dan broker
summary diverifikasi terhadap respons nyata BBCA pada 2026-07-13. Parsing
terisolasi di `app/services/data_loader.py`; detail field ada di
`data_sources.md`.

## yfinance - fallback / intraday (v2)
Library: `yfinance`.
- Digunakan untuk `daily_prices` saat Stockbit gagal/kosong (`source = yfinance`).
- Benchmark IHSG: `^JKSE` (untuk market regime + relative strength).
- Simbol IDX dilakukan via `<TICKER>.JK`.
- Intraday 30 menit (v2): `interval="30m"`.

## Sumber data vs metode
| Metode | Sumber utama |
|---|---|
| Trend structure, price action, volume/breakout, harmonic, candlestick, Elliott | `daily_prices` (Stockbit → yfinance) |
| Relative strength | `daily_prices` vs `^JKSE` |
| Bandarmology (semua label) | `marketdetectors` (broker flow) |
| Foreign flow | `marketdetectors` (`INVESTOR_TYPE_FOREIGN`) |
| Market regime | `^JKSE` via yfinance |

## Window data
- Teknikal: `TECHNICAL_LOOKBACK_DAYS` (default 1000 hari).
- Bandarmology: `BANDARMOLOGY_LOOKBACK_DAYS` (default 90 hari).

## Catatan token
Token JWT Stockbit punya `exp` (umumnya ~24 jam). `exp` dibaca otomatis saat
token disimpan. Sistem menolak token expired sebelum request; HTTP 401
menonaktifkan token dan menyimpan `last_error`. Dashboard menampilkan banner
dan mengarahkan user ke Settings. Refresh tetap dilakukan dengan re-input
manual.
