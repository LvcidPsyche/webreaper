#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV="$ROOT_DIR/.venv"
RUNTIME_DIR="$HOME/.webreaper/runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_DIR="$RUNTIME_DIR/pids"
mkdir -p "$LOG_DIR" "$PID_DIR" "$HOME/.webreaper"

PUBLIC_HOST="${PUBLIC_HOST:-$(hostname -I | awk '{print $1}')}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
WEB_HOST="${WEB_HOST:-0.0.0.0}"
WEB_PORT="${WEB_PORT:-4001}"
DB_PATH="${DB_PATH:-$HOME/.webreaper/webreaper-prod.db}"
DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///$DB_PATH}"
WEBREAPER_LICENSE_SECRET="${WEBREAPER_LICENSE_SECRET:-wr-dev-secret}"
WEBREAPER_ADMIN="${WEBREAPER_ADMIN:-1}"
WEBREAPER_DISABLE_MIGRATIONS="${WEBREAPER_DISABLE_MIGRATIONS:-1}"
INSTALL_BROWSERS="${INSTALL_BROWSERS:-0}"

API_LOG="$LOG_DIR/api.log"
WEB_LOG="$LOG_DIR/web.log"
API_PID_FILE="$PID_DIR/api.pid"
WEB_PID_FILE="$PID_DIR/web.pid"

API_URL="http://${PUBLIC_HOST}:${API_PORT}"
WS_URL="ws://${PUBLIC_HOST}:${API_PORT}"
SSE_URL="$API_URL"

echo "== WebReaper VPS Deploy =="
echo "Root:        $ROOT_DIR"
echo "API:         http://${PUBLIC_HOST}:${API_PORT}"
echo "Dashboard:   http://${PUBLIC_HOST}:${WEB_PORT}"
echo "DB:          $DB_PATH"
echo "Admin mode:  $WEBREAPER_ADMIN"
echo

if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/pip" install -q -r requirements.txt

if [[ "$INSTALL_BROWSERS" == "1" ]]; then
  "$VENV/bin/python" -m pip install -q playwright || true
  "$VENV/bin/python" -m playwright install chromium || true
fi

cd "$ROOT_DIR/web"
pnpm install --silent
NEXT_PUBLIC_API_URL="$API_URL" \
NEXT_PUBLIC_WS_URL="$WS_URL" \
NEXT_PUBLIC_SSE_URL="$SSE_URL" \
pnpm build
cd "$ROOT_DIR"

stop_pid_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
      sleep 1
    fi
    rm -f "$file"
  fi
}

listener_pid_for_port() {
  local port="$1"
  ss -ltnp 2>/dev/null | sed -n "s/.*:${port}[[:space:]].*pid=\\([0-9]\\+\\).*/\\1/p" | head -n1
}

stop_pid_file "$WEB_PID_FILE"
stop_pid_file "$API_PID_FILE"

# Replace older ad-hoc launches from this repo if present.
(pgrep -af "$ROOT_DIR/.venv/bin/python -m server.main" || true) | awk '{print $1}' | while read -r pid; do
  [[ -n "$pid" ]] && kill "$pid" || true
done

PYTHONPATH="$ROOT_DIR" \
DATABASE_URL="$DATABASE_URL" \
WEBREAPER_ADMIN="$WEBREAPER_ADMIN" \
WEBREAPER_LICENSE_SECRET="$WEBREAPER_LICENSE_SECRET" \
WEBREAPER_DISABLE_MIGRATIONS="$WEBREAPER_DISABLE_MIGRATIONS" \
nohup "$VENV/bin/python" -c "from server.main import start_server; start_server(host='${API_HOST}', port=${API_PORT})" \
  >"$API_LOG" 2>&1 &
echo $! > "$API_PID_FILE"

sleep 2
if ! curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null; then
  echo "API failed to start. See $API_LOG"
  exit 1
fi
api_real_pid="$(listener_pid_for_port "$API_PORT" || true)"
if [[ -n "${api_real_pid:-}" ]]; then
  echo "$api_real_pid" > "$API_PID_FILE"
fi

cd "$ROOT_DIR/web"
nohup python3 -m http.server "$WEB_PORT" --bind "$WEB_HOST" --directory "$ROOT_DIR/web/out" \
  >"$WEB_LOG" 2>&1 &
echo $! > "$WEB_PID_FILE"
cd "$ROOT_DIR"

sleep 2
if ! curl -fsS "http://127.0.0.1:${WEB_PORT}" >/dev/null; then
  echo "Web UI failed to start. See $WEB_LOG"
  exit 1
fi
web_real_pid="$(listener_pid_for_port "$WEB_PORT" || true)"
if [[ -n "${web_real_pid:-}" ]]; then
  echo "$web_real_pid" > "$WEB_PID_FILE"
fi

echo
echo "✅ WebReaper deployed"
echo "Dashboard: http://${PUBLIC_HOST}:${WEB_PORT}"
echo "API docs:  http://${PUBLIC_HOST}:${API_PORT}/docs"
echo "API log:   $API_LOG"
echo "Web log:   $WEB_LOG"
echo
echo "Note: Running in admin mode (WEBREAPER_ADMIN=1). Set a real secret and disable admin mode for hardened usage."
