# Plan: Screening Saham IPO / New Listing

> Status: DRAFT  
> Dibuat: 2026-07-26  
> Target: menemukan saham baru yang sedang diakumulasi dan membentuk setup entry
> tanpa memaksakan syarat histori saham matang.

## 1. Audit Data Awal

Sumber pembanding:

- file terbaru: `/home/fajrirog/Downloads/Daftar Saham  - 20260726.xlsx`;
- master aplikasi: `backend/data/stock_list.xlsx`;
- tabel database: `stocks`.

Hasil audit pada 2026-07-26:

- ketiga sumber berisi `963` ticker;
- kode ticker file terbaru identik dengan master aplikasi;
- tidak ada ticker baru yang perlu ditambahkan;
- listing terbaru adalah `RANS`, tanggal 2026-07-10;
- ada 6 ticker berumur maksimal 30 hari kalender: `RANS`, `PRDL`, `BACH`,
  `EMMI`, `JECX`, dan `JELI`;
- ada 1 ticker berumur 61-120 hari: `WBSA`.

File terbaru memakai judul kolom, nama bulan, dan nama papan dalam Bahasa
Indonesia. Seeder saat ini hanya menerima format Bahasa Inggris. Pada fase
implementasi, importer perlu menerima kedua format agar pembaruan berikutnya
tidak memerlukan konversi manual.

## 2. Prinsip Utama

Saham IPO tidak masuk jalur `Siap Entry` reguler sebelum histori teknikalnya
cukup. Saham tersebut tetap dapat ditemukan melalui jalur `IPO / New Listing`
dengan status dan confidence tersendiri.

Aturan utamanya:

1. Gunakan jumlah sesi perdagangan sebagai umur analisis utama; umur kalender
   hanya dipakai untuk membentuk universe.
2. Jangan menggagalkan IPO hanya karena EMA50, EMA200, atau coverage 120 hari
   belum tersedia.
3. Broker flow yang kuat adalah alasan untuk memantau, bukan alasan tunggal
   untuk entry.
4. Entry membutuhkan struktur harga yang terbaca, likuiditas yang cukup, dan
   level invalidasi yang konkret.
5. Saham yang sudah terlalu jauh dari base atau anchored VWAP tidak boleh
   berstatus siap entry meskipun broker flow kuat.
6. Hasil IPO harus dipisahkan dari screener reguler agar standar data keduanya
   tetap jujur dan dapat dibandingkan.

## 3. Universe dan Fase IPO

Universe awal adalah saham dengan usia maksimal `120` hari kalender sejak
listing. Jumlah sesi perdagangan tidak dipakai untuk memperluas universe karena
saham lama yang sering suspend bisa memiliki sesi sedikit dan salah terbaca
sebagai IPO. Jumlah sesi hanya dipakai untuk menentukan fase dan status.

| Fase | Sesi tersedia | Status maksimum | Fokus analisis |
|---|---:|---|---|
| `price_discovery` | 1-5 | `IPO Observasi` | range awal, likuiditas, ARA/ARB, distribusi |
| `early_watch` | 6-20 | `IPO Early Entry` | akumulasi, opening range, anchored VWAP |
| `base_forming` | 21-40 | `IPO Mendekati Entry` | base, contraction, dry-up volume, resistance |
| `setup_ready` | 41+ | `IPO Siap Entry` | breakout/retest/BOW dengan invalidasi |
| `transition` | >120 hari kalender | screener reguler | rule teknikal dan trade status reguler |

Fase `early_watch` dapat menjadi `IPO Early Entry` jika opening range sudah
terbentuk, broker accumulation kuat, harga belum extended, dan level invalidasi
jelas. Ukuran posisi tetap harus dianggap lebih agresif dibanding setup 21+
sesi karena base belum matang.

## 4. Data dan Feature

Gunakan data yang sudah tersedia tanpa rescore historis penuh:

- `stocks.listing_date`, `board`, dan `shares_outstanding`;
- OHLCV `daily_prices` sejak tanggal listing;
- `broker_flows` sepanjang sesi yang tersedia;
- hasil `entry_readiness` dan `trade_setup` hanya untuk feature yang memang dapat
  dihitung dari histori pendek;
- nilai transaksi harian untuk mengukur likuiditas.

Feature khusus IPO:

- `trading_session_age`: jumlah sesi harga sejak listing;
- `active_session_ratio`: rasio sesi yang memiliki transaksi;
- `ipo_opening_range_high/low`: range lima sesi pertama;
- `anchored_vwap`: VWAP harian yang di-anchor dari hari listing;
- `base_high/low`: range konsolidasi paling relevan setelah price discovery;
- `base_width_pct`: lebar base terhadap midpoint;
- `volume_contraction`: volume 5 sesi dibanding 20 sesi atau seluruh histori;
- `broker_net_5/10/20`: net accumulation sesuai jumlah sesi tersedia;
- `broker_consistency`: proporsi sesi net buy positif;
- `broker_concentration`: dominasi broker pembeli utama;
- `distribution_reversal`: flow 3-5 sesi terakhir berbalik negatif;
- `extension_from_avwap` dan `extension_from_base`: guardrail anti-kejar harga;
- jumlah ARA/ARB atau candle ekstrem sebagai penalti risiko.

Broker coverage dihitung terhadap sesi perdagangan yang tersedia sejak listing,
bukan dibagi target 30/120 hari. Dengan demikian saham baru tidak otomatis
dianggap incomplete hanya karena belum lama tercatat.

## 5. Hard Gate

Ticker tidak boleh naik menjadi kandidat entry jika salah satu kondisi berikut
terjadi:

- kurang dari 6 sesi perdagangan;
- rata-rata nilai transaksi 5 sesi di bawah batas likuiditas konfigurasi;
- tidak ada transaksi pada lebih dari 30% sesi yang seharusnya aktif;
- broker coverage terhadap sesi tersedia di bawah 80%;
- flow terbaru menunjukkan distribusi kuat atau reversal negatif;
- harga lebih dari `2 ATR` atau 12% di atas base breakout/anchored VWAP;
- belum ada level invalidasi yang dapat dihitung;
- base terlalu lebar, struktur terus membuat lower low, atau volatilitas belum
  berkontraksi;
- ticker berada pada papan pemantauan khusus. Ticker ini tetap dapat dilihat,
  tetapi status maksimum `IPO Watch - Risiko Tinggi`.

Nilai ambang likuiditas, extension, dan volatilitas harus menjadi konfigurasi,
bukan angka tersebar di frontend dan backend.

## 6. Setup yang Dicari

### 6.1 Opening Range Breakout

- Range berasal dari lima sesi pertama.
- Harga close di atas range high.
- Volume minimal `1.5x` baseline volume yang tersedia.
- Broker flow 5 sesi tetap positif dan tidak terkonsentrasi pada transaksi satu
  hari saja.
- Entry tidak lebih dari 5% di atas trigger; jika lebih jauh, status menjadi
  `Terlambat / Tunggu Retest`.

### 6.2 Base Breakout

- Minimal 8 sesi membentuk base setelah price discovery.
- Lebar base ideal maksimal 15%; threshold disesuaikan ATR IPO.
- Volatilitas dan volume berkontraksi menjelang breakout.
- Breakout disertai volume dan broker accumulation.
- Tampilkan trigger, entry range, stop di bawah base, dan risk/reward.

### 6.3 Retest Setelah Breakout

- Breakout sebelumnya valid, tetapi harga tidak sedang extended.
- Harga kembali ke opening range high atau base high dengan volume lebih kecil.
- Flow tidak berubah menjadi distribusi.
- Close kembali bertahan di atas level retest menjadi konfirmasi entry.

### 6.4 Buy on Weakness IPO

- Hanya untuk struktur higher low setelah base terbentuk.
- Zona tunggu berasal dari confluence base support dan anchored VWAP.
- Pullback harus bervolume lebih kecil dan broker flow tetap netral-positif.
- Tidak digunakan selama lima sesi price discovery pertama.

## 7. Status Hasil

| Status | Arti |
|---|---|
| `IPO Data Belum Cukup` | Kurang dari 6 sesi atau coverage buruk |
| `IPO Observasi` | Masih price discovery, belum ada struktur entry |
| `IPO Watch - Akumulasi` | Flow menarik, tetapi base belum matang |
| `IPO Early Entry` | Usia 6-20 sesi, flow kuat, dekat trigger/AVWAP, risiko agresif |
| `IPO Base Forming` | Struktur mulai terbentuk dan level tunggu tersedia |
| `IPO Mendekati Entry` | Harga dekat trigger/zona entry, menunggu konfirmasi |
| `IPO Siap Entry` | Setup valid, tidak extended, flow dan volume mendukung |
| `IPO Tunggu Retest` | Breakout valid tetapi harga sudah terlalu jauh |
| `IPO Hindari - Distribusi` | Flow reversal/distribusi atau struktur rusak |
| `IPO Risiko Tinggi` | Likuiditas, papan, atau volatilitas tidak memenuhi gate |

Setiap hasil minimal menampilkan umur sesi, status, setup, trigger atau zona
entry, stop/invalidation, jarak ke trigger, broker flow 5/10 sesi, likuiditas,
confidence, blocker, dan tautan ke Chart serta Watchlist.

## 8. Skor IPO

Gunakan `ipo_setup_score` derivatif, terpisah dari composite score reguler:

| Komponen | Bobot awal |
|---|---:|
| Broker accumulation dan consistency | 30% |
| Struktur base dan kedekatan ke setup | 30% |
| Likuiditas dan active-session ratio | 15% |
| Volume confirmation/contraction | 15% |
| Penalti volatilitas, extension, dan distribusi | 10% |

Skor hanya menentukan urutan kandidat setelah hard gate. Skor tinggi tidak boleh
mengubah ticker dengan distribusi atau harga extended menjadi siap entry.

## 9. Produk dan API

Tambahkan menu `IPO Screener` dengan filter:

- umur: `0-20`, `21-40`, `41-80` sesi;
- status IPO;
- minimum broker accumulation;
- minimum nilai transaksi;
- setup: breakout, retest, BOW, atau base forming;
- hanya kandidat yang mendekati/siap entry;
- papan pencatatan.

Endpoint yang disarankan:

- `GET /screener/ipo` untuk daftar kandidat terbaru;
- `GET /screener/ipo/{ticker}` untuk detail feature, rule, dan level;
- `POST /screener/ipo/ai-analysis` untuk analisis AI atas hasil deterministik.

AI tidak menghitung level sendiri. Prompt menerima hasil deterministic engine,
menjelaskan alasan status, risiko IPO, skenario entry, invalidasi, dan apa yang
masih harus dikonfirmasi.

## 10. Pembaruan Master Saham

Perbaiki `seed_stocks` agar:

- menerima alias kolom Inggris dan Indonesia;
- memahami bulan `Jan-Feb-Mar-Apr-Mei-Jun-Jul-Agu-Sep-Okt-Nov-Des`;
- memetakan `Utama`, `Pengembangan`, `Pemantauan Khusus`, `Akselerasi`, dan
  `Ekonomi Baru` ke kode board internal;
- membersihkan pemisah saham `.` maupun `,`;
- menyediakan mode audit/dry-run yang melaporkan `created`, `updated`,
  `unchanged`, dan ticker yang hilang dari file terbaru;
- tidak menghapus ticker lama secara otomatis karena bisa sedang suspend,
  delisting dalam proses, atau tidak muncul akibat masalah sumber.

Alur update berikutnya: audit file, tampilkan diff, salin sebagai master hanya
jika valid, jalankan seed, lalu enqueue data harga dan broker flow khusus ticker
yang baru dibuat.

## 11. Tahap Implementasi

### Fase 1 - Data Master

- Normalisasi importer dua bahasa dan tambah dry-run.
- Tambah test fixture untuk format file terbaru.
- Audit database dan enqueue ticker baru jika ditemukan.

### Fase 2 - Engine IPO

- Buat service `ipo_screener.py` yang menghitung umur sesi, IPO range, anchored
  VWAP, base, broker feature, hard gate, score, status, dan level entry.
- Gunakan konfigurasi threshold terpusat.
- Tambah unit test untuk seluruh fase dan blocker.

### Fase 3 - API dan UI

- Tambah endpoint list/detail dan menu `IPO Screener`.
- Tampilkan status, setup, level, blocker, Chart, dan tombol Watchlist.
- Tambah panel IPO pada chart ticker new listing.

### Fase 4 - AI dan Operasional

- Kirim hasil deterministic engine ke AI Screener.
- Tambah update master saham ke pipeline berkala dengan audit terlebih dahulu.
- Setelah data cukup, backtest threshold memakai seluruh IPO historis yang
  memiliki data sejak listing; jangan kalibrasi hanya dari tujuh ticker aktif.

## 12. Acceptance Criteria

- Saham dengan histori pendek tidak hilang dari semua screener.
- Saham kurang dari 6 sesi tidak pernah berstatus siap entry.
- Broker flow kuat tanpa base hanya menghasilkan `IPO Watch - Akumulasi`.
- Breakout yang extended menghasilkan `IPO Tunggu Retest`, bukan siap entry.
- Setup valid selalu memiliki trigger/zona entry dan invalidasi.
- Coverage dihitung terhadap sesi yang tersedia sejak listing.
- Hasil IPO konsisten di API, menu IPO Screener, Chart, Watchlist, dan AI.
- Import file terbaru dapat diaudit tanpa mengubah database dan tanpa menghapus
  ticker lama.
