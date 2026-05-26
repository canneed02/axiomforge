#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -s tests

if find . \
  -path './.git' -prune -o \
  -path './.venv' -prune -o \
  -path './state' -prune -o \
  -name '.env' -print | grep -q .; then
  echo "hygiene failed: .env file present" >&2
  exit 1
fi

if grep -R -E '(n[v]api-|s[k]-[A-Za-z0-9]{20,})' \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=__pycache__ \
  --exclude-dir=state \
  . >/dev/null; then
  echo "secret scan failed" >&2
  exit 1
fi

echo "ci_hygiene=ok"
