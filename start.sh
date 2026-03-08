#!/bin/bash
# WebReaper — local dev startup script
# Usage: ./start.sh
# Remote access: ssh -L 3000:localhost:3000 -L 8000:localhost:8000 user@server

set -e
cd "$(dirname "$0")"

VENV=".venv"
DB_DIR="$HOME/.webreaper"
DB_PATH="$DB_DIR/webreaper.db"

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///$DB_PATH}"
export APP_ENV="${APP_ENV:-development}"

# Anthropic API key — required for AI digest feature
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "[!] Warning: ANTHROPIC_API_KEY not set. AI digest will be disabled."
    echo "    Set it with: export ANTHROPIC_API_KEY=sk-ant-..."
fi

echo "=== WebReaper ==="
echo "DB:   $DATABASE_URL"
echo "ENV:  $APP_ENV"
echo ""

# ---------------------------------------------------------------------------
# Python venv
# ---------------------------------------------------------------------------
if [ ! -d "$VENV" ]; then
    echo "[*] Creating Python virtual environment..."
    python3 -m venv "$VENV"
fi

echo "[*] Installing Python dependencies..."
"$VENV/bin/pip" install -q -r requirements.txt

# Install dev deps if in development mode
if [ "$APP_ENV" = "development" ]; then
    if [ -f "requirements.dev.txt" ]; then
        "$VENV/bin/pip" install -q -r requirements.dev.txt
    fi
fi

# ---------------------------------------------------------------------------
# Playwright browsers (one-time install, ~300MB)
# ---------------------------------------------------------------------------
if [ ! -d "$HOME/.cache/ms-playwright" ]; then
    echo "[*] Installing Playwright browsers (one-time, ~300MB)..."
    "$VENV/bin/playwright" install chromium
fi

# ---------------------------------------------------------------------------
# Database init
# ---------------------------------------------------------------------------
mkdir -p "$DB_DIR"
echo "[*] Initializing database..."
"$VENV/bin/python" -c "
import asyncio, os
os.environ['DATABASE_URL'] = '$DATABASE_URL'
from webreaper.database import DatabaseManager
asyncio.run(DatabaseManager().create_tables())
print('    Database ready.')
"

# Run pending migrations
echo "[*] Running migrations..."
DATABASE_URL="$DATABASE_URL" "$VENV/bin/alembic" upgrade head

# ---------------------------------------------------------------------------
# Node / frontend
# ---------------------------------------------------------------------------
if [ -d "web" ]; then
    if [ ! -d "web/node_modules" ]; then
        echo "[*] Installing frontend dependencies..."
        cd web && pnpm install --silent && cd ..
    fi
else
    echo "[!] Warning: web/ directory not found. Dashboard will not start."
fi

# ---------------------------------------------------------------------------
# Start API server
# ---------------------------------------------------------------------------
echo ""
echo "[*] Starting API server on http://localhost:8000..."
DATABASE_URL="$DATABASE_URL" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
APP_ENV="$APP_ENV" \
"$VENV/bin/python" webreaper.py &
API_PID=$!

# Wait for API to be ready
sleep 2
if ! kill -0 $API_PID 2>/dev/null; then
    echo "[!] API server failed to start. Check for errors above."
    exit 1
fi
echo "    API server running (PID: $API_PID)"

# ---------------------------------------------------------------------------
# Start Next.js dashboard (only if web/ exists)
# ---------------------------------------------------------------------------
WEB_PID=""
if [ -d "web" ]; then
    echo "[*] Starting dashboard on http://localhost:3000..."
    cd web && NEXT_PUBLIC_API_URL="http://localhost:8000" pnpm dev --port 3000 &
    WEB_PID=$!
    cd ..
fi

# ---------------------------------------------------------------------------
# Ready
# ---------------------------------------------------------------------------
echo ""
echo "====================================="
echo "  WebReaper is running!"
echo "====================================="
echo ""
echo "  Dashboard:    http://localhost:3000"
echo "  API server:   http://localhost:8000"
echo "  API docs:     http://localhost:8000/docs"
echo ""
echo "  SSH tunnel:"
echo "  ssh -L 3000:localhost:3000 -L 8000:localhost:8000 user@$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'your-server')"
echo ""
echo "  Copy .env.example to .env and fill in your keys to unlock all features."
echo ""
echo "  Press Ctrl+C to stop."
echo ""

# Graceful shutdown
cleanup() {
    echo ""
    echo "Stopping..."
    kill $API_PID 2>/dev/null
    [ -n "$WEB_PID" ] && kill $WEB_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM
wait $API_PID
