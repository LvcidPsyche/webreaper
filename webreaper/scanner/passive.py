from __future__ import annotations

from typing import Any

from webreaper.modules.security import SecurityScanner
from .contracts import ScanContext


class PassiveScannerModule:
    name = 'legacy-passive'

    def run(self, scanner: SecurityScanner, ctx: ScanContext) -> list[dict[str, Any]]:
        return scanner.scan(ctx.url, ctx.headers, ctx.body, ctx.forms)


class TechnologyFingerprintModule:
    name = 'tech-fingerprint'

    def run(self, scanner: SecurityScanner, ctx: ScanContext) -> dict[str, Any]:
        return scanner.fingerprint_tech(ctx.url, ctx.headers, ctx.body)
