---
schema_version: "4.0"
domain: architecture
priority: 1
last_triggered: 2026-07-15
status: active
---

# Architecture

**MUST** keep backend and frontend decoupled:
- Backend: Python 3.11, FastAPI, SQLAlchemy, Celery, Redis, MySQL.
- Frontend: Next.js 14, TypeScript, Tailwind, Recharts.
- Communication: REST API + server-side fetching.

**MUST** route all Stockbit calls through `backend/app/clients/stockbit.py`.
Token storage is encrypted (Fernet) in DB; never commit tokens.

**NEVER** run AI recommendations for all 963 tickers; cap at top 10 by composite score.
**MUST** filter recommendations by liquidity (min average daily value) and volatility/wick ratio before sending to AI.

**MUST** make all ticker displays clickable → chart page. Use `frontend/components/TickerLink.tsx` in `frontend/components/DataTable.tsx` (auto-links `ticker` column).

**MUST** serve Recommendations API filtered by `date` (default today) in `backend/app/api/routes/recommendations.py`; frontend `/recommendations` page is a client component with date picker.
