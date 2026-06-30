# NOAH LABS TAKE HOME CHALLENGE

Solutions for the Noah Labs backend and frontend challenges.

## Projects

| Challenge | Folder | Quick start |
|---|---|---|
| **Backend** — PostgreSQL task pool | [`noah-labs-challenge-classroom-backend-challenge-task-pool-backend-challenge-task-pool/`](noah-labs-challenge-classroom-backend-challenge-task-pool-backend-challenge-task-pool/) | `CLEAN_ALL=1 ./scripts/reviewer-demo.sh` |
| **Frontend** — React + MUI | [`noah-labs-challenge-classroom-frontend-challenge-frontend-challenge/`](noah-labs-challenge-classroom-frontend-challenge-frontend-challenge/) | `npm install && npm run dev` |

## CI

GitHub Actions runs backend tests (lint, mypy, PostgreSQL suite, Docker build) and frontend lint/build on every push.

## Push to GitHub (personal access token)

1. Copy the env template and add your token (`.env` is gitignored):

   ```bash
   cp .env.example .env
   # edit .env → GITHUB_TOKEN=ghp_your_token_here
   ```

2. Push:

   ```bash
   ./scripts/push-github.sh
   ```

   Token needs **repo** scope. It is read from `.env` only for the push command and is **not** stored in `git config`.

---

Please note that you must complete both challenges. Once you have finished, compress your solutions into a single zip file (your_full_name.zip) and send it back to our email at apply@noah-labs.com.