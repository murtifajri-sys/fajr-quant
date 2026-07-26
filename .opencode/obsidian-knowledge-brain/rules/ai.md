---
schema_version: "4.0"
domain: ai
priority: 3
last_triggered: 2026-07-15
status: active
---

# AI Conventions

**MUST** keep AI prompts in `docs/AI_PROMPT.md` or `backend/app/services/ai/`.

**MUST** limit recommendations to top 10 tickers by composite score.

**MUST** write AI rationale in Bahasa Indonesia, human-readable (not raw numeric scores). System prompt is in `backend/app/services/ai/prompt.py`.

**MUST** filter recommendations by liquidity (min avg daily value) and volatility/wick ratio before sending to AI (`backend/app/services/ai/recommendation_filter.py`).

**MUST** use free fallback model when primary runs out of tokens: primary `deepseek-v4-pro` → on 402/429 auto-switch to `deepseek-v4-flash` (free) via `backend/app/services/ai/fallback.py`. Record actual model used in `recommendations.provider`.

**MUST** log token usage per recommendation batch.

**NEVER** send raw PII or secret tokens in AI prompts.
