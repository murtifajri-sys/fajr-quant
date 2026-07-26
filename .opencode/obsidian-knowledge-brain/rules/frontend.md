---
schema_version: "4.0"
domain: frontend
priority: 2
last_triggered: 2026-07-15
status: active
---

# Frontend Conventions

**MUST** use Next.js 14 App Router under `frontend/app/`.

**MUST** share data tables via `frontend/components/DataTable.tsx`.

**MUST** use `frontend/lib/` for API clients and utilities.

**NEVER** fetch backend data directly from client components; use server components or API routes.
