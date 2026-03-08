# WebReaper Fix Merge — Work Notes

**Started:** 2026-03-08 | **Author:** Claude Opus 4.6
**Goal:** Integrate FIXSHEET.md fixes without breaking existing functionality

## Context

A code review (FIXSHEET.md) identified 20 issues and patched 13. The auth/billing/security
fixes are solid. BUT the reviewer treated `server/main.py`, `tests/conftest.py`, and
`webreaper/usage.py` as greenfield and replaced working implementations with skeletons.

## What's Good (KEEP these changes as-is)

- `webreaper/auth.py` — Supabase singleton, DEV_SKIP_AUTH removed, plan validation ✅
- `webreaper/billing.py` — Customer lookup implemented, null-safe signature, defensive data access ✅
- `requirements.txt` — supabase/stripe uncommented, dev deps split out ✅
- `requirements.dev.txt` — new file, dev dependencies separated ✅
- `setup.py` — supabase/stripe uncommented, version bumped ✅
- `alembic.ini` / `alembic/env.py` — metadata wired up ✅
- `Dockerfile` — curl + healthcheck added ✅
- `docker-compose.yml` — postgres default, APP_ENV=production ✅
- `start.sh` — guards for missing web/, cleaner shutdown ✅
- `package.json` — workspaces removed, version bumped ✅

## What's Broken (MUST FIX)

### 1. server/main.py — GUTTED ❌
**Problem:** Original had lifespan handler, 15 route mounts, service initialization.
Fix replaced it with a 30-line skeleton (root + health only).

**Fix:** Restore original, then apply:
- Version bump to 2.2.1
- Add billing router mount: `app.include_router(billing.router, prefix="/webhooks", tags=["billing"])`
- Keep CORS origins from original (not wildcard "*")

**Status:** ✅ FIXED

### 2. tests/conftest.py — REPLACED ❌
**Problem:** Original had event_loop, temp_db, mock_db_session, mock_crawler_config,
sample_html, mock_fetcher — all used by 55 existing tests. Fix replaced with auth-only fixtures.

**Fix:** Restore original fixtures, ADD the new auth mock fixtures (mock_auth_user,
plan-specific users) alongside them.

**Status:** ✅ FIXED

### 3. webreaper/usage.py — COMPLETELY REWRITTEN ❌
**Problem:** Original was file-based (~/.webreaper/usage.json) for CLI usage.
Fix replaced with async DB-based tracker. But:
- `server/routes/jobs.py:109` still calls `get_usage()` (old API)
- References `UserUsage.period_start` which doesn't exist in models.py
- References `Scraper.is_deleted` which doesn't exist in models.py
- Imports `sqlite_upsert` at top but uses `pg_upsert` in function body
- Old `add_pages()` function used by jobs.py is gone

**Fix:** Restore original file-based functions at bottom for backward compat.
Fix model references. Clean up dialect imports.

**Status:** ✅ FIXED

### 4. webreaper/models.py — MISSING COLUMNS ❌
**Problem:** usage.py references columns that don't exist:
- `UserUsage.period_start` (model has `month_start` instead)
- `UserUsage.updated_at` (doesn't exist)
- `Scraper.is_deleted` (doesn't exist)

**Fix:** Add missing columns to models.py, or update usage.py to match existing column names.

**Status:** ✅ FIXED (added period_start, updated_at, is_deleted)

### 5. server/routes/jobs.py — MINOR IMPORT ISSUE ❌
**Problem:** Line 108-109 imports `get_usage` from `webreaper.usage` — this function
was removed in the rewrite.

**Fix:** Keep `get_usage()` in usage.py (backward compat).

**Status:** ✅ FIXED (get_usage restored in usage.py)

### 6. pytest.ini — cov-fail-under disabled ❌
**Problem:** `--cov-fail-under=70` was commented out. This is fine for now but
should be re-enabled once tests pass.

**Status:** Acceptable as-is. Re-enable later.

## Test Results

**102 passed, 0 failed** (excluding test_migrations.py which needs DATABASE_URL — pre-existing).

```
.venv/bin/python -m pytest tests/ -q --tb=short --ignore=tests/test_migrations.py --no-cov
```

## Files Modified During This Merge

1. `server/main.py` — restored original + billing router + version bump
2. `tests/conftest.py` — restored original + added auth mock fixtures
3. `webreaper/usage.py` — kept new DB functions + restored old file-based compat
4. `webreaper/models.py` — added period_start, updated_at, is_deleted columns
5. `MERGE_NOTES.md` — this file (delete after merge is verified)
