---
schema_version: "4.0"
domain: devops
priority: 4
last_triggered: 2026-07-15
status: active
---

# DevOps Conventions

**MUST** run services via `docker compose up --build`.

**MUST** keep operational runbooks in `docs/OPERATIONS.md`.

**MUST** scale workers horizontally when pipeline throughput is low.

**NEVER** commit `.env` files with real secrets.
