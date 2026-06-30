#!/usr/bin/env bash
# Push to GitHub using GITHUB_TOKEN from .env (token is not saved in git config).
#
# Create .env at repo root with:
#   GITHUB_TOKEN=ghp_...
#   GITHUB_USERNAME=haroun97   # optional
#   GITHUB_REPO=Noahlabs       # optional
#
# Usage: ./scripts/push-github.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Error: .env not found. Create .env with GITHUB_TOKEN=your_pat" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "Error: GITHUB_TOKEN is empty in .env" >&2
  exit 1
fi

GITHUB_USERNAME="${GITHUB_USERNAME:-haroun97}"
GITHUB_REPO="${GITHUB_REPO:-Noahlabs}"
BRANCH="${GITHUB_BRANCH:-main}"

PUSH_URL="https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/${GITHUB_USERNAME}/${GITHUB_REPO}.git"

echo "==> Pushing to github.com/${GITHUB_USERNAME}/${GITHUB_REPO}.git (${BRANCH})"

# One-off URL only — token is not written to git config / .git/config.
GIT_TERMINAL_PROMPT=0 git push "$PUSH_URL" "HEAD:${BRANCH}"

echo "==> Done"
