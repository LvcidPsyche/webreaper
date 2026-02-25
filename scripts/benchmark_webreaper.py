#!/usr/bin/env python3
"""Small local benchmark harness for WebReaper development slices.

Measures selected test commands and emits JSON timings. Thresholds can fail the run.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def run_cmd(cmd: str) -> dict:
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    dt = time.perf_counter() - t0
    return {
        'cmd': cmd,
        'seconds': round(dt, 3),
        'returncode': proc.returncode,
        'stdout_tail': proc.stdout[-1000:],
        'stderr_tail': proc.stderr[-1000:],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-seconds', type=float, default=None, help='Fail if any command exceeds this duration')
    ap.add_argument('--out', default='benchmarks.latest.json')
    ap.add_argument('cmds', nargs='*', help='Commands to benchmark')
    args = ap.parse_args()

    default_cmds = [
        './.venv/bin/pytest -q tests/test_proxy_routes.py tests/test_repeater_routes.py tests/test_intruder_routes.py',
        'cd web && npx tsc --noEmit',
    ]
    cmds = args.cmds or default_cmds

    results = [run_cmd(c) for c in cmds]
    summary = {
        'generated_at': time.time(),
        'cwd': str(Path.cwd()),
        'results': results,
        'all_passed': all(r['returncode'] == 0 for r in results),
    }
    if args.max_seconds is not None:
        summary['threshold_seconds'] = args.max_seconds
        summary['threshold_passed'] = all(r['seconds'] <= args.max_seconds for r in results)
    Path(args.out).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    if not summary['all_passed']:
        raise SystemExit(1)
    if args.max_seconds is not None and not summary.get('threshold_passed', True):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
