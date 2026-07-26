# Plan: Status Trade Chart yang Lebih Ketat

> Status: DRAFT  
> Dibuat: 2026-07-26  
> Target: `/charts/[ticker]` menampilkan status `Siap Entry`,
> `Tunggu Konfirmasi`, atau `Hold` berdasarkan guardrail broker flow dan
> entry readiness yang konsisten dengan screener.

## 1. Tujuan

- Mengurangi status yang terlalu optimistis akibat hanya melihat skor agregat.
- Memastikan kondisi data buruk, flow stale, reversal, dan risiko distribusi
  selalu mengalahkan skor tinggi.
- Menampilkan alasan singkat agar user tahu syarat yang lolos dan yang masih
  menghambat entry.
- Menjaga status chart konsisten dengan field yang dihasilkan engine broker
  accumulation dan entry readiness saat ini.

Status ini merupakan ringkasan kondisi sistem, bukan rekomendasi transaksi
otomatis. Keputusan akhir tetap perlu memperhatikan harga entry, stop loss,
likuiditas, dan risiko portofolio.

## 2. Temuan Kondisi Saat Ini

Logic saat ini berada di `frontend/app/charts/[ticker]/page.tsx` dan hanya
memakai:

- `broker_conviction.status`
- `broker_conviction.score`
- `entry_readiness.score`
- `flow_quality.score`
- cluster confirmation

Masalah yang perlu diperbaiki:

1. UI membaca `cluster_confirmed` atau `cluster_ratio` dari
   `broker_conviction`, padahal API menaruh `cluster_ratio` di `one_month` dan
   `one_week`. Akibatnya, jalur `Siap Entry` praktis tidak dapat lolos.
2. `broker_conviction.label` belum dipakai. Skor tinggi tanpa label akumulasi
   masih dapat terlihat lebih baik dari kondisi sebenarnya.
3. Hard-risk seperti `reversal_risk`, `recent_5_session_net < 0`, dan
   `retail_distribution_risk` belum dievaluasi secara eksplisit.
4. Coverage, broker coverage, recency, retention, directional purity, dan fase
   teknikal belum menjadi gate.
5. Saat data masih loading atau tidak tersedia, fallback saat ini terlihat
   sebagai `Hold`; UI seharusnya membedakan `Hold` dari `Data Belum Siap`.
6. Alasan status masih berupa teks umum dan belum menunjukkan faktor spesifik
   yang menahan atau mengonfirmasi setup.

## 3. Sumber Data

Gunakan response `GET /screener/broker/{ticker}` tanpa menambah endpoint baru.

| Kategori | Field |
|---|---|
| Conviction | `broker_conviction.status`, `score`, `label` |
| Flow quality | `flow_quality.score`, `label`, `retail_distribution_risk`, `high_freq_low_value` |
| Entry | `entry_readiness.score`, `phase`, `tags` |
| Data utama 1M | `one_month.coverage_ratio`, `broker_coverage_ratio`, `recency_sessions`, `recent_5_session_net`, `retention`, `cluster_ratio`, `directional_purity`, `positive_ratio`, `acceleration` |
| Momentum pembanding | `one_week.status`, `broker_conviction_score`, `recent_5_session_net` |
| Konfigurasi | `broker_conviction.config.minimum_cluster_ratio` dan threshold engine lain bila tersedia |

Window utama tetap `one_month` karena `broker_conviction` API dibentuk dari 1M
bila tersedia. Window 1W hanya dipakai sebagai konfirmasi momentum terbaru,
bukan pengganti total conviction.

## 4. Urutan Keputusan

Evaluasi harus memakai prioritas berikut. Rule yang lebih atas menghentikan
evaluasi rule di bawahnya.

### 4.1 Data Belum Siap

Tampilkan `Data Belum Siap` bila salah satu kondisi berikut terjadi:

- response broker belum selesai dimuat;
- `broker_conviction.score` atau `entry_readiness.score` tidak tersedia;
- payload window utama tidak tersedia;
- `status === insufficient_data`;
- `coverage_ratio < 0.80` atau `broker_coverage_ratio < 0.80`.

Status ini bersifat netral dan tidak boleh ditampilkan sebagai `Hold`, karena
belum ada bukti yang cukup untuk menilai setup.

### 4.2 Hard Block menjadi Hold

Tampilkan `Hold` bila salah satu kondisi berikut terjadi:

- `status` adalah `no_accumulation`, `stale`, atau `reversal_risk`;
- `broker_conviction.label === none`;
- `recent_5_session_net <= 0`;
- `flow_quality.retail_distribution_risk === true`;
- `flow_quality.label` adalah `retail_distribution_risk` atau
  `insufficient_flow_quality`;
- `entry_readiness.phase` adalah `Siap Jual` atau `Exit`;
- `entry_readiness.tags` mengandung `weak_phase`;
- `recency_sessions > 2`.

Hard block mengalahkan skor conviction dan entry readiness berapa pun.

### 4.3 Siap Entry

Tampilkan `Siap Entry` hanya bila seluruh gate berikut lolos:

| Gate | Syarat awal |
|---|---|
| Engine status | `active` |
| Conviction label | `big_accumulation` atau `aggressive_accumulation` |
| Conviction score | `>= 70` |
| Entry readiness | `>= 75` |
| Entry phase | `Siap Entry` atau `Hold` dengan readiness `>= 80` |
| Flow quality score | `>= 60` |
| Flow quality label | `smart_like_accumulation`, atau `mixed_accumulation` dengan quality `>= 70` |
| Coverage | data dan broker coverage masing-masing `>= 0.80` |
| Recency | `<= 1` sesi |
| Recent flow | `recent_5_session_net > 0` |
| Retention | `>= 0.70` |
| Cluster | `cluster_ratio >= minimum_cluster_ratio`, default `0.50` |
| Directional purity | `>= 0.20` |
| Persistence | `positive_ratio >= 0.40` |
| Risk flags | tidak ada hard block |

Tambahan konfirmasi 1W:

- bila data 1W tersedia, status 1W tidak boleh `reversal_risk` atau `stale`;
- bila `one_week.recent_5_session_net <= 0`, turunkan menjadi
  `Tunggu Konfirmasi` meskipun semua gate 1M lolos.

### 4.4 Tunggu Konfirmasi

Tampilkan `Tunggu Konfirmasi` bila tidak terkena hard block, tetapi belum
memenuhi seluruh gate `Siap Entry`, dengan syarat minimum:

- `status === active`;
- label termasuk `accumulation`, `big_accumulation`, atau
  `aggressive_accumulation`;
- conviction score `>= 55`;
- entry readiness `>= 50`;
- `recent_5_session_net > 0`;
- coverage cukup;
- tidak ada risiko distribusi.

Contoh faktor yang membuat status tetap menunggu:

- conviction baru `accumulation`;
- entry readiness belum mencapai 75;
- recency sudah 2 sesi;
- retention atau cluster belum cukup;
- flow masih `mixed_accumulation` dengan score di bawah 70;
- momentum 1W melemah tetapi belum menjadi reversal.

### 4.5 Hold sebagai Fallback

Bila data cukup tetapi syarat minimum `Tunggu Konfirmasi` tidak terpenuhi,
tampilkan `Hold` beserta faktor utama yang gagal.

## 5. Bentuk Hasil Evaluasi

Pisahkan evaluasi dari JSX menjadi helper murni agar bisa diuji. Bentuk hasil
yang disarankan:

```ts
type TradeStatus = {
  code: "ready" | "waiting" | "hold" | "unavailable";
  label: "Siap Entry" | "Tunggu Konfirmasi" | "Hold" | "Data Belum Siap";
  summary: string;
  passed: string[];
  blockers: string[];
  warnings: string[];
};
```

Evaluator harus mengumpulkan reason code stabil, misalnya:

- `coverage_low`
- `broker_coverage_low`
- `conviction_too_low`
- `entry_not_ready`
- `cluster_weak`
- `retention_weak`
- `flow_not_recent`
- `recent_flow_negative`
- `reversal_risk`
- `retail_distribution_risk`
- `weak_technical_phase`

Teks Bahasa Indonesia dibuat melalui mapping reason code di frontend. Dengan
cara ini, rule tidak bercampur dengan copy UI dan lebih mudah dites.

## 6. Perubahan UI

Card status pada chart tetap berada di bagian atas, dengan isi:

- badge status dan warna yang konsisten;
- ringkasan satu kalimat;
- maksimal tiga faktor konfirmasi utama;
- maksimal tiga blocker/warning utama;
- nilai ringkas: conviction, entry readiness, flow quality, dan recency;
- disclaimer kecil bahwa status bukan instruksi transaksi otomatis.

Warna yang disarankan:

| Status | Tone |
|---|---|
| Siap Entry | emerald |
| Tunggu Konfirmasi | amber |
| Hold | slate atau red bila ada hard-risk |
| Data Belum Siap | slate dengan indikator data |

Status tidak boleh muncul sebagai `Hold` selama request masih loading. Saat API
error, tampilkan pesan error yang sudah ada dan status `Data Belum Siap`.

## 7. Rencana Implementasi

### Tahap 1 - Refactor evaluator

- Pindahkan logic dari `getTradeStatus()` ke helper murni, misalnya
  `frontend/lib/tradeStatus.ts`.
- Normalisasi field dari `broker_conviction`, `flow_quality`, `entry_readiness`,
  `one_month`, dan `one_week`.
- Gunakan `one_month.cluster_ratio`, bukan field cluster pada
  `broker_conviction`.
- Terapkan urutan `unavailable -> hard block -> ready -> waiting -> hold`.

### Tahap 2 - Integrasi chart

- Gunakan hasil evaluator di `/charts/[ticker]`.
- Bedakan loading, API error, dan data tidak cukup.
- Tampilkan score ringkas, blocker, warning, dan konfirmasi.
- Pertahankan tombol watchlist yang sudah ada.

### Tahap 3 - Test

- Tambahkan unit test untuk helper evaluator.
- Tambahkan test rendering minimal untuk label dan alasan status bila setup
  frontend saat ini mendukung component test.
- Jalankan lint dan test frontend yang tersedia.

### Tahap 4 - Kalibrasi

- Ambil sampel ticker untuk setiap status.
- Bandingkan hasil chart dengan kolom broker screener.
- Catat distribusi jumlah ticker per status agar threshold tidak menghasilkan
  hampir semua ticker pada satu kategori.
- Kalibrasi threshold hanya setelah hasil sampel ditinjau; jangan mengubah
  formula backend pada tahap awal.

## 8. Skenario Test Minimum

| Skenario | Hasil |
|---|---|
| Data masih loading | `Data Belum Siap` |
| Coverage 0.70 dengan skor tinggi | `Data Belum Siap` |
| Status `reversal_risk` dengan readiness 90 | `Hold` |
| Recent 5 session net negatif | `Hold` |
| Retail distribution risk aktif | `Hold` |
| Label `none` dengan skor entry tinggi | `Hold` |
| Active, label accumulation, conviction 60, entry 60 | `Tunggu Konfirmasi` |
| Semua gate ready lolos | `Siap Entry` |
| Semua gate 1M lolos tetapi 1W negatif | `Tunggu Konfirmasi` |
| Phase `Exit` dengan conviction tinggi | `Hold` |
| Cluster ratio tepat pada threshold config | lolos gate cluster |
| Cluster ratio di bawah threshold config | maksimal `Tunggu Konfirmasi` |

## 9. Acceptance Criteria

- `Siap Entry` tidak mungkin muncul bila ada hard-risk atau coverage kurang.
- Status memakai cluster ratio dari window utama yang benar.
- Semua status memiliki minimal satu alasan yang dapat dipahami user.
- Loading/error tidak menyamar sebagai `Hold`.
- Logic evaluator memiliki test untuk semua jalur keputusan utama.
- Hasil lint dan test frontend lulus.
- Watchlist dan link chart yang sudah ditambahkan tetap berfungsi.

## 10. Di Luar Scope Tahap Ini

- Mengubah bobot atau formula broker conviction di backend.
- Menghasilkan order otomatis.
- Menghitung position sizing, stop loss, atau target profit.
- Menjamin performa trading berdasarkan status.
- Melakukan backtest threshold baru; ini menjadi pekerjaan lanjutan setelah
  status UI stabil dan histori broker flow mencukupi.

