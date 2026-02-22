"""robots.txt fetcher and checker."""

import asyncio
from typing import Dict, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class RobotsCache:
    """Async-safe robots.txt cache with per-domain entries."""

    DEFAULT_UA = "WebReaper/1.0"

    def __init__(self, user_agent: str = DEFAULT_UA):
        self.user_agent = user_agent
        self._cache: Dict[str, Optional[RobotFileParser]] = {}
        self._lock = asyncio.Lock()

    async def allowed(self, url: str, fetcher) -> bool:
        """Return True if crawling this URL is allowed."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        async with self._lock:
            if domain not in self._cache:
                self._cache[domain] = await self._fetch(domain, fetcher)

        rp = self._cache[domain]
        if rp is None:
            return True  # Fetch failed — assume allowed

        return rp.can_fetch(self.user_agent, url)

    async def _fetch(self, domain: str, fetcher) -> Optional[RobotFileParser]:
        """Fetch and parse robots.txt for a domain."""
        robots_url = f"{domain}/robots.txt"
        try:
            status, _, text = await fetcher.fetch(robots_url)
            if status != 200 or not text:
                return None

            rp = RobotFileParser()
            rp.parse(text.splitlines())
            return rp
        except Exception:
            return None

    def get_crawl_delay(self, url: str) -> float:
        """Return crawl delay for domain if specified in robots.txt."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._cache.get(domain)
        if rp is None:
            return 0.0
        delay = rp.crawl_delay(self.user_agent)
        return float(delay) if delay else 0.0
