"""Command line interface for WebReaper."""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import Config
from .crawler import Crawler
from .database import get_db_manager
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
        webreaper digest --genre cybersecurity
        webreaper watch https://example.com
        webreaper stats
        webreaper fingerprint https://example.com
    """
    ctx.ensure_object(dict)

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
@click.option('--respect-robots', is_flag=True, help='Respect robots.txt')
@click.option('--rate-limit', default=10.0, help='Max requests per second (0=unlimited)')
@click.option('--genre', default=None, help='Tag crawl with a genre label')
@click.option('--no-db', is_flag=True, help='Skip database persistence')
@click.option('--dashboard', is_flag=True, help='Show live dashboard while crawling')
@click.pass_context
def crawl(ctx, urls: List[str], depth: int, max_pages: int, concurrency: int,
          output: str, format: str, stealth: bool, tor: bool,
          delay_min: float, delay_max: float, respect_robots: bool,
          rate_limit: float, genre: Optional[str], no_db: bool, dashboard: bool):
    """Crawl website(s) and extract data."""

    config = ctx.obj['config']
    config.crawler.max_depth = depth
    config.crawler.max_pages = max_pages
    config.crawler.concurrency = concurrency
    config.crawler.respect_robots = respect_robots
    config.crawler.rate_limit = rate_limit
    config.output.directory = Path(output)
    config.output.format = format

    if stealth or tor:
        config.stealth.enabled = True
        config.stealth.tor_enabled = tor
        config.stealth.delay_min = delay_min
        config.stealth.delay_max = delay_max

    if genre:
        config.__dict__['genre'] = genre

    console.print(f"[bold blue]🕷️ WebReaper Crawler[/bold blue]")
    console.print(f"Target: {', '.join(urls)}")
    console.print(f"Depth: {depth} | Max Pages: {max_pages} | Workers: {concurrency}")
    if rate_limit > 0:
        console.print(f"[dim]Rate limit: {rate_limit} req/s[/dim]")
    if stealth:
        console.print(f"[yellow]⚡ Stealth mode enabled[/yellow]")
    if tor:
        console.print(f"[magenta]🧅 Tor routing enabled[/magenta]")

    # Dashboard mode: hand off to animated UI
    if dashboard:
        from .dashboard import launch_dashboard
        launch_dashboard(start_urls=list(urls), config=config)
        return

    # Database
    db = None
    if not no_db:
        db = get_db_manager()
        if db:
            console.print(f"[green]✓ Database connected[/green]")
        else:
            console.print(f"[dim]No DATABASE_URL set — saving to files only[/dim]")

    async def run():
        if db:
            await db.init_async()

        try:
            crawler_obj = Crawler(config, db_manager=db)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Crawling...", total=None)

                def update_progress(result):
                    progress.update(task, description=f"[cyan]Crawled: {result.url[:60]}[/cyan]")

                results = await crawler_obj.crawl(list(urls), callback=update_progress)
                progress.update(task, description=f"[green]Done! {len(results)} pages[/green]")

            crawler_obj.save_results(config.output.directory, config.output.format)

            table = Table(title="Crawl Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Pages Crawled", str(len(results)))
            table.add_row("Internal Links", str(sum(len(r.links) for r in results)))
            table.add_row("External Links", str(sum(len(r.external_links) for r in results)))
            total_mb = sum(len(r.content_text) for r in results) / 1024 / 1024
            table.add_row("Total Size", f"{total_mb:.2f} MB")
            if db:
                table.add_row("Saved to DB", "✓")
            console.print(table)
        finally:
            if db:
                await db.close()

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
        from bs4 import BeautifulSoup

        scanner = SecurityScanner(auto_attack=auto_attack)

        async with StealthFetcher(config.stealth) as fetcher:
            status, headers, body = await fetcher.fetch(url)

            if status != 200:
                console.print(f"[red]Failed to fetch {url}: {status}[/red]")
                return

            soup = BeautifulSoup(body, 'lxml')
            forms = []
            for form in soup.find_all('form'):
                forms.append({
                    'action': form.get('action', ''),
                    'method': form.get('method', 'GET').upper(),
                    'inputs': [{'name': i.get('name'), 'type': i.get('type', 'text')}
                               for i in form.find_all(['input', 'textarea', 'select'])]
                })

            findings = scanner.scan(url, headers, body, forms)

            if findings:
                console.print(f"\n[red]Found {len(findings)} security issues:[/red]")
                table = Table(title="Security Findings")
                table.add_column("Type", style="cyan")
                table.add_column("Severity", style="red")
                table.add_column("Evidence", style="yellow")
                for finding in findings:
                    sev = finding['severity']
                    color = {"Critical": "bold red", "High": "red", "Medium": "yellow", "Low": "dim"}.get(sev, "white")
                    table.add_row(
                        finding['type'],
                        f"[{color}]{sev}[/{color}]",
                        (finding.get('evidence', '') or '')[:60],
                    )
                console.print(table)
            else:
                console.print("[green]No security issues found![/green]")

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
@click.option('--save-db', is_flag=True, help='Save articles to database')
@click.option('--genre', default=None, help='Tag articles with genre')
@click.pass_context
def blogwatcher(ctx, url: str, output: str, format: str, title: str, save_db: bool, genre: Optional[str]):
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
        db = get_db_manager() if save_db else None

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

            # Optionally tag and save to DB
            if genre:
                for a in articles:
                    a['genre'] = genre
                    a['source_feed'] = title
                    a['source_url'] = url

            if db:
                await db.init_async()
                saved = 0
                for a in articles:
                    aid = await db.save_article(a)
                    if aid:
                        saved += 1
                console.print(f"[green]Saved {saved} new articles to DB[/green]")
                await db.close()

            table = Table(title="Extracted Articles")
            table.add_column("Title", style="cyan")
            table.add_column("Date", style="green")
            for article in articles[:10]:
                t = article['title']
                table.add_row(t[:50] + "..." if len(t) > 50 else t, article.get('date', 'Unknown')[:10])
            console.print(table)

            output_path = bridge.save_feed(articles, Path(output), title, url)
            console.print(f"\n[green]Feed saved to {output_path}[/green]")
            console.print(f"\nTo add to blogwatcher:")
            console.print(f'  blogwatcher add "{title}" "{output_path}"')

    asyncio.run(run())


@cli.command()
@click.option('--genre', '-g', default=None, help='Filter by genre')
@click.option('--limit', '-l', default=50, help='Articles to include')
@click.option('--output', '-o', default=None, help='Save digest to file (default: print)')
@click.option('--mark-processed', is_flag=True, default=True, help='Mark articles as processed')
def digest(genre: Optional[str], limit: int, output: Optional[str], mark_processed: bool):
    """Generate AI-powered digest from collected articles."""

    db = get_db_manager()
    if not db:
        console.print("[red]DATABASE_URL not set. Run with database to use digest.[/red]")
        sys.exit(1)

    async def run():
        from .modules.digest import generate_digest
        await db.init_async()
        try:
            result = await generate_digest(db, genre=genre, limit=limit, mark_processed=mark_processed)
            if output:
                Path(output).write_text(result)
                console.print(f"[green]Digest saved to {output}[/green]")
            else:
                console.print(result)
        finally:
            await db.close()

    asyncio.run(run())


@cli.command()
@click.argument('url')
@click.option('--interval', '-i', default=3600, help='Check interval in seconds')
@click.option('--once', is_flag=True, help='Check once and exit (no loop)')
@click.option('--notify', is_flag=True, help='Print notification on change')
def watch(url: str, interval: int, once: bool, notify: bool):
    """Monitor a URL for content changes."""

    db = get_db_manager()
    if not db:
        console.print("[yellow]No DATABASE_URL — running without persistence[/yellow]")

    async def run():
        from .modules.monitor import Monitor
        await db.init_async() if db else None
        try:
            monitor = Monitor(db_manager=db)
            await monitor.run(url, interval=interval, once=once, notify=notify)
        finally:
            await db.close() if db else None

    asyncio.run(run())


@cli.command()
@click.argument('url')
@click.option('--output', '-o', default='./fingerprint.json', help='Output file')
def fingerprint(url: str, output: str):
    """Fingerprint a website's technology stack."""

    async def run():
        from .fetcher import StealthFetcher
        from .modules.security import SecurityScanner
        from .config import Config
        import json

        cfg = Config()
        scanner = SecurityScanner()

        async with StealthFetcher(cfg.stealth) as fetcher:
            status, headers, body = await fetcher.fetch(url)

        if status != 200:
            console.print(f"[red]Failed: HTTP {status}[/red]")
            return

        tech = scanner.fingerprint_tech(url, headers, body)

        table = Table(title=f"Tech Stack — {url}")
        table.add_column("Category", style="cyan")
        table.add_column("Detected", style="green")
        for category, items in tech.items():
            if items:
                table.add_row(category, ", ".join(items))
        console.print(table)

        with open(output, 'w') as f:
            json.dump(tech, f, indent=2)
        console.print(f"[green]Saved to {output}[/green]")

    asyncio.run(run())


@cli.command()
@click.option('--crawl-id', default=None, help='Specific crawl ID to report on')
@click.option('--output', '-o', default='./report.html', help='Output HTML file')
def report(crawl_id: Optional[str], output: str):
    """Generate HTML report from database."""

    db = get_db_manager()
    if not db:
        console.print("[red]DATABASE_URL not set.[/red]")
        sys.exit(1)

    async def run():
        from .modules.reporter import generate_html_report
        await db.init_async()
        try:
            await generate_html_report(db, crawl_id=crawl_id, output_path=Path(output))
            console.print(f"[green]Report saved to {output}[/green]")
        finally:
            await db.close()

    asyncio.run(run())


@cli.command()
def stats():
    """Show crawl history and database statistics."""

    db = get_db_manager()
    if not db:
        console.print("[red]DATABASE_URL not set.[/red]")
        sys.exit(1)

    async def run():
        await db.init_async()
        try:
            crawls = await db.get_crawl_stats()

            if not crawls:
                console.print("[yellow]No crawls in database yet.[/yellow]")
                return

            table = Table(title="Crawl History")
            table.add_column("ID", style="dim", width=8)
            table.add_column("URL", style="cyan", max_width=40)
            table.add_column("Status", style="green")
            table.add_column("Pages", justify="right")
            table.add_column("Failed", justify="right", style="red")
            table.add_column("Req/s", justify="right", style="yellow")
            table.add_column("Genre")
            table.add_column("Started", style="dim")

            for c in crawls:
                cid = str(c['id'])[:8]
                started = str(c['started_at'])[:16] if c['started_at'] else '—'
                rps = f"{c['requests_per_sec']:.1f}" if c['requests_per_sec'] else '—'
                status_color = "green" if c['status'] == 'completed' else "yellow"
                table.add_row(
                    cid,
                    str(c['target_url'])[:40],
                    f"[{status_color}]{c['status']}[/{status_color}]",
                    str(c['pages_crawled'] or 0),
                    str(c['pages_failed'] or 0),
                    rps,
                    c['genre'] or '—',
                    started,
                )

            console.print(table)
        finally:
            await db.close()

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
    console.print("\n[dim]Use --genre with crawl command to tag scrapes[/dim]")


@cli.command()
@click.option('--path', '-p', default='./webreaper.yaml', help='Config file path')
def init(path: str):
    """Initialize default configuration file."""
    config = Config()
    config.to_yaml(Path(path))
    console.print(f"[green]✓ Configuration file created: {path}[/green]")
    console.print("[dim]Edit this file to customize WebReaper settings[/dim]")


@cli.command()
@click.option('--host', default='127.0.0.1', help='Server host')
@click.option('--port', '-p', default=8000, help='Server port')
def server(host: str, port: int):
    """Start the WebReaper API server."""
    console.print(f"[bold blue]WebReaper API Server[/bold blue]")
    console.print(f"Starting on {host}:{port}")
    console.print(f"Dashboard: http://{host}:{port}")

    from server.main import start_server
    start_server(host=host, port=port)


@cli.command()
@click.argument('provider', type=click.Choice(['openclaw', 'claude_api', 'openai_api', 'ollama']))
@click.option('--uri', default=None, help='WebSocket URI (for openclaw/custom)')
@click.option('--api-key', default=None, help='API key (for claude/openai)')
@click.option('--model', default=None, help='Model name')
def connect(provider: str, uri: str, api_key: str, model: str):
    """Connect to an AI agent provider."""
    console.print(f"[bold cyan]Connecting to {provider}...[/bold cyan]")

    config = {}
    if uri:
        config["uri"] = uri
    if api_key:
        config["api_key"] = api_key
    if model:
        config["model"] = model

    async def run():
        from webreaper.gateway.gateway import AgentGateway
        gateway = AgentGateway.instance()
        success = await gateway.connect(provider, config)
        if success:
            console.print(f"[green]Connected to {provider}[/green]")
        else:
            console.print(f"[red]Failed to connect to {provider}[/red]")

    asyncio.run(run())


@cli.group()
def license():
    """Manage your WebReaper license."""
    pass


@license.command("status")
def license_status():
    """Show current license and monthly usage."""
    from .license import get_license, get_tier, get_page_limit, TIER_PRICES
    from .usage import get_summary

    tier = get_tier()
    lic = get_license()
    limit = get_page_limit()
    summary = get_summary(limit)

    table = Table(title="WebReaper License")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    if lic:
        key_preview = lic["key"][:11] + "****"
        table.add_row("Status", "[green]Active[/green]")
        table.add_row("Tier", f"[bold]{tier}[/bold]")
        table.add_row("Key", key_preview)
        table.add_row("Installed", lic.get("installed_at", "")[:10])
        if tier in TIER_PRICES:
            table.add_row("Plan", TIER_PRICES[tier])
    else:
        table.add_row("Status", "[yellow]No license installed[/yellow]")
        table.add_row("Tier", "FREE (CLI only, limited)")

    table.add_row("Month", summary["month"])
    table.add_row("Pages used", str(summary["pages_used"]))
    if summary["pages_limit"]:
        bar = "█" * int(summary["pct_used"] / 10) + "░" * (10 - int(summary["pct_used"] / 10))
        table.add_row("Pages limit", f"{summary['pages_limit']}/month")
        table.add_row("Remaining", str(summary["pages_remaining"]))
        color = "red" if summary["pct_used"] > 80 else "yellow" if summary["pct_used"] > 50 else "green"
        table.add_row("Usage", f"[{color}]{bar} {summary['pct_used']}%[/{color}]")
    else:
        table.add_row("Pages limit", "[green]Unlimited[/green]")

    console.print(table)


@license.command("activate")
@click.argument("key")
def license_activate(key: str):
    """Install a license key (e.g. WR-PRO-ABCD1234-EFGH5678)."""
    from .license import install_license

    result = install_license(key)
    if result["valid"]:
        console.print(f"[green]License activated![/green] Tier: [bold]{result['tier']}[/bold]")
    else:
        console.print(f"[red]Invalid key:[/red] {result['error']}")


@license.command("deactivate")
def license_deactivate():
    """Remove the installed license."""
    from .license import revoke_license, get_license

    if not get_license():
        console.print("[yellow]No license installed.[/yellow]")
        return
    revoke_license()
    console.print("[green]License removed.[/green]")


@license.command("generate")
@click.argument("tier", type=click.Choice(["lite", "pro"], case_sensitive=False))
def license_generate(tier: str):
    """[Admin] Generate a license key. Requires WEBREAPER_LICENSE_SECRET env var."""
    import os
    from .license import generate_key, _DEV_SECRET, _secret

    if _secret() == _DEV_SECRET:
        console.print("[yellow]Warning: Using dev secret. Set WEBREAPER_LICENSE_SECRET for production keys.[/yellow]")

    key = generate_key(tier)
    console.print(f"[green]Generated {tier.upper()} key:[/green]")
    console.print(f"[bold cyan]{key}[/bold cyan]")


def main():
    cli()


if __name__ == '__main__':
    main()
