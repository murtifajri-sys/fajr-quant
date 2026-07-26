---
schema_version: "4.0"
domain: backend
priority: 2
last_triggered: 2026-07-15
status: active
---

# Backend Conventions

**MUST** place FastAPI routers in `backend/app/api/routes/`.

**MUST** use Celery tasks for long-running pipelines in `backend/app/workers/tasks.py`.

**MUST** create a new DB session per worker thread when parallelizing.

**NEVER** block the event loop with synchronous I/O inside async routes.
