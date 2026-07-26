# Fajr-Quant — Knowledge Navigation

Obsidian Knowledge Brain v4.0 hub for the Fajr-Quant project.

## Critical Rules
- Record `[ERROR:]` stubs immediately after fixing any bug.
- Run `wrap up` / `收尾` at session end to capture decisions and errors.
- Run `health check` / `健康检查` weekly.
- After project file changes, commit and push to `origin/main`; report the latest
  commit hash. If push fails, report the local commit and blocker.

## Project Index
| Project | File | Status |
|---------|------|--------|
| Fajr-Quant | `projects/fajr-quant.md` | active |

## Rules Index
| Domain | File | Description | Trigger |
|--------|------|-------------|---------|
| Architecture | `rules/architecture.md` | System overview and tech stack | Always |
| API | `rules/api.md` | FastAPI route and schema conventions | API changes |
| Backend | `rules/backend.md` | Python/FastAPI/Celery patterns | Backend work |
| Frontend | `rules/frontend.md` | Next.js/Tailwind conventions | Frontend work |
| Database | `rules/database.md` | SQLAlchemy/Alembic/MySQL rules | DB changes |
| Data Pipeline | `rules/data-pipeline.md` | Stockbit ingestion and pipeline | Pipeline work |
| AI | `rules/ai.md` | DeepSeek prompt and recommendation rules | AI changes |
| DevOps | `rules/devops.md` | Docker, worker scaling, monitoring | Infra work |
| Security | `rules/security.md` | Token encryption and secrets | Security work |

## External Docs
- `README.md` — Quick start and overview
- `TODO.md` — Active improvement backlog
- `docs/ARCHITECTURE.md` — Full architecture
- `docs/API.md` — API documentation
- `docs/OPERATIONS.md` — Runbooks
