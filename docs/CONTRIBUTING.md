# Contributing

## Aturan utama
1. Semua akses Stockbit endpoint HANYA melalui `backend/app/clients/stockbit.py`.
2. Sensitive value (token) di-encrypt via `app/utils/encryption.py`.
3. Analisis teknikal/bandarmology terdaftar di `REGISTRY` masing-masing.
4. Long-running work = Celery task, bukan di request handler.
5. **Update dokumentasi**: setiap perubahan yang memengaruhi data flow, DB
   schema, endpoint, scoring weights/formula, AI prompt, atau Telegram
   behavior WAJIB disertai update file `docs/` terkait + entry
   `docs/CHANGELOG.md` di commit yang sama.

## Menjalankan lokal
```bash
cp backend/.env.example backend/.env  # isi ENCRYPTION_KEY, AI_API_KEY, TELEGRAM_BOT_TOKEN
docker compose up --build
# backend: http://localhost:8000  (docs: /docs)
# frontend: http://localhost:3000
# flower: http://localhost:5555
```

## Migrasi database
```bash
docker compose exec backend alembic revision --autogenerate -m "desc"
docker compose exec backend alembic upgrade head
```

## Test
```bash
docker compose exec backend pytest
```
