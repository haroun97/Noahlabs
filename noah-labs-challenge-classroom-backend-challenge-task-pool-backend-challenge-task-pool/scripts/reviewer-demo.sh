#!/usr/bin/env bash
# One-shot demo for reviewers: build, migrate, produce tasks, run workers, show counts.
#
# Usage (from repo root):
#   CLEAN_ALL=1 CONSUMERS=4 TASKS=20 ./scripts/reviewer-demo.sh   # recommended (fresh start)
#   ./scripts/reviewer-demo.sh
#
# Options (env vars):
#   CONSUMERS=4     how many parallel workers (default 4)
#   TASKS=20        how many tasks to create (default 20)
#   CLEAN=1         run "docker-compose down" before start (keeps DB volume)
#   CLEAN_ALL=1     run "docker-compose down -v" (wipes database — fresh start)
#   COMPOSE=docker-compose   override compose command
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE="${COMPOSE:-docker-compose}"
CONSUMERS="${CONSUMERS:-4}"
TASKS="${TASKS:-20}"

if ! command -v "$COMPOSE" >/dev/null 2>&1; then
  echo "Error: '$COMPOSE' not found. Install docker-compose (hyphen form)." >&2
  exit 1
fi

step() {
  echo ""
  echo "==> $*"
}

step "Task Pool — reviewer demo"
echo "    workers=$CONSUMERS  tasks=$TASKS"

if [[ ! -f .env ]]; then
  step "Create .env from .env.example"
  cp .env.example .env
fi

if [[ "${CLEAN_ALL:-0}" == "1" ]]; then
  step "Clean all (remove containers + database volume)"
  $COMPOSE down -v
elif [[ "${CLEAN:-0}" == "1" ]]; then
  step "Clean containers (keep database volume)"
  $COMPOSE down
fi

step "Build images"
$COMPOSE build

step "Start PostgreSQL"
$COMPOSE up -d db

step "Wait until database is healthy"
for _ in $(seq 1 60); do
  if $COMPOSE exec -T db pg_isready -U "${POSTGRES_USER:-taskpool}" -d "${POSTGRES_DB:-taskpool}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! $COMPOSE exec -T db pg_isready -U "${POSTGRES_USER:-taskpool}" -d "${POSTGRES_DB:-taskpool}" >/dev/null 2>&1; then
  echo "Error: database did not become healthy in time." >&2
  exit 1
fi

step "Run migrations"
$COMPOSE run --rm migrate

step "Produce $TASKS sample tasks"
$COMPOSE run --rm producer --topic all --count "$TASKS"

step "Run $CONSUMERS consumers in parallel"
pids=()
for i in $(seq 1 "$CONSUMERS"); do
  $COMPOSE run --rm consumer --max-tasks "$TASKS" &
  pids+=("$!")
done

failed=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    failed=1
  fi
done
if [[ "$failed" -ne 0 ]]; then
  echo "Warning: one or more consumers exited with an error." >&2
fi

step "Final task counts"
$COMPOSE run --rm admin counts

step "Done"
echo "    Database still running on port ${POSTGRES_HOST_PORT:-5433}."
echo "    Stop with: $COMPOSE down"
