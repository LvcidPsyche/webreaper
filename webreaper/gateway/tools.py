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
        "description": "Scan a URL for security vulnerabilities (XSS, SQLi, missing headers, JWT, SSRF). Set auto_attack=true for active payload testing.",
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
        "description": "Detect technology stack of a website (CMS, frameworks, CDN, WAF, JS libraries)",
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
        "name": "recon",
        "description": "Full reconnaissance: crawl + fingerprint + security scan in one operation. Best first tool for any target.",
        "permission": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL"},
                "depth": {"type": "integer", "description": "Crawl depth", "default": 2},
                "stealth": {"type": "boolean", "description": "Enable stealth mode", "default": False},
            },
            "required": ["url"],
        },
    },
    {
        "name": "watch",
        "description": "Take a snapshot of a URL for change monitoring. Returns content hash and summary.",
        "permission": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to snapshot"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "blogwatch",
        "description": "Extract articles from a website without an RSS feed",
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
        "description": "Query crawl results with filters. Returns page list with metadata.",
        "permission": "read",
        "parameters": {
            "type": "object",
            "properties": {
                "crawl_id": {"type": "string", "description": "Filter by crawl ID"},
                "domain": {"type": "string", "description": "Filter by domain"},
                "status_code": {"type": "integer", "description": "Filter by HTTP status code"},
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

    elif name == "recon":
        from webreaper.fetcher import StealthFetcher
        from webreaper.config import StealthConfig
        # Crawl
        config = Config()
        config.crawler.max_depth = params.get("depth", 2)
        config.crawler.concurrency = 20
        config.stealth.enabled = params.get("stealth", False)
        crawler = Crawler(config, db_manager=db)
        results = await crawler.crawl([params["url"]], callback=None)
        # Fingerprint + scan the root URL
        fetcher_config = StealthConfig()
        async with StealthFetcher(fetcher_config) as fetcher:
            status, headers, body = await fetcher.fetch(params["url"])
        scanner = SecurityScanner(auto_attack=False)
        findings = scanner.scan(params["url"], headers, body, [])
        tech = scanner.fingerprint_tech(params["url"], headers, body)
        return {
            "pages_crawled": len(results),
            "technology": tech,
            "findings_count": len(findings),
            "findings": findings[:10],
            "summary": [{"url": r.url, "title": r.title, "status": r.status} for r in results[:10]],
        }

    elif name == "watch":
        import hashlib
        from webreaper.fetcher import StealthFetcher
        from webreaper.config import StealthConfig
        fetcher_config = StealthConfig()
        async with StealthFetcher(fetcher_config) as fetcher:
            status, headers, body = await fetcher.fetch(params["url"])
        content_hash = hashlib.sha256(body.encode()).hexdigest()[:16]
        word_count = len(body.split())
        return {
            "url": params["url"],
            "status_code": status,
            "content_hash": content_hash,
            "word_count": word_count,
            "snapshot_taken": True,
        }

    elif name == "blogwatch":
        from webreaper.fetcher import StealthFetcher
        from webreaper.config import StealthConfig, BlogwatcherConfig
        from webreaper.modules.blogwatcher import BlogwatcherBridge
        fetcher_config = StealthConfig()
        async with StealthFetcher(fetcher_config) as fetcher:
            status, headers, body = await fetcher.fetch(params["url"])
        bridge = BlogwatcherBridge(BlogwatcherConfig())
        articles = bridge.extract_articles(body, params["url"])
        return {"articles_found": len(articles), "articles": articles[:10]}

    elif name == "digest":
        from webreaper.modules.digest import generate_digest
        if not db:
            return {"error": "Database not available"}
        md = await generate_digest(db, genre=params.get("genre"), limit=params.get("limit", 50))
        return {"digest": md}

    elif name == "search":
        if not db:
            return {"error": "Database not available"}
        query = params["query"]
        limit = params.get("limit", 20)
        async with db.get_session() as session:
            from sqlalchemy import text
            # Try PostgreSQL full-text search first, fall back to LIKE for SQLite
            try:
                result = await session.execute(
                    text("SELECT url, title, content_text FROM pages WHERE search_vector @@ plainto_tsquery(:q) LIMIT :limit"),
                    {"q": query, "limit": limit},
                )
                rows = result.fetchall()
            except Exception:
                like_q = f"%{query}%"
                result = await session.execute(
                    text("SELECT url, title, content_text FROM pages WHERE url LIKE :q OR title LIKE :q OR content_text LIKE :q LIMIT :limit"),
                    {"q": like_q, "limit": limit},
                )
                rows = result.fetchall()
            return {
                "query": query,
                "results": [{"url": r.url, "title": r.title, "excerpt": (r.content_text or "")[:200]} for r in rows],
            }

    elif name == "query_results":
        if not db:
            return {"error": "Database not available"}
        async with db.get_session() as session:
            from sqlalchemy import select, text
            from webreaper.database import Page
            q = select(Page)
            if params.get("crawl_id"):
                q = q.where(Page.crawl_id == params["crawl_id"])
            if params.get("domain"):
                q = q.where(Page.url.contains(params["domain"]))
            if params.get("status_code"):
                q = q.where(Page.status_code == params["status_code"])
            q = q.order_by(Page.scraped_at.desc()).limit(params.get("limit", 50))
            result = await session.execute(q)
            pages = result.scalars().all()
            return {
                "total": len(pages),
                "pages": [
                    {"url": p.url, "title": p.title, "status_code": p.status_code,
                     "word_count": p.word_count, "links_count": p.links_count}
                    for p in pages
                ],
            }

    else:
        return {"error": f"Unknown tool: {name}"}
