---
schema_version: "4.0"
domain: backend
priority: 2
last_triggered: 2026-07-20
status: active
---

# Daily Pipeline Chain (Fajr-Quant)

**MUST** chain the daily pipeline in `backend/app/workers/tasks.py` as:
`run_full_data_load` -> `run_recommendations_batch` -> `run_daily_screener` -> `send_daily_digest`.

**MUST NOT** schedule `send_daily_digest` with a fixed `countdown` (e.g. 15 min) before recommendations finish — it fires before recs are written, so the digest sends the PREVIOUS day's recommendations.

**MUST** include `run_daily_screener` in the chain (or the top-screener in the Telegram digest stays stuck on the last manual run, i.e. yesterday's data).

**WHY** (2026-07-20 pitfall): telegram digest kept sending prior-day recs and stale screener because (1) digest was on a fixed countdown, and (2) screener was only triggerable manually via `POST /api/v1/screener/run`, never in the pipeline.
