"""URL frontier for managing crawl queue."""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Set
from urllib.parse import urljoin, urlparse
import tldextract


@dataclass(order=True)
class URLTask:
    """A URL to be crawled with priority."""
    priority: int
    depth: int = field(compare=False)
    url: str = field(compare=False)
    parent: Optional[str] = field(default=None, compare=False)


class URLFrontier:
    """Manages the URL crawling queue with deduplication."""
    
    def __init__(self, max_size: int = 100000):
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self.seen_urls: Set[str] = set()
        self.seen_lock = asyncio.Lock()
        self.total_seen = 0
        self.total_queued = 0
    
    async def add(self, url: str, depth: int = 0, priority: int = 5, parent: Optional[str] = None) -> bool:
        """Add a URL to the frontier. Returns True if added, False if already seen."""
        # Normalize URL
        url = self._normalize_url(url)
        
        async with self.seen_lock:
            if url in self.seen_urls:
                return False
            self.seen_urls.add(url)
            self.total_seen += 1
        
        # Lower priority number = higher priority
        # Depth 0 = highest priority (start URLs)
        task = URLTask(priority=depth * 10 + priority, depth=depth, url=url, parent=parent)
        
        try:
            await self.queue.put(task)
            self.total_queued += 1
            return True
        except asyncio.QueueFull:
            return False
    
    async def get(self) -> Optional[URLTask]:
        """Get the next URL to crawl."""
        try:
            return await self.queue.get()
        except asyncio.QueueEmpty:
            return None
    
    def seen(self, url: str) -> bool:
        """Check if a URL has been seen."""
        url = self._normalize_url(url)
        return url in self.seen_urls
    
    def qsize(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()
    
    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize URL for deduplication."""
        # Remove fragment
        if "#" in url:
            url = url.split("#")[0]
        
        # Ensure consistent trailing slash handling
        parsed = urlparse(url)
        if not parsed.path:
            url = url + "/"
        
        return url
    
    @staticmethod
    def is_same_domain(url1: str, url2: str) -> bool:
        """Check if two URLs are on the same domain."""
        ext1 = tldextract.extract(url1)
        ext2 = tldextract.extract(url2)
        return ext1.registered_domain == ext2.registered_domain
    
    @staticmethod
    def is_subdomain(url: str, base_url: str) -> bool:
        """Check if URL is a subdomain of base_url."""
        ext1 = tldextract.extract(url)
        ext2 = tldextract.extract(base_url)
        
        # Same registered domain
        if ext1.registered_domain != ext2.registered_domain:
            return False
        
        # URL domain ends with base domain
        domain1 = f"{ext1.subdomain}.{ext1.registered_domain}".lstrip(".")
        domain2 = f"{ext2.subdomain}.{ext2.registered_domain}".lstrip(".")
        
        return domain1 == domain2 or domain1.endswith("." + domain2)
