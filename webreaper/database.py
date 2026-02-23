"""WebReaper database models and connection management.

Supports both SQLite (default, for local/desktop use) and PostgreSQL.
Set DATABASE_URL env var:
  SQLite:     sqlite+aiosqlite:////home/user/.webreaper/webreaper.db
  PostgreSQL: postgresql+asyncpg://user:pass@localhost:5432/webreaper
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, DateTime,
    Boolean, Text, JSON, ForeignKey,
    func, text
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Crawl(Base):
    """Crawl job metadata and statistics."""
    __tablename__ = 'crawls'

    id = Column(String(36), primary_key=True, default=_uuid)
    started_at = Column(DateTime(timezone=True), default=_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default='running')
    target_url = Column(Text, nullable=False)
    config = Column(JSON)

    pages_crawled = Column(Integer, default=0)
    pages_failed = Column(Integer, default=0)
    total_bytes = Column(Integer, default=0)
    unique_links = Column(Integer, default=0)
    external_links = Column(Integer, default=0)
    avg_response_time_ms = Column(Integer)
    requests_per_sec = Column(Float)
    peak_memory_mb = Column(Integer)

    genre = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=_now)

    pages = relationship("Page", back_populates="crawl", cascade="all, delete-orphan")
    links = relationship("Link", back_populates="crawl", cascade="all, delete-orphan")
    findings = relationship("SecurityFinding", back_populates="crawl", cascade="all, delete-orphan")


class Page(Base):
    """Individual crawled pages with full content."""
    __tablename__ = 'pages'

    id = Column(String(36), primary_key=True, default=_uuid)
    crawl_id = Column(String(36), ForeignKey('crawls.id', ondelete='CASCADE'))

    url = Column(Text, nullable=False, index=True)
    canonical_url = Column(Text)
    domain = Column(String(255), index=True)
    path = Column(Text)

    status_code = Column(Integer, index=True)
    content_type = Column(String(100))
    content_length = Column(Integer)
    response_headers = Column(JSON)
    response_time_ms = Column(Integer)

    title = Column(Text)
    meta_description = Column(Text)
    content_text = Column(Text)
    word_count = Column(Integer)

    headings = Column(JSON)
    headings_count = Column(Integer)
    images_count = Column(Integer)
    links_count = Column(Integer)
    external_links_count = Column(Integer)

    h1 = Column(Text)
    h2s = Column(JSON)  # list of strings
    meta_keywords = Column(Text)
    og_title = Column(Text)
    og_description = Column(Text)
    og_image = Column(Text)

    scraped_at = Column(DateTime(timezone=True), default=_now, index=True)
    depth = Column(Integer, default=0)

    crawl = relationship("Crawl", back_populates="pages")
    outgoing_links = relationship("Link", foreign_keys="Link.source_page_id", back_populates="source_page")
    findings = relationship("SecurityFinding", back_populates="page")
    forms = relationship("Form", back_populates="page")
    classification = relationship("GenreClassification", back_populates="page", uselist=False)


class Link(Base):
    """Discovered links with relationship mapping."""
    __tablename__ = 'links'

    id = Column(String(36), primary_key=True, default=_uuid)
    crawl_id = Column(String(36), ForeignKey('crawls.id', ondelete='CASCADE'))
    source_page_id = Column(String(36), ForeignKey('pages.id', ondelete='CASCADE'))
    target_url = Column(Text, nullable=False)
    target_domain = Column(String(255))
    anchor_text = Column(Text)
    rel_attributes = Column(JSON)  # list of strings
    is_external = Column(Boolean, default=False, index=True)
    is_broken = Column(Boolean, default=False, index=True)
    status_code = Column(Integer)
    link_type = Column(String(20), default='text')
    discovered_at = Column(DateTime(timezone=True), default=_now)

    crawl = relationship("Crawl", back_populates="links")
    source_page = relationship("Page", foreign_keys=[source_page_id], back_populates="outgoing_links")


class SecurityFinding(Base):
    """Vulnerability findings from security scans."""
    __tablename__ = 'security_findings'

    id = Column(String(36), primary_key=True, default=_uuid)
    crawl_id = Column(String(36), ForeignKey('crawls.id', ondelete='CASCADE'))
    page_id = Column(String(36), ForeignKey('pages.id', ondelete='CASCADE'))

    finding_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    confidence = Column(String(20), default='medium')
    url = Column(Text, nullable=False)
    parameter = Column(String(255))
    evidence = Column(Text)
    title = Column(Text, nullable=False)
    description = Column(Text)
    remediation = Column(Text)
    references = Column(JSON)  # list of strings

    cve_id = Column(String(20))
    cwe_id = Column(String(20))
    cvss_score = Column(Float)

    payload = Column(Text)
    payload_type = Column(String(50))

    discovered_at = Column(DateTime(timezone=True), default=_now)
    verified = Column(Boolean, default=False, index=True)
    false_positive = Column(Boolean, default=False)

    crawl = relationship("Crawl", back_populates="findings")
    page = relationship("Page", back_populates="findings")


class Article(Base):
    """Extracted articles from RSS-less sites (blogwatcher)."""
    __tablename__ = 'articles'

    id = Column(String(36), primary_key=True, default=_uuid)
    source_feed = Column(String(255), index=True)
    source_url = Column(Text)
    source_domain = Column(String(255))
    url = Column(Text, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    author = Column(String(255))
    published_at = Column(DateTime(timezone=True), index=True)
    summary = Column(Text)
    content = Column(Text)
    word_count = Column(Integer)
    image_url = Column(Text)
    genre = Column(String(50), index=True)
    tags = Column(JSON)  # list of strings
    scraped_at = Column(DateTime(timezone=True), default=_now, index=True)
    processed = Column(Boolean, default=False, index=True)
    error_message = Column(Text)

    classification = relationship("GenreClassification", back_populates="article", uselist=False)


class Form(Base):
    """Discovered forms for security testing."""
    __tablename__ = 'forms'

    id = Column(String(36), primary_key=True, default=_uuid)
    page_id = Column(String(36), ForeignKey('pages.id', ondelete='CASCADE'))
    crawl_id = Column(String(36), ForeignKey('crawls.id', ondelete='CASCADE'))
    action_url = Column(Text)
    method = Column(String(10), default='GET')
    fields = Column(JSON)
    fields_count = Column(Integer)
    csrf_protected = Column(Boolean, default=False)
    captcha_present = Column(Boolean, default=False)
    discovered_at = Column(DateTime(timezone=True), default=_now)

    page = relationship("Page", back_populates="forms")


class DashboardMetric(Base):
    """Real-time dashboard analytics data."""
    __tablename__ = 'dashboard_metrics'

    id = Column(String(36), primary_key=True, default=_uuid)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_type = Column(String(20), default='gauge')
    genre = Column(String(50), index=True)
    domain = Column(String(255))
    crawl_id = Column(String(36))
    recorded_at = Column(DateTime(timezone=True), default=_now, index=True)


class GenreClassification(Base):
    """Content classification scores."""
    __tablename__ = 'genre_classifications'

    id = Column(String(36), primary_key=True, default=_uuid)
    page_id = Column(String(36), ForeignKey('pages.id', ondelete='CASCADE'), nullable=True)
    article_id = Column(String(36), ForeignKey('articles.id', ondelete='CASCADE'), nullable=True)

    cybersecurity_score = Column(Float, default=0)
    ai_ml_score = Column(Float, default=0)
    systems_score = Column(Float, default=0)
    hardware_score = Column(Float, default=0)
    reverse_eng_score = Column(Float, default=0)
    web_dev_score = Column(Float, default=0)
    data_science_score = Column(Float, default=0)
    startups_score = Column(Float, default=0)
    science_score = Column(Float, default=0)
    creative_score = Column(Float, default=0)
    government_score = Column(Float, default=0)
    niche_score = Column(Float, default=0)

    primary_genre = Column(String(50), index=True)
    confidence = Column(Float)
    classified_at = Column(DateTime(timezone=True), default=_now)

    page = relationship("Page", back_populates="classification")
    article = relationship("Article", back_populates="classification")


class PageSnapshot(Base):
    """Content snapshots for change monitoring."""
    __tablename__ = 'page_snapshots'

    id = Column(String(36), primary_key=True, default=_uuid)
    url = Column(Text, nullable=False, index=True)
    content_hash = Column(String(64), nullable=False)
    content_text = Column(Text)
    title = Column(Text)
    status_code = Column(Integer)
    snapshot_at = Column(DateTime(timezone=True), default=_now, index=True)
    changed = Column(Boolean, default=False, index=True)
    diff_summary = Column(Text)


# ============================================================
# Database Connection Management
# ============================================================

def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _make_async_engine(url: str):
    """Create async engine appropriate for the DB type."""
    if _is_sqlite(url):
        from sqlalchemy.pool import StaticPool
        return create_async_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_async_engine(
        url,
        echo=False,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
    )


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, database_url: Optional[str] = None):
        url = database_url or os.getenv('DATABASE_URL')
        if not url:
            raise RuntimeError(
                "DATABASE_URL environment variable not set.\n"
                "  SQLite:     sqlite+aiosqlite:////home/user/.webreaper/webreaper.db\n"
                "  PostgreSQL: postgresql+asyncpg://user:pass@localhost/webreaper"
            )
        self.database_url = url
        self.engine = None
        self.async_session_maker = None
        self.sync_engine = None
        self.sync_session_maker = None

    async def init_async(self):
        self.engine = _make_async_engine(self.database_url)
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def init_sync(self):
        if _is_sqlite(self.database_url):
            sync_url = self.database_url.replace("sqlite+aiosqlite", "sqlite")
        else:
            sync_url = self.database_url.replace('postgresql+asyncpg', 'postgresql+psycopg2')
        self.sync_engine = create_engine(sync_url, echo=False)
        self.sync_session_maker = sessionmaker(bind=self.sync_engine)

    async def create_tables(self):
        if not self.engine:
            await self.init_async()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def get_session(self):
        if not self.async_session_maker:
            await self.init_async()
        session = self.async_session_maker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    def get_sync_session(self) -> Session:
        if not self.sync_session_maker:
            self.init_sync()
        return self.sync_session_maker()

    async def close(self):
        if self.engine:
            await self.engine.dispose()

    # ── Crawler helpers ──────────────────────────────────────

    async def create_crawl(self, target_url: str, config: Dict = None, genre: str = None) -> str:
        """Create a crawl record. Returns the crawl UUID as string."""
        if not self.async_session_maker:
            await self.init_async()
        async with self.get_session() as session:
            crawl = Crawl(
                target_url=target_url,
                config=config,
                genre=genre,
                status='running',
            )
            session.add(crawl)
            await session.flush()
            return str(crawl.id)

    async def complete_crawl(self, crawl_id: str, stats: Dict):
        """Mark crawl as complete and update stats."""
        if not self.async_session_maker:
            await self.init_async()

        elapsed = stats.get("total_time", 0)
        rps = stats["pages_crawled"] / elapsed if elapsed > 0 else 0

        async with self.get_session() as session:
            await session.execute(
                text("""
                    UPDATE crawls SET
                        status = 'completed',
                        completed_at = :now,
                        pages_crawled = :pages_crawled,
                        pages_failed = :pages_failed,
                        total_bytes = :total_size,
                        external_links = :external_links,
                        requests_per_sec = :rps
                    WHERE id = :crawl_id
                """),
                {
                    "crawl_id": crawl_id,
                    "now": _now().isoformat(),
                    "pages_crawled": stats.get("pages_crawled", 0),
                    "pages_failed": stats.get("pages_failed", 0),
                    "total_size": stats.get("total_size", 0),
                    "external_links": stats.get("external_links", 0),
                    "rps": rps,
                }
            )

    async def save_page(self, crawl_id: str, **kwargs) -> Optional[str]:
        """Save a crawled page. Returns page UUID as string."""
        if not self.async_session_maker:
            await self.init_async()
        async with self.get_session() as session:
            page = Page(crawl_id=crawl_id, **kwargs)
            session.add(page)
            await session.flush()
            return str(page.id)

    async def save_links(self, crawl_id: str, page_id: str, links: List[str], is_external: bool = False):
        """Batch-save discovered links."""
        if not links:
            return
        if not self.async_session_maker:
            await self.init_async()

        from urllib.parse import urlparse as _up
        async with self.get_session() as session:
            objs = []
            for url in links:
                domain = _up(url).netloc
                objs.append(Link(
                    crawl_id=crawl_id,
                    source_page_id=page_id,
                    target_url=url,
                    target_domain=domain,
                    is_external=is_external,
                ))
            session.add_all(objs)

    async def save_finding(self, crawl_id: str, page_id: Optional[str], finding: Dict):
        """Save a security finding."""
        if not self.async_session_maker:
            await self.init_async()
        async with self.get_session() as session:
            obj = SecurityFinding(
                crawl_id=crawl_id,
                page_id=page_id,
                finding_type=finding.get("type", "Unknown"),
                severity=finding.get("severity", "Info"),
                confidence=finding.get("confidence", "medium"),
                url=finding.get("url", ""),
                parameter=finding.get("parameter"),
                evidence=finding.get("evidence"),
                title=finding.get("type", "Finding"),
                description=finding.get("description"),
                remediation=finding.get("remediation"),
                payload=finding.get("payload"),
            )
            session.add(obj)

    async def save_article(self, article: Dict) -> Optional[str]:
        """Save a blogwatcher article. Returns UUID or None if duplicate."""
        if not self.async_session_maker:
            await self.init_async()
        try:
            async with self.get_session() as session:
                obj = Article(
                    url=article["url"],
                    title=article["title"],
                    summary=article.get("summary"),
                    content=article.get("content"),
                    published_at=article.get("published_at"),
                    source_feed=article.get("source_feed"),
                    source_url=article.get("source_url"),
                    genre=article.get("genre"),
                    tags=article.get("tags"),
                )
                session.add(obj)
                await session.flush()
                return str(obj.id)
        except Exception:
            return None  # Duplicate URL

    async def get_unprocessed_articles(self, limit: int = 100, genre: Optional[str] = None) -> List[Dict]:
        """Fetch unprocessed articles for digest."""
        if not self.async_session_maker:
            await self.init_async()
        async with self.get_session() as session:
            q = "SELECT id, title, summary, content, genre, source_feed, published_at FROM articles WHERE processed = 0"
            params: Dict = {}
            if genre:
                q += " AND genre = :genre"
                params["genre"] = genre
            q += " ORDER BY published_at DESC LIMIT :limit"
            params["limit"] = limit
            result = await session.execute(text(q), params)
            rows = result.fetchall()
            return [dict(r._mapping) for r in rows]

    async def mark_articles_processed(self, article_ids: List[str]):
        """Mark articles as processed after digest."""
        if not article_ids:
            return
        if not self.async_session_maker:
            await self.init_async()
        # Use parameterized placeholders for safety
        placeholders = ",".join([f":id_{i}" for i in range(len(article_ids))])
        params = {f"id_{i}": aid for i, aid in enumerate(article_ids)}
        async with self.get_session() as session:
            await session.execute(
                text(f"UPDATE articles SET processed = 1 WHERE id IN ({placeholders})"),
                params
            )

    async def get_crawl_stats(self) -> List[Dict]:
        """Return summary stats for all crawls."""
        if not self.async_session_maker:
            await self.init_async()
        async with self.get_session() as session:
            result = await session.execute(text("""
                SELECT id, target_url, status, pages_crawled, pages_failed,
                       external_links, requests_per_sec, genre,
                       started_at, completed_at
                FROM crawls
                ORDER BY started_at DESC
                LIMIT 20
            """))
            return [dict(r._mapping) for r in result.fetchall()]

    async def save_snapshot(self, url: str, content_hash: str, content_text: str,
                            title: Optional[str], status_code: int,
                            changed: bool, diff_summary: Optional[str] = None) -> str:
        """Save a page snapshot for change monitoring."""
        if not self.async_session_maker:
            await self.init_async()
        async with self.get_session() as session:
            snap = PageSnapshot(
                url=url,
                content_hash=content_hash,
                content_text=content_text,
                title=title,
                status_code=status_code,
                changed=changed,
                diff_summary=diff_summary,
            )
            session.add(snap)
            await session.flush()
            return str(snap.id)

    async def get_latest_snapshot(self, url: str) -> Optional[Dict]:
        """Get the most recent snapshot for a URL."""
        if not self.async_session_maker:
            await self.init_async()
        async with self.get_session() as session:
            result = await session.execute(text("""
                SELECT content_hash, content_text, title, snapshot_at
                FROM page_snapshots
                WHERE url = :url
                ORDER BY snapshot_at DESC
                LIMIT 1
            """), {"url": url})
            row = result.fetchone()
            return dict(row._mapping) if row else None


def get_db_manager() -> Optional["DatabaseManager"]:
    """Return a DatabaseManager if DATABASE_URL is configured, else None."""
    if os.getenv("DATABASE_URL"):
        return DatabaseManager()
    return None
