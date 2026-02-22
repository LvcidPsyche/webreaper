"""Page change monitoring module."""

import asyncio
import difflib
import hashlib
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from rich.console import Console

console = Console()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _extract_text(html: str) -> str:
    """Strip HTML, return normalized text for comparison."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    body = soup.find("body")
    if body:
        return " ".join(body.get_text(separator=" ", strip=True).split())
    return ""


def _diff_summary(old_text: str, new_text: str, max_lines: int = 10) -> str:
    """Return a short unified diff summary between two texts."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=1))
    if not diff:
        return ""
    # Keep only added/removed lines up to max_lines
    changes = [l for l in diff if l.startswith(("+", "-")) and not l.startswith(("---", "+++"))]
    return "\n".join(changes[:max_lines])


class Monitor:
    """Polls URLs and records content changes."""

    def __init__(self, db_manager=None):
        self.db = db_manager

    async def run(self, url: str, interval: int = 3600, once: bool = False, notify: bool = True):
        """Monitor loop. Runs forever unless --once is set."""
        from ..fetcher import StealthFetcher
        from ..config import StealthConfig

        console.print(f"[bold cyan]👁  Monitoring:[/bold cyan] {url}")
        if not once:
            console.print(f"[dim]Check interval: {interval}s — Ctrl+C to stop[/dim]")

        fetcher_config = StealthConfig()

        while True:
            changed, summary = await self._check(url, fetcher_config)

            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            if changed:
                console.print(f"[bold yellow]⚠  [{ts}] CHANGED:[/bold yellow] {url}")
                if summary:
                    console.print(f"[dim]{summary[:300]}[/dim]")
            else:
                console.print(f"[green]✓  [{ts}] No change[/green]")

            if once:
                break

            await asyncio.sleep(interval)

    async def _check(self, url: str, fetcher_config) -> tuple[bool, Optional[str]]:
        """Fetch URL, compare to last snapshot. Returns (changed, diff_summary)."""
        from ..fetcher import StealthFetcher

        async with StealthFetcher(fetcher_config) as fetcher:
            status, headers, html = await fetcher.fetch(url)

        if status not in (200, 201) or not html:
            console.print(f"[red]Fetch failed: HTTP {status}[/red]")
            return False, None

        soup = BeautifulSoup(html, "lxml")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        text = _extract_text(html)
        content_hash = _text_hash(text)

        # Compare with last snapshot
        changed = False
        diff = None

        if self.db:
            last = await self.db.get_latest_snapshot(url)
            if last:
                changed = last["content_hash"] != content_hash
                if changed:
                    diff = _diff_summary(last.get("content_text", ""), text)
            else:
                changed = False  # First snapshot — not "changed"

            await self.db.save_snapshot(
                url=url,
                content_hash=content_hash,
                content_text=text,
                title=title,
                status_code=status,
                changed=changed,
                diff_summary=diff,
            )
        else:
            # Stateless mode: store in-memory between calls
            key = f"_snap_{url}"
            last_hash = getattr(self, key, None)
            if last_hash is not None:
                changed = last_hash != content_hash
            setattr(self, key, content_hash)

        return changed, diff
