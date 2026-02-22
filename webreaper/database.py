"""WebReaper database models and connection management."""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, DateTime, 
    Boolean, Text, JSON, ForeignKey, Index, UniqueConstraint,
    func, text
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, TSVECTOR
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Base class for models
Base = declarative_base()


class Crawl(Base):
    """Crawl job metadata and statistics."""
    __tablename__ = 'crawls'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default='running')  # running, completed, failed
    target_url = Column(Text, nullable=False)
    config = Column(JSON)
    
    # Statistics
    pages_crawled = Column(Integer, default=0)
    pages_failed = Column(Integer, default=0)
    total_bytes = Column(Integer, default=0)
    unique_links = Column(Integer, default=0)
    external_links = Column(Integer, default=0)
    avg_response_time_ms = Column(Integer)
    requests_per_sec = Column(Float)
    peak_memory_mb = Column(Integer)
    
    genre = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    pages = relationship("Page", back_populates="crawl", cascade="all, delete-orphan")
    links = relationship("Link", back_populates="crawl", cascade="all, delete-orphan")
    findings = relationship("SecurityFinding", back_populates="crawl", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Crawl(id={self.id}, url={self.target_url[:50]}, status={self.status})>"


class Page(Base):
    """Individual crawled pages with full content."""
    __tablename__ = 'pages'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    crawl_id = Column(UUID(as_uuid=True), ForeignKey('crawls.id', ondelete='CASCADE'))
    
    # URL info
    url = Column(Text, nullable=False, index=True)
    canonical_url = Column(Text)
    domain = Column(String(255), index=True)
    path = Column(Text)
    
    # Response
    status_code = Column(Integer, index=True)
    content_type = Column(String(100))
    content_length = Column(Integer)
    response_headers = Column(JSON)
    response_time_ms = Column(Integer)
    
    # Content
    title = Column(Text)
    meta_description = Column(Text)
    content_text = Column(Text)
    word_count = Column(Integer)
    
    # Structure
    headings = Column(JSON)  # [{level: 1, text: "..."}, ...]
    headings_count = Column(Integer)
    images_count = Column(Integer)
    links_count = Column(Integer)
    external_links_count = Column(Integer)
    
    # SEO
    h1 = Column(Text)
    h2s = Column(ARRAY(Text))
    meta_keywords = Column(Text)
    og_title = Column(Text)
    og_description = Column(Text)
    og_image = Column(Text)
    
    scraped_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    depth = Column(Integer, default=0)
    
    # Full-text search
    search_vector = Column(TSVECTOR)
    
    # Relationships
    crawl = relationship("Crawl", back_populates="pages")
    outgoing_links = relationship("Link", foreign_keys="Link.source_page_id", back_populates="source_page")
    findings = relationship("SecurityFinding", back_populates="page")
    forms = relationship("Form", back_populates="page")
    classification = relationship("GenreClassification", back_populates="page", uselist=False)
    
    def __repr__(self):
        return f"<Page(id={self.id}, url={self.url[:50]})>"


class Link(Base):
    """Discovered links with relationship mapping."""
    __tablename__ = 'links'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    crawl_id = Column(UUID(as_uuid=True), ForeignKey('crawls.id', ondelete='CASCADE'))
    source_page_id = Column(UUID(as_uuid=True), ForeignKey('pages.id', ondelete='CASCADE'))
    target_url = Column(Text, nullable=False)
    target_domain = Column(String(255))
    anchor_text = Column(Text)
    rel_attributes = Column(ARRAY(String))
    is_external = Column(Boolean, default=False, index=True)
    is_broken = Column(Boolean, default=False, index=True)
    status_code = Column(Integer)
    link_type = Column(String(20), default='text')  # text, image, button, nav
    discovered_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    crawl = relationship("Crawl", back_populates="links")
    source_page = relationship("Page", foreign_keys=[source_page_id], back_populates="outgoing_links")
    
    def __repr__(self):
        return f"<Link(source={self.source_page_id[:8]}, target={self.target_url[:50]})>"


class SecurityFinding(Base):
    """Vulnerability findings from security scans."""
    __tablename__ = 'security_findings'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    crawl_id = Column(UUID(as_uuid=True), ForeignKey('crawls.id', ondelete='CASCADE'))
    page_id = Column(UUID(as_uuid=True), ForeignKey('pages.id', ondelete='CASCADE'))
    
    finding_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    confidence = Column(String(20), default='medium')
    url = Column(Text, nullable=False)
    parameter = Column(String(255))
    evidence = Column(Text)
    title = Column(Text, nullable=False)
    description = Column(Text)
    remediation = Column(Text)
    references = Column(ARRAY(Text))
    
    # CVE/CWE
    cve_id = Column(String(20))
    cwe_id = Column(String(20))
    cvss_score = Column(Float)
    
    # Payload
    payload = Column(Text)
    payload_type = Column(String(50))
    
    discovered_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    verified = Column(Boolean, default=False, index=True)
    false_positive = Column(Boolean, default=False)
    
    # Relationships
    crawl = relationship("Crawl", back_populates="findings")
    page = relationship("Page", back_populates="findings")
    
    def __repr__(self):
        return f"<SecurityFinding(type={self.finding_type}, severity={self.severity})>"


class Article(Base):
    """Extracted articles from RSS-less sites (blogwatcher)."""
    __tablename__ = 'articles'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
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
    tags = Column(ARRAY(String))
    scraped_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    processed = Column(Boolean, default=False, index=True)
    error_message = Column(Text)
    
    # Full-text search
    search_vector = Column(TSVECTOR)
    
    # Relationships
    classification = relationship("GenreClassification", back_populates="article", uselist=False)
    
    def __repr__(self):
        return f"<Article(title={self.title[:50]}, source={self.source_feed})>"


class Form(Base):
    """Discovered forms for security testing."""
    __tablename__ = 'forms'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    page_id = Column(UUID(as_uuid=True), ForeignKey('pages.id', ondelete='CASCADE'))
    crawl_id = Column(UUID(as_uuid=True), ForeignKey('crawls.id', ondelete='CASCADE'))
    action_url = Column(Text)
    method = Column(String(10), default='GET')
    fields = Column(JSON)  # [{name: "email", type: "email", required: true}, ...]
    fields_count = Column(Integer)
    csrf_protected = Column(Boolean, default=False)
    captcha_present = Column(Boolean, default=False)
    discovered_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    page = relationship("Page", back_populates="forms")
    
    def __repr__(self):
        return f"<Form(page_id={self.page_id[:8]}, fields={self.fields_count})>"


class DashboardMetric(Base):
    """Real-time dashboard analytics data."""
    __tablename__ = 'dashboard_metrics'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_type = Column(String(20), default='gauge')  # gauge, counter, histogram
    genre = Column(String(50), index=True)
    domain = Column(String(255))
    crawl_id = Column(UUID(as_uuid=True))
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<DashboardMetric(name={self.metric_name}, value={self.metric_value})>"


class GenreClassification(Base):
    """ML-based content classification scores."""
    __tablename__ = 'genre_classifications'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    page_id = Column(UUID(as_uuid=True), ForeignKey('pages.id', ondelete='CASCADE'), nullable=True)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='CASCADE'), nullable=True)
    
    # Classification scores (0-1)
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
    classified_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    page = relationship("Page", back_populates="classification")
    article = relationship("Article", back_populates="classification")
    
    def __repr__(self):
        return f"<GenreClassification(primary={self.primary_genre}, confidence={self.confidence})>"


# ============================================================
# Database Connection Management
# ============================================================

class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv(
            'DATABASE_URL',
            'postgresql+asyncpg://webreaper:webreaper@localhost:5432/webreaper'
        )
        self.engine = None
        self.async_session_maker = None
        self.sync_engine = None
        self.sync_session_maker = None
    
    async def init_async(self):
        """Initialize async engine and session maker."""
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
        )
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    def init_sync(self):
        """Initialize sync engine and session maker."""
        # Convert asyncpg URL to psycopg2
        sync_url = self.database_url.replace('postgresql+asyncpg', 'postgresql+psycopg2')
        self.sync_engine = create_engine(
            sync_url,
            echo=False,
            pool_size=20,
            max_overflow=30,
        )
        self.sync_session_maker = sessionmaker(bind=self.sync_engine)
    
    async def create_tables(self):
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """Get async database session."""
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
        """Get sync database session."""
        if not self.sync_session_maker:
            self.init_sync()
        return self.sync_session_maker()
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()


# Global instance
db_manager = DatabaseManager()
