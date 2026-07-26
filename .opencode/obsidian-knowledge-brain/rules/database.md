---
schema_version: "4.0"
domain: database
priority: 3
last_triggered: 2026-07-15
status: active
---

# Database Conventions

**MUST** use SQLAlchemy 2.0 style models.

**MUST** write Alembic migrations in `backend/alembic/versions/`.

**MUST** keep seed scripts in `backend/app/scripts/`.

**NEVER** modify the stocks table without running the seed script.
