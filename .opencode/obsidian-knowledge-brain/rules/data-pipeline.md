---
schema_version: "4.0"
domain: data-pipeline
priority: 2
last_triggered: 2026-07-15
status: active
---

# Data Pipeline Conventions

**MUST** route all Stockbit calls through `backend/app/clients/stockbit.py`.

**MUST** add rate-limit delay between Stockbit calls (default 0.5s).

**MUST** gracefully skip individual tickers on failure; never kill the whole pipeline.

**NEVER** leave a pipeline stuck in `PROGRESS` after worker restart.
