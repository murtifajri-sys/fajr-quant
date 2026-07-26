---
schema_version: "4.0"
project: fajr-quant
status: active
updated: 2026-07-15
---

# Fajr-Quant

**Path**: `/home/fajrirog/Fajr-Quant`

Indonesian stock analysis platform combining technical analysis, bandarmology, and AI recommendations.

## Recent Milestones
- Data explorer phase 1 completed.
- Worker scaled from 1 to 3 containers.
- Recommendations limited to top 10 tickers by composite score.
- Background monitor script created.
- Recommendation rationale now Bahasa Indonesia, human-readable.
- Liquidity/volatility filter added (min avg daily value 500M IDR, max avg wick 5%).
- All ticker displays clickable to chart page (`TickerLink` + `DataTable`).
- Recommendations menu defaults to today with date picker; stale 2026-07-14 rows cleaned.
- Free fallback AI model (`deepseek-v4-flash`) on quota exhaustion (402/429).

## Blockers
- Pipeline occasionally stuck in PROGRESS after worker restart.
- Stockbit rate limit slows full data load (~3 hours for 963 tickers).

## Active TODOs
- Cancel task endpoint.
- Token 401 graceful handling.
- Rate-limit delay configuration.
- Parallel processing with ThreadPoolExecutor.

## Data Sources
- Stockbit Exodus API (daily prices, broker summary, company profile, shareholders).
- Fallback: yfinance.

## Tech Stack
- Backend: Python 3.11, FastAPI, SQLAlchemy, Celery, Redis, MySQL.
- Frontend: Next.js 14, TypeScript, Tailwind, Recharts.
- AI: DeepSeek via OpenAI-compatible proxy at `https://opencode.ai/zen/go/v1`; primary `deepseek-v4-pro`, free fallback `deepseek-v4-flash`.
