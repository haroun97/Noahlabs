#!/usr/bin/env bash
# Dispatch container role based on the first argument, or TASKPOOL_ROLE from compose.
#
# docker-compose run REPLACES the service command with anything you pass after the
# service name. Example:
#   docker-compose run producer --topic all --count 20
# sends ONLY ["--topic", "all", "--count", "20"] to the entrypoint — not "producer".
# So we fall back to TASKPOOL_ROLE (set per service in docker-compose.yml).
#
#   migrate            -> alembic upgrade head
#   producer [args]    -> producer CLI
#   consumer [args]    -> consumer CLI
#   admin [args]       -> admin CLI
set -euo pipefail

default_role="${TASKPOOL_ROLE:-consumer}"

case "${1:-}" in
  migrate|producer|consumer|admin)
    role="$1"
    shift
    ;;
  *)
    role="$default_role"
    ;;
esac

case "${role}" in
  migrate)
    exec alembic upgrade head
    ;;
  producer)
    exec python -m taskpool.cli.producer "$@"
    ;;
  consumer)
    exec python -m taskpool.cli.consumer "$@"
    ;;
  admin)
    exec python -m taskpool.cli.admin "$@"
    ;;
  *)
    exec "${role}" "$@"
    ;;
esac
