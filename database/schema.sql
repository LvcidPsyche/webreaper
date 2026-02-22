-- WebReaper Database Schema
-- PostgreSQL 15+
-- Run: psql -U postgres -d webreaper -f schema.sql

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fuzzy search

-- =====================================================
-- 1. CRAWLS Table
-- =====================================================
CREATE TABLE crawls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'running',
    target_url TEXT NOT NULL,
    config JSONB,
    
    pages_crawled INTEGER DEFAULT 0,
    pages_failed INTEGER DEFAULT 0,
    total_bytes BIGINT DEFAULT 0,
    unique_links INTEGER DEFAULT 0,
    external_links INTEGER DEFAULT 0,
    avg_response_time_ms INTEGER,
    requests_per_sec FLOAT,
    peak_memory_mb INTEGER,
    genre VARCHAR(50),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_crawls_status ON crawls(status);
CREATE INDEX idx_crawls_genre ON crawls(genre);
CREATE INDEX idx_crawls_started_at ON crawls(started_at DESC);

-- =====================================================
-- 2. PAGES Table
-- =====================================================
CREATE TABLE pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_id UUID REFERENCES crawls(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    canonical_url TEXT,
    domain VARCHAR(255),
    path TEXT,
    status_code INTEGER,
    content_type VARCHAR(100),
    content_length INTEGER,
    response_headers JSONB,
    response_time_ms INTEGER,
    title TEXT,
    meta_description TEXT,
    content_text TEXT,
    word_count INTEGER,
    headings JSONB,
    headings_count INTEGER,
    images_count INTEGER,
    links_count INTEGER,
    external_links_count INTEGER,
    h1 TEXT,
    h2s TEXT[],
    meta_keywords TEXT,
    og_title TEXT,
    og_description TEXT,
    og_image TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    depth INTEGER DEFAULT 0,
    search_vector tsvector
);

CREATE INDEX idx_pages_crawl_id ON pages(crawl_id);
CREATE INDEX idx_pages_url ON pages(url);
CREATE INDEX idx_pages_domain ON pages(domain);
CREATE INDEX idx_pages_status ON pages(status_code);
CREATE INDEX idx_pages_scraped_at ON pages(scraped_at DESC);
CREATE INDEX idx_pages_search ON pages USING GIN(search_vector);

-- Full-text search trigger
CREATE OR REPLACE FUNCTION update_page_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.meta_description, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.content_text, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_page_search_vector
    BEFORE INSERT OR UPDATE ON pages
    FOR EACH ROW
    EXECUTE FUNCTION update_page_search_vector();

-- =====================================================
-- 3. LINKS Table
-- =====================================================
CREATE TABLE links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_id UUID REFERENCES crawls(id) ON DELETE CASCADE,
    source_page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    target_url TEXT NOT NULL,
    target_domain VARCHAR(255),
    anchor_text TEXT,
    rel_attributes TEXT[],
    is_external BOOLEAN DEFAULT FALSE,
    is_broken BOOLEAN DEFAULT FALSE,
    status_code INTEGER,
    link_type VARCHAR(20) DEFAULT 'text',
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_links_crawl_id ON links(crawl_id);
CREATE INDEX idx_links_source ON links(source_page_id);
CREATE INDEX idx_links_target ON links(target_url);
CREATE INDEX idx_links_external ON links(is_external) WHERE is_external = TRUE;
CREATE INDEX idx_links_broken ON links(is_broken) WHERE is_broken = TRUE;

-- =====================================================
-- 4. SECURITY_FINDINGS Table
-- =====================================================
CREATE TABLE security_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_id UUID REFERENCES crawls(id) ON DELETE CASCADE,
    page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    finding_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence VARCHAR(20) DEFAULT 'medium',
    url TEXT NOT NULL,
    parameter VARCHAR(255),
    evidence TEXT,
    title TEXT NOT NULL,
    description TEXT,
    remediation TEXT,
    references TEXT[],
    cve_id VARCHAR(20),
    cwe_id VARCHAR(20),
    cvss_score FLOAT,
    payload TEXT,
    payload_type VARCHAR(50),
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verified BOOLEAN DEFAULT FALSE,
    false_positive BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_findings_crawl ON security_findings(crawl_id);
CREATE INDEX idx_findings_page ON security_findings(page_id);
CREATE INDEX idx_findings_type ON security_findings(finding_type);
CREATE INDEX idx_findings_severity ON security_findings(severity);
CREATE INDEX idx_findings_verified ON security_findings(verified) WHERE verified = FALSE;

-- Severity summary view
CREATE VIEW security_findings_summary AS
SELECT 
    crawl_id,
    finding_type,
    severity,
    COUNT(*) as count
FROM security_findings
WHERE false_positive = FALSE
GROUP BY crawl_id, finding_type, severity;

-- =====================================================
-- 5. ARTICLES Table (Blogwatcher)
-- =====================================================
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_feed VARCHAR(255),
    source_url TEXT,
    source_domain VARCHAR(255),
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    author VARCHAR(255),
    published_at TIMESTAMP WITH TIME ZONE,
    summary TEXT,
    content TEXT,
    word_count INTEGER,
    image_url TEXT,
    genre VARCHAR(50),
    tags TEXT[],
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    search_vector tsvector
);

CREATE INDEX idx_articles_feed ON articles(source_feed);
CREATE INDEX idx_articles_genre ON articles(genre);
CREATE INDEX idx_articles_published ON articles(published_at DESC);
CREATE INDEX idx_articles_scraped ON articles(scraped_at DESC);
CREATE INDEX idx_articles_processed ON articles(processed) WHERE processed = FALSE;
CREATE INDEX idx_articles_search ON articles USING GIN(search_vector);

-- Full-text search trigger
CREATE OR REPLACE FUNCTION update_article_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.summary, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.tags, ' '), '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_article_search_vector
    BEFORE INSERT OR UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_article_search_vector();

-- =====================================================
-- 6. FORMS Table
-- =====================================================
CREATE TABLE forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    crawl_id UUID REFERENCES crawls(id) ON DELETE CASCADE,
    action_url TEXT,
    method VARCHAR(10) DEFAULT 'GET',
    fields JSONB,
    fields_count INTEGER,
    csrf_protected BOOLEAN DEFAULT FALSE,
    captcha_present BOOLEAN DEFAULT FALSE,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_forms_page ON forms(page_id);
CREATE INDEX idx_forms_crawl ON forms(crawl_id);

-- =====================================================
-- 7. DASHBOARD_METRICS Table
-- =====================================================
CREATE TABLE dashboard_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_type VARCHAR(20) DEFAULT 'gauge',
    genre VARCHAR(50),
    domain VARCHAR(255),
    crawl_id UUID,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_metrics_name ON dashboard_metrics(metric_name);
CREATE INDEX idx_metrics_recorded ON dashboard_metrics(recorded_at DESC);
CREATE INDEX idx_metrics_genre ON dashboard_metrics(genre);

-- Hourly aggregation view
CREATE VIEW dashboard_metrics_hourly AS
SELECT 
    metric_name,
    genre,
    DATE_TRUNC('minute', recorded_at) as minute,
    AVG(metric_value) as avg_value,
    MAX(metric_value) as max_value,
    MIN(metric_value) as min_value,
    COUNT(*) as sample_count
FROM dashboard_metrics
WHERE recorded_at > NOW() - INTERVAL '1 hour'
GROUP BY metric_name, genre, DATE_TRUNC('minute', recorded_at);

-- =====================================================
-- 8. GENRE_CLASSIFICATIONS Table
-- =====================================================
CREATE TABLE genre_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    cybersecurity_score FLOAT DEFAULT 0,
    ai_ml_score FLOAT DEFAULT 0,
    systems_score FLOAT DEFAULT 0,
    hardware_score FLOAT DEFAULT 0,
    reverse_eng_score FLOAT DEFAULT 0,
    web_dev_score FLOAT DEFAULT 0,
    data_science_score FLOAT DEFAULT 0,
    startups_score FLOAT DEFAULT 0,
    science_score FLOAT DEFAULT 0,
    creative_score FLOAT DEFAULT 0,
    government_score FLOAT DEFAULT 0,
    niche_score FLOAT DEFAULT 0,
    primary_genre VARCHAR(50),
    confidence FLOAT,
    classified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_classifications_page ON genre_classifications(page_id);
CREATE INDEX idx_classifications_article ON genre_classifications(article_id);
CREATE INDEX idx_classifications_genre ON genre_classifications(primary_genre);

-- =====================================================
-- 9. PAGE_SNAPSHOTS Table (Change Monitoring)
-- =====================================================
CREATE TABLE page_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    content_text TEXT,
    title TEXT,
    status_code INTEGER,
    snapshot_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    changed BOOLEAN DEFAULT FALSE,
    diff_summary TEXT
);

CREATE INDEX idx_snapshots_url ON page_snapshots(url);
CREATE INDEX idx_snapshots_snapshot_at ON page_snapshots(snapshot_at DESC);
CREATE INDEX idx_snapshots_changed ON page_snapshots(changed) WHERE changed = TRUE;

COMMENT ON TABLE page_snapshots IS 'Content snapshots for URL change monitoring';

-- =====================================================
-- Create Database User
-- =====================================================
-- Run separately as superuser:
-- CREATE USER webreaper WITH PASSWORD 'your_secure_password';
-- GRANT ALL PRIVILEGES ON DATABASE webreaper TO webreaper;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO webreaper;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO webreaper;

-- =====================================================
-- Comments for documentation
-- =====================================================
COMMENT ON TABLE crawls IS 'Crawl job metadata and statistics';
COMMENT ON TABLE pages IS 'Individual crawled pages with full content';
COMMENT ON TABLE links IS 'Discovered links with relationship mapping';
COMMENT ON TABLE security_findings IS 'Vulnerability findings from security scans';
COMMENT ON TABLE articles IS 'Extracted articles from RSS-less sites (blogwatcher)';
COMMENT ON TABLE forms IS 'Discovered forms for security testing';
COMMENT ON TABLE dashboard_metrics IS 'Real-time dashboard analytics data';
COMMENT ON TABLE genre_classifications IS 'ML-based content classification scores';
