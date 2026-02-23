#!/bin/bash
# WebReaper — local deployment script
# Usage: ./start.sh
# Access via SSH tunnel: ssh -L 3000:localhost:3000 -L 8000:localhost:8000 user@server

set -e
cd "$(dirname "$0")"

VENV=".venv"
DB_PATH="$HOME/.webreaper/webreaper.db"
export DATABASE_URL="sqlite+aiosqlite:///$DB_PATH"

# Set this to your own secret before generating production license keys.
# Keys generated with the dev secret are fine for testing.
export WEBREAPER_LICENSE_SECRET="${WEBREAPER_LICENSE_SECRET:-wr-dev-secret-change-in-production}"

echo "=== WebReaper ==="
echo "DB:  $DB_PATH"
echo ""

# --- Python venv ---
if [ ! -d "$VENV" ]; then
    echo "[*] Creating Python virtual environment..."
    python3 -m venv "$VENV"
fi

echo "[*] Installing Python dependencies..."
"$VENV/bin/pip" install -q -r requirements.txt

# --- Playwright ---
if [ ! -d "$HOME/.cache/ms-playwright" ]; then
    echo "[*] Installing Playwright browsers (one-time, ~300MB)..."
    "$VENV/bin/playwright" install chromium
fi

# --- DB init ---
mkdir -p "$HOME/.webreaper"
echo "[*] Initializing database..."
"$VENV/bin/python" -c "
import asyncio, os
os.environ['DATABASE_URL'] = '$DATABASE_URL'
from webreaper.database import DatabaseManager
asyncio.run(DatabaseManager().create_tables())
print('    Database ready.')
"

# --- Node deps ---
if [ ! -d "web/node_modules" ]; then
    echo "[*] Installing frontend dependencies..."
    cd web && pnpm install --silent && cd ..
fi

# --- Generate a test license key (dev) ---
echo ""
echo "[*] Generating a development license key for you..."
"$VENV/bin/python" -c "
from webreaper.license import generate_key
print('    LITE key:', generate_key('lite'))
print('    PRO  key:', generate_key('pro'))
"
echo "    (These keys use the dev secret. Use 'webreaper license activate <key>' to install.)"

# --- Start API server ---
echo ""
echo "[*] Starting API server on http://localhost:8000..."
DATABASE_URL="$DATABASE_URL" \
WEBREAPER_LICENSE_SECRET="$WEBREAPER_LICENSE_SECRET" \
"$VENV/bin/python" -m server.main &
API_PID=$!

# Wait for API to be ready
sleep 2
if ! kill -0 $API_PID 2>/dev/null; then
    echo "[!] API server failed to start. Check for errors above."
    exit 1
fi
echo "    API server running (PID: $API_PID)"

# --- Start Next.js dashboard ---
echo "[*] Starting dashboard on http://localhost:3000..."
cd web && DATABASE_URL="$DATABASE_URL" pnpm dev --port 3000 &
WEB_PID=$!
cd ..

echo ""
echo "====================================="
echo "  WebReaper is running!"
echo "====================================="
echo ""
echo "  API server:   http://localhost:8000"
echo "  Dashboard:    http://localhost:3000"
echo "  API docs:     http://localhost:8000/docs"
echo ""
echo "  SSH tunnel from your machine:"
echo "  ssh -L 3000:localhost:3000 -L 8000:localhost:8000 user@$(hostname -I | awk '{print $1}')"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

# Graceful shutdown
trap "echo ''; echo 'Stopping...'; kill $API_PID $WEB_PID 2>/dev/null; exit 0" INT TERM
wait $API_PID
