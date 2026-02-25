"""Playwright-backed browser page capture for JS-rendered crawl mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BrowserCaptureResult:
    url: str
    final_url: str
    status_code: Optional[int] = None
    dom_html: str = ""
    observed_requests: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class BrowserCrawlerWorker:
    """Captures browser-rendered DOM and network observations using Playwright."""

    async def capture(self, url: str, config) -> BrowserCaptureResult:
        # Lazy import so environments without Playwright browsers can still use
        # HTTP-only mode and run most tests.
        from playwright.async_api import async_playwright

        observed: List[Dict[str, Any]] = []
        status_code: Optional[int] = None
        final_url = url

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            blocked = {r.lower() for r in getattr(config, "blocked_resource_types", [])}

            if blocked:
                async def route_handler(route):
                    try:
                        resource_type = getattr(route.request, "resource_type", None)
                        if resource_type and resource_type.lower() in blocked:
                            await route.abort()
                            return
                    except Exception:
                        pass
                    await route.continue_()

                await context.route("**/*", route_handler)

            def on_request(req):
                if len(observed) >= getattr(config, "max_requests_per_page", 200):
                    return
                observed.append({
                    "url": req.url,
                    "method": req.method,
                    "resource_type": getattr(req, "resource_type", None),
                    "source": "browser_network",
                })

            def on_response(resp):
                nonlocal status_code
                try:
                    req = resp.request
                    if resp.url == page.url and status_code is None:
                        status_code = resp.status
                    # annotate latest matching request entry with response status
                    for item in reversed(observed):
                        if item.get("url") == resp.url and item.get("method") == getattr(req, "method", None):
                            item["status_code"] = resp.status
                            break
                except Exception:
                    return

            page.on("request", on_request)
            page.on("response", on_response)

            response = await page.goto(
                url,
                wait_until=getattr(config, "wait_until", "domcontentloaded"),
                timeout=getattr(config, "timeout_ms", 15000),
            )
            if response and status_code is None:
                status_code = response.status

            final_url = page.url
            dom_html = await page.content()

            if getattr(config, "capture_screenshots", False):
                # Placeholder for later artifact persistence. Capture bytes to ensure
                # render path is exercised when enabled.
                await page.screenshot(type="png")

            await context.close()
            await browser.close()

        return BrowserCaptureResult(
            url=url,
            final_url=final_url,
            status_code=status_code,
            dom_html=dom_html,
            observed_requests=observed,
        )

