# Development Plan — PostgreSQL-Backed Task Pool

> **Status: Submission-ready (Phases 1–10 complete for core challenge; optional hardening remains).**
> Application code lives under
> `noah-labs-challenge-classroom-backend-challenge-task-pool-backend-challenge-task-pool/`.
> This document remains the design reference; the **Implementation Status** section
> below tracks what is done vs. what remains.

---

## Implementation Status (last updated: 2026-06-30)

### Summary

| Area | Status | Notes |
|---|---|---|
| Core application (Phases 1–7) | **Done** | Typed service API, repository, handlers, producer/consumer/admin CLIs |
| Tests — unit + static typing | **Done** | 32 unit tests pass; mypy strict on `src` + `tests` (41 files) |
| Tests — integration / concurrency / e2e | **Done** | 49 tests pass via `SUITE=all ./scripts/run-tests.sh` against Postgres on `:5433` |
| Docker / Compose (Phase 9) | **Done (verified)** | `reviewer-demo.sh` green (`completed: 20`, `pending: 0`); scaled consumers work |
| README (§23) | **Done** | Implementation `README.md` (setup, producer, scaled consumers, tests, troubleshooting) |
| CI pipeline (§22) | **Done** | `.github/workflows/ci.yml` — lint, mypy, unit, PG suite, Docker build |
| Phase 10 hardening extras | **Partial** | Abandoned reaper/admin done; metrics optional; PG least-priv not done |

### Implemented files (backend root)

```
backend/
  pyproject.toml, alembic.ini, Dockerfile, docker-compose.yml, .env.example
  migrations/versions/0001_create_tasks.py
  src/taskpool/
    config.py, logging.py, db.py, exceptions.py, observability.py
    repository.py, service.py
    domain/{topics,task}.py
    payloads/{base,predict_voice,raise_voice_alert,registry}.py
    persistence/models.py
    handlers/{base,predict_voice,raise_voice_alert}.py
    cli/{producer,consumer,admin}.py
  tests/
    unit/          test_payloads, test_registry, test_handler_routing, test_misc
    typing/        test_static_contracts  (mypy overload proofs)
    integration/   test_service.py
    concurrency/   test_skip_locked.py
    e2e/           test_producer_consumer.py
```

### Phase completion (§24)

| Phase | Status | Verification |
|---|---|---|
| P1 — Skeleton & tooling | ✅ Done | `ruff check`, `mypy src`, unit tests green |
| P2 — Domain, payloads, registry | ✅ Done | Unit + `tests/typing/test_static_contracts.py` |
| P3 — Persistence + migrations | ✅ Done | Alembic `0001`; `tests/integration/test_migrations.py` |
| P4 — Repository | ✅ Done | Covered via `tests/integration/test_service.py` (no isolated repo test file) |
| P5 — Service (public API) | ✅ Done | Integration tests written |
| P6 — Handlers + dispatch | ✅ Done | `assert_never` in `handlers/base.py`; unit tests |
| P7 — Producer & Consumer CLIs | ✅ Done | E2E tests pass against PG (`tests/e2e/`) |
| P8 — Concurrency tests | ✅ Done | `test_skip_locked.py` green (8 workers, 60 tasks, no double-claim) |
| P9 — Docker + admin | ✅ Done | `reviewer-demo.sh` verified; admin `counts/get/stale/reap` |
| P10 — CI + README + hardening | ✅ **Done** | README, CI, PG tests, migration test; optional hardening remains |

### Remaining work (ordered by priority)

**Required to meet Definition of Done (§27)**

1. ~~**Run PostgreSQL-backed tests to green**~~ — **Done** (2026-06-30): `docker-compose up -d db` + `SUITE=all ./scripts/run-tests.sh` → 49 passed.
2. ~~**Write implementation README**~~ — **Done**: backend `README.md` covers setup, producer, scaled consumers, tests, troubleshooting.
3. ~~**Add CI pipeline**~~ — **Done**: `.github/workflows/ci.yml` (ruff, mypy, unit, PG suite, Docker build).
4. ~~**Verify Docker end-to-end**~~ — **Done** (2026-06-30): `CLEAN_ALL=1 CONSUMERS=4 TASKS=20 ./scripts/reviewer-demo.sh` → all tasks `completed`, `pending: 0`.
5. ~~**Migration up/down test**~~ — **Done**: `tests/integration/test_migrations.py`.

**Hardening (nice-to-have, labeled in README)**

- `[Optional]` Prometheus metrics (`observability.py` counters/histograms).
- `[Hardening]` Least-privilege Postgres app role in Compose (DDL only for migrate).
- `[Hardening]` DB-level payload size CHECK (app validates today; DB check not added).
- `[Hardening]` Explicit graceful-shutdown test (SIGTERM handler exists in consumer; manual/e2e only).
- `[Hardening]` Isolated `test_repository.py` and dedicated `test_error_serialization.py` (logic exists; tests consolidated into `test_service.py` / `test_misc.py`).

**Not started / out of scope for backend**

- Frontend challenge (`noah-labs-challenge-classroom-frontend-challenge-frontend-challenge/`).

---

## 0. Review of the Suggested Strategy

The brief in `document/strategy.md` is strong and production-oriented. It correctly
emphasizes the three things that actually make this challenge hard:

1. **Safe concurrent claiming** via `SELECT ... FOR UPDATE SKIP LOCKED` with a short
   claim transaction that commits *before* processing.
2. **Honest processing semantics** — it explicitly asks us *not* to claim
   exactly-once for external side effects, which is the correct and honest position.
   We target **at-most-once** processing with idempotency hooks.
3. **Typing-first design** — a typed topic→payload registry so a
   `RaiseVoiceAlertPayload` can never be passed to `predict_voice`.

Where I refine / take a position relative to the brief:

| Topic | Decision | Rationale |
|---|---|---|
| Sync vs async | **Synchronous** Python + psycopg3 sync | Per-worker workload is "claim one task, process, mark done". There is no fan-out I/O concurrency inside a single task that async would accelerate. Concurrency is achieved by running *many worker processes/containers*, which is exactly what the challenge tests. Async adds complexity (event loop, async SQLAlchemy, async drivers) with no benefit here. |
| Retries | **No automatic retries** | The assignment explicitly forbids reprocessing failed tasks. We keep failed tasks for inspection only. |
| `abandoned` status | **Included but not auto-recovered** | Crash-after-claim leaves a row stuck in `processing`. We provide an operational reaper/inspection command that can mark stale `processing` rows as `abandoned`. We do **not** auto-requeue them (that would violate the no-reprocessing rule). This is labeled *Production hardening*. |
| Multi-topic consumer | **Configurable topic subset** | A consumer claims from one-or-more topics it is configured for; default is "all known topics". Lets you scale topics independently. |
| Claim batch size | **One task per claim transaction** (default), optional small batch | Keeps the claim transaction tiny and the lock window minimal. Batch is an optional optimization. |

Two small gaps in the brief that this plan closes:
- A concrete **stale-task detection** mechanism (heartbeat vs claim-age threshold). We
  use claim-age threshold for simplicity.
- **Connection failure / retry-on-transient** behavior at the session boundary
  (reconnect on `OperationalError`, pool `pool_pre_ping`).

Everything below follows the 27-section structure requested by the brief.

---

## 1. Executive Summary

We build a lightweight, PostgreSQL-backed background-job queue. Producers call a
typed `add_task(topic, payload)` to insert rows into a single `tasks` table with
status `pending`. Consumers call `get_task(topics, worker_id)` which atomically
claims one `pending` row using `SELECT ... FOR UPDATE SKIP LOCKED`, flips it to
`processing`, commits immediately, and returns a fully typed task. The consumer then
runs the topic-specific handler (simulated work via `sleep`) and calls
`mark_task_completed(...)` or `mark_task_failed(...)`.

Correctness rests on a short claim transaction with row-level locking so two
consumers can never claim the same row. We are explicit that PostgreSQL locking gives
**at-most-once claiming**, not exactly-once *execution* of external side effects;
idempotency keys and idempotent handlers close that gap as far as is honestly
possible.

The stack is Python 3.12+, PostgreSQL 16, SQLAlchemy 2.x (sync), psycopg 3,
Pydantic 2, Alembic, Docker/Compose, pytest, Ruff, and a strict type checker.

**Feature labels used throughout:** `[Required]` for assignment acceptance criteria,
`[Hardening]` for production robustness, `[Optional]` for nice-to-have future work.

---

## 2. Requirements Interpretation

From the README (authoritative acceptance criteria) and the strategy brief:

- **Multiple producers / consumers in parallel** `[Required]` — process/container-level
  concurrency, validated by a concurrency test.
- **Multiple topics** `[Required]` — `predict_voice`, `raise_voice_alert`, extensible.
- **A task is never processed twice** `[Required]` — enforced by atomic claim
  (`pending → processing` once) + state-transition guards. (Claim is once; *execution*
  side effects are mitigated by idempotency, see §4.)
- **Failed tasks retained, not reprocessed** `[Required]` — terminal `failed` status;
  `get_task` never returns non-`pending` rows.
- **No required ordering** `[Required]` — `SKIP LOCKED` may reorder; acceptable.
- **Reusable, fully typed `add_task` / `get_task`** `[Required]`.
- **Typing-first** `[Required]` — typed registry, generics, strict checker passes.
- **Concurrent consumers across containers** `[Required]` — Compose scaling demo.
- **README** `[Required]`.

---

## 3. Explicit Assumptions

1. A "task is never processed twice" is interpreted as **claimed/started at most
   once**. True exactly-once *external* effects are impossible with a crash between
   side effect and commit; we state this honestly (§4).
2. Failed = terminal. No automatic retry. Reprocessing, if ever needed, is a manual
   operational action (re-insert a new task), not built in.
3. Handlers are simulated (`sleep` + light logic). `predict_voice` does not actually
   download from S3; it validates/normalizes the URL and logs intent.
4. Postgres runs at default `READ COMMITTED` isolation, which is sufficient and
   correct for the `FOR UPDATE SKIP LOCKED` pattern (§8).
5. Worker IDs are unique strings (e.g. `f"{hostname}-{pid}-{uuid4()}"`), generated by
   the consumer at startup.
6. Payload size is bounded (reject oversized payloads in app code; also a DB check
   on serialized size is `[Hardening]`).
7. Timestamps are always timezone-aware UTC (`TIMESTAMPTZ`).
8. One logical database, single `tasks` table (no per-topic tables) — simplest design
   that meets all requirements.

---

## 4. Processing Guarantees and Trade-offs

### What PostgreSQL locking guarantees
- `SELECT ... FOR UPDATE SKIP LOCKED` inside a transaction takes a **row lock**. Two
  concurrent claimers skip each other's locked rows, so **no row is claimed by two
  workers**.
- The `UPDATE ... SET status='processing'` in the same transaction is atomic with the
  select; on commit the row is durably `processing` and invisible to future `pending`
  queries.

### Why `SELECT` then later `UPDATE` (separate statements/txns) is unsafe
A plain `SELECT ... WHERE status='pending'` without locking returns the same row to
two consumers (read-read is not exclusive). Both then `UPDATE` it → both "claim" it →
the task is processed twice. Even within one transaction, a plain `SELECT` (no
`FOR UPDATE`) does not block another transaction from reading the same row. Row
locking via `FOR UPDATE` is what makes the read-then-claim exclusive; `SKIP LOCKED`
makes it non-blocking so workers grab *different* rows instead of queuing on the same
one.

### The honest failure scenario (from the brief)
1. Consumer claims task → 2. DB commits `processing` → 3. consumer performs external
side effect → 4. consumer **crashes** before `mark_task_completed`.

Result: the row is stuck in `processing` forever (locking gives us nothing here — the
transaction already committed). The side effect already happened.

**Therefore DB locking alone does NOT give exactly-once execution.** It gives
at-most-once *claiming*. We do not pretend otherwise.

### Production protections (layered)
- **Idempotency key** `[Hardening]` — optional `idempotency_key` unique constraint
  prevents duplicate *task creation*; idempotent handlers prevent duplicate *effects*
  if a task is ever manually re-created.
- **Idempotent handlers** `[Hardening]` — handlers keyed on `(user_id, ...)` so a
  re-run is a no-op / upsert.
- **Task execution records / unique constraints** `[Optional]` — downstream effect
  tables with unique keys to dedupe side effects.
- **Abandoned-task inspection** `[Hardening]` — a command lists `processing` rows
  older than a threshold and can mark them `abandoned` for human review. **No
  auto-requeue** (respects "no reprocessing").
- **Manual inspection** `[Required-ish]` — `failed`/`abandoned` rows retained with
  bounded error info.

**Net guarantee statement (for README):** *At-most-once processing. A task is claimed
by exactly one worker at a time and never auto-reprocessed after success or failure.
Crash-after-side-effect-before-commit can leave a task in `processing`; such tasks are
surfaced for manual inspection, not silently retried.*

---

## 5. High-Level Architecture

```
+-------------+        add_task()         +------------------+
|  Producer   | ------------------------> |                  |
|  CLI        |                           |   PostgreSQL     |
+-------------+                           |   tasks table    |
                                          |  (status FSM)    |
+-------------+   get_task()/mark_*()     |                  |
|  Consumer   | <-----------------------> |                  |
|  CLI (xN)   |                           +------------------+
+-------------+
      |
      v  dispatch by topic
+-----------------------------+
| Typed handlers              |
|  predict_voice              |
|  raise_voice_alert          |
+-----------------------------+
```

Layering (dependencies point downward only):

```
CLIs (producer / consumer / admin)
  -> Service (add_task, get_task, mark_*, inspection)
    -> Repository (SQLAlchemy queries, claim SQL)
      -> Persistence models / Session factory
Domain types + Pydantic payloads + Topic registry   (shared, no DB deps)
Config + Logging + Observability                     (cross-cutting)
```

---

## 6. Task Lifecycle and State Machine

States: `pending → processing → completed | failed`, plus `processing → abandoned`
`[Hardening]`.

```
            add_task
              |
              v
          [pending] --claim(get_task)--> [processing] --success--> [completed]
                                              |        \--failure--> [failed]
                                              \--stale (admin)-----> [abandoned]
```

Valid transitions:
- `pending → processing` (only via `get_task`, atomic, sets `claimed_at`, `worker_id`)
- `processing → completed` (only via `mark_task_completed`, requires current=`processing`)
- `processing → failed` (only via `mark_task_failed`, requires current=`processing`)
- `processing → abandoned` (admin reaper, requires current=`processing` + age threshold)

Invalid (must be rejected by app + ideally DB):
- any transition out of a terminal state (`completed`/`failed`/`abandoned`)
- `pending → completed/failed` directly (must go through `processing`)
- re-claiming a non-`pending` row

Enforcement: app-level guards in service (update `... WHERE id=:id AND status='processing'`
and assert rowcount==1) + DB `CHECK`/trigger as `[Hardening]`.

---

## 7. Database Schema

Single table `tasks`.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | default `gen_random_uuid()` (pgcrypto) |
| `topic` | `task_topic` enum (or `TEXT`+CHECK) | indexed |
| `payload` | `JSONB` NOT NULL | validated by Pydantic before insert |
| `status` | `task_status` enum | default `pending`, indexed |
| `idempotency_key` | `TEXT` NULL | UNIQUE (nullable) |
| `worker_id` | `TEXT` NULL | set on claim |
| `created_at` | `TIMESTAMPTZ` NOT NULL | default `now()` |
| `updated_at` | `TIMESTAMPTZ` NOT NULL | maintained on every update |
| `claimed_at` | `TIMESTAMPTZ` NULL | set on claim |
| `completed_at` | `TIMESTAMPTZ` NULL | set on complete |
| `failed_at` | `TIMESTAMPTZ` NULL | set on fail |
| `error_type` | `TEXT` NULL | bounded (e.g. 255) |
| `error_message` | `TEXT` NULL | bounded/truncated (e.g. 2KB) |
| `error_details` | `JSONB` NULL | bounded, sanitized |
| `processing_duration_ms` | `INTEGER` NULL | set on terminal transition |

Enums:
- `task_status`: `pending | processing | completed | failed | abandoned`
- `task_topic`: `predict_voice | raise_voice_alert`
  - Decision: use a **native PG enum** for `status` (small, stable set) and **PG enum
    or TEXT+CHECK** for `topic`. TEXT+CHECK for `topic` is slightly easier to extend
    via migration; enum is stricter. Plan picks **PG enum for both** for strictness,
    accepting that adding a topic needs a migration (acceptable, it needs a handler
    anyway).

Indexes / constraints:
- **Partial index for claiming** `[Required]`:
  `CREATE INDEX ix_tasks_pending ON tasks (topic, created_at) WHERE status = 'pending';`
  Keeps the claim query fast and the index small (only pending rows).
- `UNIQUE (idempotency_key)` (partial, `WHERE idempotency_key IS NOT NULL`) `[Hardening]`.
- Index on `status` for inspection counts `[Hardening]`.
- CHECK constraints `[Hardening]`:
  - terminal-state timestamp coherence (e.g. `completed → completed_at NOT NULL`),
  - `processing_duration_ms >= 0`,
  - bounded `error_message` length.

App-validated vs DB-protected:
- **App (Pydantic):** payload shape, UUID format, datetime tz-awareness, float ∈ [0,1],
  URL sanity, payload size.
- **DB:** allowed `status`/`topic` values, idempotency uniqueness, NOT NULL,
  state/timestamp coherence, no SQL injection (parameterized).

---

## 8. Concurrency and Transaction Design

### The claim (core)
```sql
-- inside one short transaction
WITH next AS (
  SELECT id
  FROM tasks
  WHERE status = 'pending'
    AND topic = ANY(:topics)
  ORDER BY created_at          -- best-effort, not guaranteed FIFO
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE tasks t
SET status = 'processing',
    worker_id = :worker_id,
    claimed_at = now(),
    updated_at = now()
FROM next
WHERE t.id = next.id
RETURNING t.*;          -- return the claimed row, fully populated
COMMIT;
```
SQLAlchemy 2.x equivalent: `select(Task.id).where(...).with_for_update(skip_locked=True)
.limit(1)` feeding an `update(...).where(...).returning(Task)`, or a CTE via
`select(...).cte()`. Either is parameterized (no injection).

### Transaction boundaries per operation
| Operation | Txn scope | Commit point | Rollback |
|---|---|---|---|
| `add_task` | single INSERT | immediately after insert | on validation/IntegrityError (dup idempotency → handled, not crash) |
| `get_task` (claim) | claim CTE above | **immediately**, before any processing | on error, nothing claimed |
| processing (handler) | **no DB txn / no lock held** | n/a | n/a |
| `mark_task_completed` | single guarded UPDATE | after update | if rowcount≠1 → invalid-transition error |
| `mark_task_failed` | single guarded UPDATE | after update | same |

### Key rules
- **Processing happens with NO row lock held.** The lock lives only for the
  microseconds of the claim transaction. Long `sleep`/work never blocks other workers.
- **No long-running transactions.** Each operation is one short statement/txn.
- **Isolation:** `READ COMMITTED` is sufficient. `SKIP LOCKED` already prevents double
  claim; we do not need `SERIALIZABLE`.
- **Connection pooling:** SQLAlchemy `QueuePool` with `pool_pre_ping=True` (drops dead
  connections), modest `pool_size`/`max_overflow`. `[Hardening]`
- **Connection failure handling:** wrap session use; on `OperationalError` the
  consumer logs, backs off, and retries the *loop* (not the task) — the unclaimed task
  stays `pending`; a partially-processed task that lost its DB connection before
  `mark_*` becomes a stale `processing` row handled by inspection. `[Hardening]`
- **Session scope:** one short-lived session per operation (context-managed), not one
  long session per consumer lifetime.

---

## 9. Type-System Design

Goal: make `add_task("predict_voice", RaiseVoiceAlertPayload(...))` a **static type
error**.

Core constructs:
- `Topic` = `Literal["predict_voice", "raise_voice_alert"]` (or `StrEnum`).
- `TaskStatus` = `StrEnum`.
- Pydantic payload models:
  - `PredictVoicePayload`: `user_id: UUID`, `audio_s3_url: AnyUrl|str` (validated S3-ish).
  - `RaiseVoiceAlertPayload`: `user_id: UUID`, `measured_at: AwareDatetime`,
    `audio_quality: float` and `voice_score: float` as `confloat(ge=0, le=1)`
    (Pydantic `Annotated[float, Field(ge=0, le=1)]`).
- **Typed topic→payload registry**:
  ```python
  TOPIC_PAYLOADS: dict[Topic, type[BaseModel]] = {
      "predict_voice": PredictVoicePayload,
      "raise_voice_alert": RaiseVoiceAlertPayload,
  }
  ```
- **Generic task model**: `Task[PayloadT]` (Pydantic generic) so a claimed task carries
  its concrete payload type.
- **Function overloads** for `add_task` (and the handler dispatch) so each `Topic`
  literal binds to its payload type:
  ```python
  @overload
  def add_task(topic: Literal["predict_voice"], payload: PredictVoicePayload, *, idempotency_key: str | None = ...) -> Task[PredictVoicePayload]: ...
  @overload
  def add_task(topic: Literal["raise_voice_alert"], payload: RaiseVoiceAlertPayload, *, idempotency_key: str | None = ...) -> Task[RaiseVoiceAlertPayload]: ...
  ```

Guarantee layers:
- **Static (mypy/pyright strict):** topic↔payload match, exhaustive handler dispatch
  (via `assert_never`), no `Any` leaks across public contracts.
- **Runtime (Pydantic):** value validation — UUID, tz-aware datetime, float ∈ [0,1],
  URL, payload size; raises on bad data before DB.
- **DB (Postgres):** allowed enum values, uniqueness, NOT NULL, coherence checks.

---

## 10. Application Layers

1. **Domain types** (`Topic`, `TaskStatus`, `Task[PayloadT]`) — pure, no DB. Must not
   import SQLAlchemy.
2. **Pydantic payloads** — validation only. Must not know about persistence.
3. **Persistence models** (SQLAlchemy `Task` ORM) — table mapping only. No business
   rules.
4. **Repository** — all SQL incl. the claim CTE and guarded updates. Returns ORM rows.
   Must not contain business policy or logging of payloads.
5. **Service** (`add_task`, `get_task`, `mark_*`, inspection) — orchestrates
   validation + repository + mapping ORM↔domain; owns transaction boundaries. Public,
   typed API. Must not do topic *processing*.
6. **Handlers** — topic-specific simulated work. Pure-ish, idempotent. Must not touch
   the DB queue directly (no status writes); they only do the work and return/raise.
7. **Producer CLI** — generates sample tasks via `add_task`.
8. **Consumer CLI** — loop: claim → dispatch → mark. Owns worker_id + signal handling.
9. **Config & DI** — settings (env), engine/session factory, logging setup.
10. **Observability** — structured logging, optional metrics.
11. **Tests** — unit / integration / concurrency / e2e.

---

## 11. Proposed Project Structure

```
backend/
  pyproject.toml                # deps pinned, ruff + mypy/pyright + pytest config
  README.md
  Dockerfile
  docker-compose.yml
  .env.example
  alembic.ini
  migrations/
    env.py
    versions/
      0001_create_tasks.py
  src/taskpool/
    __init__.py
    config.py                   # Settings (pydantic-settings), DSN, pool config
    logging.py                  # structured logging setup
    db.py                       # engine, session factory, session contextmanager
    domain/
      __init__.py
      topics.py                 # Topic literal/enum, TaskStatus enum
      task.py                   # generic Task[PayloadT] domain model
    payloads/
      __init__.py
      predict_voice.py          # PredictVoicePayload
      raise_voice_alert.py      # RaiseVoiceAlertPayload
      registry.py               # TOPIC_PAYLOADS, parse/validate helpers
    persistence/
      __init__.py
      models.py                 # SQLAlchemy Task ORM, enums
    repository.py               # TaskRepository (claim CTE, guarded updates)
    service.py                  # add_task, get_task, mark_*, inspection (public API)
    handlers/
      __init__.py
      base.py                   # Handler protocol / typed dispatch table
      predict_voice.py
      raise_voice_alert.py
    cli/
      __init__.py
      producer.py               # sample task generation
      consumer.py               # worker loop + signals
      admin.py                  # inspect / reap abandoned  [Hardening]
    observability.py            # log fields, optional metric counters
  tests/
    conftest.py                 # pg fixtures (testcontainers or compose), session
    unit/
      test_payloads.py
      test_registry_and_overloads.py
      test_state_transitions.py
      test_error_serialization.py
      test_handler_routing.py
    integration/
      test_repository.py        # real Postgres
    concurrency/
      test_skip_locked.py       # many tasks, N workers, uniqueness
    e2e/
      test_producer_consumer.py
```

---

## 12. Public Function Contracts

```python
# service.py  (all overloaded per topic; shown condensed)

def add_task(topic, payload, *, idempotency_key: str | None = None) -> Task[PayloadT]:
    """Validate payload -> serialize JSONB -> INSERT status=pending -> return Task.
    Duplicate idempotency_key: return existing task (or raise DuplicateTask), never crash."""

def get_task(topics: Sequence[Topic], worker_id: str) -> Task[Any] | None:
    """Atomically claim one pending task in `topics` via FOR UPDATE SKIP LOCKED,
    set processing/claimed_at/worker_id, COMMIT, return typed Task. None if empty."""

def mark_task_completed(task_id: UUID, *, duration_ms: int | None = None) -> Task[Any]:
    """Guarded UPDATE WHERE status='processing'. Raise InvalidTransition if rowcount!=1."""

def mark_task_failed(task_id: UUID, *, error_type: str, error_message: str,
                     error_details: dict | None = None, duration_ms: int | None = None) -> Task[Any]:
    """Guarded UPDATE WHERE status='processing'. Truncate/sanitize error fields."""

# inspection / admin  [Hardening]
def get_task_by_id(task_id: UUID) -> Task[Any] | None: ...
def list_stale_processing(older_than: timedelta) -> list[Task[Any]]: ...
def mark_abandoned(task_id: UUID) -> Task[Any]: ...
def counts_by_status() -> dict[TaskStatus, int]: ...
```

Invariants enforced: claim only `pending`; complete/fail only from `processing`;
error fields bounded; all timestamps tz-aware UTC.

---

## 13. Producer Design `[Required]`

CLI `python -m taskpool.cli.producer`:
- Args/env: `--topic {predict_voice,raise_voice_alert,all}`, `--count N`,
  `--seed S` (deterministic data `[Hardening]`), optional `--idempotency-prefix`.
- Generates valid UUIDs, tz-aware `measured_at` (UTC), scores in [0,1].
- Uses the real `add_task(...)` (no direct SQL).
- Logs each created `task_id` + `topic` (structured), not full payloads.
- Exit code reflects success/failure of the batch.

---

## 14. Consumer Design `[Required]`

CLI `python -m taskpool.cli.consumer`:
1. Build unique `worker_id` (`hostname-pid-uuid4`).
2. Read configured topics (env `TASKPOOL_TOPICS`, CLI `--topics`; default all).
3. Loop:
   - `task = get_task(topics, worker_id)`
   - if `None`: sleep `poll_interval` (configurable, jittered `[Hardening]`) and continue.
   - else: dispatch to typed handler by `task.topic` (exhaustive, `assert_never`).
   - on success: `mark_task_completed(task.id, duration_ms=...)`.
   - on exception: `mark_task_failed(...)` with bounded/sanitized error; **continue**
     the loop (one failure never kills the worker).
4. Graceful shutdown: install `SIGTERM`/`SIGINT` handlers that set a stop flag; finish
   the in-flight task (or let it fail), then exit cleanly. No new claims after signal.

Topic routing: a typed dispatch table `dict[Topic, Handler]`; dispatch is total over
the `Topic` union so adding a topic without a handler is a static error.

Decision: **consumers can be configured to support selected topics** (default all).

---

## 15. Handler Design

- A `Handler` protocol: `def handle(payload: PayloadT) -> None` (or returns a small
  result dict for logging).
- `predict_voice`: validate/normalize `audio_s3_url`, `sleep` to simulate download +
  inference, log a simulated score. No real network. Idempotent by `user_id`.
- `raise_voice_alert`: evaluate `voice_score`/`audio_quality`, `sleep`, log a simulated
  alert decision. Idempotent.
- Handlers raise on failure (caught by consumer → `mark_task_failed`). Handlers never
  write task status themselves.

---

## 16. Configuration Strategy

`pydantic-settings` `Settings` from env (12-factor):
- `DATABASE_URL` (or discrete `POSTGRES_*`), `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`,
  `DB_POOL_PRE_PING`.
- `TASKPOOL_TOPICS`, `POLL_INTERVAL_SECONDS`, `CLAIM_BATCH_SIZE` (default 1).
- `LOG_LEVEL`, `LOG_FORMAT` (json|console).
- `ABANDONED_THRESHOLD_SECONDS` `[Hardening]`.
No secrets in code/repo; `.env.example` documents all keys with safe defaults.

---

## 17. Docker and Docker Compose Strategy

**Dockerfile** `[Required]`:
- Base `python:3.12-slim`, multi-stage (builder installs pinned deps into venv;
  runtime copies venv).
- Non-root user `[Hardening/Required-ish]`.
- Reproducible install (locked deps; `pip install --no-cache-dir` from a lockfile or
  pinned `pyproject`).
- Single image; entrypoint chooses producer/consumer/migrate/admin via command.

**docker-compose.yml**:
- `db`: postgres:16 with healthcheck (`pg_isready`), volume, least-priv app user
  `[Hardening]`.
- `migrate`: one-shot `alembic upgrade head`, `depends_on: db (service_healthy)`.
- `producer`: one-shot, `depends_on: migrate`.
- `consumer`: long-running, `depends_on: migrate`, **scalable** via
  `docker compose up --scale consumer=N`.
- `.env` for config; no committed secrets.

README demo commands:
```
docker compose up -d db
docker compose run --rm migrate
docker compose run --rm producer --topic all --count 50
docker compose up --scale consumer=4 consumer
docker compose run --rm admin counts          # inspect
pytest ; ruff check . ; mypy src   (or pyright)
```
The `--scale consumer=4` line demonstrates the concurrency acceptance criterion.

---

## 18. Migration Strategy (Alembic)

- **No app-startup schema creation** (`Base.metadata.create_all` forbidden in app).
- `0001_create_tasks`:
  - create extensions (`pgcrypto` for `gen_random_uuid`),
  - create enum types (`task_status`, `task_topic`),
  - create `tasks` table,
  - create partial pending index, idempotency unique index, status index,
  - CHECK constraints `[Hardening]`.
- **Downgrade**: drop indexes → table → enum types → (leave extension).
- Migrations run via the one-shot `migrate` service / `alembic upgrade head`.

---

## 19. Logging and Observability

Structured logs (JSON in prod) with fields: `task_id`, `topic`, `worker_id`,
`status`, `duration_ms`, `error_type`, plus `event` (claimed/completed/failed/empty).
- **No full sensitive payloads** by default (log topic + ids + maybe a hash).
- Error logs carry bounded `error_message`/`error_type` only.

Metrics `[Optional]` (counters/gauges, e.g. Prometheus client):
- pending / processing / completed / failed / abandoned counts,
- task processing duration histogram, claim latency,
- consumer liveness, stale-processing gauge.

---

## 20. Security and Reliability

- Secrets via env only; `.env` git-ignored; `.env.example` committed.
- Least-privilege Postgres app role (DML on `tasks`, no DDL) `[Hardening]`.
- Input validation (Pydantic) on all payloads; bounded payload + error sizes.
- Safe S3 URL handling (scheme/host validation, no SSRF since we don't fetch).
- Parameterized SQL / SQLAlchemy everywhere (no string interpolation).
- Non-root containers, pinned deps, graceful shutdown, UTC tz-aware timestamps.
- `pool_pre_ping` + reconnect/backoff on transient DB errors.

---

## 21. Testing Strategy

### Unit `[Required]`
- Payload validation: bad UUID, non-aware datetime, scores `< 0` / `> 1`, bad URL.
- Topic↔payload mismatch (both runtime Pydantic and a typing test via `reveal_type` /
  a mypy "expect-error" check).
- Handler routing exhaustiveness.
- State-transition validation (guards reject illegal transitions).
- Error serialization/truncation.

### Repository integration (real Postgres, NOT SQLite) `[Required]`
- create / claim / complete / fail,
- `failed` and `completed` tasks not returned by `get_task`,
- unsupported topic rejected,
- duplicate idempotency key handled,
- transaction rollback on error,
- invalid state transitions rejected at repo level.
- Fixtures via testcontainers-python *or* the compose `db`; truncate between tests.

### Concurrency `[Required]`
- Insert many tasks; start N worker threads/processes each with its own session.
- Assert: every claimed id unique; no id claimed twice; all tasks end
  `completed|failed`; none left unintentionally `pending`; workers make progress
  (no deadlock); `SKIP LOCKED` lets workers grab different rows.
- **Determinism for CI:** fixed task count, bounded handler `sleep`, barrier to start
  workers together, overall timeout, assert on aggregate invariants (set equality of
  claimed ids) rather than timing.

### End-to-end `[Required]`
- Run real producer then real consumer(s) against Postgres; assert final counts.

---

## 22. CI Pipeline

GitHub Actions (or similar), services: postgres:16. Stages:
1. Install pinned deps.
2. `ruff format --check`.
3. `ruff check`.
4. Strict type check (`mypy --strict src` or `pyright`).
5. Unit tests.
6. Postgres integration tests.
7. Concurrency tests (bounded, deterministic).
8. Docker image build.
Fail-fast per stage; cache deps.

---

## 23. README Structure (to be written during implementation)

Purpose · Architecture overview · Task lifecycle · Concurrency explanation ·
At-most-once guarantee + limitations · Tech choices · Env vars · Setup · Migrations ·
Producer usage · Consumer usage · Multiple-consumer (scale) usage · Testing · Linting ·
Type checking · Failure inspection · Known trade-offs · Future improvements.

---

## 24. Step-by-Step Implementation Phases

> Each phase: Goal · Tasks · Files · Tests · Completion criteria · Dependencies.

**Phase 1 — Project skeleton & tooling** ✅ *Done*
- Goal: compiling, lint/type/test harness green on empty code.
- Tasks: `pyproject` (deps pinned), ruff/mypy/pytest config, package layout, logging,
  config.
- Files: `pyproject.toml`, `src/taskpool/{config,logging,__init__}.py`.
- Tests: trivial smoke test; CI runs ruff+mypy.
- Done: `ruff`, type checker, `pytest` all pass on skeleton.
- Deps: none.

**Phase 2 — Domain types, payloads, registry** ✅ *Done*
- Goal: typed topic→payload model with overloads.
- Tasks: `Topic`, `TaskStatus`, payloads, `Task[PayloadT]`, `TOPIC_PAYLOADS`.
- Files: `domain/*`, `payloads/*`.
- Tests: unit payload validation + typing/mismatch tests.
- Done: invalid payloads rejected; mismatch is a static error.
- Deps: P1.

**Phase 3 — Persistence + migrations** ✅ *Done* (migration test pending)
- Goal: `tasks` table via Alembic.
- Tasks: ORM model, enums, `0001` migration, indexes/constraints, `db.py` session.
- Files: `persistence/models.py`, `migrations/*`, `db.py`.
- Tests: migration up/down on real PG.
- Done: schema created by migration only; no startup DDL.
- Deps: P1–P2.

**Phase 4 — Repository (claim SQL + guards)** ✅ *Done*
- Goal: atomic claim + guarded updates.
- Tasks: `TaskRepository`: insert, claim CTE (`FOR UPDATE SKIP LOCKED`), complete/fail,
  inspection queries.
- Files: `repository.py`.
- Tests: integration (create/claim/complete/fail, exclusions, rollback, transitions).
- Done: integration tests green on real PG.
- Deps: P3.

**Phase 5 — Service (public API)** ✅ *Done*
- Goal: typed `add_task/get_task/mark_*` + idempotency.
- Tasks: validation, txn boundaries, ORM↔domain mapping, overloads, idempotency
  handling.
- Files: `service.py`.
- Tests: unit (transitions, idempotency) + integration.
- Done: public contracts behave per §12.
- Deps: P4.

**Phase 6 — Handlers + dispatch** ✅ *Done*
- Goal: typed topic handlers + exhaustive routing.
- Files: `handlers/*`.
- Tests: routing + handler unit tests.
- Done: `assert_never` exhaustiveness; handlers idempotent.
- Deps: P2, P5.

**Phase 7 — Producer & Consumer CLIs** ✅ *Done*
- Goal: runnable producer + worker loop with signals.
- Files: `cli/producer.py`, `cli/consumer.py`.
- Tests: e2e producer→consumer.
- Done: README demo flow works locally.
- Deps: P5–P6.

**Phase 8 — Concurrency tests** ✅ *Written* (PG verification pending)
- Goal: prove no double-claim under load.
- Files: `tests/concurrency/*`.
- Done: invariants hold deterministically in CI.
- Deps: P7.

**Phase 9 — Docker/Compose + admin/inspection** ✅ *Done* (manual verification pending)
- Goal: containerized, scalable consumers, inspection.
- Files: `Dockerfile`, `docker-compose.yml`, `cli/admin.py`.
- Done: `--scale consumer=N` demo; counts/abandoned inspection.
- Deps: P7.

**Phase 10 — CI + README + hardening** ✅ *Done*
- Goal: green pipeline + docs + `[Hardening]` items (abandoned reaper, metrics).
- Done: README, CI workflow, 50 PG-backed tests green, migration up/down test, `reviewer-demo.sh` verified.
- Deps: all.

---

## 25. Acceptance-Criteria Traceability Matrix

| Requirement | Planned implementation | Verification | Relevant test | Status |
|---|---|---|---|---|
| Multiple producers concurrent | stateless `add_task`, single INSERT | integration + e2e | `e2e/test_producer_consumer.py` | ✅ |
| Multiple consumers concurrent | worker processes + claim CTE | concurrency test | `concurrency/test_skip_locked.py` | ✅ |
| Multiple topics | `Topic` enum + registry + handlers | unit | `unit/test_registry.py` | ✅ |
| Never claimed/processed twice | `FOR UPDATE SKIP LOCKED` + state guards | concurrency + integration | `concurrency/test_skip_locked.py`, `integration/test_service.py` | ✅ |
| Completed retained | terminal `completed` status | integration | `integration/test_service.py` | ✅ |
| Failed retained | terminal `failed` status + error fields | integration | `integration/test_service.py` | ✅ |
| Failed not reprocessed | `get_task` filters `status='pending'` | integration | `integration/test_service.py` | ✅ |
| No FIFO required | `ORDER BY created_at` best-effort + `SKIP LOCKED` | concurrency | `concurrency/test_skip_locked.py` | ✅ |
| Works across containers | Compose `--scale` | e2e/manual + concurrency | `concurrency/*` + `reviewer-demo.sh` | ✅ |
| Typed `add_task`/`get_task` | overloads + generics + strict checker | type check + unit | CI mypy + `tests/typing/test_static_contracts.py` | ✅ |
| Topic/payload mismatch prevented | overloads + Pydantic | static + runtime | `unit/test_payloads.py`, `tests/typing/test_static_contracts.py` | ✅ |
| Scores ∈ [0,1] | constrained floats | unit | `unit/test_payloads.py` | ✅ |
| UUID / tz-aware datetime | Pydantic `UUID`/`AwareDatetime` | unit | `unit/test_payloads.py` | ✅ |
| Error info bounded/sanitized | truncation in `mark_task_failed` | unit | `integration/test_service.py::test_error_message_truncated` | ✅ |
| Graceful shutdown | SIGTERM/SIGINT handlers | manual/e2e | consumer e2e / manual | ⏳ code done; no automated SIGTERM test |
| Migrations only (no startup DDL) | Alembic `0001`, no `create_all` | migration test | `integration/test_migrations.py` | ✅ |
| README docs | §23 | review | n/a | ✅ |

---

## 26. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Crash after side effect, before commit | task stuck `processing`, effect done | at-most-once stance; abandoned inspection; idempotent handlers `[Hardening]` |
| Flaky concurrency test in CI | false failures | bounded sleeps, start barrier, aggregate invariants, timeout |
| Using SQLite for lock tests | wrong semantics | mandate real Postgres in integration/concurrency |
| Long txn holding lock during processing | throughput collapse | commit claim before processing; no lock during work |
| Enum topic extension friction | migration needed per topic | accepted (handler needed anyway); document |
| Connection drops | worker crash/lost work | `pool_pre_ping`, reconnect/backoff, loop-level retry |
| Oversized payload / error blobs | DB bloat | bounded sizes in app + CHECK `[Hardening]` |
| Idempotency race on duplicate key | insert error | UNIQUE constraint + handle IntegrityError gracefully |

---

## 27. Final Definition of Done

| Criterion | Status |
|---|---|
| `add_task` / `get_task` reusable, fully typed, strict mypy | ✅ Done |
| Producer and consumer CLIs for both topics | ✅ Done |
| Multiple consumers, zero double-claims (concurrency test) | ✅ Done (PG verified 2026-06-30) |
| Completed/failed retained; no auto-reprocess | ✅ Done (integration tests green) |
| Schema via Alembic only; up/down work | ✅ Done (`test_migrations.py`) |
| Structured logging; no sensitive payloads logged | ✅ Done |
| CI green (ruff, mypy, unit + PG tests, Docker build) | ✅ Done (`.github/workflows/ci.yml`) |
| README per §23 | ✅ Done |
| `[Required]` complete; `[Hardening]` where time allows | ✅ Core complete; optional hardening remains |

**Optional hardening (not required for submission):**

- Prometheus metrics, least-privilege Postgres role, DB payload size CHECK.
- Isolated `test_repository.py`; automated SIGTERM shutdown test.

**Verified locally (2026-06-30):**

- `SUITE=all ./scripts/run-tests.sh` → 50 passed (ruff, mypy, unit, integration, concurrency, e2e, migrations).
- `CLEAN_ALL=1 CONSUMERS=4 TASKS=20 ./scripts/reviewer-demo.sh` → `completed: 20`, `pending: 0`.
