"""Configuration management for WebReaper."""

from pathlib import Path
from typing import Optional, List
import yaml
from pydantic import BaseModel, Field


class CrawlerConfig(BaseModel):
    """Crawler configuration."""
    max_depth: int = Field(default=3, ge=0, le=10)
    max_pages: int = Field(default=10000, ge=1)
    concurrency: int = Field(default=100, ge=1, le=1000)
    rate_limit: float = Field(default=10.0, ge=0.1)  # requests per second
    respect_robots: bool = False
    follow_redirects: bool = True
    timeout: int = Field(default=30, ge=1)
    user_agent: Optional[str] = None
    headers: dict = Field(default_factory=dict)
    cookies: dict = Field(default_factory=dict)
    auth: Optional[tuple] = None  # (username, password)


class StealthConfig(BaseModel):
    """Stealth mode configuration."""
    enabled: bool = False
    rotate_ua: bool = True
    randomize_canvas: bool = True
    spoof_webgl: bool = True
    randomize_fonts: bool = True
    randomize_screen: bool = True
    simulate_mouse: bool = False
    rotate_ja3: bool = False
    delay_min: float = 0.5
    delay_max: float = 3.0
    
    # Tor settings
    tor_enabled: bool = False
    tor_proxy: str = "socks5://127.0.0.1:9050"
    tor_control_port: int = 9051
    tor_password: Optional[str] = None
    circuit_rotate: int = 10  # requests per circuit


class SecurityConfig(BaseModel):
    """Security testing configuration."""
    enabled: bool = False
    xss_detection: bool = True
    sqli_detection: bool = True
    idor_detection: bool = True
    open_redirect: bool = True
    cors_scan: bool = True
    jwt_analyze: bool = True
    fuzz_parameters: bool = True
    fuzz_payloads: int = 50  # payloads per parameter
    auto_attack: bool = False  # Actually send payloads


class BlogwatcherConfig(BaseModel):
    """Blogwatcher integration configuration."""
    enabled: bool = False
    output_format: str = "rss"  # rss, json, atom
    scrape_interval: int = 3600  # seconds
    article_selectors: List[str] = Field(default_factory=lambda: [
        "article",
        "[class*='post']",
        "[class*='article']",
        "[class*='entry']",
        ".blog-item"
    ])
    title_selectors: List[str] = Field(default_factory=lambda: [
        "h1",
        "h2",
        "[class*='title']",
        ".entry-title"
    ])
    content_selectors: List[str] = Field(default_factory=lambda: [
        "article",
        "[class*='content']",
        ".entry-content",
        "main"
    ])
    date_selectors: List[str] = Field(default_factory=lambda: [
        "time",
        "[class*='date']",
        ".published",
        ".entry-date"
    ])


class OutputConfig(BaseModel):
    """Output configuration."""
    format: str = "json"  # json, csv, xml, markdown, html
    directory: Path = Field(default=Path("./output"))
    save_responses: bool = False
    save_screenshots: bool = False
    include_headers: bool = True


class Config(BaseModel):
    """Main configuration."""
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    stealth: StealthConfig = Field(default_factory=StealthConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    blogwatcher: BlogwatcherConfig = Field(default_factory=BlogwatcherConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)
