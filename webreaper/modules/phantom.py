"""Phantom Tap — Hidden API Discovery.

Intercepts XHR/Fetch requests during page load to discover undocumented APIs.
Catalogs endpoints, params, auth tokens, and response schemas.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("webreaper.phantom")


@dataclass
class APIEndpoint:
    """A discovered API endpoint."""
    url: str
    method: str
    path: str
    query_params: dict = field(default_factory=dict)
    request_headers: dict = field(default_factory=dict)
    response_status: int = 0
    response_headers: dict = field(default_factory=dict)
    response_body_sample: str = ""
    response_schema: dict = field(default_factory=dict)
    auth_type: Optional[str] = None  # bearer, api_key, cookie, basic
    auth_header: Optional[str] = None
    content_type: str = ""
    direct_access: bool = False  # Can be hit without browser


class PhantomTap:
    """Discovers hidden APIs by intercepting network requests during page load."""

    def __init__(self):
        self._endpoints: list[APIEndpoint] = []
        self._seen_urls: set[str] = set()

    async def discover(self, url: str) -> list[APIEndpoint]:
        """Load a page in a headless browser and intercept all API calls."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright required for Phantom Tap — install with: pip install playwright")
            return []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Intercept all network requests
            page.on("response", lambda resp: asyncio.create_task(self._on_response(resp)))

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                # Scroll to trigger lazy loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Page load issue: {e}")
            finally:
                await browser.close()

        return self._endpoints

    async def _on_response(self, response):
        """Process intercepted network responses."""
        url = response.url
        if url in self._seen_urls:
            return
        self._seen_urls.add(url)

        # Only interested in API-like responses
        content_type = response.headers.get("content-type", "")
        if not any(t in content_type for t in ["json", "xml", "protobuf", "grpc"]):
            return

        parsed = urlparse(url)
        request = response.request

        endpoint = APIEndpoint(
            url=url,
            method=request.method,
            path=parsed.path,
            query_params=parse_qs(parsed.query),
            request_headers=dict(request.headers),
            response_status=response.status,
            response_headers=dict(response.headers),
            content_type=content_type,
        )

        # Detect auth type
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            endpoint.auth_type = "bearer"
            endpoint.auth_header = auth_header[:20] + "..."
        elif auth_header.lower().startswith("basic "):
            endpoint.auth_type = "basic"
        elif "x-api-key" in request.headers:
            endpoint.auth_type = "api_key"
        elif "cookie" in request.headers:
            endpoint.auth_type = "cookie"

        # Sample response body
        try:
            body = await response.text()
            endpoint.response_body_sample = body[:2000]
            if "json" in content_type:
                endpoint.response_schema = self._infer_schema(json.loads(body))
        except Exception:
            pass

        self._endpoints.append(endpoint)

    def _infer_schema(self, data, max_depth: int = 3) -> dict:
        """Infer a JSON schema from a response body."""
        if max_depth <= 0:
            return {"type": type(data).__name__}

        if isinstance(data, dict):
            return {
                "type": "object",
                "properties": {
                    k: self._infer_schema(v, max_depth - 1)
                    for k, v in list(data.items())[:20]
                },
            }
        elif isinstance(data, list):
            if data:
                return {"type": "array", "items": self._infer_schema(data[0], max_depth - 1)}
            return {"type": "array", "items": {}}
        elif isinstance(data, bool):
            return {"type": "boolean"}
        elif isinstance(data, int):
            return {"type": "integer"}
        elif isinstance(data, float):
            return {"type": "number"}
        elif isinstance(data, str):
            return {"type": "string"}
        return {"type": type(data).__name__}

    async def verify_direct_access(self, endpoint: APIEndpoint) -> bool:
        """Test if an API endpoint works without a browser session."""
        import httpx
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            if endpoint.auth_type != "cookie":
                # Include auth header if not cookie-based
                if endpoint.auth_header:
                    headers["Authorization"] = endpoint.auth_header

            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    endpoint.method,
                    endpoint.url,
                    headers=headers,
                    timeout=10,
                )
                endpoint.direct_access = resp.status_code == endpoint.response_status
                return endpoint.direct_access
        except Exception:
            return False

    def get_api_map(self) -> dict:
        """Return structured API map of all discovered endpoints."""
        by_domain: dict[str, list] = {}
        for ep in self._endpoints:
            domain = urlparse(ep.url).netloc
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append({
                "method": ep.method,
                "path": ep.path,
                "auth": ep.auth_type,
                "status": ep.response_status,
                "content_type": ep.content_type,
                "direct_access": ep.direct_access,
                "schema": ep.response_schema,
            })
        return by_domain
