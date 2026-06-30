# Noah Labs Take-Home Challenge

Solutions for the **backend** (PostgreSQL task pool) and **frontend** (React + MUI) coding challenges.

## Overview

### Backend — PostgreSQL task pool

A typed job queue where producers enqueue tasks and multiple consumers claim work in parallel without double-processing.

- **API:** `add_task()` / `get_task()` with topic-specific payloads (`predict_voice`, `raise_voice_alert`)
- **Concurrency:** `SELECT … FOR UPDATE SKIP LOCKED`; claim commits before handler work
- **Stack:** Python 3.12, PostgreSQL 16, SQLAlchemy, Pydantic, Alembic, Docker
- **Guarantee:** at-most-once claiming; failed tasks are retained, not reprocessed

### Frontend — People table & details panel

A React app that fixes table layout issues and fetches per-person details with full async state handling.

- **Task 1:** table padding and status-column alignment
- **Task 2:** per-row “View details” with loading, error, not-found, and success states + race-condition guard
- **Stack:** React 19, TypeScript, MUI, Biome

## Quick start

| Project | Directory | Start here |
|---|---|---|
| Backend | [`noah-labs-challenge-classroom-backend-challenge-task-pool-backend-challenge-task-pool/`](noah-labs-challenge-classroom-backend-challenge-task-pool-backend-challenge-task-pool/) | `CLEAN_ALL=1 CONSUMERS=4 TASKS=20 ./scripts/reviewer-demo.sh` |
| Frontend | [`noah-labs-challenge-classroom-frontend-challenge-frontend-challenge/`](noah-labs-challenge-classroom-frontend-challenge-frontend-challenge/) | `npm install && npm run dev` → http://localhost:5173 |

See each folder’s **README** for full setup, options, and troubleshooting.

## CI

GitHub Actions on every push: backend lint, mypy, ~50 PostgreSQL tests, Docker build; frontend lint and production build.

## Repository layout

```
noah-labs-challenge-classroom-backend-challenge-task-pool-backend-challenge-task-pool/   # task pool
noah-labs-challenge-classroom-frontend-challenge-frontend-challenge/                      # React app
document/                                                                                 # planning notes (optional)
```
