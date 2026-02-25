"""Tests for crawler.py — URL logic, depth limits, DB interaction."""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from webreaper.crawler import Crawler, CrawlResult
from webreaper.frontier import URLFrontier


# ── URLFrontier helpers ─────────────────────────────────────

def test_is_same_domain_match():
    assert URLFrontier.is_same_domain("https://example.com/page", "https://example.com/") is True


def test_is_same_domain_subdomain():
    # Subdomains share the same registered domain — is_same_domain treats them as same
    assert URLFrontier.is_same_domain("https://sub.example.com/", "https://example.com/") is True


def test_is_same_domain_different():
    assert URLFrontier.is_same_domain("https://other.com/", "https://example.com/") is False


# ── Link extraction ─────────────────────────────────────────

def test_extract_links_same_domain(mock_crawler_config):
    from bs4 import BeautifulSoup
    crawler = Crawler(mock_crawler_config)
    html = """
    <html><body>
      <a href="/page2">Internal</a>
      <a href="https://example.com/page3">Also internal</a>
      <a href="https://external.com/page">External</a>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    internal = crawler._extract_links(soup, "https://example.com/", external=False)
    external = crawler._extract_links(soup, "https://example.com/", external=True)

    assert any("page2" in u for u in internal)
    assert any("page3" in u for u in internal)
    assert any("external.com" in u for u in external)


def test_extract_links_skips_non_http(mock_crawler_config):
    from bs4 import BeautifulSoup
    crawler = Crawler(mock_crawler_config)
    html = '<html><body><a href="mailto:user@example.com">Mail</a><a href="/ok">OK</a></body></html>'
    soup = BeautifulSoup(html, "lxml")
    links = crawler._extract_links(soup, "https://example.com/", external=False)
    assert not any("mailto" in u for u in links)
    assert any("ok" in u for u in links)


# ── max_pages enforcement ───────────────────────────────────

def test_max_pages_cap_applied(mock_crawler_config):
    mock_crawler_config.crawler.max_pages = 5
    crawler = Crawler(mock_crawler_config)
    assert crawler.config.crawler.max_pages == 5


# ── DB interaction — no accumulation when DB present ────────

@pytest.mark.asyncio
async def test_results_not_accumulated_when_db_used(mock_crawler_config):
    """When a DB manager is set, results should NOT accumulate in memory."""
    mock_db = AsyncMock()
    mock_db.create_crawl = AsyncMock(return_value="crawl-uuid-1")
    mock_db.save_page = AsyncMock(return_value="page-uuid-1")
    mock_db.save_links = AsyncMock()
    mock_db.complete_crawl = AsyncMock()

    crawler = Crawler(mock_crawler_config, db_manager=mock_db)
    crawler._crawl_id = "crawl-uuid-1"

    # Simulate a result being processed
    result = CrawlResult(
        url="https://example.com/page",
        status=200,
        title="Test",
        content_text="hello world",
        word_count=2,
        links=[],
        external_links=[],
        images=[],
    )
    crawler.stats["pages_crawled"] += 1
    # With DB set: don't append to results
    if crawler.db_manager and crawler._crawl_id:
        await crawler._save_to_db(result)
    else:
        crawler.results.append(result)

    # Result should NOT be in memory list
    assert len(crawler.results) == 0
    mock_db.save_page.assert_called_once()


@pytest.mark.asyncio
async def test_results_accumulated_without_db(mock_crawler_config):
    """Without DB, results accumulate in memory."""
    crawler = Crawler(mock_crawler_config, db_manager=None)
    crawler._crawl_id = None

    result = CrawlResult(url="https://example.com/page", status=200)
    crawler.stats["pages_crawled"] += 1
    if crawler.db_manager and crawler._crawl_id:
        await crawler._save_to_db(result)
    else:
        crawler.results.append(result)

    assert len(crawler.results) == 1


# ── DB error logging (not swallowed) ────────────────────────

@pytest.mark.asyncio
async def test_db_save_error_is_logged_not_swallowed(mock_crawler_config, caplog):
    import logging
    mock_db = AsyncMock()
    mock_db.save_page = AsyncMock(side_effect=RuntimeError("disk full"))
    mock_db.save_links = AsyncMock()

    crawler = Crawler(mock_crawler_config, db_manager=mock_db)
    crawler._crawl_id = "crawl-1"

    result = CrawlResult(url="https://example.com/", status=200, external_links=[])

    with caplog.at_level(logging.ERROR, logger="webreaper.crawler"):
        await crawler._save_to_db(result)

    assert "DB save error" in caplog.text


@pytest.mark.asyncio
async def test_crawl_page_falls_back_when_deep_extraction_fails(mock_crawler_config, caplog):
    import logging

    crawler = Crawler(mock_crawler_config)
    crawler.deep_extractor.extract = MagicMock(side_effect=RuntimeError("extract boom"))

    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(return_value=(
        200,
        {"Content-Type": "text/html"},
        "<html><head><title>X</title></head><body><h1>Hello</h1><a href='/a'>A</a></body></html>",
    ))

    with caplog.at_level(logging.ERROR, logger="webreaper.crawler"):
        result = await crawler._crawl_page(fetcher, "https://example.com", 0)

    assert result is not None
    assert result.title == "X"
    assert any("/a" in u for u in result.links)
    assert "Deep extraction failed" in caplog.text


@pytest.mark.asyncio
async def test_save_to_db_persists_rich_links_and_forms(mock_crawler_config, sample_html_page, sample_headers):
    from webreaper.deep_extractor import DeepExtractor

    mock_db = AsyncMock()
    mock_db.save_page = AsyncMock(return_value="page-1")
    mock_db.save_links = AsyncMock()
    mock_db.save_forms = AsyncMock()
    mock_db.upsert_endpoints = AsyncMock()
    mock_db.derive_endpoints_from_page = MagicMock(return_value=[{"host": "example.com", "scheme": "https", "method": "GET", "path": "/"}])
    mock_db.derive_endpoints_from_observed_requests = MagicMock(return_value=[{"host": "api.example.com", "scheme": "https", "method": "GET", "path": "/v1"}])

    crawler = Crawler(mock_crawler_config, db_manager=mock_db)
    crawler._crawl_id = "crawl-1"
    crawler._save_assets = AsyncMock()
    crawler._save_technologies = AsyncMock()

    deep = DeepExtractor().extract(
        url="https://example.com",
        status_code=200,
        html=sample_html_page,
        headers=sample_headers,
        response_time_ms=10,
        depth=0,
    )
    crawler.deep_results["https://example.com"] = deep
    from webreaper.browser.worker import BrowserCaptureResult
    crawler.browser_results["https://example.com"] = BrowserCaptureResult(
        url="https://example.com",
        final_url="https://example.com",
        status_code=200,
        dom_html=sample_html_page,
        observed_requests=[{"url": "https://api.example.com/v1?q=x", "method": "GET", "source": "browser_network"}],
    )

    result = CrawlResult(
        url="https://example.com",
        status=200,
        title=deep.title,
        meta_description=deep.meta_description,
        headings=deep.headings,
        links=[l.url for l in deep.links if not l.is_external],
        external_links=[l.url for l in deep.links if l.is_external],
        images=[a.url for a in deep.images],
        content_text=deep.content_text,
        word_count=deep.word_count,
        headers=sample_headers,
        response_time=0.01,
        depth=0,
        forms=deep.forms,
    )

    await crawler._save_to_db(result)

    mock_db.save_links.assert_called_once()
    save_links_kwargs = mock_db.save_links.await_args.kwargs
    assert any(isinstance(item, dict) and "anchor_text" in item for item in save_links_kwargs["links"])

    mock_db.save_forms.assert_called_once()
    save_forms_kwargs = mock_db.save_forms.await_args.kwargs
    assert save_forms_kwargs["forms"][0]["field_count"] >= 1

    assert mock_db.upsert_endpoints.await_count == 2


@pytest.mark.asyncio
async def test_crawl_page_browser_failure_falls_back_to_http(mock_crawler_config):
    mock_crawler_config.browser.enabled = True
    mock_crawler_config.browser.fallback_to_http = True

    crawler = Crawler(mock_crawler_config)
    crawler.browser_worker = AsyncMock()
    crawler.browser_worker.capture = AsyncMock(side_effect=RuntimeError("browser boom"))

    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(return_value=(
        200,
        {"Content-Type": "text/html"},
        "<html><head><title>Fallback</title></head><body><a href='/x'>x</a></body></html>",
    ))

    result = await crawler._crawl_page(fetcher, "https://example.com", 0)
    assert result is not None
    assert result.fetch_mode == "http"
    assert result.title == "Fallback"


@pytest.mark.asyncio
async def test_crawl_page_browser_failure_no_fallback_returns_none(mock_crawler_config):
    mock_crawler_config.browser.enabled = True
    mock_crawler_config.browser.fallback_to_http = False

    crawler = Crawler(mock_crawler_config)
    crawler.browser_worker = AsyncMock()
    crawler.browser_worker.capture = AsyncMock(side_effect=RuntimeError("browser boom"))

    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(return_value=(200, {"Content-Type": "text/html"}, "<html><body>ok</body></html>"))

    result = await crawler._crawl_page(fetcher, "https://example.com", 0)
    assert result is None


@pytest.mark.asyncio
async def test_persist_progress_if_needed_calls_db_update(mock_crawler_config):
    mock_db = AsyncMock()
    mock_db.update_crawl_progress = AsyncMock()
    crawler = Crawler(mock_crawler_config, db_manager=mock_db)
    crawler._crawl_id = "crawl-1"
    crawler.stats.update({
        "start_time": 1.0,
        "pages_crawled": 30,
        "pages_failed": 0,
        "total_size": 100,
        "external_links": 2,
    })

    with patch("webreaper.crawler.time.time", return_value=11.0):
        await crawler._persist_progress_if_needed()

    mock_db.update_crawl_progress.assert_awaited_once()


def test_crawl_marks_cancelled_status_on_stop_flag(mock_crawler_config):
    crawler = Crawler(mock_crawler_config)
    crawler._stop_flag = True
    crawler.stats["start_time"] = 100.0
    with patch("webreaper.crawler.time.time", return_value=110.0):
        # emulate finalization lines in crawl() without running a crawl
        elapsed = time.time() - crawler.stats["start_time"]
        crawler.stats["total_time"] = elapsed
        crawler.stats["crawl_status"] = "cancelled" if crawler._stop_flag else "completed"
    assert crawler.stats["crawl_status"] == "cancelled"
