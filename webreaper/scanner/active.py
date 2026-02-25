from __future__ import annotations

from webreaper.modules.security import SecurityScanner
from .contracts import ScanContext


class ActiveScannerModule:
    name = 'legacy-active'

    async def run(self, scanner: SecurityScanner, ctx: ScanContext, session):
        if not ctx.auto_attack:
            return []
        return await scanner.active_scan(ctx.url, ctx.forms, session=session, aggressive=ctx.aggressive)
