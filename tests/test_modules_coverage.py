"""Tests for untested modules — fingerprints, echo, missions, vault, phantom, blogwatcher, monitor, reporter.

Covers pure logic (no network). Network-dependent methods tested with mocks.
"""

import asyncio
import json
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ──────────────────────────────────────────────────────────────────────
# BrowserFingerprints
# ──────────────────────────────────────────────────────────────────────

class TestBrowserFingerprints:
    def test_random_fingerprint_structure(self):
        from webreaper.utils.fingerprints import BrowserFingerprints

        fp = BrowserFingerprints.get_random_fingerprint()
        assert "user_agent" in fp
        assert "screen" in fp
        assert "navigator" in fp
        assert "webgl" in fp
        assert "timezone" in fp
        assert fp["screen"]["width"] > 0
        assert fp["screen"]["height"] > 0
        assert fp["navigator"]["cookieEnabled"] is True

    def test_chrome_fingerprint(self):
        from webreaper.utils.fingerprints import BrowserFingerprints

        fp = BrowserFingerprints.get_chrome_fingerprint()
        assert "Chrome" in fp["user_agent"]
        assert fp["navigator"]["platform"] == "Win32"
        assert fp["screen"]["colorDepth"] == 24

    def test_firefox_fingerprint(self):
        from webreaper.utils.fingerprints import BrowserFingerprints

        fp = BrowserFingerprints.get_firefox_fingerprint()
        assert "Firefox" in fp["user_agent"]
        assert fp["navigator"]["deviceMemory"] is None  # Firefox doesn't expose

    def test_mobile_fingerprint(self):
        from webreaper.utils.fingerprints import BrowserFingerprints

        fp = BrowserFingerprints.get_mobile_fingerprint()
        assert "iPhone" in fp["user_agent"]
        assert fp["navigator"]["maxTouchPoints"] == 5
        assert fp["screen"]["pixelRatio"] in (2.0, 3.0)

    def test_fingerprints_are_randomized(self):
        """Two calls should produce different fingerprints (with high probability)."""
        from webreaper.utils.fingerprints import BrowserFingerprints

        fps = [BrowserFingerprints.get_random_fingerprint() for _ in range(10)]
        # At least 2 different user agents in 10 draws
        agents = set(fp["user_agent"] for fp in fps)
        assert len(agents) >= 2


# ──────────────────────────────────────────────────────────────────────
# Echo — Content Intelligence
# ──────────────────────────────────────────────────────────────────────

class TestEcho:
    def test_no_change_detection(self):
        from webreaper.modules.echo import Echo

        echo = Echo()
        result = echo.detect_change("https://example.com", "hello", "hello")
        assert result is None

    def test_change_detection(self):
        from webreaper.modules.echo import Echo, ChangeType

        echo = Echo()
        result = echo.detect_change("https://example.com", "old content", "new content here")
        assert result is not None
        assert result.url == "https://example.com"
        assert result.old_hash != result.new_hash

    def test_pricing_change_classification(self):
        from webreaper.modules.echo import Echo, ChangeType

        echo = Echo()
        result = echo.detect_change(
            "https://example.com",
            "Our plan costs $10 per month",
            "Our plan costs $20 per month",
        )
        assert result is not None
        assert result.change_type == ChangeType.PRICING

    def test_policy_change_classification(self):
        from webreaper.modules.echo import Echo, ChangeType

        echo = Echo()
        result = echo.detect_change(
            "https://example.com",
            "We respect your privacy and follow data collection guidelines.",
            "Updated privacy policy: GDPR consent required for data collection.",
        )
        assert result is not None
        assert result.change_type == ChangeType.POLICY

    def test_legal_change_classification(self):
        from webreaper.modules.echo import Echo, ChangeType

        echo = Echo()
        result = echo.detect_change(
            "https://example.com",
            "Terms of service: basic agreement",
            "Updated terms of service: new liability clause",
        )
        assert result is not None
        assert result.change_type == ChangeType.LEGAL

    def test_diff_summary(self):
        from webreaper.modules.echo import Echo

        echo = Echo()
        result = echo.detect_change("https://example.com", "line one", "line one\nline two")
        assert result is not None
        assert "Added" in result.summary

    def test_generate_diff(self):
        from webreaper.modules.echo import Echo

        echo = Echo()
        diff = echo._generate_diff("old line\n", "new line\n")
        assert "+" in diff or "-" in diff

    def test_classify_unknown_change(self):
        from webreaper.modules.echo import Echo, ChangeType

        echo = Echo()
        ct = echo._classify_change("some random text that doesn't match any category")
        assert ct == ChangeType.CONTENT


# ──────────────────────────────────────────────────────────────────────
# Missions — Autonomous Research
# ──────────────────────────────────────────────────────────────────────

class TestMissions:
    def test_create_competitive_intel_mission(self):
        from webreaper.modules.missions import MissionPlanner, MissionStatus, MissionType

        planner = MissionPlanner()
        mission = planner.create_mission("competitive_intel", "Analyze competitor.com", "https://competitor.com")
        assert mission.type == MissionType.COMPETITIVE_INTEL
        assert mission.status == MissionStatus.PLANNING
        assert len(mission.steps) == 3
        assert mission.steps[0].tool == "crawl"

    def test_create_custom_mission(self):
        from webreaper.modules.missions import MissionPlanner, MissionType

        planner = MissionPlanner()
        mission = planner.create_mission("unknown_type", "Custom task", "https://example.com")
        assert mission.type == MissionType.CUSTOM
        assert len(mission.steps) == 2  # Crawl + fingerprint

    def test_create_mission_without_url(self):
        from webreaper.modules.missions import MissionPlanner

        planner = MissionPlanner()
        mission = planner.create_mission("custom", "Just exploring")
        assert len(mission.steps) == 0

    @pytest.mark.asyncio
    async def test_execute_mission(self):
        from webreaper.modules.missions import MissionPlanner, MissionStatus

        planner = MissionPlanner()
        mission = planner.create_mission("competitive_intel", "Test", "https://example.com")

        async def mock_executor(tool, params):
            return {"status": "ok", "tool": tool}

        result = await planner.execute(mission, mock_executor)
        assert result.status == MissionStatus.COMPLETED
        assert len(result.results) == 3

    @pytest.mark.asyncio
    async def test_execute_mission_with_failure(self):
        from webreaper.modules.missions import MissionPlanner, MissionStatus

        planner = MissionPlanner()
        mission = planner.create_mission("threat_hunt", "Test", "https://example.com")

        async def failing_executor(tool, params):
            if tool == "fingerprint":
                raise RuntimeError("Network error")
            return {"ok": True}

        result = await planner.execute(mission, failing_executor)
        assert result.status == MissionStatus.COMPLETED
        failed = [s for s in result.steps if s.status == "failed"]
        assert len(failed) == 1
        assert "Network error" in failed[0].error

    def test_generate_report(self):
        from webreaper.modules.missions import MissionPlanner, MissionStatus

        planner = MissionPlanner()
        mission = planner.create_mission("deep_profile", "Profile target", "https://target.com")
        mission.status = MissionStatus.COMPLETED
        mission.results = {"step_0_crawl": {"pages": 50}}

        report = planner.generate_report(mission)
        assert "# Mission Report" in report
        assert "Profile target" in report
        assert "step_0_crawl" in report

    def test_get_active_and_completed(self):
        from webreaper.modules.missions import MissionPlanner

        planner = MissionPlanner()
        planner.create_mission("competitive_intel", "Test 1", "https://a.com")
        planner.create_mission("threat_hunt", "Test 2", "https://b.com")

        active = planner.get_active()
        assert len(active) == 2
        assert active[0]["type"] == "competitive_intel"


# ──────────────────────────────────────────────────────────────────────
# Vault — Data Export
# ──────────────────────────────────────────────────────────────────────

class TestVault:
    @pytest.fixture
    def sample_data(self):
        return [
            {"url": "https://a.com", "title": "Page A", "status": 200},
            {"url": "https://b.com", "title": "Page B", "status": 404},
        ]

    @pytest.mark.asyncio
    async def test_export_csv(self, sample_data, tmp_path):
        from webreaper.modules.vault import Vault

        vault = Vault()
        path = str(tmp_path / "test.csv")
        result = await vault.export(sample_data, "csv", path)
        assert Path(result).exists()
        content = Path(result).read_text()
        assert "url" in content
        assert "https://a.com" in content

    @pytest.mark.asyncio
    async def test_export_json(self, sample_data, tmp_path):
        from webreaper.modules.vault import Vault

        vault = Vault()
        path = str(tmp_path / "test.json")
        result = await vault.export(sample_data, "json", path)
        data = json.loads(Path(result).read_text())
        assert len(data) == 2
        assert data[0]["url"] == "https://a.com"

    @pytest.mark.asyncio
    async def test_export_jsonl(self, sample_data, tmp_path):
        from webreaper.modules.vault import Vault

        vault = Vault()
        path = str(tmp_path / "test.jsonl")
        result = await vault.export(sample_data, "jsonl", path)
        lines = Path(result).read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["url"] == "https://a.com"

    @pytest.mark.asyncio
    async def test_export_xlsx(self, sample_data, tmp_path):
        from webreaper.modules.vault import Vault

        vault = Vault()
        path = str(tmp_path / "test.xlsx")
        result = await vault.export(sample_data, "xlsx", path)
        assert Path(result).exists()
        assert Path(result).stat().st_size > 0

    @pytest.mark.asyncio
    async def test_export_sqlite(self, sample_data, tmp_path):
        from webreaper.modules.vault import Vault

        vault = Vault()
        path = str(tmp_path / "test.sqlite")
        result = await vault.export(sample_data, "sqlite", path)
        conn = sqlite3.connect(result)
        rows = conn.execute("SELECT * FROM export_data").fetchall()
        conn.close()
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_export_empty_data(self, tmp_path):
        from webreaper.modules.vault import Vault

        vault = Vault()
        path = str(tmp_path / "empty.csv")
        result = await vault.export([], "csv", path)
        assert Path(result).exists()

    @pytest.mark.asyncio
    async def test_export_unsupported_format(self, sample_data, tmp_path):
        from webreaper.modules.vault import Vault

        vault = Vault()
        with pytest.raises(ValueError, match="Unsupported format"):
            await vault.export(sample_data, "pdf", str(tmp_path / "test.pdf"))

    @pytest.mark.asyncio
    async def test_export_nested_data(self, tmp_path):
        from webreaper.modules.vault import Vault

        vault = Vault()
        data = [{"url": "https://a.com", "meta": {"key": "val"}, "tags": ["a", "b"]}]
        path = str(tmp_path / "nested.csv")
        result = await vault.export(data, "csv", path)
        content = Path(result).read_text()
        assert '"key"' in content  # JSON serialized


# ──────────────────────────────────────────────────────────────────────
# Phantom — API Schema Inference (no browser needed)
# ──────────────────────────────────────────────────────────────────────

class TestPhantomSchemaInference:
    def test_infer_dict_schema(self):
        from webreaper.modules.phantom import PhantomTap

        pt = PhantomTap()
        schema = pt._infer_schema({"name": "Alice", "age": 30, "active": True})
        assert schema["type"] == "object"
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["age"]["type"] == "integer"
        assert schema["properties"]["active"]["type"] == "boolean"

    def test_infer_list_schema(self):
        from webreaper.modules.phantom import PhantomTap

        pt = PhantomTap()
        schema = pt._infer_schema([{"id": 1}, {"id": 2}])
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "object"

    def test_infer_empty_list_schema(self):
        from webreaper.modules.phantom import PhantomTap

        pt = PhantomTap()
        schema = pt._infer_schema([])
        assert schema["type"] == "array"
        assert schema["items"] == {}

    def test_infer_nested_schema(self):
        from webreaper.modules.phantom import PhantomTap

        pt = PhantomTap()
        schema = pt._infer_schema({"user": {"name": "Bob", "score": 9.5}})
        assert schema["properties"]["user"]["type"] == "object"
        assert schema["properties"]["user"]["properties"]["score"]["type"] == "number"

    def test_infer_max_depth(self):
        from webreaper.modules.phantom import PhantomTap

        pt = PhantomTap()
        deep = {"a": {"b": {"c": {"d": "value"}}}}
        schema = pt._infer_schema(deep, max_depth=2)
        # At depth 2, "c" should not be fully expanded
        assert "properties" not in schema["properties"]["a"]["properties"]["b"]

    def test_api_map_empty(self):
        from webreaper.modules.phantom import PhantomTap

        pt = PhantomTap()
        assert pt.get_api_map() == {}

    def test_api_map_with_endpoints(self):
        from webreaper.modules.phantom import PhantomTap, APIEndpoint

        pt = PhantomTap()
        pt._endpoints = [
            APIEndpoint(
                url="https://api.example.com/v1/users",
                method="GET",
                path="/v1/users",
                response_status=200,
                content_type="application/json",
            ),
        ]
        api_map = pt.get_api_map()
        assert "api.example.com" in api_map
        assert api_map["api.example.com"][0]["method"] == "GET"


# ──────────────────────────────────────────────────────────────────────
# Blogwatcher — Article Extraction
# ──────────────────────────────────────────────────────────────────────

class TestBlogwatcher:
    @pytest.fixture
    def bridge(self):
        from webreaper.config import BlogwatcherConfig
        from webreaper.modules.blogwatcher import BlogwatcherBridge

        config = BlogwatcherConfig()
        return BlogwatcherBridge(config)

    def test_extract_by_article_tag(self, bridge):
        html = """
        <html><body>
        <article>
            <h2><a href="/blog/post-1">First Post</a></h2>
            <p>Summary of the post.</p>
        </article>
        <article>
            <h2><a href="/blog/post-2">Second Post</a></h2>
            <p>Another summary.</p>
        </article>
        </body></html>
        """
        articles = bridge.extract_articles(html, "https://example.com")
        assert len(articles) >= 2
        assert articles[0]["title"] == "First Post"
        assert articles[0]["url"] == "https://example.com/blog/post-1"

    def test_is_article_url(self, bridge):
        assert bridge._is_article_url("/blog/my-post") is True
        assert bridge._is_article_url("/news/breaking") is True
        assert bridge._is_article_url("/2024/03/post") is True
        assert bridge._is_article_url("/about") is False

    def test_extract_date_iso(self, bridge):
        assert bridge._extract_date("Published on 2024-03-15") is not None

    def test_extract_date_us_format(self, bridge):
        result = bridge._extract_date("Date: 03/15/2024")
        assert result is not None

    def test_extract_date_full_month(self, bridge):
        result = bridge._extract_date("March 15, 2024")
        assert result is not None

    def test_extract_date_no_match(self, bridge):
        assert bridge._extract_date("no date here") is None

    def test_escape_xml(self, bridge):
        assert "&amp;" in bridge._escape_xml("a & b")
        assert "&lt;" in bridge._escape_xml("<tag>")

    def test_generate_rss(self, bridge):
        articles = [{"title": "Test", "url": "https://a.com", "summary": "S", "date": "2024-01-01"}]
        rss = bridge.generate_rss(articles, "My Feed", "https://blog.com")
        assert '<?xml version="1.0"' in rss
        assert "<title>Test</title>" in rss

    def test_generate_json_feed(self, bridge):
        articles = [{"title": "Test", "url": "https://a.com", "summary": "Summary"}]
        feed = bridge.generate_json_feed(articles, "Feed", "https://blog.com")
        parsed = json.loads(feed)
        assert parsed["title"] == "Feed"
        assert len(parsed["items"]) == 1

    def test_deduplicate_articles(self, bridge):
        html = """
        <html><body>
        <article><h2><a href="/same">Post</a></h2></article>
        <article><h2><a href="/same">Post</a></h2></article>
        </body></html>
        """
        articles = bridge.extract_articles(html, "https://example.com")
        assert len(articles) == 1

    def test_save_feed_rss(self, bridge, tmp_path):
        articles = [{"title": "A", "url": "https://a.com", "summary": "S"}]
        bridge.config.output_format = "rss"
        result = bridge.save_feed(articles, tmp_path / "feed", "Test", "https://blog.com")
        assert result.suffix == ".xml"
        assert result.exists()

    def test_save_feed_json(self, bridge, tmp_path):
        articles = [{"title": "A", "url": "https://a.com"}]
        bridge.config.output_format = "json"
        result = bridge.save_feed(articles, tmp_path / "feed", "Test", "https://blog.com")
        assert result.suffix == ".json"


# ──────────────────────────────────────────────────────────────────────
# Monitor — Change detection helpers (no network)
# ──────────────────────────────────────────────────────────────────────

class TestMonitorHelpers:
    def test_text_hash(self):
        from webreaper.modules.monitor import _text_hash

        h1 = _text_hash("hello")
        h2 = _text_hash("hello")
        h3 = _text_hash("world")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64  # SHA256 hex

    def test_extract_text(self):
        from webreaper.modules.monitor import _extract_text

        html = """
        <html><body>
        <nav>Menu</nav>
        <div>Main content here</div>
        <footer>Footer</footer>
        </body></html>
        """
        text = _extract_text(html)
        assert "Main content" in text
        assert "Menu" not in text
        assert "Footer" not in text

    def test_diff_summary(self):
        from webreaper.modules.monitor import _diff_summary

        diff = _diff_summary("old line\n", "new line\n")
        assert diff  # Should have some diff output

    def test_diff_summary_no_change(self):
        from webreaper.modules.monitor import _diff_summary

        diff = _diff_summary("same\n", "same\n")
        assert diff == ""


# ──────────────────────────────────────────────────────────────────────
# Reporter — HTML report building (pure logic)
# ──────────────────────────────────────────────────────────────────────

class TestReporter:
    def test_sev_badge(self):
        from webreaper.modules.reporter import _sev_badge

        badge = _sev_badge("Critical")
        assert "#dc2626" in badge
        assert "Critical" in badge

    def test_sev_badge_unknown(self):
        from webreaper.modules.reporter import _sev_badge

        badge = _sev_badge("Unknown")
        assert "#6b7280" in badge  # Falls back to gray

    def test_build_html(self):
        from webreaper.modules.reporter import _build_html

        crawls = [{
            "id": "abc123",
            "target_url": "https://example.com",
            "status": "completed",
            "pages_crawled": 10,
            "pages_failed": 1,
            "requests_per_sec": 5.0,
            "genre": "web_dev",
            "started_at": "2024-01-01T00:00:00",
        }]
        pages = [{
            "url": "https://example.com",
            "status_code": 200,
            "title": "Home",
            "word_count": 500,
            "depth": 0,
            "response_time_ms": 120,
        }]
        findings = [{
            "finding_type": "XSS",
            "severity": "High",
            "url": "https://example.com/search",
            "evidence": "<script>alert(1)</script>",
            "remediation": "Encode output",
        }]

        html = _build_html(crawls, pages, findings)
        assert "<!DOCTYPE html>" in html
        assert "example.com" in html
        assert "XSS" in html
        assert "High" in html

    def test_build_html_empty(self):
        from webreaper.modules.reporter import _build_html

        html = _build_html([], [], [])
        assert "<!DOCTYPE html>" in html
        assert "No findings" in html
        assert "No pages" in html


# ──────────────────────────────────────────────────────────────────────
# JobQueue
# ──────────────────────────────────────────────────────────────────────

class TestJobQueue:
    @pytest.mark.asyncio
    async def test_submit_and_complete(self):
        from webreaper.job_queue import JobQueue, JobStatus

        queue = JobQueue(max_concurrent=2)
        completed = False

        async def work():
            nonlocal completed
            completed = True

        job_id = await queue.submit(work)
        # Give the task time to run
        await asyncio.sleep(0.1)
        assert completed
        status = queue.get_status(job_id)
        assert status["status"] == "completed"

    @pytest.mark.asyncio
    async def test_submit_with_error(self):
        from webreaper.job_queue import JobQueue, JobStatus

        queue = JobQueue()

        async def failing_work():
            raise ValueError("Something broke")

        job_id = await queue.submit(failing_work)
        await asyncio.sleep(0.1)
        status = queue.get_status(job_id)
        assert status["status"] == "failed"
        assert "Something broke" in status["error"]

    @pytest.mark.asyncio
    async def test_cancel_job(self):
        from webreaper.job_queue import JobQueue

        queue = JobQueue(max_concurrent=1)

        async def slow_work():
            await asyncio.sleep(10)

        job_id = await queue.submit(slow_work)
        await asyncio.sleep(0.05)
        assert await queue.cancel(job_id) is True

    @pytest.mark.asyncio
    async def test_list_jobs(self):
        from webreaper.job_queue import JobQueue

        queue = JobQueue()

        async def work():
            pass

        await queue.submit(work, meta={"url": "https://a.com"})
        await queue.submit(work, meta={"url": "https://b.com"})
        await asyncio.sleep(0.1)

        jobs = queue.list_jobs()
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_active_count(self):
        from webreaper.job_queue import JobQueue

        queue = JobQueue(max_concurrent=5)
        running = asyncio.Event()

        async def blocking_work():
            running.set()
            await asyncio.sleep(10)

        await queue.submit(blocking_work)
        await running.wait()
        assert queue.active_count == 1
        await queue.shutdown(timeout=1.0)

    @pytest.mark.asyncio
    async def test_shutdown(self):
        from webreaper.job_queue import JobQueue

        queue = JobQueue()

        async def slow():
            await asyncio.sleep(10)

        await queue.submit(slow)
        await queue.submit(slow)
        await asyncio.sleep(0.05)
        cancelled = await queue.shutdown(timeout=1.0)
        assert cancelled >= 1

    @pytest.mark.asyncio
    async def test_cleanup_completed(self):
        from webreaper.job_queue import JobQueue

        queue = JobQueue()

        async def noop():
            pass

        for _ in range(5):
            await queue.submit(noop)
        await asyncio.sleep(0.2)

        removed = queue.cleanup_completed(keep_last=2)
        assert removed == 3

    @pytest.mark.asyncio
    async def test_get_status_nonexistent(self):
        from webreaper.job_queue import JobQueue

        queue = JobQueue()
        assert queue.get_status("nonexistent") is None

    @pytest.mark.asyncio
    async def test_cancel_completed_job(self):
        from webreaper.job_queue import JobQueue

        queue = JobQueue()

        async def noop():
            pass

        job_id = await queue.submit(noop)
        await asyncio.sleep(0.1)
        assert await queue.cancel(job_id) is False  # Already completed


# ──────────────────────────────────────────────────────────────────────
# XRay — CDN detection logic (no network)
# ──────────────────────────────────────────────────────────────────────

class TestXRayCDNDetection:
    def test_infra_report_defaults(self):
        from webreaper.modules.xray import InfraReport

        report = InfraReport(domain="example.com")
        assert report.domain == "example.com"
        assert report.dns_records == {}
        assert report.subdomains == []

    def test_xray_caching(self):
        from webreaper.modules.xray import InfraXray, InfraReport

        xray = InfraXray()
        cached = InfraReport(domain="cached.com", ip_addresses=["1.2.3.4"])
        xray._cache["cached.com"] = cached

        # Should return cached version
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(xray.scan("cached.com"))
        assert result.ip_addresses == ["1.2.3.4"]
