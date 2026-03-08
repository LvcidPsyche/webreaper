#!/usr/bin/env python3
"""
WebReaper — Entry Point
=======================
Starts the FastAPI server.
The Next.js dashboard (web/) is the UI — run it separately with:
    cd web && pnpm dev

For full startup of both servers, use:
    ./start.sh
"""

import os
import sys
from pathlib import Path

# Ensure the package root is on the path
sys.path.insert(0, str(Path(__file__).parent))


def main() -> None:
    """Start the WebReaper API server."""
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    app_env = os.environ.get("APP_ENV", "development")
    reload = app_env == "development"

    # Sanity check: make sure the app module is importable
    try:
        import server.main  # noqa: F401
    except ImportError as exc:
        print(f"[!] Cannot import server.main: {exc}")
        print("    Make sure the server/ package exists with a main.py that defines `app`.")
        sys.exit(1)

    print(f"🕷️  WebReaper API starting on http://{host}:{port}")
    print(f"   Environment: {app_env}")
    print(f"   API docs: http://{host}:{port}/docs")
    print(f"   Dashboard: http://localhost:3000 (run 'cd web && pnpm dev')")
    print()

    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
