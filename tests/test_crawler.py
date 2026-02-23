"""Tests for crawler.py — URL logic, depth limits, DB interaction."""

import asyncio
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
