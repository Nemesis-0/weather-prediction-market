#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
    source ".venv/bin/activate"
fi

mkdir -p logs

python -m src.market.collector \
    >> logs/market_collector.log \
    2>&1
