# Task Pool — Backend Implementation

PostgreSQL-backed job queue. Producers add tasks; consumers claim and process them safely in parallel.

**Stack:** Python 3.12 · PostgreSQL 16 · SQLAlchemy · Pydantic · Alembic · Docker

> Challenge brief: [CHALLENGE.md](CHALLENGE.md)

---

## What this implements

- Reusable **`add_task(...)`** and **`get_task(...)`** API (`taskpool.service`, re-exported from `taskpool`)
- Producer script for two topics with typed payloads
- Consumer script that supports multiple parallel workers (Docker scale or separate containers)
- Failed tasks are retained and not re-processed; completed tasks are never claimed again

### Topics and payloads

| Topic | Payload fields |
|---|---|
| `predict_voice` | `user_id` (UUID), `audio_s3_url` (string) |
| `raise_voice_alert` | `user_id` (UUID), `measured_at` (datetime), `audio_quality` (float 0–1), `voice_score` (float 0–1) |

---

## Prerequisites

- **Docker** and **`docker-compose`** (hyphen form — this project uses `docker-compose`, not necessarily `docker compose`)

---

## Quick start (recommended for reviewers)

One command: build, migrate, produce tasks, run workers, show final counts.

```bash
cd noah-labs-challenge-classroom-backend-challenge-task-pool-backend-challenge-task-pool
CLEAN_ALL=1 CONSUMERS=4 TASKS=20 ./scripts/reviewer-demo.sh
```

The script creates `.env` from `.env.example` automatically on first run.

**Expected result:** admin output shows all tasks `completed` and `pending: 0` (e.g. `completed: 20`).

Stop the stack:

```bash
docker-compose down
```

---

## Setup (manual path only)

Skip this section if you used `reviewer-demo.sh` above. Run **one command at a time**.

**Fresh start** (wipes previous task data): run `docker-compose down -v` before `docker-compose up -d db`.

```bash
cp .env.example .env
docker-compose build
docker-compose up -d db
docker-compose ps    # db should show (healthy)
docker-compose run --rm migrate
```

Postgres listens on host port **5433** by default (`POSTGRES_HOST_PORT` in `.env`).

---

## Run the producer

Creates sample tasks for **`predict_voice`** and **`raise_voice_alert`**.

```bash
docker-compose run --rm producer --topic all --count 20
```

**Expected:** last log line `"message": "producer_done", "tasks_created": 20` (after 20 `task_created` entries).

### Producer options

| Flag | Description | Default |
|---|---|---|
| `--topic` | `predict_voice`, `raise_voice_alert`, or `all` | `all` |
| `--count` | Number of tasks to create | `20` |
| `--seed` | RNG seed for reproducible payloads | random |

**Optional** — demos for `--topic`; skip before consumer testing if you want a predictable `pending` count.

```bash
docker-compose run --rm producer --topic predict_voice --count 10
docker-compose run --rm producer --topic raise_voice_alert --count 5
```

**Expected:** first run ends with `"producer_done", "tasks_created": 10`; second with `"tasks_created": 5`.

Wait for each producer container to exit before starting consumers.

---

## Start consumers

Consumers poll the pool, simulate processing (sleep), then mark tasks **completed** or **failed**.

Confirm tasks exist before starting:

```bash
docker-compose run --rm admin counts   # pending should be > 0
```

**Expected:** `pending` matches total tasks produced (e.g. `20` after one `--count 20` run).

### One consumer

```bash
docker-compose up consumer
```

**Expected:** logs show `task_claimed` → `task_completed`. After the queue is drained, logs stop but the consumer keeps running until **Ctrl+C**.

### Multiple consumers (parallel containers)

```bash
docker-compose up --scale consumer=4 consumer
```

**Expected:** four workers process tasks in parallel; same log lines, different `worker_id`s. After the queue is drained, logs stop but workers keep running until **Ctrl+C**.

### Verify results

In a second terminal:

```bash
docker-compose run --rm admin counts
```

**Expected:** `pending: 0`, `completed` equals total tasks produced (e.g. `20` after one `--count 20` run).

Shut down:

```bash
docker-compose down
```

---

## How it works

```
Producer  →  add_task()  →  pending
Consumer  →  get_task()   →  processing  →  handler  →  completed | failed
```

- **`add_task(topic, payload, ...)`** — validates and stores a typed payload
- **`get_task(topics, worker_id, ...)`** — atomically claims the next available task
- **`mark_task_completed` / `mark_task_failed`** — terminal states; failed tasks stay in the DB for inspection

Key source locations:

- Public API: `src/taskpool/service.py`
- Payload types: `src/taskpool/payloads/`
- Producer CLI: `src/taskpool/cli/producer.py`
- Consumer CLI: `src/taskpool/cli/consumer.py`

---

## Tests (optional)

```bash
./scripts/run-tests.sh              # fast: lint + unit tests (no database)
SUITE=all ./scripts/run-tests.sh    # full suite (starts Postgres in Docker)
```

**CI:** GitHub Actions runs lint, mypy, unit tests, the full PostgreSQL suite, and a Docker build on every push/PR (see the repo root `.github/workflows/ci.yml`).

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `docker-compose: command not found` | Install standalone `docker-compose`, or set `COMPOSE=docker compose` if using the plugin |
| Port 5433 already in use | Change `POSTGRES_HOST_PORT` in `.env`, then `docker-compose down` and start again |
| Producer succeeds but consumers show no progress | Confirm migrate ran; check `docker-compose run --rm admin counts` |
| Stale data from a previous run | `docker-compose down -v` (wipes the DB volume) then repeat Setup |
| `pending: 0` but you expected work | Run the producer again, or `docker-compose down -v` for a fresh start |
| DB container name conflict | Run `docker-compose up -d db` and wait for healthy before producer/consumers |
| `consumer-run-*` containers still running after `docker-compose down` | Stop them: `docker ps -q --filter "name=consumer-run" \| xargs -r docker stop` |

---

## Project layout

```
src/taskpool/          Application code (service, payloads, handlers, CLI)
migrations/            Alembic schema migrations
scripts/               Demo and test helper scripts
tests/                 Unit, integration, concurrency, and e2e tests
docker-compose.yml     Postgres + migrate + producer + consumer + admin
```

---
