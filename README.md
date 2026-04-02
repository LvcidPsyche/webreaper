# WebReaper

WebReaper is a workspace-first web crawling and content filing platform for teams that need to collect, organize, and review website data quickly.

The current product direction is centered on four things:
- broad crawling with browser-render fallback
- deep page extraction and structured inventory
- workspace libraries for filing, labeling, and exporting collected pages
- an analyst-facing UI backed by FastAPI and SQLite/Postgres-compatible models

Proxy, repeater, and intruder tooling remain in the product and are useful for analyst workflows, but the primary story is now crawling plus structured content operations.

## Core Capabilities

### Crawl and extract
- Async crawl execution with resumable job tracking
- Browser-render fallback for pages that need client-side rendering
- Page metadata, headings, contacts, technology, and content extraction
- Endpoint and parameter inventory derived from links, forms, and observed browser requests
- Duplicate-content, link-health, and content-analysis views

### Workspace library
- Workspace-scoped crawl boundaries and scope rules
- Auto-filing suggestions for category, folder, and labels
- Manual filing controls for starring, notes, labels, and folder/category overrides
- Workspace-level summaries, recent pages, and filtered library views
- JSON and CSV export of library datasets

### Analyst tooling
- Proxy session management with HTTP history and intercept queue
- Repeater for replaying saved requests and comparing responses
- Intruder for queued payload fuzzing with result triage
- On-demand security findings, triage metadata, and report export

### Platform surface
- Next.js dashboard with static export support
- FastAPI backend with SSE streams and WebSocket/chat plumbing
- Alembic migrations and async SQLAlchemy data layer
- SQLite by default, with a Postgres-compatible schema layout

## Architecture

- Backend: FastAPI, SQLAlchemy async ORM, Alembic
- Frontend: Next.js App Router, TypeScript
- Storage: SQLite local default, Postgres-friendly schema
- Streaming: SSE for metrics/logs/progress, WebSocket support for chat/gateway features
- Background execution: in-process async job queue

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 20+ with `npm`/`npx`
- `pnpm` is preferred, but `start.sh` will fall back to `npx pnpm` if `pnpm` is not installed globally

### Start the full local stack

```bash
./start.sh
```

This script:
- creates a local virtual environment if needed
- installs Python and frontend dependencies
- initializes the SQLite database
- runs migrations
- starts the FastAPI backend on `http://localhost:8000`
- starts the dashboard on `http://localhost:3000`

Useful endpoints:
- Dashboard: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Seed a deterministic demo dataset

```bash
export PYTHONPATH=.
export DATABASE_URL='sqlite+aiosqlite:////tmp/webreaper_demo.db'
./.venv/bin/python scripts/seed_demo_data.py
```

For a fuller walkthrough, see [docs/demo-flow.md](docs/demo-flow.md).

## Development Workflow

### Backend tests

```bash
./.venv/bin/pytest tests
```

### Frontend build and tests

```bash
cd web
npx pnpm build
npx pnpm test
```

### Production-style dashboard export

The dashboard is configured with `output: 'export'`.

```bash
cd web
NEXT_PUBLIC_API_URL='http://127.0.0.1:8000' \
NEXT_PUBLIC_WS_URL='ws://127.0.0.1:8000' \
NEXT_PUBLIC_SSE_URL='http://127.0.0.1:8000' \
npx pnpm build

npx pnpm start
```

`pnpm start` serves the generated `web/out` bundle.

## Recommended Product Demo

1. Open the dashboard and verify the live metrics stream.
2. Start or inspect a crawl from Jobs.
3. Review extracted content in Data.
4. Open a workspace and review or edit library filings.
5. Inspect captured traffic in Proxy.
6. Replay a request in Repeater.
7. Review a fuzzing job in Intruder.
8. Review findings and exports in Security.

## Configuration Notes

- Local/self-hosted usage does not require license enforcement by default.
- To enable the legacy gated behavior explicitly, set `WEBREAPER_REQUIRE_LICENSE=1`.
- Missing Supabase or Stripe configuration will degrade those related features, but the local crawler/library workflow still runs in development mode.

## Safety

Use interception, replay, fuzzing, or active security testing features only against systems you own or are explicitly authorized to assess.
