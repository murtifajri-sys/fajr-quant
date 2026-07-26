# Operations

## Prasyarat

- Docker Engine + Docker Compose
- Git
- SSH key yang punya akses ke repository GitHub jika repo private
- Port 3000, 3306, 5555, 6379, dan 8000 tersedia

Mesin pengembangan saat verifikasi 2026-07-13 belum memiliki Docker maupun
Node.js. Backend dan integrasi data sudah diuji melalui Python dan database
SQLite sementara, tetapi deployment lengkap tetap memerlukan prasyarat di atas.

## Install server baru Ubuntu

Langkah minimum untuk server Ubuntu kosong:

```bash
sudo apt update
sudo apt install -y git ca-certificates curl gnupg
```

Install Docker Engine dan Docker Compose plugin dari repository resmi Docker:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Izinkan user menjalankan Docker tanpa `sudo`:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
```

Verifikasi:

```bash
docker --version
docker compose version
```

Siapkan SSH key untuk GitHub:

```bash
ssh-keygen -t ed25519 -C "server-fajr-quant"
cat ~/.ssh/id_ed25519.pub
```

Tambahkan public key ke GitHub, lalu test:

```bash
ssh -T git@github.com
```

Clone dan siapkan environment:

```bash
git clone git@github.com:murtifajri-sys/fajr-quant.git
cd fajr-quant
cp backend/.env.example backend/.env
```

Edit `backend/.env` minimal:

- `ENCRYPTION_KEY`: wajib; samakan dengan mesin lama jika restore DB lama;
- `AI_API_KEY`: diperlukan untuk AI recommendation/AI screener;
- `TELEGRAM_BOT_TOKEN`: diperlukan jika memakai notifikasi Telegram.

Start aplikasi:

```bash
docker compose up --build -d
```

Akses default:

- Frontend: `http://<server-ip>:3000`
- API: `http://<server-ip>:8000/api/v1`
- Flower: `http://<server-ip>:5555`

## First run

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed_stocks
```

Kemudian:

1. Buka `http://localhost:3000/settings/tokens`.
2. Masukkan JWT Stockbit dan tekan **Test**.
3. Isi DeepSeek key dan Telegram bot token di `backend/.env` bila diperlukan.
4. Buka dashboard dan tekan **Run Daily Pipeline**.

## Deploy server baru dengan data yang sama

Repo menyimpan schema lewat Alembic migration, bukan isi database production.
Untuk server baru yang harus punya data sama persis, pindahkan dump MariaDB dari
server lama.

### 1. Backup dari mesin lama

Pastikan stack lama masih berjalan, lalu jalankan:

```bash
./scripts/db-backup.sh
```

Output default masuk ke folder lokal `backups/`, misalnya:

```text
backups/fajr_quant_20260726_223000.sql.gz
```

Folder `backups/` di-ignore oleh Git. Jangan commit dump database karena bisa
berisi token terenkripsi, task history, dan data runtime.

### 2. Siapkan server baru

```bash
git clone git@github.com:murtifajri-sys/fajr-quant.git
cd fajr-quant
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

- isi `ENCRYPTION_KEY` dengan key yang sama dari mesin lama jika ingin token
  terenkripsi lama tetap bisa dibaca;
- isi `AI_API_KEY`, `TELEGRAM_BOT_TOKEN`, dan konfigurasi lain sesuai server;
- pastikan `DATABASE_URL` tetap mengarah ke service Docker `db` jika memakai
  `docker-compose.yml` default.

Start database dan service:

```bash
docker compose up --build -d
```

Command backend sudah menjalankan `alembic upgrade head` saat start. Untuk restore
dump penuh, migration tidak wajib dijalankan manual karena dump membawa isi tabel.

### 3. Restore dump ke server baru

Pindahkan file dump ke server baru, misalnya ke folder `backups/`, lalu:

```bash
./scripts/db-restore.sh backups/fajr_quant_20260726_223000.sql.gz
```

Setelah restore:

```bash
docker compose restart backend worker beat frontend
```

Buka:

- Frontend: `http://<server-ip>:3000`
- API: `http://<server-ip>:8000/api/v1`
- Flower: `http://<server-ip>:5555`

### Catatan restore

- Restore akan menimpa isi tabel sesuai dump. Jalankan di server baru atau DB yang
  memang siap diganti.
- Jika token Stockbit/AI tidak terbaca setelah restore, biasanya `ENCRYPTION_KEY`
  di `backend/.env` tidak sama dengan mesin lama.
- Jika hanya butuh schema kosong, cukup jalankan `docker compose up --build -d`
  dan seed stocks; tidak perlu restore dump.

## Daily pipeline

Manual:

```bash
curl -X POST http://localhost:8000/api/v1/tasks/daily-pipeline
```

Otomatis: Celery Beat menjalankan pipeline Senin-Jumat pukul 18:00 WIB.
Jumlah ticker saat tidak ada watchlist dibatasi oleh
`DAILY_PIPELINE_MAX_TICKERS` (default 50). Jika watchlist tersedia, pipeline
memproses isi watchlist.

### Auto-run saat PC dinyalakan setelah jam 18:00

Jika PC mati/sleep saat jadwal 18:00, pipeline normalnya tertinggal.
Script `scripts/startup_daily_pipeline.sh` otomatis trigger pipeline saat
boot jika:

- Backend API sudah ready (menunggu maksimal 5 menit).
- Waktu saat ini sudah lewat jam 18:00 WIB.
- Belum ada task `daily_pipeline` hari ini.

Script dijalankan via cron user `fajrirog`:

```bash
crontab -l
# @reboot sleep 60 && /home/fajrirog/Fajr-Quant/scripts/startup_daily_pipeline.sh
# */15 18-23 * * 1-5 /home/fajrirog/Fajr-Quant/scripts/startup_daily_pipeline.sh
```

- `@reboot` → handle PC yang mati/nyala ulang setelah jam 18:00.
- `*/15 18-23 * * 1-5` → handle PC yang sleep/hibernate lalu dibangunkan.
  Script sudah idempoten: kalau `daily_pipeline` hari ini sudah ada, dia skip.

Log: `logs/startup_daily_pipeline.log`.

## Start / Stop aplikasi

Ada script bantuan di folder `scripts/`:

```bash
# Start seluruh stack (Docker Compose up + tunggu API ready)
./scripts/start.sh

# Stop seluruh stack (Docker Compose stop)
./scripts/stop.sh
```

Log masing-masing ada di:
- `logs/start_fajr_quant.log`
- `logs/stop_fajr_quant.log`

## Auto start/stop saat PC nyala/matikan

Agar aplikasi otomatis jalan saat PC dinyalakan dan mati rapi saat PC dimatikan,
pasang systemd service-nya:

```bash
./scripts/install-systemd-service.sh
```

Setelah terpasang:

```bash
# Start sekarang
sudo systemctl start fajr-quant

# Cek status
sudo systemctl status fajr-quant

# Biarkan auto-start saat boot
sudo systemctl enable fajr-quant
```

Service file: `scripts/fajr-quant.service`. Service ini:
- Menjalankan `scripts/start.sh` saat boot setelah Docker daemon siap.
- Menjalankan `scripts/stop.sh` saat shutdown.
- Berjalan sebagai user `fajrirog` (pastikan user sudah masuk grup `docker`).

## Monitoring

- Dashboard: `http://localhost:3000` → tabel **Pipeline Status**.
- Flower: `http://localhost:5555`.
- API recent runs: `GET /api/v1/tasks/runs`.
- API satu task: `GET /api/v1/tasks/{task_id}`.
- Logs: `docker compose logs -f worker beat backend`.

Status persisten: `QUEUED`, `STARTED`, `PROGRESS`, `SUCCESS`, atau `FAILURE`.
Progress menyimpan stage, jumlah ticker diproses/sukses/gagal, result, dan error.

## Broker Flow Backfill

Broker flow untuk screener accumulation dibackfill terpisah dari daily pipeline.

Schedule otomatis Celery Beat:

- `19:00 WIB` hari kerja → `run_broker_flow_backfill`
- `19:30 WIB` hari kerja → `run_broker_flow_backfill`
- `20:00 WIB` hari kerja → `run_daily_screener` untuk snapshot broker screener

Trigger manual:

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/broker-flow-backfill?limit=50&period_days=30&universe=idx"
curl -X POST "http://localhost:8000/api/v1/tasks/daily-screener-snapshot"
```

Cek coverage terbaru:

```bash
curl "http://localhost:8000/api/v1/tasks/broker-flow-backfill/coverage?period_days=30&universe=idx&limit=25"
```

Retry batch gagal:

```bash
curl -X POST "http://localhost:8000/api/v1/tasks/broker-flow-backfill/<task_id>/retry"
```

Hasil task backfill menyimpan:

- `requested_tickers`
- `failed_tickers`
- `coverage_before`
- `coverage_after`
- `fetched_dates`

Gunakan `GET /api/v1/tasks/{task_id}` untuk membaca report batch lengkap.

## Token Stockbit

- JWT `exp` dibaca otomatis saat token disimpan.
- Token yang sudah expired ditolak sebelum request.
- HTTP 401 menonaktifkan token dan menyimpan `last_error`.
- Dashboard menampilkan banner merah bila token hilang, expired, atau error.
- Token hanya dimasukkan melalui UI/API dan disimpan terenkripsi; jangan pernah
  menaruh JWT di dokumentasi atau repository.
