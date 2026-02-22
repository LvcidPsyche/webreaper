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

from .config import Config
from .fetcher import StealthFetcher
from .frontier import URLFrontier


console = Console()


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
    
    def __init__(self, config: Config):
        self.config = config
        self.frontier = URLFrontier()
        self.results: List[CrawlResult] = []
        self.stats = {
            "pages_crawled": 0,
            "pages_failed": 0,
            "total_size": 0,
            "start_time": 0,
            "external_links": 0,
        }
        self.progress: Optional[Progress] = None
        self.task_id: Optional[TaskID] = None
        self._stop_event = asyncio.Event()
    
    async def crawl(self, start_urls: List[str], callback: Optional[Callable] = None) -> List[CrawlResult]:
        """Start crawling from seed URLs."""
        self.stats["start_time"] = time.time()
        
        # Add start URLs to frontier
        for url in start_urls:
            await self.frontier.add(url, depth=0, priority=0)
        
        console.print(f"[green]Starting crawl of {len(start_urls)} URLs...[/green]")
        console.print(f"[dim]Max depth: {self.config.crawler.max_depth}, Max pages: {self.config.crawler.max_pages}[/dim]")
        
        # Create fetcher session
        async with StealthFetcher(self.config.stealth) as fetcher:
            # Create worker tasks
            workers = [
                asyncio.create_task(self._worker(fetcher, callback))
                for _ in range(self.config.crawler.concurrency)
            ]
            
            # Wait for completion or stop signal
            await self._stop_event.wait()
            
            # Cancel workers
            for w in workers:
                w.cancel()
            
            try:
                await asyncio.gather(*workers, return_exceptions=True)
            except asyncio.CancelledError:
                pass
        
        elapsed = time.time() - self.stats["start_time"]
        console.print(f"\n[green]Crawl complete![/green]")
        console.print(f"Pages crawled: {self.stats['pages_crawled']}")
        console.print(f"Pages failed: {self.stats['pages_failed']}")
        console.print(f"Time: {elapsed:.1f}s")
        console.print(f"Rate: {self.stats['pages_crawled'] / elapsed:.1f} pages/sec")
        
        return self.results
    
    async def _worker(self, fetcher: StealthFetcher, callback: Optional[Callable]):
        """Worker that processes URLs from frontier."""
        while not self._stop_event.is_set():
            try:
                # Get URL from frontier
                task = await asyncio.wait_for(self.frontier.get(), timeout=1.0)
                if not task:
                    continue
                
                # Check limits
                if self.stats["pages_crawled"] >= self.config.crawler.max_pages:
                    self._stop_event.set()
                    break
                
                # Crawl the page
                result = await self._crawl_page(fetcher, task.url, task.depth)
                
                if result:
                    self.results.append(result)
                    self.stats["pages_crawled"] += 1
                    
                    # Add discovered links to frontier
                    await self._add_links(result, task.depth)
                    
                    # Callback if provided
                    if callback:
                        callback(result)
                else:
                    self.stats["pages_failed"] += 1
                
                # Check if we should stop
                if self.frontier.qsize() == 0 and self.stats["pages_crawled"] > 0:
                    # Wait a bit for more URLs
                    await asyncio.sleep(0.5)
                    if self.frontier.qsize() == 0:
                        self._stop_event.set()
                        
            except asyncio.TimeoutError:
                if self.stats["pages_crawled"] > 0 and self.frontier.qsize() == 0:
                    self._stop_event.set()
            except asyncio.CancelledError:
                break
            except Exception as e:
                console.print(f"[red]Worker error: {e}[/red]")
    
    async def _crawl_page(self, fetcher: StealthFetcher, url: str, depth: int) -> Optional[CrawlResult]:
        """Crawl a single page."""
        start_time = time.time()
        
        status, headers, text = await fetcher.fetch(
            url,
            allow_redirects=self.config.crawler.follow_redirects
        )
        
        response_time = time.time() - start_time
        
        if status != 200 or not text:
            return None
        
        # Parse HTML
        soup = BeautifulSoup(text, 'lxml')
        
        # Extract data
        result = CrawlResult(
            url=url,
            status=status,
            title=self._extract_title(soup),
            meta_description=self._extract_meta(soup, "description"),
            headings=self._extract_headings(soup),
            links=self._extract_links(soup, url, external=False),
            external_links=self._extract_links(soup, url, external=True),
            images=self._extract_images(soup, url),
            content_text=self._extract_content(soup),
            word_count=len(self._extract_content(soup).split()),
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
    
    async def _add_links(self, result: CrawlResult, current_depth: int):
        """Add discovered links to frontier."""
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
        """Extract page title."""
        if soup.title:
            return soup.title.string.strip() if soup.title.string else None
        h1 = soup.find("h1")
        return h1.get_text(strip=True) if h1 else None
    
    def _extract_meta(self, soup: BeautifulSoup, name: str) -> Optional[str]:
        """Extract meta tag content."""
        meta = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": f"og:{name}"})
        return meta.get("content") if meta else None
    
    def _extract_headings(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract all headings."""
        headings = []
        for i in range(1, 7):
            for h in soup.find_all(f"h{i}"):
                headings.append({"level": i, "text": h.get_text(strip=True)})
        return headings
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str, external: bool = False) -> List[str]:
        """Extract links from page."""
        links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            if not href:
                continue
            
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Skip non-HTTP schemes
            if parsed.scheme not in ("http", "https"):
                continue
            
            is_external = not URLFrontier.is_same_domain(full_url, base_url)
            
            if external and is_external:
                links.append(full_url)
            elif not external and not is_external:
                links.append(full_url)
        
        return list(set(links))  # Deduplicate
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract image URLs."""
        images = []
        for img in soup.find_all("img", src=True):
            src = img.get("src")
            if src:
                images.append(urljoin(base_url, src))
        return images
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main content text."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Try to find main content area
        for selector in ["main", "article", "[role='main']", ".content", "#content"]:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(separator=" ", strip=True)
        
        # Fallback to body
        body = soup.find("body")
        return body.get_text(separator=" ", strip=True) if body else ""
    
    def _extract_forms(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract forms from page."""
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
        """Save crawl results to file."""
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
        """Convert result to dictionary."""
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
