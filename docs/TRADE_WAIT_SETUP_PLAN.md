# Plan: Titik Tunggu dan Buy on Weakness

> Status: DRAFT  
> Dibuat: 2026-07-26  
> Target: memecah `Tunggu Konfirmasi` menjadi setup yang dapat ditindaklanjuti,
> lengkap dengan harga trigger, zona tunggu, konfirmasi, dan invalidasi.

## 1. Tujuan

- Menjelaskan apakah ticker sedang menunggu breakout, retest, atau pullback ke
  area value.
- Menampilkan level harga konkret, bukan hanya label generik.
- Mendukung setup `Buy on Weakness` tanpa menganggap setiap harga turun sebagai
  kesempatan beli.
- Menghindari entry terlambat pada saham yang sudah terlalu jauh dari support
  atau level breakout.
- Menjaga hasil yang sama di Chart, Screener, Watchlist, dan AI Screener.

Status utama tetap `Siap Entry`, `Tunggu Konfirmasi`, `Hold`, dan
`Data Belum Siap`. Setup tunggu menjadi detail di bawah status utama, bukan
pengganti guardrail broker flow.

## 2. Hasil yang Ditampilkan

Setiap ticker yang layak dipantau menghasilkan satu setup utama:

| Setup | Arti | Contoh tampilan |
|---|---|---|
| `wait_breakout` | Harga berada di bawah resistance valid | `Tunggu Breakout > 224` |
| `wait_retest` | Breakout sudah terjadi, tunggu uji ulang level | `Tunggu Retest 216-222` |
| `buy_on_weakness` | Harga turun ke demand/value zone dalam struktur bullish | `BOW Watch 198-204` |
| `wait_value_area` | Setup baik tetapi harga masih di tengah range | `Tunggu area value 190-200` |
| `no_setup` | Belum ada lokasi entry yang layak | `Hold` |

Detail minimum yang harus terlihat:

- harga terakhir dan jaraknya ke setup;
- trigger entry atau zona entry;
- syarat konfirmasi;
- level invalidasi;
- alasan pemilihan setup;
- peringatan jika risk/reward atau flow tidak mendukung.

## 3. Prinsip Keputusan

Urutan evaluasi wajib tetap:

1. Validasi kecukupan data.
2. Terapkan hard blocker dari trade status.
3. Hitung struktur harga dan zona teknikal.
4. Pilih satu setup tunggu yang paling relevan.
5. Nilai apakah setup baru `watch`, sudah terkonfirmasi, atau batal.

Setup teknikal tidak boleh mengalahkan hard blocker. Harga yang menyentuh golden
zone tetap `Hold` jika broker flow reversal, distribusi, stale, coverage buruk,
atau struktur membuat lower low baru.

## 4. Sumber Data

Gunakan data yang sudah tersedia:

- OHLCV dari `daily_prices` atau response `/charts/{ticker}/overview`;
- ATR14, EMA20, volume MA20, dan swing point dari utilitas teknikal;
- payload `price_action` untuk referensi support/resistance;
- payload `breakout` untuk breakout level, EMA, RSI, dan volume ratio;
- payload `volume_breakout` untuk OBV/ADL dan volume confirmation;
- hasil `evaluateTradeStatus` atau reason code backend yang setara;
- broker flow 1M sebagai conviction utama dan 1W sebagai momentum terbaru.

Perhitungan final sebaiknya berada di satu service backend agar Chart,
Screener, Watchlist, dan AI Screener tidak menghitung level dengan aturan yang
berbeda. Perhitungan bersifat derivatif dan tidak mengubah score historis.

## 5. Perhitungan Struktur Harga

### 5.1 Swing dan Support/Resistance

- Gunakan swing terkonfirmasi dengan window awal `3` sesi.
- Resistance hanya boleh berasal dari swing high di atas harga saat ini.
- Support hanya boleh berasal dari swing low di bawah harga saat ini.
- Gabungkan level yang berjarak maksimal `0.5 ATR` menjadi satu zona.
- Prioritaskan zona dengan minimal dua sentuhan, paling recent, dan volume yang
  memadai.
- Abaikan level yang sudah ditembus tegas dan tidak lagi relevan.

Ini memperbaiki keterbatasan payload `price_action` saat ini yang memilih swing
berdasarkan jarak absolut, sehingga level terdekat belum tentu berada di sisi
harga yang benar.

### 5.2 Impulse dan Fibonacci

Golden zone hanya dihitung jika terdapat bullish impulse yang valid:

- anchor bawah adalah confirmed swing low terakhir sebelum break of structure;
- anchor atas adalah confirmed swing high setelah impulse;
- struktur masih mempertahankan higher low;
- panjang impulse minimal `2 ATR` agar retracement tidak berasal dari noise.

Level retracement:

- `0.50` sebagai awal value area;
- `0.618` sebagai golden ratio utama;
- `0.705` sebagai batas bawah golden pocket.

Zona Fibonacci tidak berdiri sendiri. Zona baru layak menjadi kandidat BOW jika
berimpit dengan support, EMA20/EMA50, atau demand zone.

### 5.3 Discount Area

- Gunakan dealing range dari swing low ke swing high bullish yang sama.
- Area di bawah midpoint `0.50` disebut discount.
- Discount bukan sinyal beli otomatis; struktur bullish harus masih utuh.
- Jika harga menembus swing low atau membentuk lower low, discount dibatalkan.

### 5.4 Demand Zone / Order Block Heuristik

Karena order block bersifat interpretatif, sistem memberi label
`demand zone`, bukan mengklaim institutional order block secara pasti.

Kandidat demand zone adalah candle bearish terakhir sebelum impulse bullish
yang:

- menghasilkan break of structure;
- bergerak minimal `1.5 ATR` dalam maksimal lima sesi berikutnya;
- disertai kenaikan volume atau broker flow yang tetap positif.

Zona awal menggunakan `low` sampai `open` candle tersebut. Kandidat dibatalkan
jika ada close tegas di bawah `low` zona.

## 6. Rule Setiap Setup

### 6.1 Tunggu Breakout

Dipilih jika:

- harga masih di bawah resistance valid;
- jarak ke resistance maksimal `1 ATR` atau `5%`, ambil yang lebih ketat;
- struktur minimal sideways-bullish;
- broker status memenuhi minimum `Tunggu Konfirmasi`.

Konfirmasi breakout:

- daily close di atas batas resistance + buffer `0.1 ATR`;
- volume minimal `1.2x` volume MA20;
- body candle minimal `50%` dari range;
- upper wick tidak lebih dari `40%` range;
- broker recent flow tetap positif dan tidak muncul reversal risk.

Jika close melewati resistance tetapi volume belum cukup, status tetap
`Tunggu Breakout`, dengan warning `breakout_without_volume`.

### 6.2 Tunggu Retest

Dipilih jika breakout valid terjadi dalam maksimal `10` sesi terakhir dan
harga belum terlalu extended.

Zona retest:

- batas bawah: breakout level - `0.5 ATR`;
- batas atas: breakout level + `0.25 ATR`.

Konfirmasi retest:

- volume pullback maksimal `0.9x` volume MA20;
- tidak ada close tegas di bawah batas bawah;
- muncul rejection bullish atau close kembali di atas breakout level;
- broker recent flow tetap positif.

Setup batal jika close di bawah zona selama dua sesi atau sekali close di bawah
zona lebih dari `0.5 ATR`.

### 6.3 Buy on Weakness

Dipilih hanya jika seluruh syarat dasar berikut terpenuhi:

- broker flow `active`, recent flow positif, dan tidak ada hard blocker;
- struktur masih bullish atau membentuk base, bukan downtrend;
- harga masuk zona yang memiliki minimal dua confluence;
- confluence dapat berasal dari support, demand zone, Fibonacci
  `0.50-0.705`, discount area, EMA20, atau EMA50;
- volume pullback mengecil, target awal maksimal `0.9x` volume MA20;
- tidak ada lower low yang merusak struktur.

Konfirmasi entry BOW:

- bullish rejection, bullish engulfing, atau close kembali di atas batas atas
  zona;
- volume rebound lebih besar dari volume sesi pullback sebelumnya;
- flow 1W tidak berubah menjadi stale atau reversal.

Sistem membedakan dua kondisi:

- `BOW Watch`: harga belum masuk zona atau belum ada candle konfirmasi;
- `BOW Confirmed`: harga berada di zona dan konfirmasi sudah muncul.

`BOW Confirmed` dapat menjadi `Siap Entry` hanya jika seluruh gate broker dan
risiko tetap lolos. Menyentuh zona saja tidak cukup.

### 6.4 Tunggu Value Area

Dipilih bila broker setup baik, tetapi harga berada di tengah range dan terlalu
jauh dari resistance maupun demand zone. UI menampilkan zona bernilai terbaik
yang paling dekat dan jarak menuju zona. Setup ini mencegah sistem menyuruh
mengejar harga di lokasi risk/reward buruk.

## 7. Anti-Chasing dan Invalidation

Setup diturunkan menjadi `wait_retest` atau `wait_value_area` jika:

- harga lebih dari `1.5 ATR` di atas breakout level;
- jarak harga ke EMA20 terlalu lebar, threshold awal `> 8%`;
- RSI atau extension tinggi tetapi support terdekat terlalu jauh;
- reward menuju resistance berikutnya kurang dari `1.8x` risiko ke invalidasi.

Invalidasi selalu berbasis struktur dan ditampilkan sebagai harga:

- breakout: kembali di bawah breakout zone;
- retest: close tegas di bawah batas bawah zona;
- BOW: close di bawah demand zone atau confirmed swing low;
- semua setup: broker reversal/distribution membatalkan setup walaupun harga
  belum menyentuh invalidasi teknikal.

## 8. Pemilihan Setup Utama

Jika beberapa setup tersedia, gunakan prioritas berikut:

1. `BOW Confirmed` dengan minimal dua confluence dan flow sehat.
2. `Retest Confirmed` setelah breakout valid.
3. `Tunggu Retest` jika harga sudah breakout tetapi extended.
4. `Tunggu Breakout` jika harga dekat resistance.
5. `BOW Watch` jika harga mendekati demand/value zone.
6. `Tunggu Value Area` jika harga berada di lokasi risk/reward buruk.
7. `no_setup` bila struktur atau data tidak memadai.

Prioritas bukan ranking profit. Tujuannya memilih instruksi tunggu yang paling
jelas dan paling dekat dengan kondisi harga sekarang.

## 9. Bentuk Data

Tambahkan hasil derivatif seperti berikut:

```json
{
  "setup_type": "buy_on_weakness",
  "setup_state": "watch",
  "label": "BOW Watch 198-204",
  "last_price": 210,
  "trigger_price": 205,
  "zone_low": 198,
  "zone_high": 204,
  "invalidation_price": 194,
  "distance_pct": -2.86,
  "risk_reward": 2.1,
  "confirmations": ["volume_pullback_dry", "bullish_rejection"],
  "confluences": ["swing_support", "fib_0.618", "ema20"],
  "blockers": ["waiting_price_in_zone"],
  "as_of_date": "2026-07-24"
}
```

Harga harus mengikuti tick size IDX saat ditampilkan. Field yang belum dapat
dihitung bernilai `null`, bukan nol.

## 10. Integrasi Produk

### Chart

- Card status menampilkan sub-label setup tepat di bawah status trade.
- Gambar garis resistance, breakout, zona entry, dan invalidasi pada chart
  lokal; jika tetap memakai TradingView iframe, tampilkan level sebagai panel
  angka karena overlay tidak dapat dikontrol langsung.
- Tampilkan kalimat konkret, misalnya:
  `Tunggu close > 224 dengan volume >= 1.2x MA20`.

### Screener dan Watchlist

- Tambahkan filter `Setup`: Breakout, Retest, BOW, Value Area.
- Tambahkan kolom `Titik Tunggu` dan `Jarak`.
- Urutkan kandidat terdekat berdasarkan jarak ke trigger/zona, tetapi tetap
  setelah filter kualitas broker.

### AI Screener

- Kirim setup type, level, confluence, invalidasi, dan jarak ke prompt AI.
- AI menjelaskan konteks dan risiko, tetapi tidak boleh mengarang level di luar
  hasil deterministic engine.
- Ranking AI memprioritaskan setup sehat dan dekat, bukan sekadar skor tertinggi.
- Tambahkan filter `Setup` di halaman AI Screener: Siap Entry, Tunggu Breakout,
  Tunggu Retest, BOW, Value Area, dan Hold.
- Tampilkan ringkasan per kandidat: status trade, setup label, jarak ke trigger
  atau zona, konfirmasi yang dibutuhkan, invalidasi, dan blocker utama.
- Prompt AI wajib menerima field `setup_detail` mentah agar rekomendasi
  memakai angka yang sama dengan Chart/Screener/Watchlist.
- Jika `setup_detail` belum tersedia, AI Screener harus menurunkan confidence
  dan menulis `data_setup_belum_lengkap`, bukan membuat level konseptual baru.

Payload minimum untuk AI Screener:

```json
{
  "ticker": "TAMA",
  "trade_status": {
    "code": "waiting",
    "label": "Tunggu Konfirmasi"
  },
  "setup_detail": {
    "setup_type": "wait_breakout",
    "setup_state": "watch",
    "label": "Tunggu Breakout > 75",
    "last_price": 74,
    "trigger_price": 75,
    "zone_low": null,
    "zone_high": null,
    "invalidation_price": 69,
    "distance_pct": 1.35,
    "risk_reward": 2.0,
    "confirmations": ["close_above_trigger", "volume_1_2x_ma20"],
    "confluences": ["near_resistance", "broker_flow_positive"],
    "blockers": ["waiting_breakout_confirmation"]
  }
}
```

## 11. Rencana Implementasi

### Tahap 1 - Engine Struktur Harga

- Buat helper murni untuk ATR, swing terkonfirmasi, directional S/R, cluster
  zona, impulse anchor, Fibonacci, discount, dan demand zone.
- Tambahkan unit test dengan fixture OHLCV kecil dan deterministik.
- Jangan mengubah scoring atau menjalankan rescore.

### Tahap 2 - Setup Classifier

- Gabungkan struktur harga dengan reason code trade status dan broker window.
- Implementasikan rule breakout, retest, BOW, value area, anti-chasing, dan
  invalidation.
- Kembalikan satu setup utama beserta kandidat alternatif untuk debugging.

### Tahap 3 - API dan UI Chart

- Masukkan hasil setup ke endpoint broker detail atau endpoint derivatif yang
  dapat dipakai bersama.
- Tambahkan sub-status, harga tunggu, konfirmasi, invalidasi, dan jarak pada
  chart.
- Pastikan kondisi loading atau data basi tidak menampilkan level aktif.

### Tahap 4 - Screener, Watchlist, dan AI

- Tambahkan field setup pada hasil screener tanpa mengubah composite score.
- Tambahkan filter dan sorting berdasarkan tipe setup dan jarak.
- Perluas payload AI Screener dengan level deterministic.
- Ubah prompt builder AI agar `decision` mengikuti setup deterministic:
  `entry_now`, `wait_breakout`, `wait_retest`, `buy_on_weakness`,
  `wait_value_area`, atau `skip`.
- Tambahkan kolom/card AI Screener untuk `Titik Tunggu`, `Jarak`, `Konfirmasi`,
  dan `Invalidasi`.
- Pastikan tombol analisis AI memakai kandidat hasil filter setup yang sedang
  dipilih, bukan selalu top 10 skor mentah.

### Tahap 5 - Kalibrasi

- Uji pada minimal 20 ticker: breakout valid, false breakout, retest, BOW,
  downtrend, distribusi, dan data tidak cukup.
- Review khusus TAMA dan MDIA sebagai regression case.
- Catat distribusi tiap setup sebelum mengubah threshold awal.

## 12. Test dan Acceptance Criteria

- Resistance selalu berada di atas harga; support selalu di bawah harga.
- Golden zone tidak muncul tanpa bullish impulse yang valid.
- Downtrend atau lower low tidak pernah menjadi BOW hanya karena harga murah.
- Breakout tanpa volume tetap menunggu, bukan `Siap Entry`.
- Pullback bervolume mengecil dengan flow sehat dapat menjadi kandidat BOW.
- Harga extended tidak diberi entry baru; diarahkan menunggu retest/value area.
- Setiap setup memiliki level trigger/zona dan invalidasi yang dapat dijelaskan.
- Hard blocker broker membatalkan semua setup teknikal.
- Chart, Screener, Watchlist, dan AI memakai hasil engine yang sama.
- AI Screener tidak boleh mengarang level jika `setup_detail` kosong.
- AI Screener bisa memfilter dan menganalisis kandidat berdasarkan tipe setup,
  termasuk BOW dan retest.
- Tidak perlu rescore histori untuk menghasilkan setup baru.

## 13. Keputusan yang Perlu Dikunci Saat Kalibrasi

Nilai awal berikut sengaja dijadikan konfigurasi, bukan angka permanen:

- swing confirmation window: `3` sesi;
- cluster distance: `0.5 ATR`;
- breakout volume: `1.2x MA20`;
- dry pullback volume: `0.9x MA20`;
- breakout freshness: `10` sesi;
- anti-chasing extension: `1.5 ATR` atau `8%` dari EMA20;
- minimum risk/reward: `1.8`;
- minimum BOW confluence: `2`.

Threshold dikalibrasi setelah hasil sampel dilihat, bukan berdasarkan satu
ticker saja.

## 14. Di Luar Scope

- Eksekusi order otomatis.
- Position sizing berdasarkan portofolio user.
- Intraday confirmation; versi awal memakai candle harian.
- Klaim bahwa demand zone adalah order institusi yang pasti.
- Perubahan bobot composite score atau rescore histori.
