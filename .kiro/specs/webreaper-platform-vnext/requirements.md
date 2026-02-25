# Requirements Document

## Introduction

WebReaper is intended to become a unified web intelligence platform that combines high-speed crawling, SEO/site auditing, and Burp Suite-style web security testing in one product. The current codebase already has strong foundations (async crawler, FastAPI backend, Next.js UI, passive security analysis, deep extraction work in local uncommitted changes), but it does not yet deliver a complete integrated workflow comparable to Screaming Frog + Burp Suite.

This specification defines the target behavior for a production-grade "WebReaper vNext" platform with:
- Deep crawling (HTTP + browser-rendered)
- Rich extraction and SEO/content analytics
- Intercepting proxy + manual testing tools (Burp-like)
- Active security scanning and fuzzing
- A powerful interactive UI with customization and analyst workflows
- Stable data model, migrations, and extensibility

## Requirements

### Requirement 1: Unified Project/Crawl Workspace

**User Story:** As an analyst, I want each target assessment to live in a single workspace, so that crawling, proxy traffic, security findings, and notes are correlated.

#### Acceptance Criteria

1. WHEN a user creates a new assessment THEN WebReaper SHALL create a project/workspace record with target scope, labels, and timestamps.
2. WHEN a crawl, proxy session, or security scan runs inside a workspace THEN WebReaper SHALL associate generated pages, requests, responses, and findings to that workspace.
3. IF a user views a page or finding THEN WebReaper SHALL display linked crawl metadata, request/response history, and related findings when available.
4. WHERE cross-module data exists WebReaper SHALL provide filters by workspace, crawl run, host, status, tag, and severity.

### Requirement 2: High-Performance Crawl Engine (HTTP)

**User Story:** As a technical SEO or recon operator, I want a fast crawler with precise scope controls, so that I can map large sites quickly without losing stability.

#### Acceptance Criteria

1. WHEN a user starts an HTTP crawl THEN WebReaper SHALL support configurable depth, concurrency, max pages, robots behavior, rate limiting, and include/exclude rules.
2. IF a URL is out of scope based on workspace rules THEN WebReaper SHALL skip it and record the reason.
3. WHILE a crawl is running WebReaper SHALL expose live metrics including queue size, pages crawled, error counts, and throughput.
4. WHEN crawl workers encounter retries/timeouts/redirects THEN WebReaper SHALL record request outcome details and retry behavior.

### Requirement 3: Browser-Rendered Crawl Mode

**User Story:** As an analyst, I want a browser-based crawl mode, so that SPAs and JS-generated links/forms are discoverable.

#### Acceptance Criteria

1. WHEN a user enables browser crawl mode THEN WebReaper SHALL render pages in a real browser engine and extract DOM links/forms after script execution.
2. IF browser rendering fails for a page THEN WebReaper SHALL record the failure and optionally fall back to HTTP mode according to user settings.
3. WHEN browser mode is enabled THEN WebReaper SHALL capture relevant artifacts including final URL, DOM HTML snapshot, and detected JS routes or client-side navigations.
4. WHILE browser crawl mode is active WebReaper SHALL enforce per-domain concurrency and timeout limits separate from HTTP-only workers.

### Requirement 4: Deep Extraction and Content Intelligence

**User Story:** As an analyst, I want deep page extraction, so that I can inspect SEO, content quality, assets, structured data, and technology fingerprints without re-fetching pages.

#### Acceptance Criteria

1. WHEN a page is successfully fetched THEN WebReaper SHALL extract title, meta tags, headings, links, forms, assets, structured data, and response headers.
2. WHEN deep extraction is enabled THEN WebReaper SHALL compute content metrics including word count, content-to-HTML ratio, readability indicators, and content hash.
3. WHEN page metadata is stored THEN WebReaper SHALL persist canonical, hreflang, robots meta, OG/Twitter metadata, and detected technologies.
4. IF extraction fails for a specific sub-component THEN WebReaper SHALL preserve the successful page data and record component-level extraction errors.

### Requirement 5: SEO and Technical Site Audit

**User Story:** As a technical SEO, I want Screaming Frog-style auditing and aggregations, so that I can prioritize site issues quickly.

#### Acceptance Criteria

1. WHEN crawl data is available THEN WebReaper SHALL generate page-level SEO checks (title/meta/H1/canonical/status/indexability/content depth/image alt coverage).
2. WHEN a user opens the audit overview THEN WebReaper SHALL provide issue distributions, severity or priority buckets, and affected-page counts.
3. IF duplicate or near-duplicate content is detected THEN WebReaper SHALL group affected pages and expose comparison details.
4. WHERE link data exists WebReaper SHALL report internal linking issues including broken links, redirect chains, orphan candidates, and depth outliers.

### Requirement 6: Intercepting Proxy (Burp-like Core)

**User Story:** As a security tester, I want an intercepting proxy with history and editing, so that I can inspect and modify live traffic.

#### Acceptance Criteria

1. WHEN a user starts proxy mode THEN WebReaper SHALL expose a local proxy listener and record HTTP/HTTPS traffic for configured clients.
2. WHEN interception is enabled THEN WebReaper SHALL allow pause/forward/drop/edit actions for requests and responses before release.
3. WHEN HTTPS interception is configured THEN WebReaper SHALL provide certificate setup guidance and verify certificate readiness before capture.
4. WHILE proxy capture is active WebReaper SHALL store request/response pairs, timing, headers, bodies (subject to retention rules), and tags in history.

### Requirement 7: Manual Testing Tools (Repeater, Intruder, Decoder)

**User Story:** As a security tester, I want Burp-style manual tools built into the same workspace, so that I can iterate on attacks without switching tools.

#### Acceptance Criteria

1. WHEN a user selects a captured request THEN WebReaper SHALL allow sending it to Repeater with editable raw and structured views.
2. WHEN a user runs a Repeater request THEN WebReaper SHALL preserve each attempt, diff responses, and show timing/status/body changes.
3. WHEN a user configures Intruder positions and payload sets THEN WebReaper SHALL execute queued variations with rate controls and result summaries.
4. WHEN a user uses Decoder utilities THEN WebReaper SHALL support common transformations (URL/Base64/HTML/hex/JWT parsing) without leaving the workspace.

### Requirement 8: Active Security Scanning and Fuzzing

**User Story:** As a security tester, I want configurable active scanning tied to discovered endpoints, so that I can identify exploitable issues beyond passive heuristics.

#### Acceptance Criteria

1. WHEN a user launches an active scan on a target page, endpoint, or workspace THEN WebReaper SHALL generate test requests from discovered parameters and forms.
2. WHEN active scanning runs THEN WebReaper SHALL support configurable modules (XSS, SQLi, SSRF, IDOR heuristics, open redirect, header misconfigurations, auth/session checks).
3. IF an active test may be destructive or noisy THEN WebReaper SHALL require explicit user confirmation and honor safe-mode policies.
4. WHEN a finding is produced THEN WebReaper SHALL store severity, confidence, evidence, reproduction request(s), and remediation guidance linked to the source endpoint/page.

### Requirement 9: Interactive UI and Analyst Workflow

**User Story:** As a power user, I want a fast and customizable interactive UI, so that I can pivot between crawl data, traffic, and findings efficiently.

#### Acceptance Criteria

1. WHEN a user opens the WebReaper UI THEN WebReaper SHALL present a workspace-centric navigation for Crawl, Data, Proxy, Security, Findings, and Reports.
2. WHEN live jobs are running THEN WebReaper SHALL stream real-time logs, metrics, and progress updates to the UI without manual refresh.
3. WHEN a user customizes the interface THEN WebReaper SHALL persist table layouts, column visibility, filters, themes, and saved views per user or workspace.
4. WHERE data lists are large WebReaper SHALL provide fast search, faceted filtering, sorting, and bulk actions.

### Requirement 10: Customization, Profiles, and Automation

**User Story:** As an advanced operator, I want reusable profiles and automations, so that I can run repeatable assessments with different goals.

#### Acceptance Criteria

1. WHEN a user creates a run profile THEN WebReaper SHALL support saved settings for crawl scope, rate limits, extraction toggles, proxy behavior, and scan modules.
2. WHEN a user starts a job from a profile THEN WebReaper SHALL show the resolved configuration and allow one-off overrides before execution.
3. IF a profile includes risky behaviors THEN WebReaper SHALL display warnings and require explicit confirmation according to policy.
4. WHEN automation is enabled THEN WebReaper SHALL support workflow chaining (for example crawl -> deep extract -> passive scan -> report generation).

### Requirement 11: Data Model, Migrations, and Backward Compatibility

**User Story:** As an operator managing long-lived installs, I want safe schema evolution, so that upgrades do not break existing crawl data.

#### Acceptance Criteria

1. WHEN the application starts on an existing database THEN WebReaper SHALL run versioned migrations instead of relying only on create-table behavior.
2. IF a migration cannot be safely applied THEN WebReaper SHALL stop with a clear error and recovery guidance before mutating data.
3. WHEN new data fields are introduced THEN WebReaper SHALL preserve compatibility with older records in UI and API responses.
4. WHERE API contracts change WebReaper SHALL version the response or provide compatibility shims for existing UI clients.

### Requirement 12: Extensible API and Plugin Surface

**User Story:** As a builder/integrator, I want stable APIs and extension points, so that I can add scanners, extractors, and outputs without forking core code.

#### Acceptance Criteria

1. WHEN a module integrates with WebReaper THEN WebReaper SHALL expose documented interfaces for extractors, scanners, and report exporters.
2. WHEN external tools consume the backend THEN WebReaper SHALL provide authenticated APIs for workspaces, jobs, pages, requests, and findings.
3. IF a plugin fails at runtime THEN WebReaper SHALL isolate the failure, log it, and continue core processing when safe.
4. WHERE permissions apply WebReaper SHALL enforce least-privilege access to sensitive actions (active scans, proxy interception, tool execution).

### Requirement 13: Reporting and Evidence Export

**User Story:** As an analyst, I want professional reports and evidence packages, so that I can share results with clients or teams.

#### Acceptance Criteria

1. WHEN a user generates a report THEN WebReaper SHALL support crawl audit, security findings, and combined assessment report types.
2. WHEN a finding is exported THEN WebReaper SHALL include evidence requests/responses, affected URLs, severity, confidence, and timestamps.
3. IF sensitive content is present in captured traffic THEN WebReaper SHALL support redaction rules before export.
4. WHEN exporting data THEN WebReaper SHALL support machine-readable formats and a human-readable report format.

### Requirement 14: Observability, Reliability, and Safety Controls

**User Story:** As an operator, I want robust guardrails and observability, so that I can run WebReaper safely on large or sensitive assessments.

#### Acceptance Criteria

1. WHILE any long-running job is active WebReaper SHALL emit structured logs, health metrics, and error counters for backend and workers.
2. WHEN a job crashes or is interrupted THEN WebReaper SHALL preserve partial progress and expose resumable or restart-safe behavior where feasible.
3. IF usage may violate configured safety policy (rate limits, blocked targets, destructive modules) THEN WebReaper SHALL block execution and report the violated rule.
4. WHERE legal/authorization boundaries matter WebReaper SHALL require explicit acknowledgement before active testing features are enabled.

### Requirement 15: Performance and Quality Benchmarks

**User Story:** As a product owner, I want measurable quality gates, so that "better than Screaming Frog and Burp" is defined by evidence instead of hype.

#### Acceptance Criteria

1. WHEN defining a release candidate THEN WebReaper SHALL include benchmark scenarios for crawl throughput, UI responsiveness, and scan module performance.
2. WHEN a core workflow is changed THEN WebReaper SHALL run automated tests covering crawler, API contracts, UI critical paths, and database migrations.
3. IF benchmark results regress beyond defined thresholds THEN WebReaper SHALL flag the release candidate as blocked until reviewed.
4. WHERE competitor comparison claims are made WebReaper SHALL base them on documented scenarios and versioned test conditions.

## Notes / Current Codebase Findings (Ground Truth for This Spec)

- Local checkout `/home/botuser/.openclaw/workspace-webreaper` matches `origin/main` at commit `06de77c9` but has significant uncommitted local work likely from prior Claude sessions.
- Uncommitted changes include deep extraction (`webreaper/deep_extractor.py`), expanded DB schema (`webreaper/database.py`), analysis APIs (`server/routes/analysis.py`), crawler integration (`webreaper/crawler.py`), and a large Data Explorer UI rewrite (`web/app/data/page.tsx`).
- Current codebase has strong crawl/data foundations but lacks a real intercepting proxy, Repeater/Intruder workflows, browser-rendered crawling, and migration-safe schema evolution.
