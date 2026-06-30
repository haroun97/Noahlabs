"""Concurrency test: prove no task is ever claimed by two workers.

Determinism for CI: a fixed task count, a thread barrier so workers start
together, bounded work, and assertions on *aggregate invariants* (set equality
of claimed ids) rather than timing.
"""

from __future__ import annotations

import threading
from collections import Counter
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from taskpool.domain.topics import TaskStatus, Topic
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.service import add_task, counts_by_status, get_task, mark_task_completed

pytestmark = pytest.mark.concurrency

NUM_TASKS = 60
NUM_WORKERS = 8


def _seed_tasks(n: int) -> set[UUID]:
    ids: set[UUID] = set()
    for _ in range(n):
        task = add_task(
            Topic.PREDICT_VOICE,
            PredictVoicePayload(user_id=uuid4(), audio_s3_url="s3://b/k.wav"),
        )
        ids.add(task.id)
    return ids


def test_no_double_claim_under_load(clean_db: Engine) -> None:
    expected_ids = _seed_tasks(NUM_TASKS)

    claimed_by_worker: dict[str, list[UUID]] = {}
    lock = threading.Lock()
    barrier = threading.Barrier(NUM_WORKERS)

    def worker(worker_id: str) -> None:
        barrier.wait()  # start everyone at once to maximise contention
        local: list[UUID] = []
        while True:
            task = get_task([Topic.PREDICT_VOICE], worker_id)
            if task is None:
                break
            local.append(task.id)
            # Minimal work; the claim already committed before this point.
            mark_task_completed(task.id)
        with lock:
            claimed_by_worker[worker_id] = local

    threads = [
        threading.Thread(target=worker, args=(f"w-{i}",), name=f"w-{i}") for i in range(NUM_WORKERS)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
        assert not thread.is_alive(), "worker thread did not finish (possible deadlock)"

    all_claimed = [task_id for ids in claimed_by_worker.values() for task_id in ids]

    # 1. No id claimed more than once.
    duplicates = [tid for tid, c in Counter(all_claimed).items() if c > 1]
    assert duplicates == [], f"tasks claimed more than once: {duplicates}"

    # 2. Every task was claimed exactly once (set equality).
    assert set(all_claimed) == expected_ids
    assert len(all_claimed) == NUM_TASKS

    # 3. Work was actually shared (SKIP LOCKED let workers grab different rows).
    workers_that_did_work = [w for w, ids in claimed_by_worker.items() if ids]
    assert len(workers_that_did_work) > 1

    # 4. No task left pending; all completed.
    counts = counts_by_status()
    assert counts[TaskStatus.PENDING] == 0
    assert counts[TaskStatus.PROCESSING] == 0
    assert counts[TaskStatus.COMPLETED] == NUM_TASKS
