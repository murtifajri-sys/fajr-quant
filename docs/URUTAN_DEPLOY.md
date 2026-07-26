# Urutan Deploy Server Baru

Checklist ringkas untuk memindahkan Fajr-Quant ke server baru dengan data yang
sama seperti mesin lama.

## 1. Backup DB di Mesin Lama

Pastikan aplikasi lama masih berjalan, lalu:

```bash
cd /home/fajrirog/Fajr-Quant
./scripts/db-backup.sh
```

Output masuk ke:

```text
backups/fajr_quant_YYYYmmdd_HHMMSS.sql.gz
```

Pindahkan file dump itu ke server baru. Folder `backups/` tidak ikut Git.

## 2. Siapkan Server Baru

Install dependency minimum:

```bash
sudo apt update
sudo apt install -y git ca-certificates curl gnupg
```

Install Docker Engine + Docker Compose plugin sesuai panduan di
`docs/OPERATIONS.md`.

Pastikan command berikut jalan:

```bash
docker --version
docker compose version
```

## 3. Clone Repo

Siapkan SSH key GitHub di server baru, lalu:

```bash
git clone git@github.com:murtifajri-sys/fajr-quant.git
cd fajr-quant
```

## 4. Siapkan Environment

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Wajib diperhatikan:

- `ENCRYPTION_KEY` harus sama dengan mesin lama jika restore DB lama dan ingin
  token terenkripsi tetap terbaca.
- `AI_API_KEY` diisi jika memakai fitur AI.
- `TELEGRAM_BOT_TOKEN` diisi jika memakai Telegram.
- `DATABASE_URL` biarkan default jika memakai Docker Compose bawaan.

## 5. Start Aplikasi

```bash
docker compose up --build -d
```

Tunggu service siap:

```bash
docker compose ps
```

## 6. Restore Dump DB

Letakkan file dump di server baru, misalnya:

```text
backups/fajr_quant_YYYYmmdd_HHMMSS.sql.gz
```

Restore:

```bash
./scripts/db-restore.sh backups/fajr_quant_YYYYmmdd_HHMMSS.sql.gz
```

## 7. Restart Service

```bash
docker compose restart backend worker beat frontend
```

## 8. Cek Akses

Buka:

- Frontend: `http://<server-ip>:3000`
- API: `http://<server-ip>:8000/api/v1`
- Flower: `http://<server-ip>:5555`

## 9. Cek Setelah Deploy

Pastikan:

- Dashboard terbuka.
- Token Stockbit terbaca di menu Settings.
- Task pipeline bisa terlihat di dashboard.
- Watchlist, screener, chart, dan recommendation tampil.
- Jika token tidak terbaca, cek ulang `ENCRYPTION_KEY`.
