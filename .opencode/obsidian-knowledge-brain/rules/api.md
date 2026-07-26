---
schema_version: "4.0"
domain: api
priority: 2
last_triggered: 2026-07-15
status: active
---

# API Conventions

**MUST** use `/api/v1/` prefix for all routes.

**MUST** return task responses with `task_id`, `status`, and `progress`.

**MUST** keep Pydantic schemas in `backend/app/api/schemas.py` or grouped by feature.

**NEVER** expose raw SQLAlchemy models directly in API responses.
