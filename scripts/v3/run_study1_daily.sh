#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <duration-hours> <rotation-index>" >&2
  exit 2
fi
HOURS="$1"
ROTATION="$2"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "ERROR: activate the repo .venv first: source .venv/bin/activate" >&2
  exit 1
fi
exec caffeinate -dimsu python scripts/v3/run_study1_shakedown.py \
  --base-url https://localhost:5001/v1/api \
  --duration-hours "$HOURS" \
  --rotation-index "$ROTATION" \
  --cadence-seconds 30 \
  --batch-size 8 \
  --max-markets 24 \
  --contracts-per-market 8 \
  --rotation-modulus 3
