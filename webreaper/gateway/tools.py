"""Tool manifest — all WebReaper capabilities exposed to agents."""

import logging
from webreaper.config import Config
from webreaper.crawler import Crawler
from webreaper.database import get_db_manager
from webreaper.modules.security import SecurityScanner

logger = logging.getLogger("webreaper.gateway.tools")

TOOL_MANIFEST = [
    {
        "name": "crawl",
        "description": "Crawl a website recursively, extracting content, links, and metadata",
        "permission": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL to crawl"},
                "depth": {"type": "integer", "description": "Max crawl depth", "default": 3},
                "concurrency": {"type": "integer", "description": "Concurrent requests", "default": 50},
                "stealth": {"type": "boolean", "description": "Enable stealth mode", "default": False},
            },
            "required": ["url"],
        },
    },
    {
        "name": "security_scan",
        "description": "Scan a URL for security vulnerabilities (XSS, SQLi, headers, JWT, SSRF)",
        "permission": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL"},
                "auto_attack": {"type": "boolean", "description": "Send actual attack payloads", "default": False},
            },
            "required": ["url"],
        },
    },
    {
        "name": "fingerprint",
        "description": "Detect technology stack of a website (CMS, frameworks, CDN, libraries)",
        "permission": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "watch",
        "description": "Monitor a URL for content changes",
        "permission": "write",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to monitor"},
                "interval": {"type": "integer", "description": "Check interval in seconds", "default": 3600},
            },
            "required": ["url"],
        },
    },
    {
        "name": "blogwatch",
        "description": "Extract articles from a website without RSS feed",
        "permission": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Blog/news site URL"},
                "genre": {"type": "string", "description": "Content genre filter"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "digest",
        "description": "Generate AI-powered summary of collected articles",
        "permission": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "genre": {"type": "string", "description": "Filter by genre"},
                "limit": {"type": "integer", "description": "Max articles to process", "default": 50},
            },
        },
    },
    {
        "name": "search",
        "description": "Full-text search across all crawled content",
        "permission": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_results",
        "description": "Query crawl results with filters",
        "permission": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "crawl_id": {"type": "string"},
                "domain": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
]


async def execute_tool(name: str, params: dict) -> dict:
    """Execute a WebReaper tool and return the result."""
    db = get_db_manager()

    if name == "crawl":
        config = Config()
        config.crawler.max_depth = params.get("depth", 3)
        config.crawler.concurrency = params.get("concurrency", 50)
        config.stealth.enabled = params.get("stealth", False)
        crawler = Crawler(config, db_manager=db)
        results = await crawler.crawl([params["url"]], callback=None)
        return {
            "pages_crawled": len(results),
            "summary": [{"url": r.url, "title": r.title, "status": r.status} for r in results[:20]],
        }

    elif name == "security_scan":
        from webreaper.fetcher import StealthFetcher
        from webreaper.config import StealthConfig
        fetcher_config = StealthConfig()
        async with StealthFetcher(fetcher_config) as fetcher:
            status, headers, body = await fetcher.fetch(params["url"])
        scanner = SecurityScanner(auto_attack=params.get("auto_attack", False))
        findings = scanner.scan(params["url"], headers, body, [])
        return {"findings_count": len(findings), "findings": findings[:20]}

    elif name == "fingerprint":
        from webreaper.fetcher import StealthFetcher
        from webreaper.config import StealthConfig
        fetcher_config = StealthConfig()
        async with StealthFetcher(fetcher_config) as fetcher:
            status, headers, body = await fetcher.fetch(params["url"])
        scanner = SecurityScanner()
        tech = scanner.fingerprint_tech(params["url"], headers, body)
        return tech

    elif name == "search":
        if not db:
            return {"error": "Database not available"}
        async with db.get_session() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT url, title FROM pages WHERE search_vector @@ plainto_tsquery(:q) LIMIT :limit"),
                {"q": params["query"], "limit": params.get("limit", 20)},
            )
            return {"results": [{"url": r.url, "title": r.title} for r in result.fetchall()]}

    elif name == "digest":
        from webreaper.modules.digest import generate_digest
        if not db:
            return {"error": "Database not available"}
        md = await generate_digest(db, genre=params.get("genre"), limit=params.get("limit", 50))
        return {"digest": md}

    else:
        return {"error": f"Unknown tool: {name}"}
