"""HTTP fetcher with stealth capabilities.

Supports two modes:
  - Stealth mode: curl_cffi with TLS fingerprint impersonation
  - Basic mode: aiohttp (original behavior)
"""

import asyncio
import random
import time
from collections import defaultdict
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse

import aiohttp
from fake_useragent import UserAgent

try:
    from curl_cffi.requests import AsyncSession as CurlSession
    from curl_cffi import CurlError
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    CurlSession = None
    CurlError = Exception

from .config import StealthConfig


class TokenBucket:
    """Token bucket rate limiter per domain."""

    def __init__(self, rate: float):
        self.rate = rate  # tokens per second
        self._buckets: Dict[str, float] = defaultdict(lambda: 1.0)
        self._last_refill: Dict[str, float] = defaultdict(time.monotonic)

    async def acquire(self, domain: str):
        """Wait until a token is available for this domain."""
        while True:
            now = time.monotonic()
            elapsed = now - self._last_refill[domain]
            self._buckets[domain] = min(1.0, self._buckets[domain] + elapsed * self.rate)
            self._last_refill[domain] = now

            if self._buckets[domain] >= 1.0:
                self._buckets[domain] -= 1.0
                return

            wait = (1.0 - self._buckets[domain]) / self.rate
            await asyncio.sleep(wait)


class StealthFetcher:
    """HTTP fetcher with stealth features.

    In stealth mode with curl_cffi available: uses TLS fingerprint impersonation.
    Otherwise: falls back to aiohttp with UA rotation.
    """

    IMPERSONATE_TARGETS = [
        "chrome120", "chrome124", "chrome131",
        "safari17_0", "safari18_0",
        "edge120", "edge124",
    ]

    def __init__(self, config: StealthConfig, rate_limit: float = 0.0):
        self.config = config
        self.rate_limit = rate_limit
        self.ua = UserAgent(fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        self.session = None
        self._curl_session: Optional["CurlSession"] = None
        self.request_count = 0
        self.circuit_count = 0
        self._rate_limiter: Optional[TokenBucket] = TokenBucket(rate_limit) if rate_limit > 0 else None
        self._current_impersonation = random.choice(self.IMPERSONATE_TARGETS)
        self._use_curl = HAS_CURL_CFFI and config.enabled

        self.screen_resolutions = [
            (1920, 1080), (1366, 768), (1440, 900), (1536, 864),
            (1280, 720), (1600, 900), (1280, 1024), (1680, 1050)
        ]
        self.color_depths = [24, 32]
        self.pixel_ratios = [1.0, 1.25, 1.5, 2.0]

    async def __aenter__(self):
        if self._use_curl:
            self._curl_session = CurlSession(
                impersonate=self._current_impersonation,
                timeout=30,
            )
        else:
            connector = self._build_connector()
            self.session = aiohttp.ClientSession(
                connector=connector,
                headers=self._base_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._curl_session:
            await self._curl_session.close()
            self._curl_session = None
        if self.session:
            await self.session.close()
            self.session = None

    def _build_connector(self) -> aiohttp.BaseConnector:
        if self.config.tor_enabled:
            try:
                from aiohttp_socks import ProxyConnector
                return ProxyConnector.from_url(self.config.tor_proxy, limit=100)
            except ImportError:
                # Fallback: plain connector, Tor proxy applied per-request
                return aiohttp.TCPConnector(limit=100, enable_cleanup_closed=True, force_close=True)
        return aiohttp.TCPConnector(limit=100, enable_cleanup_closed=True, ttl_dns_cache=300)

    def _base_headers(self) -> Dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    def _request_headers(self) -> Dict[str, str]:
        """Per-request headers (rotated). No session recreation needed."""
        headers: Dict[str, str] = {}
        if self.config.rotate_ua:
            headers["User-Agent"] = self.ua.random
        headers["Accept-Language"] = random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.9", "en;q=0.8"])
        return headers

    async def fetch(self, url: str, allow_redirects: bool = True) -> Tuple[int, Dict[str, Any], str]:
        """Fetch a URL with stealth features.

        Uses curl_cffi with TLS impersonation when in stealth mode,
        falls back to aiohttp for basic mode.
        """
        domain = urlparse(url).netloc

        # Rate limiting (per domain)
        if self._rate_limiter:
            await self._rate_limiter.acquire(domain)

        # Stealth delay (in addition to rate limiting when stealth enabled)
        if self.config.enabled:
            await self._apply_delay()

        # Rotate Tor circuit if needed
        if self.config.tor_enabled and self.request_count > 0 and self.request_count % self.config.circuit_rotate == 0:
            await self._rotate_tor_circuit()

        # Per-request header rotation (no session recreation)
        headers = self._request_headers()

        try:
            if self._curl_session:
                # curl_cffi path — TLS fingerprint impersonation active
                response = await self._curl_session.get(
                    url,
                    headers=headers,
                    allow_redirects=allow_redirects,
                    impersonate=self._current_impersonation,
                )
                self.request_count += 1
                return response.status_code, dict(response.headers), response.text
            else:
                # aiohttp path — basic mode
                proxy = None
                if self.config.tor_enabled:
                    try:
                        from aiohttp_socks import ProxyConnector  # noqa: F401
                    except ImportError:
                        proxy = self.config.tor_proxy

                async with self.session.get(
                    url,
                    allow_redirects=allow_redirects,
                    proxy=proxy,
                    headers=headers,
                    ssl=None,
                ) as response:
                    self.request_count += 1
                    status = response.status
                    resp_headers = dict(response.headers)
                    text = await response.text(errors="replace")
                    return status, resp_headers, text

        except asyncio.TimeoutError:
            return 0, {}, ""
        except (CurlError, aiohttp.ClientError, Exception) as e:
            return -1, {}, str(e)

    async def fetch_with_retry(self, url: str, max_retries: int = 3, allow_redirects: bool = True) -> Tuple[int, Dict[str, Any], str]:
        """Fetch with exponential backoff retry."""
        last_result = (-1, {}, "")
        for attempt in range(max_retries):
            status, headers, body = await self.fetch(url, allow_redirects)
            if status > 0:
                return status, headers, body
            last_result = (status, headers, body)
            if attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(delay)
                self.rotate_identity()
        return last_result

    def rotate_identity(self):
        """Rotate TLS fingerprint impersonation target."""
        self._current_impersonation = random.choice(self.IMPERSONATE_TARGETS)

    async def _apply_delay(self):
        delay = random.uniform(self.config.delay_min, self.config.delay_max)
        await asyncio.sleep(delay)

    async def _rotate_tor_circuit(self):
        if not self.config.tor_enabled:
            return
        try:
            from stem import Signal
            from stem.control import Controller

            with Controller.from_port(port=self.config.tor_control_port) as controller:
                if self.config.tor_password:
                    controller.authenticate(password=self.config.tor_password)
                else:
                    controller.authenticate()
                controller.signal(Signal.NEWNYM)
                self.circuit_count += 1
                await asyncio.sleep(2)
        except Exception:
            pass

    def get_fingerprint(self) -> Dict[str, Any]:
        screen = random.choice(self.screen_resolutions)
        return {
            "screen": {
                "width": screen[0],
                "height": screen[1],
                "availWidth": screen[0] - random.randint(0, 20),
                "availHeight": screen[1] - random.randint(40, 100),
                "colorDepth": random.choice(self.color_depths),
                "pixelRatio": random.choice(self.pixel_ratios),
            },
            "navigator": {
                "hardwareConcurrency": random.choice([2, 4, 6, 8, 12, 16]),
                "deviceMemory": random.choice([2, 4, 8, 16]),
                "maxTouchPoints": 0,
                "platform": random.choice(["Win32", "MacIntel", "Linux x86_64"]),
            },
            "timezone": random.choice([-8, -5, 0, 1, 8, 9]),
        }
