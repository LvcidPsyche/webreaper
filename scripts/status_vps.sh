#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="$HOME/.webreaper/runtime"
for svc in api web; do
  pid_file="$RUNTIME_DIR/pids/$svc.pid"
  if [[ -f "$pid_file" ]]; then
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "$svc: running (pid=$pid)"
    else
      echo "$svc: stale pid file ($pid)"
    fi
  else
    echo "$svc: not running"
  fi
done

echo
curl -sS http://127.0.0.1:8000/health || true
echo

