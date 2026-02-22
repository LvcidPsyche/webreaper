# WebReaper Database Architecture
## PostgreSQL Schema Design

---

## Database Overview

**Engine:** PostgreSQL 15+  
**Purpose:** Store crawl results, security findings, scraped articles, and dashboard analytics  
**Estimated Capacity:** 10M+ pages, 100M+ links, full-text searchable  

---

## Schema Design

### 1. CRAWLS Table
Stores crawl job metadata and statistics.

```sql
CREATE TABLE crawls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'running', -- running, completed, failed
    target_url TEXT NOT NULL,
    config JSONB, -- Full crawl configuration
    
    -- Statistics
    pages_crawled INTEGER DEFAULT 0,
    pages_failed INTEGER DEFAULT 0,
    total_bytes BIGINT DEFAULT 0,
    unique_links INTEGER DEFAULT 0,
    external_links INTEGER DEFAULT 0,
    avg_response_time_ms INTEGER,
    
    -- Performance
    requests_per_sec FLOAT,
    peak_memory_mb INTEGER,
    
    -- Genre classification
    genre VARCHAR(50),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_crawls_status ON crawls(status);
CREATE INDEX idx_crawls_genre ON crawls(genre);
CREATE INDEX idx_crawls_started_at ON crawls(started_at DESC);
```

### 2. PAGES Table
Stores individual crawled pages with full content.

```sql
CREATE TABLE pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_id UUID REFERENCES crawls(id) ON DELETE CASCADE,
    
    -- URL info
    url TEXT NOT NULL,
    canonical_url TEXT,
    domain VARCHAR(255),
    path TEXT,
    
    -- Response
    status_code INTEGER,
    content_type VARCHAR(100),
    content_length INTEGER,
    response_headers JSONB,
    response_time_ms INTEGER,
    
    -- Content
    title TEXT,
    meta_description TEXT,
    content_text TEXT,
    word_count INTEGER,
    
    -- Structure
    headings JSONB, -- [{level: 1, text: "..."}, ...]
    headings_count INTEGER,
    images_count INTEGER,
    links_count INTEGER,
    external_links_count INTEGER,
    
    -- SEO
    h1 TEXT,
    h2s TEXT[],
    meta_keywords TEXT,
    og_title TEXT,
    og_description TEXT,
    og_image TEXT,
    
    -- Scraped at
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    depth INTEGER DEFAULT 0,
    
    -- Full-text search
    search_vector tsvector
);

-- Indexes
CREATE INDEX idx_pages_crawl_id ON pages(crawl_id);
CREATE INDEX idx_pages_url ON pages(url);
CREATE INDEX idx_pages_domain ON pages(domain);
CREATE INDEX idx_pages_status ON pages(status_code);
CREATE INDEX idx_pages_scraped_at ON pages(scraped_at DESC);

-- Full-text search index
CREATE INDEX idx_pages_search ON pages USING GIN(search_vector);

-- Update search vector trigger
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
```

### 3. LINKS Table
Stores all discovered links with relationship mapping.

```sql
CREATE TABLE links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_id UUID REFERENCES crawls(id) ON DELETE CASCADE,
    
    -- Source and target
    source_page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    target_url TEXT NOT NULL,
    target_domain VARCHAR(255),
    
    -- Link attributes
    anchor_text TEXT,
    rel_attributes TEXT[], -- ["nofollow", "noopener", ...]
    is_external BOOLEAN DEFAULT FALSE,
    is_broken BOOLEAN DEFAULT FALSE,
    status_code INTEGER,
    
    -- Link type
    link_type VARCHAR(20) DEFAULT 'text', -- text, image, button, nav
    
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_links_crawl_id ON links(crawl_id);
CREATE INDEX idx_links_source ON links(source_page_id);
CREATE INDEX idx_links_target ON links(target_url);
CREATE INDEX idx_links_external ON links(is_external) WHERE is_external = TRUE;
CREATE INDEX idx_links_broken ON links(is_broken) WHERE is_broken = TRUE;
```

### 4. SECURITY_FINDINGS Table
Stores all vulnerability findings from security scans.

```sql
CREATE TABLE security_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_id UUID REFERENCES crawls(id) ON DELETE CASCADE,
    page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    
    -- Finding details
    finding_type VARCHAR(50) NOT NULL, -- XSS, SQLi, IDOR, etc.
    severity VARCHAR(20) NOT NULL, -- Critical, High, Medium, Low, Info
    confidence VARCHAR(20) DEFAULT 'medium', -- high, medium, low
    
    -- Location
    url TEXT NOT NULL,
    parameter VARCHAR(255), -- Query parameter, form field, etc.
    evidence TEXT,
    
    -- Description
    title TEXT NOT NULL,
    description TEXT,
    remediation TEXT,
    references TEXT[], -- URLs to CWE, OWASP, etc.
    
    -- CVE/CWE
    cve_id VARCHAR(20),
    cwe_id VARCHAR(20),
    cvss_score FLOAT,
    
    -- Payload (if applicable)
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

-- Severity statistics view
CREATE VIEW security_findings_summary AS
SELECT 
    crawl_id,
    finding_type,
    severity,
    COUNT(*) as count
FROM security_findings
WHERE false_positive = FALSE
GROUP BY crawl_id, finding_type, severity;
```

### 5. ARTICLES Table (Blogwatcher Integration)
Stores extracted articles from RSS-less sites.

```sql
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source
    source_feed VARCHAR(255),
    source_url TEXT,
    source_domain VARCHAR(255),
    
    -- Article data
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    author VARCHAR(255),
    published_at TIMESTAMP WITH TIME ZONE,
    summary TEXT,
    content TEXT,
    word_count INTEGER,
    
    -- Media
    image_url TEXT,
    
    -- Metadata
    genre VARCHAR(50),
    tags TEXT[],
    
    -- Processing
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    
    -- Full-text search
    search_vector tsvector
);

-- Indexes
CREATE INDEX idx_articles_feed ON articles(source_feed);
CREATE INDEX idx_articles_genre ON articles(genre);
CREATE INDEX idx_articles_published ON articles(published_at DESC);
CREATE INDEX idx_articles_scraped ON articles(scraped_at DESC);
CREATE INDEX idx_articles_processed ON articles(processed) WHERE processed = FALSE;
CREATE INDEX idx_articles_search ON articles USING GIN(search_vector);

-- Update search vector trigger
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
```

### 6. FORMS Table
Stores discovered forms with fields for security testing.

```sql
CREATE TABLE forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    crawl_id UUID REFERENCES crawls(id) ON DELETE CASCADE,
    
    -- Form details
    action_url TEXT,
    method VARCHAR(10) DEFAULT 'GET',
    
    -- Fields
    fields JSONB, -- [{name: "email", type: "email", required: true}, ...]
    fields_count INTEGER,
    
    -- Security
    csrf_protected BOOLEAN DEFAULT FALSE,
    captcha_present BOOLEAN DEFAULT FALSE,
    
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_forms_page ON forms(page_id);
CREATE INDEX idx_forms_crawl ON forms(crawl_id);
```

### 7. DASHBOARD_METRICS Table
Real-time and historical dashboard data.

```sql
CREATE TABLE dashboard_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_type VARCHAR(20) DEFAULT 'gauge', -- gauge, counter, histogram
    
    -- Dimensions
    genre VARCHAR(50),
    domain VARCHAR(255),
    crawl_id UUID,
    
    -- Timestamp
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Time-series optimized
CREATE INDEX idx_metrics_name ON dashboard_metrics(metric_name);
CREATE INDEX idx_metrics_recorded ON dashboard_metrics(recorded_at DESC);
CREATE INDEX idx_metrics_genre ON dashboard_metrics(genre);

-- Aggregation view (last hour)
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
```

### 8. GENRE_CLASSIFICATIONS Table
ML/AI-based content classification cache.

```sql
CREATE TABLE genre_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    
    -- Classification scores (0-1)
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
    
    -- Primary genre
    primary_genre VARCHAR(50),
    confidence FLOAT,
    
    classified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_classifications_page ON genre_classifications(page_id);
CREATE INDEX idx_classifications_article ON genre_classifications(article_id);
CREATE INDEX idx_classifications_genre ON genre_classifications(primary_genre);
```

---

## Partitioning Strategy

For high-volume tables (pages, links), implement time-based partitioning:

```sql
-- Create partitioned table for pages
CREATE TABLE pages_partitioned (
    LIKE pages INCLUDING ALL
) PARTITION BY RANGE (scraped_at);

-- Create monthly partitions
CREATE TABLE pages_y2024m01 PARTITION OF pages_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
    
CREATE TABLE pages_y2024m02 PARTITION OF pages_partitioned
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Auto-create future partitions via cron/pg_partman
```

---

## Full-Text Search Features

### Advanced Search Query Examples

```sql
-- Search pages by content relevance
SELECT 
    url, title, meta_description,
    ts_rank(search_vector, plainto_tsquery('english', 'vulnerability exploit')) as rank
FROM pages
WHERE search_vector @@ plainto_tsquery('english', 'vulnerability exploit')
ORDER BY rank DESC
LIMIT 10;

-- Fuzzy search (trigram)
SELECT * FROM pages
WHERE url % 'example.com/security'
ORDER BY similarity(url, 'example.com/security') DESC;

-- Combined genre + text search
SELECT * FROM articles
WHERE genre = 'cybersecurity'
  AND search_vector @@ to_tsquery('english', 'CVE & (RCE | XSS)')
ORDER BY published_at DESC;
```

---

## Connection Pooling (PgBouncer)

```ini
; pgbouncer.ini
[databases]
webreaper = host=localhost port=5432 dbname=webreaper

[pgbouncer]
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 25
max_db_connections = 100
```

---

## Backup Strategy

```bash
#!/bin/bash
# Automated backups

# Daily full backup
pg_dump webreaper | gzip > /backups/webreaper_$(date +%Y%m%d).sql.gz

# Continuous archiving (WAL)
# Enable in postgresql.conf:
# wal_level = replica
# archive_mode = on
# archive_command = 'cp %p /backups/wal/%f'

# Retention: Keep 7 daily, 4 weekly, 12 monthly
```

---

## Performance Tuning

```sql
-- For high write throughput
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '64MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- For fast crawling (async commit)
ALTER SYSTEM SET synchronous_commit = 'off';
```

---

*Database schema complete. Ready for implementation.*
