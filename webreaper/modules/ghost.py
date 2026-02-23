"""Ghost Protocol — Anti-detection intelligence system.

Generates coherent browser identities where TLS fingerprint, HTTP/2 settings,
canvas/WebGL output, timezone, locale, and screen resolution are all internally
consistent. Detects blocks and adapts automatically.
"""

import asyncio
import random
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class BlockType(Enum):
    CAPTCHA_RECAPTCHA = "recaptcha"
    CAPTCHA_HCAPTCHA = "hcaptcha"
    CAPTCHA_TURNSTILE = "turnstile"
    CLOUDFLARE_CHALLENGE = "cloudflare_challenge"
    CLOUDFLARE_BLOCK = "cloudflare_block"
    RATE_LIMITED = "rate_limited"
    IP_BANNED = "ip_banned"
    HONEYPOT = "honeypot"
    SOFT_BLOCK = "soft_block"
    UNKNOWN = "unknown"


@dataclass
class BrowserIdentity:
    """A coherent browser identity — all fields are internally consistent."""
    name: str
    user_agent: str
    impersonate_target: str
    platform: str
    os_version: str
    screen_width: int
    screen_height: int
    color_depth: int
    pixel_ratio: float
    timezone: str
    locale: str
    language: str
    hardware_concurrency: int
    device_memory: int
    webgl_vendor: str
    webgl_renderer: str
    fonts: list[str] = field(default_factory=list)


IDENTITY_PROFILES = [
    {
        "name": "chrome_windows_us",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "impersonate_target": "chrome131",
        "platform": "Win32",
        "os_version": "Windows 10",
        "screen_width": 1920, "screen_height": 1080,
        "color_depth": 24, "pixel_ratio": 1.0,
        "timezone": "America/New_York",
        "locale": "en-US", "language": "en-US,en;q=0.9",
        "hardware_concurrency": 8, "device_memory": 8,
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "name": "chrome_mac_us",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "impersonate_target": "chrome131",
        "platform": "MacIntel",
        "os_version": "macOS 14.2",
        "screen_width": 2560, "screen_height": 1440,
        "color_depth": 30, "pixel_ratio": 2.0,
        "timezone": "America/Los_Angeles",
        "locale": "en-US", "language": "en-US,en;q=0.9",
        "hardware_concurrency": 10, "device_memory": 16,
        "webgl_vendor": "Apple",
        "webgl_renderer": "Apple M2 Pro",
    },
    {
        "name": "safari_mac_us",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        "impersonate_target": "safari18_0",
        "platform": "MacIntel",
        "os_version": "macOS 15.0",
        "screen_width": 1920, "screen_height": 1080,
        "color_depth": 30, "pixel_ratio": 2.0,
        "timezone": "America/Chicago",
        "locale": "en-US", "language": "en-US,en;q=0.9",
        "hardware_concurrency": 8, "device_memory": 8,
        "webgl_vendor": "Apple",
        "webgl_renderer": "Apple M1",
    },
    {
        "name": "chrome_windows_eu",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "impersonate_target": "chrome124",
        "platform": "Win32",
        "os_version": "Windows 11",
        "screen_width": 1920, "screen_height": 1200,
        "color_depth": 24, "pixel_ratio": 1.25,
        "timezone": "Europe/London",
        "locale": "en-GB", "language": "en-GB,en;q=0.9",
        "hardware_concurrency": 12, "device_memory": 16,
        "webgl_vendor": "Google Inc. (AMD)",
        "webgl_renderer": "ANGLE (AMD, AMD Radeon RX 7800 XT Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "name": "edge_windows_us",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "impersonate_target": "edge124",
        "platform": "Win32",
        "os_version": "Windows 11",
        "screen_width": 2560, "screen_height": 1440,
        "color_depth": 24, "pixel_ratio": 1.5,
        "timezone": "America/Denver",
        "locale": "en-US", "language": "en-US,en;q=0.9",
        "hardware_concurrency": 16, "device_memory": 32,
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
]


class GhostProtocol:
    """Anti-detection intelligence system with adaptive evasion."""

    def __init__(self):
        self._identities = [BrowserIdentity(**p) for p in IDENTITY_PROFILES]
        self._current: Optional[BrowserIdentity] = None
        self._block_log: list[dict] = []
        self._domain_strategies: dict[str, dict] = {}

    def get_identity(self) -> BrowserIdentity:
        """Get a random coherent browser identity."""
        self._current = random.choice(self._identities)
        return self._current

    def rotate_identity(self) -> BrowserIdentity:
        """Get a NEW identity different from current."""
        available = [i for i in self._identities if i != self._current]
        self._current = random.choice(available) if available else random.choice(self._identities)
        return self._current

    def detect_block(self, status_code: int, headers: dict, body: str) -> Optional[BlockType]:
        """Analyze response to detect block type."""
        if status_code == 403 and ("cf-ray" in headers.get("server", "").lower() or
                                    "cloudflare" in body.lower()):
            if "challenge-platform" in body or "turnstile" in body.lower():
                return BlockType.CLOUDFLARE_CHALLENGE
            return BlockType.CLOUDFLARE_BLOCK

        if status_code == 429:
            return BlockType.RATE_LIMITED

        if "recaptcha" in body.lower() or "g-recaptcha" in body:
            return BlockType.CAPTCHA_RECAPTCHA
        if "hcaptcha" in body.lower() or "h-captcha" in body:
            return BlockType.CAPTCHA_HCAPTCHA
        if "challenges.cloudflare.com" in body:
            return BlockType.CAPTCHA_TURNSTILE

        if status_code == 200 and self._is_honeypot(body):
            return BlockType.HONEYPOT

        if status_code == 200 and self._is_soft_block(body):
            return BlockType.SOFT_BLOCK

        return None

    def _is_honeypot(self, body: str) -> bool:
        """Detect AI-generated honeypot pages."""
        indicators = 0
        if body.count("<a ") < 3:
            indicators += 1
        if len(body) < 500:
            indicators += 1
        if body.count("lorem ipsum") > 0:
            indicators += 2
        return indicators >= 2

    def _is_soft_block(self, body: str) -> bool:
        """Detect soft blocks (200 OK but blocking content)."""
        block_phrases = [
            "access denied", "please verify you are human",
            "automated access", "bot detected", "unusual traffic",
            "please complete the security check",
        ]
        body_lower = body.lower()
        return any(phrase in body_lower for phrase in block_phrases)

    def log_block(self, domain: str, block_type: BlockType, identity: BrowserIdentity):
        """Log a block event for learning."""
        self._block_log.append({
            "domain": domain,
            "block_type": block_type.value,
            "identity": identity.name,
        })

    def get_proxy_stats(self, pool: "ProxyPool") -> list:
        """Return proxy health stats from a ProxyPool (for API/dashboard)."""
        return pool.get_stats()

    def get_strategy(self, domain: str) -> dict:
        """Get recommended strategy for a domain based on past blocks."""
        blocks = [b for b in self._block_log if b["domain"] == domain]
        if not blocks:
            return {"stealth_level": "standard", "delay_min": 1.0, "delay_max": 3.0}

        cf_blocks = [b for b in blocks if "cloudflare" in b["block_type"]]
        if cf_blocks:
            return {
                "stealth_level": "maximum",
                "delay_min": 3.0,
                "delay_max": 8.0,
                "use_browser": True,
                "rotate_every": 5,
            }

        rate_blocks = [b for b in blocks if b["block_type"] == "rate_limited"]
        if rate_blocks:
            return {
                "stealth_level": "high",
                "delay_min": 5.0,
                "delay_max": 15.0,
                "rotate_every": 3,
            }

        return {"stealth_level": "high", "delay_min": 2.0, "delay_max": 5.0}


# ── Proxy Pool ───────────────────────────────────────────


@dataclass
class ProxyConfig:
    url: str
    type: str  # "tor", "residential", "datacenter", "custom"
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None


class ProxyPool:
    """Health-based proxy rotation with adaptive selection."""

    def __init__(self):
        self._proxies: list[ProxyConfig] = []
        self._health: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    def add_proxy(self, proxy: ProxyConfig):
        self._proxies.append(proxy)
        self._health[proxy.url] = {
            "success": 0, "fail": 0, "last_used": 0, "avg_latency": 0,
        }

    def add_tor(self, proxy_url: str = "socks5://127.0.0.1:9050"):
        self.add_proxy(ProxyConfig(url=proxy_url, type="tor"))

    async def get_proxy(self, domain: Optional[str] = None) -> Optional[ProxyConfig]:
        """Get healthiest available proxy."""
        if not self._proxies:
            return None

        async with self._lock:
            scored = []
            for p in self._proxies:
                h = self._health[p.url]
                total = h["success"] + h["fail"]
                if total == 0:
                    score = 1.0
                else:
                    success_rate = h["success"] / total
                    latency_factor = 1 / max(h["avg_latency"], 0.1)
                    score = success_rate * latency_factor
                scored.append((score, p))

            scored.sort(key=lambda x: x[0], reverse=True)
            top = scored[:min(3, len(scored))]
            weights = [s[0] + 0.1 for s in top]
            selected = random.choices(top, weights=weights, k=1)[0][1]
            return selected

    def report_success(self, proxy_url: str, latency_ms: float):
        if proxy_url in self._health:
            h = self._health[proxy_url]
            h["success"] += 1
            total = h["success"] + h["fail"]
            h["avg_latency"] = (h["avg_latency"] * (total - 1) + latency_ms) / total

    def report_failure(self, proxy_url: str):
        if proxy_url in self._health:
            self._health[proxy_url]["fail"] += 1

    def get_stats(self) -> list[dict]:
        """Return health stats for all proxies."""
        stats = []
        for p in self._proxies:
            h = self._health[p.url]
            total = h["success"] + h["fail"]
            stats.append({
                "url": p.url,
                "type": p.type,
                "success_rate": h["success"] / max(total, 1),
                "total_requests": total,
                "avg_latency_ms": round(h["avg_latency"], 1),
            })
        return stats
