from __future__ import annotations

from .contracts import ScanContext, ScanOutput
from .passive import PassiveScannerModule, TechnologyFingerprintModule
from .active import ActiveScannerModule


class SecurityScanEngine:
    """Adapter-based scanning engine wrapping legacy scanner implementation."""

    def __init__(self, *, auto_attack: bool = False):
        from webreaper.modules.security import SecurityScanner  # lazy import for test patching / pluggable swaps
        self.scanner = SecurityScanner(auto_attack=auto_attack)
        self.passive_modules = [PassiveScannerModule()]
        self.tech_modules = [TechnologyFingerprintModule()]
        self.active_modules = [ActiveScannerModule()]

    async def run(self, ctx: ScanContext, *, http_session=None) -> ScanOutput:
        out = ScanOutput()
        for module in self.passive_modules:
            out.findings.extend(module.run(self.scanner, ctx))
            out.passive_modules.append(module.name)
        tech: dict = {}
        for module in self.tech_modules:
            data = module.run(self.scanner, ctx)
            if isinstance(data, dict):
                for k, v in data.items():
                    tech.setdefault(k, [])
                    if isinstance(v, list):
                        tech[k].extend(v)
                    elif v:
                        tech[k].append(v)
        out.technology = {k: sorted({str(i) for i in v if i}) for k, v in tech.items() if v}
        if ctx.auto_attack and http_session is not None:
            for module in self.active_modules:
                out.findings.extend(await module.run(self.scanner, ctx, http_session))
                out.active_modules.append(module.name)
        return out
