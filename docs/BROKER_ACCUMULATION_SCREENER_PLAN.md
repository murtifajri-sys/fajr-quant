# Plan: Broker Accumulation Screener & Conviction Score

> Status: DRAFT. Dibuat 2026-07-22.
> Tujuan: mendeteksi broker yang sedang aktif mengakumulasi saham, mengukur
> besarnya terhadap market cap dan likuiditas, lalu memberi label
> `accumulation`, `big_accumulation`, atau `aggressive_accumulation`.

---

## 1. Kondisi Saat Ini

Yang sudah tersedia:

- Tabel `broker_flows`: ticker, tanggal, broker, buy value, sell value, net value.
- Cache 1 bulan dan backfill bertahap untuk universe IDX.
- Screener dasar: top broker, net value, `% market cap`, `% ADV`, dan active days.
- Pilihan periode 1 minggu dan 1 bulan pada chart/screener.

Validasi data pada 2026-07-22:

- 58.786 baris broker flow, 105 saham, 23 tanggal perdagangan.
- Total buy dan sell per saham/hari seimbang; total net semua broker = 0.
- Karena itu, sinyal tidak boleh memakai penjumlahan net seluruh broker.
  Analisis harus dilakukan per broker atau cluster broker.

Masalah yang perlu dibenarkan sebelum menambah label:

- `active_days` saat ini menghitung hari broker muncul, bukan hari broker net buy.
- Akumulasi 1 bulan dapat terlihat kuat walau broker sudah berhenti membeli atau
  sudah berbalik net sell beberapa hari terakhir.
- `%ADV` saat ini adalah net periode dibagi ADV satu hari. Angka ini lebih jelas
  ditampilkan sebagai `days_of_adv`; contoh 250% ADV = 2,5 hari ADV.
- Signal `consistency` lama menjumlahkan net seluruh broker per hari. Nilainya
  secara prinsip nol dan perlu diganti dengan consistency top broker/cluster.
- Coverage data belum penuh untuk seluruh IDX, sehingga hasil global wajib
  menyertakan status kelengkapan data.
- Price chart utama masih berupa iframe TradingView. Chart tersebut tidak dapat
  disinkronkan secara penuh dengan data broker lokal, sehingga broker chart
  perlu memakai chart lokal yang sudah tersedia melalui `lightweight-charts`.

## 2. Definisi Periode

- `1W`: interval `(date_to - 7 hari, date_to]`; hanya sesi bursa di rentang itu
  yang dihitung. Boundary kiri terbuka mencegah delapan tanggal kalender ikut.
- `1M`: interval `(date_to - 1 bulan kalender, date_to]`; bukan 20 hari bursa
  dan bukan data satu hari yang diulang. Hanya sesi bursa aktual yang dihitung.
- Response selalu membawa `date_from`, `date_to`, `trading_days`, dan
  `coverage_ratio` agar periode tidak ambigu.
- Semua perhitungan memakai tanggal data terbaru, bukan `date.today()`, agar
  hasil tetap benar ketika pipeline terlambat atau pasar libur.

## 3. Faktor Conviction

### 3.1 Faktor inti (fase pertama)

| Faktor | Rumus ringkas | Fungsi |
|---|---|---|
| Magnitude | top-1/top-3 net terhadap market cap | Membandingkan ukuran akumulasi lintas saham |
| Liquidity impact | cluster net / ADV, ditampilkan sebagai `days_of_adv` | Mengukur seberapa besar flow terhadap likuiditas normal |
| Buy persistence | jumlah hari net buy / jumlah trading days | Membedakan pembelian konsisten dari satu transaksi besar |
| Recency | jarak sesi dari net buy terakhir + net 1-2 sesi terakhir | Memastikan akumulasi masih aktif |
| Acceleration | rata-rata net 5 sesi terbaru vs sesi sebelumnya | Mendeteksi pembelian yang makin agresif atau melambat |
| Retention | posisi kumulatif sekarang / puncak posisi kumulatif | Mendeteksi apakah broker sudah menjual kembali akumulasinya |
| Cluster strength | top-3/top-5 net buy dan jumlah broker positif konsisten | Mengonfirmasi top broker dengan kelompok broker lain |
| Directional purity | `abs(net) / (buy + sell)` per broker | Membedakan akumulasi satu arah dari broker yang aktif bolak-balik |
| Price response | return harga, relative strength, volume, breakout | Membedakan stealth accumulation, markup, dan chasing |

Catatan:

- `positive_days` menggantikan `active_days` sebagai ukuran conviction.
- Top broker tetap menjadi sinyal utama; top-3/top-5 menjadi konfirmasi.
- Broker dengan net 1 bulan positif tetapi net 5 hari negatif diberi status
  `cooling` atau `reversal_risk`, bukan active accumulation.
- Akumulasi saat harga datar/turun ringan dapat diberi tag
  `stealth_accumulation` atau `absorption`.
- Harga yang sudah naik terlalu jauh diberi `overheated_penalty`; broker flow
  yang kuat tidak otomatis berarti entry masih menarik.

### 3.2 Faktor lintas saham (fase kedua)

- **Broker focus/breadth**: broker yang fokus membeli sedikit saham mendapat
  conviction lebih tinggi daripada broker yang membeli puluhan saham sekaligus.
- **Sector cluster**: mendeteksi akumulasi serentak beberapa saham dalam sektor
  yang sama.
- **Universe percentile**: ranking `%MCap`, persistence, dan acceleration
  terhadap seluruh saham dengan liquidity bucket yang sebanding.
- **Broker-ticker history**: win rate return 5/10/20 sesi setelah pola broker
  serupa. Fitur ini baru layak setelah tersedia histori minimal 6-12 bulan.

### 3.3 Faktor yang belum bisa dihitung akurat

- Average buy price broker tidak tersedia karena data sekarang hanya value,
  tanpa volume saham per broker. Estimasi dengan close/VWAP hanya boleh diberi
  label `estimated_cost`, bukan angka cost resmi.
- Broker code tidak otomatis berarti institusi atau bandar. Satu broker dapat
  melayani banyak tipe nasabah. Klasifikasi institusi/retail perlu fetch
  `investor_type` terpisah dan tidak boleh ditebak hanya dari kode broker.
- Response sumber memiliki indikasi frekuensi transaksi, tetapi field tersebut
  belum disimpan di `broker_flows`. Buy/sell frequency perlu dipersist sebelum
  dipakai untuk membedakan pembelian berulang dari satu transaksi blok.

### 3.4 Smart-like vs retail-like accumulation

Target fase berikutnya bukan menebak kode broker sebagai `retail` atau
`institusi`, melainkan memberi skor apakah pola akumulasi lebih mirip smart
money atau lebih mirip distribusi ke retail.

Prinsip utama:

- Jangan menganggap broker code tertentu otomatis retail atau smart money.
- Broker retail dapat dipakai smart money untuk menyamarkan akumulasi.
- Satu broker dapat membawa flow campuran dari beberapa tipe nasabah.
- Foreign broker flow tetap sinyal penting, tetapi tidak cukup sebagai satu
  sumber kebenaran.
- Output harus berupa kualitas pola, misalnya `smart_like`, `mixed`, atau
  `retail_like`, bukan klaim identitas pelaku yang tidak dapat diverifikasi.

Fitur yang dipakai:

| Fitur | Rumus ringkas | Interpretasi |
|---|---|---|
| Average buy ticket | `buy_value / max(buy_freq, 1)` | Ticket besar cenderung lebih institutional |
| Average sell ticket | `sell_value / max(sell_freq, 1)` | Ticket besar pada sisi jual dapat menandakan distribusi besar |
| Net per trade | `net_value / max(buy_freq + sell_freq, 1)` | Net besar dengan frekuensi rendah cenderung lebih berkualitas |
| Buy/sell freq balance | `buy_freq / max(sell_freq, 1)` | Buy freq dominan lebih baik dari flow dua arah yang ramai |
| Frequency consistency | stabilitas `buy_freq` per hari | Akumulasi bertahap berulang lebih kuat dari spike satu hari |
| High-freq low-value flag | freq tinggi tetapi value per trade kecil | Cenderung retail/noisy |
| Low-freq high-value flag | freq rendah tetapi net besar | Cenderung block trade / institutional style |
| Cluster confirmation | top-3/top-5 ikut akumulasi | Membantu membedakan akumulasi nyata dari flow acak |
| Retention after high freq | posisi kumulatif tetap tertahan | Ramai beli tetapi cepat dibuang harus dipenalti |
| Foreign support | foreign net signifikan pada periode sama | Konfirmasi eksternal untuk smart-like accumulation |

Aturan interpretasi awal:

- `smart_like_accumulation`:
  net besar, `days_of_adv`/`%MCap` signifikan, `net_per_trade` memadai,
  retention baik, recency masih aktif, cluster ikut mendukung, dan bila ada
  foreign flow signifikan nilainya naik.
- `mixed_accumulation`:
  magnitude cukup baik tetapi salah satu dari retention, cluster,
  directional purity, atau kualitas frequency belum meyakinkan.
- `retail_like_accumulation`:
  `buy_freq` tinggi tetapi value per trade kecil, cluster lemah, retention
  rendah, recent flow melemah, atau terlihat pola distribusi ke banyak ticket
  kecil/noisy.
- `retail_distribution_risk`:
  1M masih net buy tetapi 5D melemah/negatif, frekuensi beli tinggi, dan
  support cluster/foreign tidak ada. Ini harus menjadi warning eksplisit.

Guardrail:

- `freq` tidak boleh dipakai sendirian untuk menilai smart money.
- Satu transaksi blok juga bisa merupakan crossing atau perpindahan internal;
  maka `low_freq_high_value` hanya evidence pendukung.
- Smart money dapat memecah order menjadi banyak transaksi kecil; karena itu
  `high_freq` baru dianggap negatif bila value per trade kecil, retention lemah,
  dan cluster/foreign tidak mendukung.
- Threshold awal harus dianggap provisional sampai ada histori minimal 6-12
  bulan untuk validasi out-of-sample.

## 4. Arsitektur Score

Gunakan dua skor terpisah:

- `broker_conviction` menjawab: seberapa kuat bukti bahwa broker sedang
  mengakumulasi saham ini?
- `entry_readiness` menjawab: apakah kondisi harga/teknikal saat ini masih
  layak untuk entry?

Label accumulation hanya berasal dari `broker_conviction`. Saham tetap dapat
berlabel `aggressive_accumulation` tetapi memiliki `entry_readiness` rendah
karena harga sudah overheated. Untuk ranking gabungan, default dapat memakai
`70% broker_conviction + 30% entry_readiness`, tetapi kedua skor tetap terlihat.

### 4.1 Broker conviction

Skor awal 0-100:

| Komponen | Bobot |
|---|---:|
| Magnitude `%MCap` dan `days_of_adv` | 20 |
| Buy persistence | 20 |
| Recency | 15 |
| Acceleration | 15 |
| Retention | 10 |
| Cluster strength/stability | 10 |
| Directional purity | 5 |
| Data quality/balance | 5 |

Penalty:

- Data coverage kurang dari 80%: tidak diberi label, status `insufficient_data`.
- Tidak ada net buy dalam dua sesi terakhir: kurangi skor dan status `stale`.
- Net 5 sesi terbaru negatif: status `reversal_risk`.
- Konsentrasi ekstrem pada saham sangat tidak likuid: tandai `concentration_risk`.

Label default provisional (semua threshold dapat diedit dari UI/config):

| Label | Gate minimum |
|---|---|
| `accumulation` | score >= 55, cluster net positif, positive ratio memadai, masih recent |
| `big_accumulation` | score >= 70 dan `%MCap >= 0,25` atau liquidity impact besar |
| `aggressive_accumulation` | score >= 85, recent net positif, acceleration kuat, dan persistence/cluster terkonfirmasi |

Label bukan hanya hasil threshold `%MCap`. Gate recency, persistence, coverage,
dan reversal wajib lolos agar label tidak menyesatkan.

Angka 55/70/85 dan threshold magnitude belum dianggap tervalidasi. Histori
broker saat ini baru sekitar satu bulan dan baru mencakup sebagian IDX. Threshold
produksi baru dikunci setelah backfill lebih panjang dan walk-forward backtest.

### 4.2 Entry readiness

Skor terpisah 0-100 dari trend/phase, relative strength, volume confirmation,
breakout freshness, risk/reward, dan jarak harga dari support/EMA. Kenaikan yang
sudah terlalu jauh memberi tag `overheated` dan menurunkan entry readiness,
tetapi tidak mengubah fakta bahwa broker sedang mengakumulasi.

## 5. Output Per Saham

Detail yang ditampilkan:

- Label, broker conviction score, dan entry readiness score.
- Top broker serta top-3/top-5 cluster.
- Net value, `%MCap`, `days_of_adv`.
- Positive days/trading days dan positive ratio.
- Net 1W vs 1M, acceleration, last buy date, retention.
- Return harga periode, volume confirmation, dan tag kondisi harga/entry.
- Data coverage, date range, serta warning stale/reversal/overheated.
- Grafik cumulative net top broker dan cluster bersamaan dengan harga.

### 5.1 Layout chart yang direkomendasikan

Chart detail memakai tiga pane vertikal dengan sumbu waktu dan crosshair yang
tersinkronisasi:

1. **Price pane**: candlestick, EMA20/EMA50 opsional, volume, serta marker
   accumulation/absorption. Ini tetap menjadi pane terbesar.
2. **Broker-flow pane**: bar net buy/sell harian dengan garis nol di tengah.
   Skala dibuat simetris agar besar buy dan sell mudah dibandingkan.
3. **Cumulative pane**: maksimum dua garis, yaitu selected top broker dan
   top-3 cluster. Jangan tampilkan semua broker sebagai garis karena sulit dibaca.

Gunakan `lightweight-charts` yang sudah menjadi dependency frontend untuk chart
lokal. TradingView iframe dapat tetap tersedia sebagai tab `TradingView`, tetapi
tab default broker analysis harus memakai chart lokal agar date range, tooltip,
crosshair, dan marker berasal dari dataset yang sama.

Di bawah chart utama tambahkan **broker heatmap**:

- Baris: top-5 broker pada periode terpilih.
- Kolom: tanggal perdagangan.
- Hijau = net buy, merah = net sell, abu-abu = tidak ada data.
- Intensitas warna dinormalisasi per saham/periode dengan cap percentile agar
  satu transaksi ekstrem tidak membuat seluruh sel lain terlihat kosong.
- Kolom kanan: total net, positive days, positive ratio, last buy, dan retention.

Heatmap menjadi cara utama melihat persistence, broker switching, dan apakah
cluster benar-benar bekerja bersama. Tabel top broker tetap ada sebagai detail,
bukan visual utama.

### 5.2 Kontrol dan keterbacaan

- Segmented control periode: `1W` dan `1M`, selalu tampilkan date range aktual.
- Segmented control flow: `Daily` dan `Cumulative`.
- Cluster selector: `Top 1`, `Top 3`, `Top 5`.
- Unit selector: `Rp`, `%MCap`, `Days ADV`; default `Rp` untuk chart harian dan
  `%MCap` untuk perbandingan screener.
- Klik broker pada heatmap/table menjadikannya selected broker pada chart.
- Tooltip lintas pane menampilkan tanggal lengkap, OHLC, volume, broker net,
  cluster net, cumulative net, `%MCap`, dan data coverage.
- Missing broker data tidak boleh diubah menjadi nol. Tampilkan gap/warna abu-abu
  dan warning coverage agar tidak terlihat seperti broker berhenti membeli.
- Warna konsisten: hijau net buy, merah net sell, biru selected broker, amber
  cluster. Label tidak hanya mengandalkan warna; selalu sertakan tanda `+/-`.
- Desktop: chart dan broker summary dapat berdampingan. Mobile: summary di atas,
  chart full-width, heatmap horizontal-scroll dengan kolom broker tetap terlihat.
- Preset tampilan awal hanya menampilkan candlestick, selected broker, cluster,
  dan marker penting. EMA/volume/technical overlay lain bersifat opsional.

### 5.3 Summary di atas chart

Tampilkan satu baris ringkas:

- `Label` dan `broker_conviction`.
- `Entry readiness` sebagai nilai terpisah.
- Top broker/cluster, net, `%MCap`, positive days, dan last buy.
- Status `active`, `cooling`, `stale`, atau `reversal_risk`.
- Coverage period dan waktu update terakhir.

Hindari radar chart untuk broker conviction. Contribution bar horizontal lebih
mudah dibaca untuk menunjukkan komponen magnitude, persistence, recency,
acceleration, retention, dan cluster.

## 6. Output Global Screener

Filter:

- Periode 1W/1M, label minimum, minimum score.
- Minimum `%MCap`, `days_of_adv`, positive ratio, dan positive days.
- Require active/recent, require acceleration, require cluster confirmation.
- Exclude stale, reversal risk, overheated, dan insufficient data.
- Universe IDX/watchlist, sektor, market-cap bucket, dan liquidity bucket.

Kolom hasil:

- Ticker, label, broker conviction, entry readiness, top broker, cluster brokers.
- Net, `%MCap`, days of ADV, positive days, last buy, acceleration, retention.
- Price return, technical phase, warning, dan coverage.

Default sorting: combined rank; user dapat memilih sort broker conviction atau
entry readiness secara terpisah.

## 7. Implementation Tasks

### P0 - Benarkan Fondasi

- [x] Pindahkan kalkulasi dari `_broker_accumulation` ke service khusus yang
  dapat dipakai screener, chart, API detail, dan tests.
- [x] Ganti `active_days` dengan `positive_days`, `negative_days`,
  `positive_ratio`, dan `consecutive_buy_days`.
- [x] Tambah recency, recent 5-session net, acceleration, retention, top-3,
  top-5, cluster ratio, cluster stability, dan directional purity.
- [x] Audit field response Stockbit lalu simpan buy/sell frequency yang memang
  tersedia (`freq`) tanpa mengestimasi field yang tidak diberikan sumber.
- [ ] Audit lanjutan untuk buy/sell volume dan average price broker; hanya
  boleh ditambah jika field sumbernya benar-benar terbukti konsisten.
- [x] Ganti display `%ADV` menjadi `days_of_adv`; pertahankan raw ratio untuk
  backward compatibility selama masa transisi.
- [x] Perbaiki `consistency` agar dihitung per broker/cluster, bukan total net
  seluruh broker.
- [x] Gunakan exact date range 1W/1M berdasarkan latest available data.
- [x] Tambah coverage check dan buy/sell balance quality check.

### P1 - Score, Label, dan API

- [x] Buat konfigurasi threshold default yang dapat dioverride oleh request.
- [x] Implementasikan broker conviction score, penalties, label, dan status.
- [x] Implementasikan entry readiness terpisah dan combined rank yang dapat
  dikonfigurasi.
- [ ] Tambah `flow_quality_score` terpisah untuk `smart_like` vs
  `retail_like`, agar tidak mencampur conviction dengan identitas pelaku.
- [ ] Tambah label/flag `smart_like_accumulation`, `mixed_accumulation`,
  `retail_like_accumulation`, dan `retail_distribution_risk`.
- [ ] Tambah threshold berbasis `freq`: average ticket, net per trade,
  high-freq low-value, low-freq high-value, dan frequency consistency.
- [ ] Tambah bonus/penalty ketika sinyal broker didukung atau tidak didukung
  oleh foreign flow signifikan pada periode yang sama.
- [x] Tambah endpoint detail per ticker dengan 1W/1M comparison.
- [x] Tambah endpoint global screener dengan filter, sort, pagination, dan
  metadata coverage.
- [x] Integrasikan hasil baru ke `ScreenerResult.dominant_factors` tanpa
  memutus response lama.
- [x] Tambah snapshot harian agar global screener tidak menghitung seluruh
  universe dari raw rows pada setiap klik.

### P2 - Frontend

- [x] Buat mode/preset `Broker Accumulation` pada halaman screener.
- [x] Tambah kontrol period, label, minimum conviction, recency, acceleration,
  cluster confirmation, sektor, market cap, dan liquidity.
- [ ] Tampilkan kolom conviction lengkap dengan tooltip definisi metrik.
- [ ] Tampilkan `flow quality` terpisah dari `broker conviction` agar user
  bisa membedakan besar akumulasi dari kualitas pola akumulasi.
- [ ] Tambah badge/tooltip `smart-like`, `mixed`, `retail-like`, dan
  `retail distribution risk` beserta penjelasan fitur yang memicunya.
- [ ] Tambah tampilan metrik frequency: `buy_freq`, `sell_freq`,
  `avg_buy_ticket`, `avg_sell_ticket`, `net_per_trade`, dan flag
  `high_freq_low_value` bila tersedia untuk periode terpilih.
- [x] Tambah badge warning untuk stale, reversal, overheated, dan data coverage.
- [x] Buat local synchronized chart dengan `lightweight-charts`: price,
  daily flow, dan cumulative flow panes.
- [x] Tambah broker heatmap top-5, broker selector, synchronized tooltip, serta
  gap indicator untuk missing data.
- [x] Tambah contribution bars untuk menjelaskan broker conviction; jangan
  gunakan radar chart untuk faktor broker.
- [x] Pertahankan TradingView sebagai tab sekunder untuk analisis manual.
- [x] Pastikan global screener langsung menampilkan snapshot terbaru; tombol run
  hanya untuk filter custom atau refresh manual.

### P3 - Data dan Backfill

- [ ] Lanjutkan backfill seluruh IDX hingga coverage 1 bulan selesai.
- [x] Jadwalkan incremental broker flow setelah market close pukul 19:00 WIB.
- [x] Buat retry untuk ticker/date gagal dan laporan coverage per batch.
- [ ] Setelah histori cukup, perluas backfill menjadi 6-12 bulan untuk validasi
  threshold dan broker-ticker historical edge.

### P4 - Test dan Validasi

- [x] Unit test magnitude, persistence, recency, acceleration, retention,
  cluster, directional purity, score, label, dan penalties.
- [ ] Unit test fitur frequency: average ticket, net per trade,
  frequency consistency, dan high-freq low-value flag.
- [ ] Regression test: net besar tetapi didominasi frekuensi kecil/noisy tanpa
  retention tidak boleh lolos sebagai `smart_like_accumulation`.
- [ ] Regression test: low-freq high-value dengan retention, cluster, dan
  foreign support yang baik harus naik menjadi `smart_like_accumulation`.
- [ ] Regression test: 1M positif tetapi 5D melemah, buy_freq tetap tinggi,
  dan cluster lemah harus diberi `retail_distribution_risk`.
- [x] Regression test: broker 1M positif tetapi 5D negatif tidak boleh berlabel
  active/aggressive accumulation.
- [x] Regression test: broker sering muncul tetapi lebih banyak net sell tidak
  boleh lolos minimum positive days.
- [x] API test untuk per-ticker/global, period boundaries, missing market cap,
  partial coverage, pagination, dan backward compatibility.
- [x] Backtest forward return 5/10/20 sesi per label dan liquidity bucket.
- [x] Walk-forward validation untuk tuning threshold; hindari tuning langsung
  pada seluruh histori agar tidak overfit.
- [ ] UI test desktop/mobile dan verifikasi nilai terhadap query raw broker flow.

## 8. Acceptance Criteria

- Periode 1W/1M selalu sesuai rentang kalender yang dipilih dan menampilkan
  tanggal serta jumlah sesi aktual.
- Saham yang akumulasinya sudah stale atau berbalik distribusi tidak tampil
  sebagai active/aggressive accumulation.
- Label dapat dijelaskan dari metrik yang terlihat; tidak ada black-box label.
- Hasil per saham dan global menggunakan engine kalkulasi yang sama.
- Screener global hanya meranking saham dengan coverage memadai.
- Setiap nilai top broker/cluster dapat direkonsiliasi dengan raw
  `broker_flows` untuk periode yang sama.
- Crosshair, date range, dan tooltip price/broker chart memakai tanggal yang
  sinkron; missing data terlihat sebagai gap dan tidak dianggap nol.
- Default chart tetap terbaca tanpa menonaktifkan overlay: maksimal dua garis
  broker pada satu pane, sementara detail top-5 ditampilkan melalui heatmap.

## 9. Urutan Eksekusi

1. P0: benarkan metrik dan data quality.
2. P1: score/label, API detail, snapshot global.
3. P2: UI screener dan chart detail.
4. P3: selesaikan backfill dan histori panjang.
5. P4: backtest, tuning threshold, lalu aktifkan label untuk pemakaian harian.

## 10. Breakdown Implementasi Smart-like vs Retail-like

Bagian ini memecah rencana `smart_like` vs `retail_like` menjadi urutan kerja
teknis yang bisa dieksekusi bertahap tanpa mencampur perubahan data, scoring,
API, dan UI dalam satu langkah besar.

### Phase 1 - Data layer dan feature engineering

Tujuan: pastikan semua fitur dasar tersedia dan hasilnya stabil sebelum
menyentuh label baru.

Pekerjaan:

- Gunakan `buy_freq` dan `sell_freq` yang sudah dipersist sebagai input baku.
- Tambah feature turunan per broker/periode:
  `avg_buy_ticket`, `avg_sell_ticket`, `net_per_trade`,
  `buy_sell_freq_ratio`, `total_freq`, dan `frequency_consistency`.
- Definisikan fallback yang eksplisit:
  jika `freq <= 0`, jangan bagi nol; simpan metric sebagai `None` atau nol
  terkontrol sesuai konteks agregasi.
- Tambah flag dasar:
  `high_freq_low_value`, `low_freq_high_value`, dan
  `retention_after_high_freq`.
- Normalisasi metrik frequency terhadap likuiditas saham:
  kombinasi `value`, `days_of_adv`, dan `net_per_trade` harus dibaca bersama,
  supaya saham sangat likuid dan sangat illiquid tidak diperlakukan sama.
- Verifikasi apakah feature tersebut cukup robust pada data yang coverage-nya
  belum penuh; jika coverage lemah, label kualitas flow harus ditahan.

Deliverable:

- Feature baru tersedia di engine broker accumulation.
- Response detail per broker sudah membawa metric frequency yang dibutuhkan.
- Tidak ada pembagian nol atau metric menyesatkan saat `freq` kosong.

### Phase 2 - Flow quality score

Tujuan: pisahkan ukuran besar akumulasi dari kualitas pola akumulasi.

Pekerjaan:

- Buat `flow_quality_score` terpisah dari `broker_conviction_score`.
- Definisikan komponen score awal, misalnya:
  magnitude per trade, retention, recency, cluster support,
  frequency consistency, directional purity, dan foreign support.
- Definisikan bonus:
  `net_per_trade` sehat, retention tinggi, cluster kuat,
  foreign flow signifikan, dan recency aktif.
- Definisikan penalty:
  `high_freq_low_value`, recent 5D melemah, cluster lemah,
  directional purity rendah, dan retention buruk.
- Tambah status/flag yang eksplisit:
  `retail_distribution_risk`, `flow_quality_insufficient_data`,
  `flow_quality_mixed`.
- Tetapkan threshold awal untuk label:
  `smart_like_accumulation`, `mixed_accumulation`,
  `retail_like_accumulation`.
- Simpan threshold di config/request override, sama seperti threshold conviction
  saat ini, agar bisa di-tune tanpa ubah code inti.

Deliverable:

- Engine menghasilkan score dan label flow quality secara konsisten.
- Label flow quality bisa hidup berdampingan dengan label conviction lama.
- Tidak ada asumsi bahwa broker code sendiri mewakili smart/retail.

### Phase 3 - API dan contract response

Tujuan: buka data baru ke frontend dan screener tanpa memutus contract lama.

Pekerjaan:

- Tambah field baru pada endpoint detail ticker:
  `flow_quality_score`, `flow_quality_label`,
  `retail_distribution_risk`, dan metric frequency utama.
- Tambah field ringkas pada endpoint global screener:
  cukup kirim score, label, dan 1-2 flag utama agar payload tetap ringan.
- Pertahankan backward compatibility:
  field lama `broker_conviction_score` dan `broker_conviction_label`
  tidak berubah makna.
- Tambah dominant factors / explanation payload:
  jelaskan mengapa label `smart_like` atau `retail_like` muncul.
- Pastikan snapshot harian menyimpan field baru yang dibutuhkan global screener,
  agar UI tidak menghitung ulang dari raw rows.

Deliverable:

- Endpoint detail dan screener bisa dipakai UI tanpa query tambahan.
- Contract response tetap stabil untuk consumer lama.

### Phase 4 - UI dan explainability

Tujuan: tampilkan score baru dengan cara yang mudah dibaca dan tidak
disalahartikan sebagai identitas broker.

Pekerjaan:

- Tampilkan `flow quality` sebagai panel/kolom terpisah dari
  `broker conviction`.
- Gunakan wording yang aman:
  `smart-like`, `mixed`, `retail-like`, bukan `broker retail` atau
  `broker institusi`.
- Tambah tooltip yang menjelaskan penyebab label:
  contoh `high net per trade`, `strong retention`,
  `weak cluster support`, `high freq low value`.
- Tampilkan metrik frequency yang paling penting saja di UI ringkas:
  `buy_freq`, `sell_freq`, `avg_buy_ticket`, `net_per_trade`.
- Tambah badge warning untuk `retail_distribution_risk`.
- Pastikan global screener bisa difilter atau di-sort berdasarkan
  `flow_quality_score` tanpa mencampur dengan entry readiness.

Deliverable:

- User bisa membedakan:
  saham yang sedang diakumulasi besar
  vs saham yang pola akumulasinya lebih mirip smart money
  vs saham yang terlihat seperti distribusi ke retail.

### Phase 5 - Validasi, backtest, dan rollout

Tujuan: jangan aktifkan label baru sebagai dasar keputusan harian sebelum
threshold dan perilakunya teruji.

Pekerjaan:

- Tambah unit test untuk semua metric frequency turunan.
- Tambah regression test untuk kasus penting:
  net besar tapi noisy,
  low-freq high-value dengan retention baik,
  1M positif tetapi 5D melemah,
  high buy freq tanpa dukungan cluster/foreign.
- Lakukan validasi manual pada sejumlah ticker contoh yang dikenal memiliki
  pola distribusi ke retail vs akumulasi yang lebih bersih.
- Setelah histori 6-12 bulan cukup, lakukan walk-forward validation untuk
  threshold `flow_quality_score`.
- Rollout bertahap:
  mulai dari badge informatif,
  lalu filter opsional,
  baru kemudian dipakai sebagai ranking penting bila performanya stabil.

Deliverable:

- Threshold label baru tidak sekadar intuitif, tetapi punya hasil validasi.
- Risiko false positive dari `freq` dapat ditekan sebelum fitur dijadikan
  komponen ranking utama.

## 11. Pending Follow-Up

Item di bawah ini belum selesai per Kamis, 23 Juli 2026 dan masih perlu
dikerjakan:

- Audit apakah response mentah `marketdetectors` juga konsisten menyediakan
  field buy/sell volume dan/atau average price broker. Jika memang tersedia,
  tambahkan parsing, persistence, dan test. Jika tidak konsisten atau tidak ada,
  tetap dokumentasikan sebagai unavailable dan jangan diestimasi.
- Definisikan threshold awal `flow_quality_score` untuk memisahkan pola
  `smart_like`, `mixed`, dan `retail_like` dengan fokus pada `freq`, retention,
  cluster, dan foreign support. Angka awal harus dianggap provisional.
- Tambah tooltip definisi metrik yang lebih lengkap di chart detail bila masih
  ada metrik broker yang belum punya penjelasan eksplisit di UI.
- Tambah UI test desktop/mobile untuk screener broker dan chart broker detail.
- Verifikasi nilai panel broker terhadap query raw `broker_flows` untuk beberapa
  ticker contoh sebagai check manual akhir.
- Lanjutkan backfill coverage broker flow sampai 1 bulan penuh untuk universe
  IDX.
- Setelah coverage 1 bulan stabil, perluas histori broker flow ke 6-12 bulan
  untuk validasi threshold dan broker-ticker historical edge yang lebih layak.
