# WebReaper

WebReaper is a **workspace-first web reconnaissance platform** that combines:
- **Screaming Frog-class crawling / technical SEO inventory**
- **Burp-style proxy/manual tooling foundations** (Proxy, Repeater, Intruder)
- **Security scanning + findings triage/reporting**
- **Interactive Next.js UI + FastAPI backend**

> This repo now includes browser-rendered crawling, proxy history/intercept queue, Repeater replay+Decoder, Intruder fuzzing backend/UI, governance policies/audit logs, and reporting/export workflows.

---

## What’s in the platform now

### Crawl + Analysis
- Async crawler with deep extraction persistence
- Browser-rendered crawl mode (Playwright foundation + fallback to HTTP)
- Endpoint/parameter inventory (links/forms/observed requests)
- SEO/content/technology analytics
- Duplicate content + link health analytics
- Manual tool seeds from endpoint inventory

### Burp-style toolset (foundations)
- **Proxy**: session lifecycle, HTTP history, capture endpoint, intercept queue, forward/drop/edit actions
- **Repeater**: save/edit requests, replay, response diff summaries
- **Decoder**: URL/Base64/HTML/hex/JWT parsing helpers + UI
- **Intruder (MVP)**: payload markers (`§FUZZ§`), queued fuzzing runs, throttling, stop conditions, result triage

### Security + Governance
- Passive + active scanning paths (modular scan engine wrappers)
- Findings triage workflow + report export (JSON / Markdown)
- Workspace risk policies (acknowledgment gates)
- Audit logging for risky/manual actions
- Run profiles + UI preference persistence + automation chain skeleton

---

## Quick start (local dev)

### 1) Start everything
```bash
./start.sh
```

This boots:
- FastAPI backend: `http://localhost:8000`
- Next.js dashboard: `http://localhost:3000`

### 2) Open the dashboard
- Dashboard: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`

---

## Dev commands

### Backend tests
```bash
./.venv/bin/pytest -q tests
```

### Frontend typecheck + UI utility tests
```bash
cd web
npx tsc --noEmit
npx vitest run
```

### Regression smoke / benchmark harness
```bash
./scripts/regression_smoke.sh
./scripts/benchmark_webreaper.py --max-seconds 15
```

See also: `docs/benchmarks.md`

---

## Demo flow (recommended)

A good local demo sequence:
1. **Dashboard** → verify live metrics stream
2. **Jobs** → start a crawl (optionally enable browser render)
3. **Data** → inspect pages, SEO/content/tech/contact views
4. **Proxy** → start session, inspect history, use intercept queue actions
5. **Repeater** → send a request to repeater and compare response diffs
6. **Intruder** → create a fuzz job with `§FUZZ§` markers and run/triage results
7. **Security** → run on-demand scan, triage findings, export report (JSON/Markdown)

More detail (with screenshots): **`docs/demo-flow.md`**

For a reproducible local UI demo dataset/screenshots, use: **`scripts/seed_demo_data.py`**

---

## Architecture (high level)

- **Backend**: FastAPI + SQLAlchemy (async) + Alembic migrations
- **Frontend**: Next.js (App Router) + TypeScript
- **Storage**: SQLite (local default), Postgres-compatible model layout
- **Streaming**: SSE (metrics/logs/job progress) + WS chat/gateway
- **Security tooling**: Proxy/Repeater/Intruder data persisted into shared HTTP transaction storage

---

## Notes / current scope

This is a fast-moving build. Some advanced capabilities are currently **foundational/MVP** (especially full MITM runtime integration, advanced intruder attack modes, and richer proxy live events), but the core data model, APIs, UI flows, and test harnesses are in place and expanding rapidly.

---

## Legal / Safety

Only use active scanning, fuzzing, interception, or security testing features against systems you own or are explicitly authorized to test.
