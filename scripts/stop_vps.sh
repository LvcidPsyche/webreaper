#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="$HOME/.webreaper/runtime"
for svc in web api; do
  pid_file="$RUNTIME_DIR/pids/$svc.pid"
  if [[ -f "$pid_file" ]]; then
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
      echo "stopped $svc ($pid)"
    fi
    rm -f "$pid_file"
  fi
done

