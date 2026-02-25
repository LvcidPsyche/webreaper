# WebReaper Local Regression + Benchmark Harness

## Critical workflow regression

Use the smoke script for release-gating basics:

```bash
./scripts/regression_smoke.sh
```

Covers:
- Realtime contracts (SSE/WS)
- Proxy / Repeater / Intruder backend flows
- Full backend tests
- Frontend TypeScript typecheck

## Timing benchmarks

```bash
./scripts/benchmark_webreaper.py --max-seconds 15
```

The script writes `benchmarks.latest.json` and can fail on thresholds.

## Competitor comparison fixture data

Versioned fixture baseline lives in:
- `tests/fixtures/benchmarks/competitor_baseline.json`

Use this to track internal improvements against target metrics inspired by Screaming Frog / Burp-style workflows (startup latency, request replay throughput, history filter response time).
