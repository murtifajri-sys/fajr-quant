# Bandarmology

Modul di `backend/app/services/bandarmology/`. Masing-masing menerima
`(prices_df, flow_df, as_of)` dan menghasilkan `{date, label, detected, value,
score, payload}` disimpan ke `bandarmology_signals`.

`flow_df` schema: `date, party (broker/investor), buy_value, sell_value,
net_value` — di-parse dari Stockbit `marketdetectors` di `data_loader.py`.

## Label & logika

### hidden_accumulation
Akumulasi tanpa kenaikan harga. Kondisi: volume spike > 1.5× rata-rata,
range harian < 0.8×ATR, perubahan harga < 1%.

### silent_accumulation
Broker tertentu net buy konsisten (≥60% hari) dalam window 15 hari, sementara
harga stabil/drift naik (drift ≥ -2%). Payload berisi top broker + rasio
konsistensi.

### shakeout
Drop tajam lalu recovery cepat. Drop < -2% dan > 1.5×ATR-normalized, recovery
≥ 70% dari drop, volume spike > 1.3×.

### absorption
Broker besar net buy di hari turun. Dari flow_df, group by party, ambil
top buyers dengan net > 0 saat `close_change < 0`.

### bandar_positioning
Rolling 20 hari: total net top-5 broker. Akumulasi jika net > 0 dan
accumulation > 1.3× distribution. Payload berisi list top broker + net.

### consistency
Rasio hari net-flow positif dalam window 20 hari. `detected` jika ≥ 65%.
Skor linear dari rasio.

### foreign_flow (terpisah)
`app/services/bandarmology/foreign_flow.py`: skor 0-100 dari net foreign
dibanding rata-rata |net| 20 hari. Disimpan ke `foreign_flows`.

## Threshold & tuning
Threshold di-hardcode awal untuk v1. Direncanakan dipindah ke config
(`docs/CHANGELOG.md` saat tersedia) agar bisa di-tune tanpa kode.

## Window data
`BANDARMOLOGY_LOOKBACK_DAYS` (default 90 hari).
