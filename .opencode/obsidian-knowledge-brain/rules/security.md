---
schema_version: "4.0"
domain: security
priority: 1
last_triggered: 2026-07-15
status: active
---

# Security Conventions

**MUST** encrypt Stockbit tokens with Fernet before storing in DB.

**MUST** keep encryption keys in environment variables, never in code.

**MUST** validate JWT expiry when accepting new tokens.

**NEVER** log decrypted tokens or API keys.
