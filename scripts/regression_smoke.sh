#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[1/3] Backend regression tests"
./.venv/bin/pytest -q tests/test_stream_routes.py tests/test_chat_ws.py tests/test_proxy_routes.py tests/test_repeater_routes.py tests/test_intruder_routes.py

echo "[2/3] Full backend suite"
./.venv/bin/pytest -q tests

echo "[3/3] Frontend typecheck"
cd web
npx vitest run
npx tsc --noEmit

echo "Regression smoke complete"
