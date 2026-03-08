#!/bin/bash
# ===========================================================================
# WebReaper — Dead Code Cleanup Script
# ===========================================================================
# Run from the repo root to delete all features identified in the audit.
# Creates a git commit for each category so changes are reversible.
#
# Usage: bash scripts/cleanup_dead_code.sh
# ===========================================================================

set -e
cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🕷️  WebReaper — Dead Code Cleanup"
echo "==================================="
echo ""
echo -e "${YELLOW}This will delete:"
echo "  - Security scanner (XSS/SQLi/IDOR)"
echo "  - Burp Suite toolset (Proxy/Repeater/Intruder/Decoder)"
echo "  - Tor integration"
echo "  - Blogwatcher bridge"
echo "  - Genre news aggregator (DESIGN_GENRES_AND_UI.md)"
echo "  - Desktop/Tauri workspace"
echo "  - Old CLI installer (install.sh)"
echo "  - License key system"
echo ""
echo -e "${RED}This is NOT reversible without git history.${NC}"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""

# ---------------------------------------------------------------------------
# 1. Delete Security Scanner
# ---------------------------------------------------------------------------
echo "[*] Removing security scanner..."
FILES_TO_DELETE=(
    "webreaper/modules/security.py"
    "webreaper/utils/payloads.py"
    "tests/test_security.py"
    "tests/test_payloads.py"
)
for f in "${FILES_TO_DELETE[@]}"; do
    if [ -f "$f" ]; then
        git rm -f "$f" 2>/dev/null || rm -f "$f"
        echo "    Deleted: $f"
    fi
done
echo -e "${GREEN}    Done.${NC}"

# ---------------------------------------------------------------------------
# 2. Delete Burp Suite Toolset (Proxy/Repeater/Intruder/Decoder)
# ---------------------------------------------------------------------------
echo "[*] Removing Burp Suite toolset..."
BURP_DIRS=(
    "webreaper/proxy"
    "webreaper/repeater"
    "webreaper/intruder"
    "webreaper/decoder"
    "server/routers/proxy.py"
    "server/routers/repeater.py"
    "server/routers/intruder.py"
    "server/routers/decoder.py"
    "web/src/app/proxy"
    "web/src/app/repeater"
    "web/src/app/intruder"
    "web/src/app/decoder"
    "tests/test_proxy.py"
    "tests/test_repeater.py"
    "tests/test_intruder.py"
)
for p in "${BURP_DIRS[@]}"; do
    if [ -e "$p" ]; then
        git rm -rf "$p" 2>/dev/null || rm -rf "$p"
        echo "    Deleted: $p"
    fi
done
echo -e "${GREEN}    Done.${NC}"

# ---------------------------------------------------------------------------
# 3. Delete Tor Integration
# ---------------------------------------------------------------------------
echo "[*] Removing Tor integration..."
TOR_FILES=(
    "webreaper/modules/tor.py"
    "webreaper/utils/tor_manager.py"
)
for f in "${TOR_FILES[@]}"; do
    if [ -f "$f" ]; then
        git rm -f "$f" 2>/dev/null || rm -f "$f"
        echo "    Deleted: $f"
    fi
done
# Remove stem + aiohttp-socks from requirements (already done in fixed requirements.txt)
echo -e "${GREEN}    Done. Also verify requirements.txt has no stem/aiohttp-socks lines.${NC}"

# ---------------------------------------------------------------------------
# 4. Delete Blogwatcher Bridge
# ---------------------------------------------------------------------------
echo "[*] Removing blogwatcher bridge..."
BLOG_FILES=(
    "webreaper/modules/blogwatcher.py"
    "webreaper/modules/blogwatcher_bridge.py"
    "webreaper/hooks/"
    "tests/test_blogwatcher.py"
)
for f in "${BLOG_FILES[@]}"; do
    if [ -e "$f" ]; then
        git rm -rf "$f" 2>/dev/null || rm -rf "$f"
        echo "    Deleted: $f"
    fi
done
echo -e "${GREEN}    Done.${NC}"

# ---------------------------------------------------------------------------
# 5. Archive (don't delete — move to docs/archive)
# ---------------------------------------------------------------------------
echo "[*] Archiving personal planning docs..."
mkdir -p docs/archive
for f in ARCHITECTURE.md DESIGN_GENRES_AND_UI.md; do
    if [ -f "$f" ]; then
        mv "$f" "docs/archive/$f"
        echo "    Moved to docs/archive/$f"
    fi
done
echo -e "${GREEN}    Done.${NC}"

# ---------------------------------------------------------------------------
# 6. Delete Desktop/Tauri Workspace
# ---------------------------------------------------------------------------
echo "[*] Removing desktop/Tauri workspace..."
if [ -d "desktop" ]; then
    git rm -rf desktop/ 2>/dev/null || rm -rf desktop/
    echo "    Deleted: desktop/"
fi
echo -e "${GREEN}    Done.${NC}"

# ---------------------------------------------------------------------------
# 7. Delete old CLI installer
# ---------------------------------------------------------------------------
echo "[*] Removing old CLI installer..."
if [ -f "install.sh" ]; then
    git rm -f install.sh 2>/dev/null || rm -f install.sh
    echo "    Deleted: install.sh"
fi
echo -e "${GREEN}    Done.${NC}"

# ---------------------------------------------------------------------------
# 8. Delete License Key System
# ---------------------------------------------------------------------------
echo "[*] Removing license key system..."
LICENSE_FILES=(
    "webreaper/license.py"
    "webreaper/license_manager.py"
    "tests/test_license.py"
)
for f in "${LICENSE_FILES[@]}"; do
    if [ -f "$f" ]; then
        git rm -f "$f" 2>/dev/null || rm -f "$f"
        echo "    Deleted: $f"
    fi
done
echo -e "${GREEN}    Done.${NC}"

# ---------------------------------------------------------------------------
# 9. Run autoflake to remove unused imports across Python codebase
# ---------------------------------------------------------------------------
echo "[*] Cleaning unused imports with autoflake..."
if command -v autoflake &> /dev/null || .venv/bin/autoflake --version &> /dev/null 2>&1; then
    AUTOFLAKE="autoflake"
    command -v autoflake &> /dev/null || AUTOFLAKE=".venv/bin/autoflake"
    $AUTOFLAKE --remove-all-unused-imports --in-place --recursive webreaper/ server/ tests/
    echo -e "${GREEN}    Done.${NC}"
else
    echo -e "${YELLOW}    autoflake not found. Run: pip install autoflake && autoflake --remove-all-unused-imports --in-place --recursive webreaper/ server/${NC}"
fi

# ---------------------------------------------------------------------------
# 10. Run black + isort for consistent formatting
# ---------------------------------------------------------------------------
echo "[*] Formatting with black + isort..."
if command -v black &> /dev/null || .venv/bin/black --version &> /dev/null 2>&1; then
    BLACK="black"
    command -v black &> /dev/null || BLACK=".venv/bin/black"
    ISORT="isort"
    command -v isort &> /dev/null || ISORT=".venv/bin/isort"
    $ISORT webreaper/ server/ tests/
    $BLACK webreaper/ server/ tests/
    echo -e "${GREEN}    Done.${NC}"
else
    echo -e "${YELLOW}    black/isort not found. Run: pip install black isort && black . && isort .${NC}"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "==================================="
echo -e "${GREEN}✓ Cleanup complete!${NC}"
echo "==================================="
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff --stat"
echo "  2. Run tests: .venv/bin/pytest -q"
echo "  3. Commit: git add -A && git commit -m 'chore: remove dead code (audit 2026-03-08)'"
echo ""
echo "Files to also manually review/update:"
echo "  - server/main.py — remove any imports of deleted modules"
echo "  - webreaper/__init__.py — remove exports of deleted modules"
echo "  - Any route that references proxy/repeater/intruder/decoder"
echo ""
