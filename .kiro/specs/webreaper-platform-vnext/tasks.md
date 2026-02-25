# Implementation Plan

- [ ] 1. Establish shared backend/frontend API contracts and compatibility adapters
  - Create Pydantic schemas for REST responses, API errors, SSE envelopes, and WebSocket event envelopes in a new `server/schemas/` package.
  - Add TypeScript types/adapters for the same payloads in `web/lib/types.ts` (or generated types) and compatibility parsers for legacy route shapes.
  - Add contract tests for representative `/api/data`, `/api/security`, SSE, and WS payloads.
  - _Requirements: 9.2, 11.3, 11.4, 12.2, 14.1_

- [x] 2. Fix live streaming and chat event integration (P0 contract repairs)
  - [x] 2.1 Normalize SSE event delivery between backend and frontend
    - Update `server/routes/stream.py` and `web/hooks/use-sse.ts` so named events (`metrics`, `log`, `progress`) are handled consistently via a shared envelope.
    - Add reconnect/status handling and tests for stream disconnect/retry behavior.
    - _Requirements: 2.3, 9.2, 14.1_
  - [x] 2.2 Normalize chat WebSocket events for gateway/tool messages
    - Add server-side translation in `server/routes/chat.py` from raw gateway chunks to UI-consumable chat/tool events.
    - Update `web/hooks/use-agent.ts` and chat components to render token streams, tool approval requests, and final assistant messages.
    - _Requirements: 9.1, 9.2, 12.2, 12.4_
  - [x] 2.3 Add integration tests for SSE and WebSocket event schemas
    - Use FastAPI test clients/websocket tests to validate event envelopes and frontend parsing expectations.
    - _Requirements: 9.2, 11.4, 14.1, 15.2_

- [x] 3. Introduce Alembic migrations and make schema evolution safe
  - [x] 3.1 Scaffold Alembic with async SQLAlchemy support and baseline migration
    - Create `alembic/` config and baseline migration matching current deployed schema/state.
    - _Requirements: 11.1, 11.2, 15.2_
  - [x] 3.2 Add migration for deep extraction tables/columns (`assets`, `technologies`, page deep fields)
    - Convert existing ORM-only deep schema additions into versioned migrations and verify upgrade on existing DB fixtures.
    - _Requirements: 4.3, 11.1, 11.3_
  - [x] 3.3 Replace startup `create_tables()`-only evolution with migration-aware startup checks
    - Fail safely with actionable error messages when migration prerequisites are not met.
    - _Requirements: 11.1, 11.2, 14.2_

- [x] 4. Add workspace domain model and scope evaluation service
  - [x] 4.1 Implement workspace models, repositories, and API routes
    - Add `workspaces` tables/models and CRUD endpoints with target scope rules, tags, and risk policy settings.
    - _Requirements: 1.1, 1.4, 10.1, 12.2_
  - [x] 4.2 Implement scope matcher and reusable scope decision service
    - Add include/exclude host/path/scheme matching with explicit decision reasons and unit tests.
    - _Requirements: 1.1, 2.2, 14.3_
  - [x] 4.3 Link crawls, pages, and findings to `workspace_id`
    - Add linkage columns and backfill/defaulting logic so new records are workspace-correlated.
    - _Requirements: 1.2, 1.3, 4.1, 8.4, 11.3_

- [ ] 5. Refactor crawl job orchestration for persistent state and real metrics
  - [x] 5.1 Introduce persistent crawl run state transitions
    - Normalize job/crawl run lifecycle (queued/running/completed/failed/canceled) in backend services and routes.
    - _Requirements: 1.2, 2.1, 2.4, 14.2_
  - [x] 5.2 Instrument crawler/fetcher metrics and progress fields used by UI streams
    - Emit queue size, active workers, current URL, throughput, retry counts, and error counts from crawl workers.
    - _Requirements: 2.3, 2.4, 9.2, 14.1_
  - [ ] 5.3 Add restart-safe handling and partial progress persistence
    - Persist resumable state/checkpoints for interrupted jobs where feasible and test recovery behavior.
    - _Requirements: 14.2, 15.2_

- [x] 6. Complete deep extraction persistence and inventory capture (stabilize Claude/local work)
  - [x] 6.1 Harden `DeepExtractor` integration and component-level error recording
    - Ensure partial extraction failures do not drop page records and persist extraction warnings/errors.
    - _Requirements: 4.1, 4.2, 4.4, 14.1_
  - [x] 6.2 Persist full links/forms/assets/technologies with metadata
    - Store internal and external links, anchor/rel/context, forms/inputs, assets, and technologies with page/workspace linkage.
    - _Requirements: 4.1, 4.3, 5.4, 8.1_
  - [x] 6.3 Add extraction and persistence tests using fixture HTML pages
    - Cover JSON-LD, OG/Twitter, hreflang/canonical, contacts, assets, and link metadata persistence.
    - _Requirements: 4.1, 4.2, 4.3, 15.2_

- [ ] 7. Build endpoint and parameter inventory as a shared substrate for scanning/manual tools
  - [x] 7.1 Add endpoint/parameter models and extraction pipelines from crawl and forms
    - Derive normalized endpoints/params from links, forms, and observed requests.
    - _Requirements: 1.2, 8.1, 8.4, 12.1_
  - [x] 7.2 Add API/query layer for endpoint inventory and parameter filters
    - Support filtering by workspace, host, method, path, parameter names, and source.
    - _Requirements: 1.4, 9.4, 12.2_
  - [ ] 7.3 Seed passive scanner and manual tools from endpoint inventory
    - Replace ad hoc target generation with endpoint inventory integration.
    - _Requirements: 7.1, 8.1, 8.2_

- [x] 8. Implement browser-rendered crawl worker (Playwright) and integrate with orchestrator
  - [x] 8.1 Build browser worker service and worker adapter interface
    - Create Playwright-based page fetch/extract service with configurable wait policy, timeouts, and resource blocking.
    - _Requirements: 3.1, 3.4, 10.1_
  - [x] 8.2 Capture DOM/network artifacts and persist browser-discovered requests/routes
    - Persist final DOM snapshot metadata, observed requests, and browser-only links/forms for later analysis.
    - _Requirements: 3.1, 3.3, 4.1, 7.1_
  - [x] 8.3 Add browser fallback and failure recording behavior
    - Implement optional HTTP fallback when browser rendering fails, with explicit error reasons and tests.
    - _Requirements: 3.2, 14.2, 15.2_

- [ ] 9. Expand SEO and technical site audit analytics (Screaming Frog-class core)
  - [ ] 9.1 Add duplicate/near-duplicate content grouping and comparison support
    - Use content hashes/similarity metrics to group duplicates and expose compare-ready payloads.
    - _Requirements: 5.3, 13.1_
  - [ ] 9.2 Add link health analytics (broken links, redirects, chains, orphan candidates, depth outliers)
    - Build crawl-time or post-crawl checks with persisted status and chain metadata.
    - _Requirements: 5.4, 2.4, 13.1_
  - [ ] 9.3 Extend `/api/analysis` endpoints and UI data contracts for new audit views
    - Add aggregates and page-level drilldowns with compatibility-safe responses.
    - _Requirements: 5.1, 5.2, 9.4, 11.4_

- [ ] 10. Implement proxy service MVP (Burp-like interception core)
  - [x] 10.1 Build proxy listener lifecycle service and control APIs
    - Add start/stop/status endpoints and persisted proxy session configuration/state.
    - _Requirements: 6.1, 6.3, 14.1_
  - [x] 10.2 Capture and persist HTTP/HTTPS flows into transaction storage
    - Store request/response metadata, timings, tags, and bounded body captures with redaction/truncation flags.
    - _Requirements: 1.2, 6.4, 13.2, 13.3_
  - [x] 10.3 Add interception queue actions (pause/forward/drop/edit) and runtime policy hooks
    - Implement intercept action APIs and tests for edit/release behavior.
    - _Requirements: 6.2, 12.4, 14.3_

- [ ] 11. Add HTTPS interception certificate status and setup verification APIs
  - Implement certificate status checks, trust guidance endpoints, and readiness verification used by UI setup flow.
  - Add tests for missing/invalid certificate states and safe error responses.
  - _Requirements: 6.3, 14.4, 12.2_

- [ ] 12. Build proxy history UI and live interception workflow
  - [x] 12.1 Create Proxy page with history table, filters, and raw request/response viewers
    - Add workspace-scoped search/filter/sort/bulk tag actions for captured traffic.
    - _Requirements: 6.4, 9.1, 9.4_
  - [x] 12.2 Implement live interception queue UI controls and status indicators
    - Render pause/forward/drop/edit flow actions and proxy listener/intercept states.
    - _Requirements: 6.2, 6.3, 9.2_
  - [ ] 12.3 Add frontend tests for proxy history filtering and live event handling
    - _Requirements: 9.2, 9.4, 15.2_

- [ ] 13. Implement Repeater backend MVP (manual request replay)
  - [x] 13.1 Add Repeater models and APIs (`tabs`, `runs`, `send-to-repeater`)
    - Persist editable requests and replay history linked to workspace and source transactions.
    - _Requirements: 7.1, 7.2, 1.2_
  - [x] 13.2 Implement request execution engine with response diffing
    - Replay requests with timeout/redirect controls and compute structured diffs vs prior runs.
    - _Requirements: 7.2, 8.4, 14.1_
  - [x] 13.3 Add integration tests for replay execution and failure cases
    - _Requirements: 7.2, 14.2, 15.2_

- [ ] 14. Build Repeater UI and Decoder utilities
  - [ ] 14.1 Create Repeater page with raw/structured editors and response diff views
    - Support multi-tab workflow and send-to-repeater from proxy history/finding evidence.
    - _Requirements: 7.1, 7.2, 9.1, 9.4_
  - [x] 14.2 Implement Decoder utilities (URL/Base64/HTML/hex/JWT parse)
    - Add stateless transform utilities and UI panel integrated into Repeater/security workflows.
    - _Requirements: 7.4, 9.1_
  - [ ] 14.3 Add frontend tests for editor state and decoder transforms
    - _Requirements: 7.4, 15.2_

- [ ] 15. Implement Intruder backend MVP (payload engine + queued fuzzing)
  - [ ] 15.1 Add Intruder job models, APIs, and payload position parsing
    - Support payload markers/positions, payload sets, concurrency, and rate control settings.
    - _Requirements: 7.3, 8.1, 10.1_
  - [ ] 15.2 Execute Intruder jobs with throttling and result summaries
    - Persist per-attempt transaction references, match/extract summaries, and stop conditions.
    - _Requirements: 7.3, 8.2, 14.1_
  - [ ] 15.3 Add tests for rate limiting, stop conditions, and job resume/cancel behavior
    - _Requirements: 7.3, 14.2, 15.2_

- [ ] 16. Build Intruder UI and result triage views
  - Create Intruder page for position selection, payload set configuration, run control, and results filtering/export.
  - Integrate send-to-intruder actions from proxy history and endpoint inventory.
  - Add frontend tests for configuration validation and result table interactions.
  - _Requirements: 7.3, 9.1, 9.4, 10.2_

- [ ] 17. Modularize security scanning engine and fully wire active scanning
  - [ ] 17.1 Split passive analyzers and active check modules into pluggable scanner interfaces
    - Refactor `webreaper/modules/security.py` into passive/active modules with shared finding contracts.
    - _Requirements: 8.2, 12.1, 12.3_
  - [ ] 17.2 Wire active scan execution paths and `auto_attack` behavior to real active modules
    - Ensure route/job code calls active scanners when enabled and policy-approved.
    - _Requirements: 8.1, 8.2, 8.3, 10.4_
  - [ ] 17.3 Persist canonical findings with evidence/reproduction linkages
    - Store severity/confidence/evidence/reproduction refs linked to workspace/page/endpoint/transaction.
    - _Requirements: 1.2, 1.3, 8.4, 13.2_

- [ ] 18. Add safety policy enforcement and audit logging for risky actions
  - [ ] 18.1 Implement workspace risk policies and confirmation gates for noisy/destructive modules
    - Enforce safe-mode checks in active scans, proxy interception edits, and Intruder runs.
    - _Requirements: 8.3, 10.3, 14.3, 14.4_
  - [ ] 18.2 Add audit logging for manual/security actions and policy decisions
    - Persist auditable records for active scan starts, intercept edits, and denied actions.
    - _Requirements: 12.4, 14.1, 14.3_
  - [ ] 18.3 Add tests for policy enforcement and explicit acknowledgment flows
    - _Requirements: 8.3, 14.4, 15.2_

- [ ] 19. Implement findings triage APIs/UI and evidence-rich reporting exports
  - [ ] 19.1 Add findings status workflow and workspace triage endpoints
    - Support open/accepted-risk/fixed/false-positive states, tags, assignees/notes (minimal first), and filters.
    - _Requirements: 1.4, 8.4, 9.4, 13.1_
  - [ ] 19.2 Build export/report generators with redaction pipeline
    - Export crawl audit, security-only, and combined reports with evidence and redaction rules.
    - _Requirements: 13.1, 13.2, 13.3, 13.4_
  - [ ] 19.3 Create Findings page and reporting UI flows
    - Add workspace-wide triage views, finding detail drilldowns, and report generation actions.
    - _Requirements: 9.1, 9.4, 13.1_

- [ ] 20. Add run profiles, UI customization persistence, and workflow automation chaining
  - [ ] 20.1 Implement run profiles for crawl/proxy/scan settings and pre-run override preview
    - Persist reusable profiles and validate risky profile settings before execution.
    - _Requirements: 10.1, 10.2, 10.3_
  - [ ] 20.2 Persist UI preferences and saved views per workspace/user
    - Store table columns, filters, themes, and named saved views used across Data/Proxy/Findings pages.
    - _Requirements: 9.3, 9.4, 10.1_
  - [ ] 20.3 Implement automation chaining executor (crawl -> extract -> scan -> report)
    - Add job chaining with explicit step status, failure handling, and cancellation behavior.
    - _Requirements: 10.4, 14.2, 14.3_

- [ ] 21. Build performance, regression, and benchmark harnesses for release gating
  - [ ] 21.1 Add backend/frontend automated regression suites for critical workflows
    - Cover crawler, migrations, API contracts, live streams, proxy/repeater/intruder core paths.
    - _Requirements: 15.2, 11.1, 11.4_
  - [ ] 21.2 Implement benchmark scenarios and threshold checks in CI/local test commands
    - Define throughput/UI responsiveness/scanner performance thresholds and failure gating.
    - _Requirements: 15.1, 15.3_
  - [ ] 21.3 Add competitor-comparison benchmark fixture documentation as versioned test data/code
    - Store reproducible benchmark scenarios and metadata used for future claims.
    - _Requirements: 15.4_
