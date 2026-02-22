"""
WebReaper Integration Module
============================
Connects WebReaper scraper to blogwatcher for RSS-less sites.
"""

import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from webreaper.config import Config
from webreaper.crawler import Crawler
from webreaper.fetcher import StealthFetcher
from webreaper.modules.blogwatcher import BlogwatcherBridge

console = Console()


class BlogwatcherIntegrator:
    """Integrates WebReaper with blogwatcher."""
    
    def __init__(self, config: Config):
        self.config = config
        self.bridge = BlogwatcherBridge(config.blogwatcher)
    
    async def scrape_and_import(self, url: str, name: str, output_dir: Path) -> Path:
        """Scrape a site and import into blogwatcher."""
        console.print(f"[bold green]🕷️ Scraping {name}...[/bold green]")
        console.print(f"URL: {url}")
        
        async with StealthFetcher(self.config.stealth) as fetcher:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Fetching...", total=None)
                
                status, headers, body = await fetcher.fetch(url)
                progress.update(task, description="[green]Fetched![/green]")
            
            if status != 200:
                console.print(f"[red]Failed: HTTP {status}[/red]")
                return None
            
            # Extract articles
            console.print("[cyan]Extracting articles...[/cyan]")
            articles = self.bridge.extract_articles(body, url)
            
            if not articles:
                console.print("[yellow]No articles found[/yellow]")
                return None
            
            console.print(f"[green]✓ Found {len(articles)} articles[/green]")
            
            # Save feed
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            feed_path = self.bridge.save_feed(
                articles,
                output_dir / f"{name.lower().replace(' ', '_')}_feed",
                name,
                url
            )
            
            # Import to blogwatcher
            console.print(f"[cyan]Importing to blogwatcher...[/cyan]")
            await self._import_to_blogwatcher(name, feed_path, url)
            
            return feed_path
    
    async def _import_to_blogwatcher(self, name: str, feed_path: Path, source_url: str):
        """Add feed to blogwatcher."""
        import subprocess
        
        try:
            result = subprocess.run(
                ["blogwatcher", "add", name, str(feed_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print(f"[green]✓ Added to blogwatcher![/green]")
            else:
                console.print(f"[yellow]Note: {result.stderr}[/yellow]")
        except FileNotFoundError:
            console.print("[yellow]blogwatcher CLI not found. Feed saved but not imported.[/yellow]")
            console.print(f"[dim]Manual import: blogwatcher add \"{name}\" \"{feed_path}\"[/dim]")
    
    async def batch_scrape(self, sites: list, output_dir: Path):
        """Scrape multiple sites."""
        results = []
        
        for site in sites:
            feed_path = await self.scrape_and_import(
                site['url'],
                site['name'],
                output_dir
            )
            results.append({
                'name': site['name'],
                'url': site['url'],
                'feed_path': str(feed_path) if feed_path else None,
                'success': feed_path is not None
            })
        
        # Summary
        table = Table(title="Batch Scrape Results")
        table.add_column("Site", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Feed", style="dim")
        
        for result in results:
            status = "✓" if result['success'] else "✗"
            feed = result['feed_path'] or "N/A"
            table.add_row(result['name'], status, feed[-40:] if feed else "N/A")
        
        console.print(table)
        
        return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Integrate WebReaper with blogwatcher"
    )
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("--name", "-n", required=True, help="Feed name")
    parser.add_argument("--output", "-o", default="./feeds", help="Output directory")
    parser.add_argument("--stealth", "-s", action="store_true", help="Enable stealth mode")
    parser.add_argument("--tor", "-t", action="store_true", help="Use Tor")
    
    args = parser.parse_args()
    
    # Load config
    config = Config()
    if args.stealth:
        config.stealth.enabled = True
    if args.tor:
        config.stealth.tor_enabled = True
    
    # Run integration
    integrator = BlogwatcherIntegrator(config)
    
    async def run():
        feed_path = await integrator.scrape_and_import(
            args.url,
            args.name,
            Path(args.output)
        )
        
        if feed_path:
            console.print(f"\n[bold green]🎉 Success! Feed saved to:[/bold green]")
            console.print(f"[cyan]{feed_path}[/cyan]")
    
    asyncio.run(run())


if __name__ == "__main__":
    main()
