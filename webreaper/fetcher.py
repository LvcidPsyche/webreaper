"""HTTP fetcher with stealth capabilities."""

import asyncio
import random
import time
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse

import aiohttp
from fake_useragent import UserAgent

from .config import StealthConfig


class StealthFetcher:
    """HTTP fetcher with stealth features."""
    
    def __init__(self, config: StealthConfig):
        self.config = config
        self.ua = UserAgent(fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_count = 0
        self.circuit_count = 0
        
        # Browser fingerprint rotation
        self.screen_resolutions = [
            (1920, 1080), (1366, 768), (1440, 900), (1536, 864),
            (1280, 720), (1600, 900), (1280, 1024), (1680, 1050)
        ]
        self.color_depths = [24, 32]
        self.pixel_ratios = [1.0, 1.25, 1.5, 2.0]
    
    async def __aenter__(self):
        """Async context manager entry."""
        connector = await self._get_connector()
        
        headers = self._get_headers()
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _get_connector(self) -> aiohttp.BaseConnector:
        """Get appropriate connector based on config."""
        if self.config.tor_enabled:
            # Use Tor proxy
            return aiohttp.TCPConnector(
                limit=100,
                enable_cleanup_closed=True,
                force_close=True,
            )
        else:
            return aiohttp.TCPConnector(
                limit=100,
                enable_cleanup_closed=True,
                ttl_dns_cache=300,
            )
    
    def _get_headers(self) -> Dict[str, str]:
        """Generate stealth headers."""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.9", "en;q=0.8"]),
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
        
        if self.config.rotate_ua:
            headers["User-Agent"] = self.ua.random
        
        return headers
    
    async def fetch(self, url: str, allow_redirects: bool = True) -> Tuple[int, Dict[str, Any], str]:
        """Fetch a URL with stealth features."""
        # Apply delay if stealth enabled
        if self.config.enabled:
            await self._apply_delay()
        
        # Rotate circuit if using Tor
        if self.config.tor_enabled and self.request_count % self.config.circuit_rotate == 0:
            await self._rotate_tor_circuit()
        
        # Randomize headers for each request
        if self.config.enabled and self.config.rotate_ua:
            if self.session:
                await self.session.close()
            self.session = aiohttp.ClientSession(
                connector=await self._get_connector(),
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=30)
            )
        
        # Build proxy config for Tor
        proxy = None
        if self.config.tor_enabled:
            proxy = self.config.tor_proxy
        
        try:
            async with self.session.get(
                url,
                allow_redirects=allow_redirects,
                proxy=proxy,
                ssl=False if self.config.tor_enabled else None  # Some Tor exits have SSL issues
            ) as response:
                self.request_count += 1
                
                status = response.status
                headers = dict(response.headers)
                text = await response.text()
                
                return status, headers, text
                
        except asyncio.TimeoutError:
            return 0, {}, ""
        except Exception as e:
            return -1, {}, str(e)
    
    async def _apply_delay(self):
        """Apply random delay between requests."""
        delay = random.uniform(self.config.delay_min, self.config.delay_max)
        await asyncio.sleep(delay)
    
    async def _rotate_tor_circuit(self):
        """Rotate Tor circuit for new identity."""
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
                
                # Wait for circuit to build
                await asyncio.sleep(2)
        except Exception:
            # Tor control failed, continue anyway
            pass
    
    def get_fingerprint(self) -> Dict[str, Any]:
        """Generate a random browser fingerprint."""
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
            "timezone": random.choice([-8, -5, 0, 1, 8, 9]),  # Offset from UTC
        }
