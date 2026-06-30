#!/usr/bin/env bash
# Run tests and quality checks in one command.
#
# Usage (from repo root):
#   ./scripts/run-tests.sh                    # unit tests + lint (fast, no DB)
#   SUITE=all ./scripts/run-tests.sh          # full suite (needs Postgres in Docker)
#
# Options (env vars):
#   SUITE=unit|lint|fast|all   what to run (default: fast = unit + lint)
#   COMPOSE=docker-compose       override compose command
#   POSTGRES_HOST_PORT=5433      host port for Postgres (default 5433)
#   VENV=.venv                   virtualenv path (default: .venv)
#   STOP_STACK=1                 run "docker-compose down" before DB tests (avoids flaky runs)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE="${COMPOSE:-docker-compose}"
SUITE="${SUITE:-fast}"
POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-5433}"
TEST_DATABASE_URL="${TASKPOOL_TEST_DATABASE_URL:-postgresql+psycopg://taskpool:taskpool@localhost:${POSTGRES_HOST_PORT}/taskpool}"
VENV="${VENV:-$ROOT/.venv}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found." >&2
  exit 1
fi

step() {
  echo ""
  echo "==> $*"
}

step "Task Pool — run tests"
echo "    suite=$SUITE  db=localhost:${POSTGRES_HOST_PORT}"

if [[ ! -d "$VENV" ]]; then
  step "Create virtualenv at $VENV"
  python3 -m venv "$VENV"
fi

step "Activate virtualenv and install package"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q -e ".[dev]"

run_lint() {
  step "ruff check"
  ruff check .
  step "ruff format --check"
  ruff format --check .
  step "mypy"
  mypy src tests
}

run_unit() {
  step "pytest unit tests (no database)"
  pytest tests/unit -v
}

ensure_db() {
  if ! command -v "$COMPOSE" >/dev/null 2>&1; then
    echo "Error: '$COMPOSE' not found. Install docker-compose for SUITE=$SUITE." >&2
    exit 1
  fi

  if [[ "${STOP_STACK:-0}" == "1" ]]; then
    step "Stop running compose stack (avoids test interference)"
    $COMPOSE down
  fi

  step "Start PostgreSQL (Docker)"
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

  export TASKPOOL_TEST_DATABASE_URL="$TEST_DATABASE_URL"
  export DATABASE_URL="$TEST_DATABASE_URL"
  export LOG_FORMAT="${LOG_FORMAT:-console}"
}

run_db_tests() {
  ensure_db
  step "pytest full suite (integration + concurrency + e2e)"
  pytest -v
}

case "$SUITE" in
  unit)
    run_unit
    ;;
  lint)
    run_lint
    ;;
  fast)
    run_lint
    run_unit
    ;;
  all)
    run_lint
    run_unit
    run_db_tests
    ;;
  db)
    run_db_tests
    ;;
  *)
    echo "Error: unknown SUITE='$SUITE' (use unit|lint|fast|db|all)" >&2
    exit 1
    ;;
esac

step "Done"
