"""
WebReaper Dashboard UI
======================
An interactive, animated, fun-as-hell terminal UI for the WebReaper scraper.
Designed to make scraping addictive and visually stunning.
"""

import asyncio
import random
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
from enum import Enum

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich.columns import Columns
from rich import box

console = Console()


class Genre(Enum):
    """Information genres."""
    SECURITY = ("🔒", "Cybersecurity", "red")
    AI = ("🤖", "AI/ML", "cyan")
    SYSTEMS = ("💻", "Systems", "green")
    HARDWARE = ("🔧", "Hardware", "yellow")
    REVERSE_ENG = ("🎮", "Reverse Eng", "magenta")
    WEB_DEV = ("🌐", "Web Dev", "blue")
    DATA_SCIENCE = ("📊", "Data Science", "bright_cyan")
    STARTUPS = ("🚀", "Startups", "bright_green")
    SCIENCE = ("🔬", "Science", "bright_blue")
    CREATIVE = ("🎨", "Creative", "bright_magenta")
    GOVERNMENT = ("🏛️", "Gov/FOIA", "white")
    NICHE = ("🎲", "Niche", "dim")
    
    def __init__(self, icon: str, name: str, color: str):
        self.icon = icon
        self.genre_name = name
        self.color = color


@dataclass
class ScrapeStats:
    """Real-time scraping statistics."""
    urls_scraped: int = 0
    urls_failed: int = 0
    total_bytes: int = 0
    start_time: float = 0
    current_url: str = ""
    requests_per_sec: float = 0
    genres_active: Dict[str, int] = None
    
    def __post_init__(self):
        if self.genres_active is None:
            self.genres_active = {}


class AnimatedDashboard:
    """The main WebReaper dashboard with animations."""
    
    def __init__(self):
        self.stats = ScrapeStats(start_time=time.time())
        self.genres = list(Genre)
        self.active_genre: Optional[Genre] = None
        self.scraping = False
        self.spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.frame_index = 0
        
        # Simulated data for demo
        self.demo_articles = [
            ("🔒", "Critical RCE in Popular Library", "2 min ago"),
            ("🤖", "New AI Model Breaks Benchmark", "5 min ago"),
            ("💻", "Linux Kernel 6.8 Released", "12 min ago"),
            ("🔧", "Raspberry Pi 5 Review", "18 min ago"),
            ("🎮", "Game Cracked in Record Time", "25 min ago"),
            ("🌐", "New Web Framework Hits 100k Stars", "32 min ago"),
        ]
    
    def _get_spinner(self) -> str:
        """Get next spinner frame."""
        frame = self.spinner_frames[self.frame_index]
        self.frame_index = (self.frame_index + 1) % len(self.spinner_frames)
        return frame
    
    def _create_genre_cards(self) -> Columns:
        """Create animated genre cards."""
        cards = []
        
        for genre in self.genres:
            # Simulate random activity
            activity = random.randint(0, 50) if self.scraping else random.randint(0, 5)
            is_active = self.active_genre == genre
            
            # Pulse animation for active genre
            pulse = "█" if is_active else "░"
            
            content = Text()
            content.append(f"{genre.icon}\n", style=f"bold {genre.color}")
            content.append(f"{genre.genre_name}\n", style="white")
            content.append(f"{activity} new {pulse}", style=f"dim {genre.color}")
            
            card = Panel(
                Align.center(content),
                box=box.ROUNDED,
                border_style=genre.color if is_active else "dim",
                padding=(1, 2)
            )
            cards.append(card)
        
        return Columns(cards, equal=True, expand=True)
    
    def _create_live_monitor(self) -> Panel:
        """Create live scrape monitor."""
        if not self.scraping:
            content = Text("Ready to scrape... Press [S] to start", style="dim")
        else:
            spinner = self._get_spinner()
            content = Text()
            content.append(f"{spinner} Scraping in progress...\n\n", style="bold cyan")
            content.append(f"Current: {self.stats.current_url[:60]}...\n", style="green")
            content.append(f"Rate: {self.stats.requests_per_sec:.1f} req/s  |  ", style="yellow")
            content.append(f"Total: {self.stats.urls_scraped} pages  |  ", style="yellow")
            content.append(f"Size: {self.stats.total_bytes / 1024 / 1024:.2f} MB", style="yellow")
        
        return Panel(
            content,
            title="[bold cyan]🎯 LIVE SCRAPE MONITOR[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED
        )
    
    def _create_stats_panel(self) -> Panel:
        """Create statistics panel."""
        elapsed = time.time() - self.stats.start_time
        
        table = Table(show_header=False, box=None)
        table.add_column("Label", style="cyan")
        table.add_column("Value", style="green bold")
        
        table.add_row("Pages Scraped", str(self.stats.urls_scraped))
        table.add_row("Links Found", str(self.stats.urls_scraped * 12))  # Simulated
        table.add_row("Total Size", f"{self.stats.total_bytes / 1024 / 1024:.1f} MB")
        table.add_row("Rate", f"{self.stats.requests_per_sec:.0f} req/s")
        table.add_row("Uptime", f"{int(elapsed // 60)}m {int(elapsed % 60)}s")
        
        return Panel(
            table,
            title="[bold green]📈 STATS[/bold green]",
            border_style="green",
            box=box.ROUNDED
        )
    
    def _create_hot_panel(self) -> Panel:
        """Create hot right now panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Icon", justify="center")
        table.add_column("Headline", style="white")
        table.add_column("Time", style="dim", justify="right")
        
        # Rotate through demo articles
        start_idx = int(time.time()) % len(self.demo_articles)
        for i in range(4):
            idx = (start_idx + i) % len(self.demo_articles)
            icon, headline, ago = self.demo_articles[idx]
            table.add_row(icon, headline[:35] + "...", ago)
        
        return Panel(
            table,
            title="[bold red]🔥 HOT RIGHT NOW[/bold red]",
            border_style="red",
            box=box.ROUNDED
        )
    
    def _create_progress_bar(self) -> Panel:
        """Create animated progress bar."""
        progress = Progress(
            BarColumn(bar_width=50),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            expand=True
        )
        
        # Simulate progress
        percent = min(100, int((time.time() % 10) * 10))
        task = progress.add_task("", total=100, completed=percent)
        
        return Panel(
            progress,
            title="[bold yellow]⚡ SCRAPE PROGRESS[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED
        )
    
    def _create_help_bar(self) -> Text:
        """Create help bar at bottom."""
        help_text = Text()
        help_text.append("[S]", style="bold cyan")
        help_text.append(" Start  ", style="dim")
        help_text.append("[P]", style="bold cyan")
        help_text.append(" Pause  ", style="dim")
        help_text.append("[G]", style="bold cyan")
        help_text.append(" Genres  ", style="dim")
        help_text.append("[R]", style="bold cyan")
        help_text.append(" Report  ", style="dim")
        help_text.append("[Q]", style="bold cyan")
        help_text.append(" Quit  ", style="dim")
        help_text.append("[?]", style="bold cyan")
        help_text.append(" Help", style="dim")
        return help_text
    
    def render(self) -> Layout:
        """Render the full dashboard layout."""
        layout = Layout()
        
        # Split into sections
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="genres", size=12),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        # Header
        header_text = Text()
        header_text.append("🕷️ ", style="bold")
        header_text.append("WEBREAPER", style="bold cyan")
        header_text.append(" COMMAND CENTER", style="bold white")
        header_text.append("    [v1.0.0]", style="dim")
        header_text.append("    STATUS: ", style="dim")
        header_text.append("ONLINE", style="bold green")
        
        layout["header"].update(
            Panel(Align.center(header_text), box=box.SIMPLE, style="on black")
        )
        
        # Genre cards
        layout["genres"].update(self._create_genre_cards())
        
        # Main content
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        layout["main"]["left"].split_column(
            Layout(self._create_live_monitor(), name="monitor"),
            Layout(self._create_progress_bar(), name="progress", size=5)
        )
        
        layout["main"]["right"].split_column(
            Layout(self._create_stats_panel(), name="stats"),
            Layout(self._create_hot_panel(), name="hot")
        )
        
        # Footer
        layout["footer"].update(
            Panel(self._create_help_bar(), box=box.SIMPLE, style="on black")
        )
        
        return layout
    
    async def run(self):
        """Run the animated dashboard."""
        console.clear()
        
        with Live(self.render(), refresh_per_second=10, screen=True) as live:
            while True:
                # Update stats if scraping
                if self.scraping:
                    self.stats.urls_scraped += random.randint(0, 3)
                    self.stats.total_bytes += random.randint(1000, 100000)
                    self.stats.requests_per_sec = random.uniform(50, 200)
                    self.stats.current_url = f"https://example.com/page/{self.stats.urls_scraped}"
                
                # Update display
                live.update(self.render())
                
                await asyncio.sleep(0.1)
    
    def start_scraping(self):
        """Start scraping simulation."""
        self.scraping = True
        self.stats.start_time = time.time()
        self.active_genre = random.choice(self.genres)
    
    def stop_scraping(self):
        """Stop scraping."""
        self.scraping = False
        self.active_genre = None


class GenreSelector:
    """Interactive genre selector with animations."""
    
    def __init__(self):
        self.genres = list(Genre)
        self.selected: List[Genre] = []
    
    def render(self) -> Layout:
        """Render genre selector."""
        layout = Layout()
        
        # Title
        title = Panel(
            Align.center(Text("SELECT GENRES TO SCRAPE", style="bold cyan")),
            box=box.DOUBLE
        )
        
        # Genre list
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Status", justify="center", width=3)
        table.add_column("Icon", justify="center")
        table.add_column("Genre", style="bold")
        table.add_column("Description")
        
        for i, genre in enumerate(self.genres):
            status = "✓" if genre in self.selected else "○"
            desc = self._get_genre_description(genre)
            table.add_row(
                f"[{'green' if genre in self.selected else 'dim'}]{status}[/{'green' if genre in self.selected else 'dim'}]",
                genre.icon,
                f"[{genre.color}]{genre.genre_name}[/{genre.color}]",
                desc
            )
        
        layout.split_column(
            Layout(title, size=5),
            Layout(Panel(table, box=box.ROUNDED)),
            Layout(
                Panel(
                    Align.center("[Space] Toggle  [A] All  [N] None  [Enter] Confirm  [Q] Cancel"),
                    box=box.SIMPLE
                ),
                size=3
            )
        )
        
        return layout
    
    def _get_genre_description(self, genre: Genre) -> str:
        """Get description for genre."""
        descriptions = {
            Genre.SECURITY: "CVEs, exploits, threat intel, CTF",
            Genre.AI: "Research papers, models, benchmarks",
            Genre.SYSTEMS: "Kernel, cloud, distributed systems",
            Genre.HARDWARE: "PCB, electronics, SDR, radio",
            Genre.REVERSE_ENG: "Binary analysis, game hacking",
            Genre.WEB_DEV: "Frameworks, performance, standards",
            Genre.DATA_SCIENCE: "Datasets, visualization, ML",
            Genre.STARTUPS: "Funding, business, market analysis",
            Genre.SCIENCE: "Physics, biology, space research",
            Genre.CREATIVE: "Generative art, demoscene",
            Genre.GOVERNMENT: "Documents, legal, transparency",
            Genre.NICHE: "Esolangs, vintage, dead tech",
        }
        return descriptions.get(genre, "")


def launch_dashboard():
    """Launch the WebReaper dashboard."""
    dashboard = AnimatedDashboard()
    
    # Start scraping for demo
    dashboard.start_scraping()
    
    try:
        asyncio.run(dashboard.run())
    except KeyboardInterrupt:
        console.print("\n[bold green]👋 Thanks for using WebReaper![/bold green]")


if __name__ == "__main__":
    launch_dashboard()
