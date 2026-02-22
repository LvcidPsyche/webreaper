"""Command line interface for WebReaper."""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import Config
from .crawler import Crawler
from .modules.security import SecurityScanner
from .modules.blogwatcher import BlogwatcherBridge

console = Console()


@click.group()
@click.option('--config', '-c', type=click.Path(), help='Path to config file')
@click.pass_context
def cli(ctx, config):
    """WebReaper - Ultimate Web Scraper
    
    A high-performance web scraper with stealth capabilities,
    security testing features, and blogwatcher integration.
    
    Examples:
        webreaper crawl https://example.com
        webreaper crawl https://example.com --stealth --depth 5
        webreaper security https://example.com
        webreaper blogwatcher https://example.com/blog
    """
    ctx.ensure_object(dict)
    
    # Load config
    if config and Path(config).exists():
        ctx.obj['config'] = Config.from_yaml(Path(config))
    else:
        ctx.obj['config'] = Config()


@cli.command()
@click.argument('urls', nargs=-1, required=True)
@click.option('--depth', '-d', default=3, help='Maximum crawl depth')
@click.option('--max-pages', '-m', default=1000, help='Maximum pages to crawl')
@click.option('--concurrency', '-c', default=100, help='Number of concurrent workers')
@click.option('--output', '-o', default='./output', help='Output directory')
@click.option('--format', '-f', default='json', type=click.Choice(['json', 'csv']))
@click.option('--stealth', is_flag=True, help='Enable stealth mode')
@click.option('--tor', is_flag=True, help='Route through Tor')
@click.option('--delay-min', default=0.5, help='Minimum delay between requests')
@click.option('--delay-max', default=3.0, help='Maximum delay between requests')
@click.pass_context
def crawl(ctx, urls: List[str], depth: int, max_pages: int, concurrency: int,
          output: str, format: str, stealth: bool, tor: bool, 
          delay_min: float, delay_max: float):
    """Crawl website(s) and extract data."""
    
    config = ctx.obj['config']
    config.crawler.max_depth = depth
    config.crawler.max_pages = max_pages
    config.crawler.concurrency = concurrency
    config.output.directory = Path(output)
    config.output.format = format
    
    if stealth or tor:
        config.stealth.enabled = True
        config.stealth.tor_enabled = tor
        config.stealth.delay_min = delay_min
        config.stealth.delay_max = delay_max
    
    console.print(f"[bold blue]🕷️ WebReaper Crawler[/bold blue]")
    console.print(f"Target: {', '.join(urls)}")
    console.print(f"Depth: {depth} | Max Pages: {max_pages} | Workers: {concurrency}")
    
    if stealth:
        console.print(f"[yellow]⚡ Stealth mode enabled[/yellow]")
    if tor:
        console.print(f"[magenta]🧅 Tor routing enabled[/magenta]")
    
    async def run():
        crawler = Crawler(config)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Crawling...", total=None)
            
            def update_progress(result):
                progress.update(task, description=f"[cyan]Crawled: {result.url[:50]}...[/cyan]")
            
            results = await crawler.crawl(list(urls), callback=update_progress)
            progress.update(task, description=f"[green]Complete! {len(results)} pages crawled[/green]")
        
        # Save results
        crawler.save_results(config.output.directory, config.output.format)
        
        # Summary table
        table = Table(title="Crawl Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Pages Crawled", str(len(results)))
        table.add_row("Internal Links", str(sum(len(r.links) for r in results)))
        table.add_row("External Links", str(sum(len(r.external_links) for r in results)))
        table.add_row("Total Size", f"{sum(len(r.content_text) for r in results) / 1024 / 1024:.2f} MB")
        
        console.print(table)
    
    asyncio.run(run())


@cli.command()
@click.argument('url')
@click.option('--xss', is_flag=True, default=True, help='Check for XSS')
@click.option('--sqli', is_flag=True, default=True, help='Check for SQL injection')
@click.option('--auto-attack', is_flag=True, help='Send actual attack payloads')
@click.option('--output', '-o', default='./security_report.json', help='Output file')
@click.pass_context
def security(ctx, url: str, xss: bool, sqli: bool, auto_attack: bool, output: str):
    """Security scan a website."""
    
    config = ctx.obj['config']
    config.security.enabled = True
    config.security.xss_detection = xss
    config.security.sqli_detection = sqli
    config.security.auto_attack = auto_attack
    
    console.print(f"[bold red]🔒 WebReaper Security Scanner[/bold red]")
    console.print(f"Target: {url}")
    
    if auto_attack:
        console.print("[yellow]⚠️  Auto-attack enabled - sending payloads![/yellow]")
    
    async def run():
        from .fetcher import StealthFetcher
        
        scanner = SecurityScanner(auto_attack=auto_attack)
        
        async with StealthFetcher(config.stealth) as fetcher:
            status, headers, body = await fetcher.fetch(url)
            
            if status != 200:
                console.print(f"[red]Failed to fetch {url}: {status}[/red]")
                return
            
            # Extract forms
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(body, 'lxml')
            forms = []
            for form in soup.find_all('form'):
                forms.append({
                    'action': form.get('action', ''),
                    'method': form.get('method', 'GET').upper(),
                    'inputs': [{'name': i.get('name'), 'type': i.get('type', 'text')} 
                              for i in form.find_all(['input', 'textarea', 'select'])]
                })
            
            # Scan
            findings = scanner.scan(url, headers, body, forms)
            
            # Display results
            if findings:
                console.print(f"\n[red]Found {len(findings)} security issues:[/red]")
                
                table = Table(title="Security Findings")
                table.add_column("Type", style="cyan")
                table.add_column("Severity", style="red")
                table.add_column("Evidence", style="yellow")
                
                for finding in findings:
                    table.add_row(
                        finding['type'],
                        finding['severity'],
                        finding['evidence'][:50] + "..."
                    )
                
                console.print(table)
            else:
                console.print("[green]No security issues found![/green]")
            
            # Save report
            import json
            report = scanner.generate_report()
            with open(output, 'w') as f:
                json.dump(report, f, indent=2)
            
            console.print(f"\n[green]Report saved to {output}[/green]")
    
    asyncio.run(run())


@cli.command()
@click.argument('url')
@click.option('--output', '-o', default='./feed', help='Output file (without extension)')
@click.option('--format', '-f', default='rss', type=click.Choice(['rss', 'json']))
@click.option('--title', default='Generated Feed', help='Feed title')
@click.pass_context
def blogwatcher(ctx, url: str, output: str, format: str, title: str):
    """Scrape RSS-less site and generate feed."""
    
    config = ctx.obj['config']
    config.blogwatcher.enabled = True
    config.blogwatcher.output_format = format
    
    console.print(f"[bold green]📰 WebReaper Blogwatcher Bridge[/bold green]")
    console.print(f"Target: {url}")
    console.print(f"Format: {format.upper()}")
    
    async def run():
        from .fetcher import StealthFetcher
        
        bridge = BlogwatcherBridge(config.blogwatcher)
        
        async with StealthFetcher(config.stealth) as fetcher:
            console.print("[cyan]Fetching page...[/cyan]")
            status, headers, body = await fetcher.fetch(url)
            
            if status != 200:
                console.print(f"[red]Failed to fetch {url}: {status}[/red]")
                return
            
            console.print("[cyan]Extracting articles...[/cyan]")
            articles = bridge.extract_articles(body, url)
            
            if not articles:
                console.print("[yellow]No articles found[/yellow]")
                return
            
            console.print(f"[green]Found {len(articles)} articles![/green]")
            
            # Show preview
            table = Table(title="Extracted Articles")
            table.add_column("Title", style="cyan")
            table.add_column("Date", style="green")
            
            for article in articles[:10]:
                table.add_row(
                    article['title'][:50] + "..." if len(article['title']) > 50 else article['title'],
                    article.get('date', 'Unknown')[:10]
                )
            
            console.print(table)
            
            # Save feed
            output_path = bridge.save_feed(
                articles,
                Path(output),
                title,
                url
            )
            
            console.print(f"\n[green]Feed saved to {output_path}[/green]")
            
            # Import into blogwatcher
            console.print(f"\nTo add to blogwatcher:")
            console.print(f"  blogwatcher add \"{title}\" \"{output_path}\"")
    
    asyncio.run(run())


@cli.command()
def genres():
    """Show available information genres."""
    genres_data = [
        ("🔒", "Cybersecurity", "Vulns, exploits, CTF, threat intel"),
        ("🤖", "AI/ML", "Research papers, models, benchmarks"),
        ("💻", "Systems", "Kernel, cloud, distributed systems"),
        ("🔧", "Hardware", "PCB, electronics, SDR, radio"),
        ("🎮", "Reverse Eng", "Binary analysis, game hacking"),
        ("🌐", "Web Dev", "Frameworks, performance, standards"),
        ("📊", "Data Science", "Datasets, visualization, stats"),
        ("🚀", "Startups", "Funding, business, market analysis"),
        ("🔬", "Science", "Physics, biology, space research"),
        ("🎨", "Creative Code", "Generative art, demoscene"),
        ("🏛️", "Gov/FOIA", "Documents, legal, transparency"),
        ("🎲", "Niche/Weird", "Esolangs, vintage, dead tech"),
    ]
    
    table = Table(title="WebReaper Information Genres")
    table.add_column("Icon", justify="center")
    table.add_column("Genre", style="cyan bold")
    table.add_column("Description", style="green")
    
    for icon, name, desc in genres_data:
        table.add_row(icon, name, desc)
    
    console.print(table)
    console.print("\n[dim]Use --genre with crawl command to focus on specific content types[/dim]")


@cli.command()
@click.option('--path', '-p', default='./webreaper.yaml', help='Config file path')
def init(path: str):
    """Initialize default configuration file."""
    config = Config()
    config.to_yaml(Path(path))
    console.print(f"[green]✓ Configuration file created: {path}[/green]")
    console.print("[dim]Edit this file to customize WebReaper settings[/dim]")


def main():
    """Entry point."""
    cli()


if __name__ == '__main__':
    main()
