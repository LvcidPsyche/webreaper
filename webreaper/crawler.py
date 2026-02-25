"""Core crawler engine."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, TaskID

import logging

from .config import Config
from .deep_extractor import DeepExtractor, DeepPageData
from .fetcher import StealthFetcher
from .frontier import URLFrontier
from .modules.robots import RobotsCache


console = Console()
logger = logging.getLogger("webreaper.crawler")


@dataclass
class CrawlResult:
    """Result of crawling a single page."""
    url: str
    status: int
    title: Optional[str] = None
    meta_description: Optional[str] = None
    headings: List[Dict[str, str]] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    external_links: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    content_text: str = ""
    word_count: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    response_time: float = 0.0
    depth: int = 0
    parent: Optional[str] = None
    forms: List[Dict] = field(default_factory=list)
    scripts: List[str] = field(default_factory=list)
    stylesheets: List[str] = field(default_factory=list)


class Crawler:
    """Main crawler engine."""

    def __init__(self, config: Config, db_manager=None):
        self.config = config
        self.db_manager = db_manager
        self.frontier = URLFrontier()
        self.deep_extractor = DeepExtractor()
        self.results: List[CrawlResult] = []
        self.deep_results: Dict[str, DeepPageData] = {}
        self.stats = {
            "pages_crawled": 0,
            "pages_failed": 0,
            "total_size": 0,
            "start_time": 0,
            "external_links": 0,
            "queue_size": 0,
            "current_url": "",
            "active_workers": 0,
            "requests_per_second": 0.0,
        }
        self.progress: Optional[Progress] = None
        self.task_id: Optional[TaskID] = None
        self._stop_event = asyncio.Event()
        self._stop_flag = False  # For graceful job cancellation via API
        self._active_workers = 0
        self._active_lock = asyncio.Lock()
        self._crawl_id: Optional[str] = None
        self._workspace_id: Optional[str] = None
        self._robots: Optional[RobotsCache] = None
        self._metrics_callback: Optional[Callable] = None  # For metrics integration

    async def crawl(self, start_urls: List[str], callback: Optional[Callable] = None) -> List[CrawlResult]:
        """Start crawling from seed URLs."""
        self.stats["start_time"] = time.time()

        # Create DB crawl record if available
        if self.db_manager:
            try:
                self._crawl_id = await self.db_manager.create_crawl(
                    target_url=start_urls[0],
                    config=self.config.model_dump(mode="json"),
                    genre=getattr(self.config, "genre", None),
                    workspace_id=self._workspace_id,
                )
            except Exception as e:
                logger.error("DB: failed to create crawl record: %s", e)

        for url in start_urls:
            await self.frontier.add(url, depth=0, priority=0)
        self.stats["queue_size"] = self.frontier.qsize()
        self._emit_metrics()

        console.print(f"[green]Starting crawl of {len(start_urls)} URLs...[/green]")
        console.print(f"[dim]Max depth: {self.config.crawler.max_depth}, Max pages: {self.config.crawler.max_pages}[/dim]")

        async with StealthFetcher(self.config.stealth, rate_limit=self.config.crawler.rate_limit) as fetcher:
            if self.config.crawler.respect_robots:
                self._robots = RobotsCache()
            workers = [
                asyncio.create_task(self._worker(fetcher, callback))
                for _ in range(self.config.crawler.concurrency)
            ]

            # Wait for all workers to finish naturally
            await asyncio.gather(*workers, return_exceptions=True)

        elapsed = time.time() - self.stats["start_time"]
        self.stats["requests_per_second"] = (self.stats["pages_crawled"] / elapsed) if elapsed > 0 else 0.0
        self.stats["queue_size"] = self.frontier.qsize()
        self.stats["current_url"] = ""
        self._emit_metrics()

        # Update DB crawl record on completion
        if self.db_manager and self._crawl_id:
            try:
                await self.db_manager.complete_crawl(self._crawl_id, self.stats)
            except Exception as e:
                logger.error("DB: failed to complete crawl record: %s", e)

        console.print(f"\n[green]Crawl complete![/green]")
        console.print(f"Pages crawled: {self.stats['pages_crawled']}")
        console.print(f"Pages failed: {self.stats['pages_failed']}")
        console.print(f"Time: {elapsed:.1f}s")
        if elapsed > 0:
            console.print(f"Rate: {self.stats['pages_crawled'] / elapsed:.1f} pages/sec")

        return self.results

    async def _worker(self, fetcher: StealthFetcher, callback: Optional[Callable]):
        """Worker that processes URLs from frontier."""
        async with self._active_lock:
            self._active_workers += 1
            self.stats["active_workers"] = self._active_workers
        self._emit_metrics()

        try:
            consecutive_empty = 0
            while True:
                # Check stop flag (set by API job cancellation)
                if self._stop_flag:
                    break

                # Check page limit
                if self.stats["pages_crawled"] >= self.config.crawler.max_pages:
                    break

                # Try to get a URL
                try:
                    task = await asyncio.wait_for(self.frontier.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    consecutive_empty += 1
                    # All workers idle with empty queue = done
                    if consecutive_empty >= 3 and self.frontier.qsize() == 0:
                        break
                    continue

                consecutive_empty = 0
                self.stats["current_url"] = task.url
                self.stats["queue_size"] = self.frontier.qsize()
                self.stats["active_workers"] = self._active_workers
                self._emit_metrics()

                result = await self._crawl_page(fetcher, task.url, task.depth)

                if result:
                    self.stats["pages_crawled"] += 1

                    await self._add_links(result, task.depth)

                    # Persist to DB; only accumulate in-memory when no DB (avoids RAM growth)
                    if self.db_manager and self._crawl_id:
                        await self._save_to_db(result)
                    else:
                        self.results.append(result)

                    if callback:
                        callback(result)
                    self._emit_metrics(
                        page_delta=1,
                        status_code=result.status,
                        bytes_delta=len(result.content_text or ""),
                    )
                else:
                    self.stats["pages_failed"] += 1
                    self._emit_metrics(fail_delta=1)

        except asyncio.CancelledError:
            pass
        finally:
            async with self._active_lock:
                self._active_workers -= 1
                self.stats["active_workers"] = self._active_workers
            self.stats["queue_size"] = self.frontier.qsize()
            self._emit_metrics()

    def _emit_metrics(
        self,
        *,
        page_delta: int = 0,
        fail_delta: int = 0,
        bytes_delta: int = 0,
        status_code: Optional[int] = None,
    ) -> None:
        """Emit incremental + gauge metrics to an external metrics callback."""
        if not self._metrics_callback:
            return
        elapsed = time.time() - self.stats["start_time"] if self.stats.get("start_time") else 0
        self.stats["requests_per_second"] = (self.stats["pages_crawled"] / elapsed) if elapsed > 0 else 0.0
        event = {
            "pages_crawled": self.stats.get("pages_crawled", 0),
            "pages_failed": self.stats.get("pages_failed", 0),
            "queue_size": self.stats.get("queue_size", 0),
            "current_url": self.stats.get("current_url", ""),
            "active_workers": self.stats.get("active_workers", 0),
            "requests_per_second": self.stats.get("requests_per_second", 0.0),
            "page_delta": page_delta,
            "fail_delta": fail_delta,
            "bytes_delta": bytes_delta,
            "status_code": status_code,
        }
        try:
            self._metrics_callback(event)
        except Exception as e:
            logger.debug("Metrics callback error ignored: %s", e)

    async def _crawl_page(self, fetcher: StealthFetcher, url: str, depth: int) -> Optional[CrawlResult]:
        """Crawl a single page with deep extraction."""
        start_time = time.time()

        # Check robots.txt if enabled
        if self.config.crawler.respect_robots and self._robots:
            if not await self._robots.allowed(url, fetcher):
                return None

        status, headers, text = await fetcher.fetch(
            url,
            allow_redirects=self.config.crawler.follow_redirects
        )

        response_time = time.time() - start_time

        if status not in (200, 201) or not text:
            return None

        deep: Optional[DeepPageData] = None
        try:
            # Deep extraction — gets everything
            deep = self.deep_extractor.extract(
                url=url,
                status_code=status,
                html=text,
                headers=headers,
                response_time_ms=int(response_time * 1000),
                depth=depth,
            )
            # Store deep result keyed by URL (latest wins on duplicates)
            self.deep_results[url] = deep

            # Build backward-compatible CrawlResult from deep data
            internal_urls = [l.url for l in deep.links if not l.is_external]
            external_urls = [l.url for l in deep.links if l.is_external]

            result = CrawlResult(
                url=url,
                status=status,
                title=deep.title,
                meta_description=deep.meta_description,
                headings=deep.headings,
                links=internal_urls,
                external_links=external_urls,
                images=[img.url for img in deep.images],
                content_text=deep.content_text,
                word_count=deep.word_count,
                headers=headers,
                response_time=response_time,
                depth=depth,
                forms=deep.forms,
                scripts=[s.url for s in deep.scripts],
                stylesheets=[s.url for s in deep.stylesheets],
            )
        except Exception as e:
            logger.exception("Deep extraction failed for %s: %s", url, e)
            # Fall back to shallow extraction to avoid losing a successful fetch.
            soup = BeautifulSoup(text, 'lxml')
            content_text = self._extract_content(soup)
            result = CrawlResult(
                url=url,
                status=status,
                title=self._extract_title(soup),
                meta_description=self._extract_meta(soup, "description"),
                headings=self._extract_headings(soup),
                links=self._extract_links(soup, url, external=False),
                external_links=self._extract_links(soup, url, external=True),
                images=self._extract_images(soup, url),
                content_text=content_text,
                word_count=len(content_text.split()),
                headers=headers,
                response_time=response_time,
                depth=depth,
                forms=self._extract_forms(soup, url),
                scripts=[s.get("src") for s in soup.find_all("script") if s.get("src")],
                stylesheets=[s.get("href") for s in soup.find_all("link", rel="stylesheet") if s.get("href")],
            )

        self.stats["total_size"] += len(text)
        self.stats["external_links"] += len(result.external_links)

        return result

    async def _save_to_db(self, result: CrawlResult):
        """Persist page result with deep extraction data to database."""
        try:
            parsed = urlparse(result.url)

            # Find matching deep result
            deep = self.deep_results.pop(result.url, None)

            page_kwargs = dict(
                crawl_id=self._crawl_id,
                workspace_id=self._workspace_id,
                url=result.url,
                domain=parsed.netloc,
                path=parsed.path,
                status_code=result.status,
                response_time_ms=int(result.response_time * 1000),
                title=result.title,
                meta_description=result.meta_description,
                content_text=result.content_text,
                word_count=result.word_count,
                headings=result.headings,
                headings_count=len(result.headings),
                images_count=len(result.images),
                links_count=len(result.links),
                external_links_count=len(result.external_links),
                h1=next((h["text"] for h in result.headings if h.get("level") == 1), None),
                h2s=[h["text"] for h in result.headings if h.get("level") == 2],
                response_headers=result.headers,
                depth=result.depth,
            )

            # Deep extraction data
            if deep:
                page_kwargs.update(
                    meta_tags=deep.meta_tags,
                    og_data=deep.og_data,
                    twitter_card=deep.twitter_card,
                    structured_data=deep.structured_data,
                    technologies=[
                        {'category': t.category, 'name': t.name, 'confidence': t.confidence}
                        for t in deep.technologies
                    ],
                    emails_found=deep.emails,
                    phone_numbers=deep.phone_numbers,
                    addresses_found=deep.addresses,
                    social_links=deep.social_links,
                    seo_score=deep.seo.score if deep.seo else None,
                    seo_issues=deep.seo.issues if deep.seo else None,
                    seo_passes=deep.seo.passes if deep.seo else None,
                    readability_score=deep.content_analysis.readability_score if deep.content_analysis else None,
                    reading_level=deep.content_analysis.reading_level if deep.content_analysis else None,
                    content_to_html_ratio=deep.content_analysis.content_to_html_ratio if deep.content_analysis else None,
                    sentence_count=deep.content_analysis.sentence_count if deep.content_analysis else None,
                    unique_word_count=deep.content_analysis.unique_word_count if deep.content_analysis else None,
                    top_words=deep.content_analysis.top_words if deep.content_analysis else None,
                    content_hash=deep.content_analysis.content_hash if deep.content_analysis else None,
                    language=deep.language,
                    favicon_url=deep.favicon_url,
                    robots_meta=deep.robots_meta,
                    hreflang=deep.hreflang,
                    has_canonical=deep.canonical_url is not None,
                    canonical_url=deep.canonical_url,
                    scripts_count=len(deep.scripts),
                    stylesheets_count=len(deep.stylesheets),
                    forms_count=len(deep.forms),
                    total_resource_count=deep.total_resource_count,
                )

            page_id = await self.db_manager.save_page(**page_kwargs)

            if page_id and deep:
                # Save links (internal + external) with metadata when available
                if deep.links:
                    await self.db_manager.save_links(
                        crawl_id=self._crawl_id,
                        page_id=page_id,
                        links=[
                            {
                                "url": l.url,
                                "is_external": l.is_external,
                                "anchor_text": l.anchor_text,
                                "rel_attributes": l.rel,
                                "link_type": "nav" if l.is_navigation else ("footer" if l.is_footer else "text"),
                            }
                            for l in deep.links
                        ],
                    )

                # Save forms
                if getattr(self.db_manager, "save_forms", None) and deep.forms:
                    await self.db_manager.save_forms(
                        crawl_id=self._crawl_id,
                        page_id=page_id,
                        forms=deep.forms,
                    )

                # Build endpoint inventory from page + links + forms
                if getattr(self.db_manager, "upsert_endpoints", None):
                    endpoint_records = self.db_manager.derive_endpoints_from_page(
                        result.url,
                        forms=deep.forms,
                        links=[{"url": l.url} for l in deep.links],
                    )
                    await self.db_manager.upsert_endpoints(
                        crawl_id=self._crawl_id,
                        page_id=page_id,
                        endpoints=endpoint_records,
                        workspace_id=self._workspace_id,
                    )

                # Save assets
                await self._save_assets(page_id, deep)

                # Save technologies
                await self._save_technologies(page_id, parsed.netloc, deep)

        except Exception as e:
            logger.error("DB save error for %s: %s", result.url, e)

    async def _save_assets(self, page_id: str, deep: 'DeepPageData'):
        """Save assets (images, scripts, stylesheets) to database."""
        from .database import Asset
        try:
            async with self.db_manager.get_session() as session:
                for asset in deep.assets:
                    obj = Asset(
                        page_id=page_id,
                        crawl_id=self._crawl_id,
                        url=asset.url,
                        asset_type=asset.asset_type,
                        alt_text=asset.alt_text,
                        is_external=asset.is_external,
                        loading=asset.loading,
                        attributes=asset.attributes,
                    )
                    session.add(obj)
        except Exception as e:
            logger.error("Asset save error for page %s: %s", page_id, e)

    async def _save_technologies(self, page_id: str, domain: str, deep: 'DeepPageData'):
        """Save detected technologies to database."""
        from .database import Technology
        try:
            async with self.db_manager.get_session() as session:
                for tech in deep.technologies:
                    obj = Technology(
                        crawl_id=self._crawl_id,
                        page_id=page_id,
                        domain=domain,
                        category=tech.category,
                        name=tech.name,
                        confidence=tech.confidence,
                    )
                    session.add(obj)
        except Exception as e:
            logger.error("Tech save error for page %s: %s", page_id, e)

    async def _add_links(self, result: CrawlResult, current_depth: int):
        if current_depth >= self.config.crawler.max_depth:
            return

        for link in result.links:
            await self.frontier.add(
                link,
                depth=current_depth + 1,
                priority=current_depth + 1,
                parent=result.url
            )

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        if soup.title:
            return soup.title.string.strip() if soup.title.string else None
        h1 = soup.find("h1")
        return h1.get_text(strip=True) if h1 else None

    def _extract_meta(self, soup: BeautifulSoup, name: str) -> Optional[str]:
        meta = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": f"og:{name}"})
        return meta.get("content") if meta else None

    def _extract_headings(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        headings = []
        for i in range(1, 7):
            for h in soup.find_all(f"h{i}"):
                headings.append({"level": i, "text": h.get_text(strip=True)})
        return headings

    def _extract_links(self, soup: BeautifulSoup, base_url: str, external: bool = False) -> List[str]:
        links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            if not href:
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            if parsed.scheme not in ("http", "https"):
                continue

            is_external = not URLFrontier.is_same_domain(full_url, base_url)

            if external and is_external:
                links.append(full_url)
            elif not external and not is_external:
                links.append(full_url)

        return list(set(links))

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        images = []
        for img in soup.find_all("img", src=True):
            src = img.get("src")
            if src:
                images.append(urljoin(base_url, src))
        return images

    def _extract_content(self, soup: BeautifulSoup) -> str:
        for script in soup(["script", "style"]):
            script.decompose()

        for selector in ["main", "article", "[role='main']", ".content", "#content"]:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(separator=" ", strip=True)

        body = soup.find("body")
        return body.get_text(separator=" ", strip=True) if body else ""

    def _extract_forms(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        forms = []
        for form in soup.find_all("form"):
            form_data = {
                "action": urljoin(base_url, form.get("action", "")),
                "method": form.get("method", "GET").upper(),
                "inputs": []
            }
            for inp in form.find_all(["input", "textarea", "select"]):
                form_data["inputs"].append({
                    "name": inp.get("name"),
                    "type": inp.get("type", "text"),
                    "required": inp.get("required") is not None,
                })
            forms.append(form_data)
        return forms

    def save_results(self, output_dir: Path, format: str = "json"):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if format == "json":
            output_file = output_dir / "crawl_results.json"
            with open(output_file, "w") as f:
                json.dump([self._result_to_dict(r) for r in self.results], f, indent=2)
            console.print(f"[green]Results saved to {output_file}[/green]")

        elif format == "csv":
            import csv
            output_file = output_dir / "crawl_results.csv"
            with open(output_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["URL", "Title", "Status", "Word Count", "Links", "External Links"])
                for r in self.results:
                    writer.writerow([r.url, r.title, r.status, r.word_count, len(r.links), len(r.external_links)])
            console.print(f"[green]Results saved to {output_file}[/green]")

    def _result_to_dict(self, result: CrawlResult) -> Dict[str, Any]:
        return {
            "url": result.url,
            "status": result.status,
            "title": result.title,
            "meta_description": result.meta_description,
            "headings": result.headings,
            "links": result.links,
            "external_links": result.external_links,
            "images": result.images,
            "word_count": result.word_count,
            "response_time": result.response_time,
            "depth": result.depth,
            "forms": result.forms,
        }
