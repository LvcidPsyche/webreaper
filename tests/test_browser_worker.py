"""Tests for Playwright browser capture worker (mocked async_playwright)."""

import sys
from types import ModuleType, SimpleNamespace

import pytest

from webreaper.browser.worker import BrowserCrawlerWorker
from webreaper.config import BrowserConfig


class _FakeRequest:
    def __init__(self, url: str, method: str = "GET", resource_type: str = "document"):
        self.url = url
        self.method = method
        self.resource_type = resource_type


class _FakeResponse:
    def __init__(self, url: str, status: int, request: _FakeRequest):
        self.url = url
        self.status = status
        self.request = request


class _FakePage:
    def __init__(self):
        self.url = "https://example.com/final"
        self._handlers = {"request": [], "response": []}

    def on(self, event, handler):
        self._handlers[event].append(handler)

    async def goto(self, url, wait_until=None, timeout=None):
        req_main = _FakeRequest(url, "GET", "document")
        req_api = _FakeRequest("https://example.com/api/data?q=1", "GET", "xhr")
        for h in self._handlers["request"]:
            h(req_main)
            h(req_api)
        for h in self._handlers["response"]:
            h(_FakeResponse(url, 200, req_main))
            h(_FakeResponse(req_api.url, 200, req_api))
        return SimpleNamespace(status=200)

    async def content(self):
        return "<html><body><div id='app'>rendered</div></body></html>"

    async def screenshot(self, type="png"):
        return b"\x89PNG"


class _FakeContext:
    def __init__(self):
        self._page = _FakePage()

    async def new_page(self):
        return self._page

    async def route(self, pattern, handler):
        return None

    async def close(self):
        return None


class _FakeBrowser:
    async def new_context(self):
        return _FakeContext()

    async def close(self):
        return None


class _FakeChromium:
    async def launch(self, headless=True):
        return _FakeBrowser()


class _FakePlaywrightCM:
    async def __aenter__(self):
        return SimpleNamespace(chromium=_FakeChromium())

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _install_fake_playwright(monkeypatch):
    mod = ModuleType("playwright.async_api")
    mod.async_playwright = lambda: _FakePlaywrightCM()
    monkeypatch.setitem(sys.modules, "playwright.async_api", mod)


@pytest.mark.asyncio
async def test_browser_worker_capture_collects_dom_and_requests(monkeypatch):
    _install_fake_playwright(monkeypatch)

    worker = BrowserCrawlerWorker()
    cfg = BrowserConfig(enabled=True, capture_screenshots=True)
    result = await worker.capture("https://example.com/start", cfg)

    assert result.final_url == "https://example.com/final"
    assert result.status_code == 200
    assert "rendered" in result.dom_html
    assert len(result.observed_requests) >= 2
    assert any(r["url"].endswith("/api/data?q=1") for r in result.observed_requests)

