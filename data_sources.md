# Stockbit Data Sources

Token Stockbit tidak boleh disimpan di repository. Masukkan Bearer JWT melalui
halaman `/settings/tokens`; aplikasi menyimpannya terenkripsi di database.

## Daily prices

```text
GET https://exodus.stockbit.com/chartbit/{symbol}/price/daily
  ?from=YYYY-MM-DD
  &to=YYYY-MM-DD
  &limit=1000
```

Catatan: API Stockbit memakai `from` sebagai batas terbaru dan `to` sebagai
batas terlama. Respons terverifikasi pada 2026-07-13:

```text
data.chartbit[]:
  date, open, high, low, close, volume, value, frequency,
  foreignbuy, foreignsell, foreignflow, shareoutstanding
```

## Broker summary / market detector

```text
GET https://exodus.stockbit.com/marketdetectors/{symbol}
  ?from=YYYY-MM-DD
  &to=YYYY-MM-DD
  &transaction_type=TRANSACTION_TYPE_NET
  &market_board=MARKET_BOARD_REGULER
  &investor_type=INVESTOR_TYPE_ALL
  &limit=25
```

Respons terverifikasi pada 2026-07-13:

```text
data.bandar_detector
data.broker_summary.brokers_buy[]
data.broker_summary.brokers_sell[]
```

Buyer fields utama: `netbs_broker_code`, `netbs_date`, `bval`, `blot`,
`netbs_buy_avg_price`, `freq`.

Seller fields utama: `netbs_broker_code`, `netbs_date`, `sval`, `slot`,
`netbs_sell_avg_price`, `freq`.

## Company profile

```text
GET https://exodus.stockbit.com/emitten/{symbol}/profile
```

## Shareholder composition

```text
GET https://exodus.stockbit.com/insider/shareholding/composition/companies/{symbol}
  ?period_start=YYYY-MM-DD
  &period_end=YYYY-MM-DD
```

## Major shareholders

```text
GET https://exodus.stockbit.com/insider/company/majorholder
  ?symbol={symbol}
  &page=1
```

Semua request menggunakan header `Authorization: Bearer <token>` yang
diambil dari penyimpanan token terenkripsi, bukan dari file ini.
