# ULTIMATE SCRAPER SYSTEM ARCHITECTURE
## Project: OpenClaw Scraper ("WebReaper")
### Design Document v1.0

---

## EXECUTIVE SUMAMRY

Building a scraper that exceeds Screaming Frog SEO Spider + Burp Suite Pro capabilities.
Features: recursive crawling, security testing, stealth mode, blogwatcher integration.

---

## CORE ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        WEBREAPER SCRAPER SYSTEM                          │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   CRAWLER   │  │   STEALTH   │  │  SECURITY   │  │   OUTPUT    │   │
│  │    CORE     │──│    MODE     │──│   MODULE    │──│   ENGINE    │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│         │                │                │                │          │
│         └────────────────┴────────────────┴────────────────┘          │
│                              │                                         │
│                    ┌─────────┴─────────┐                               │
│                    │  CONFIGURATION    │                               │
│                    │    MANAGER        │                               │
│                    └─────────┬─────────┘                               │
│                              │                                         │
│         ┌────────────────────┼────────────────────┐                   │
│         ▼                    ▼                    ▼                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐             │
│  │ BLOGWATCHER │     │   SQLITE    │     │    TOR      │             │
│  │  INTEGRATION│     │   STORAGE   │     │   PROXY     │             │
│  └─────────────┘     └─────────────┘     └─────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## TECH STACK

| Component | Technology | Reason |
|-----------|------------|--------|
| Core Language | Python 3.11+ | Ecosystem, async support |
| HTTP Client | aiohttp + httpx | Async, HTTP/2, performance |
| Browser | Playwright | Better than Selenium, stealth |
| Parsing | BeautifulSoup4 + lxml | Speed, flexibility |
| Storage | SQLite (default) / PostgreSQL | Local first, scalable |
| Queue | asyncio.Queue | Built-in, efficient |
| CLI | Click or Typer | Modern, intuitive |
| Config | Pydantic + YAML | Validation, readability |
| Tor Control | stem library | Native Tor integration |

---

## MODULE BREAKDOWN

### 1. CRAWLER CORE (crawler.py)

**Features:**
- Async recursive crawling
- Configurable depth (0-10)
- Concurrent connection pool (10-1000)
- URL deduplication (bloom filter)
- Domain restriction (subdomains, external links)
- Sitemap.xml parsing
- robots.txt respect (toggleable)
- Custom headers/cookies/auth
- Rate limiting (requests/second)
- Retry logic with exponential backoff

**Key Classes:**
```python
class Crawler:
    def __init__(self, config: CrawlerConfig)
    async def crawl(self, start_urls: List[str]) -> CrawlResult
    async def fetch(self, url: str) -> Response
    def should_crawl(self, url: str) -> bool

class URLFrontier:
    def add(self, url: str, priority: int)
    def get(self) -> Optional[str]
    def seen(self, url: str) -> bool
```

---

### 2. STEALTH MODULE (stealth.py)

**Features (ALL TOGGLEABLE):**

| Feature | Description | Config Key |
|---------|-------------|------------|
| User-Agent Rotation | Rotate 1000+ real UAs | `rotate_ua: true` |
| Browser Profiles | Chrome, Firefox, Safari fingerprints | `browser_profile: random` |
| Canvas Fingerprint | Randomize canvas hash | `randomize_canvas: true` |
| WebGL Spoofing | Mask WebGL renderer | `spoof_webgl: true` |
| Font Randomization | Vary installed fonts list | `randomize_fonts: true` |
| Screen Resolution | Randomize viewport | `randomize_screen: true` |
| Timing Delays | Human-like delays | `delay: {min: 1, max: 5}` |
| Mouse Movements | Bezier curve mouse paths | `simulate_mouse: true` |
| TLS/JA3 Fingerprint | Rotate TLS signatures | `rotate_ja3: true` |

**Tor Integration:**
- stem controller for Tor management
- Automatic circuit rotation
- Exit node country selection
- Hidden service support

---

### 3. SECURITY MODULE (security.py)

**Burp Suite-style Features:**

| Feature | Description |
|---------|-------------|
| Request Interceptor | Modify requests on-the-fly |
| Response Analyzer | Pattern matching for vulns |
| Parameter Fuzzer | Auto-test all parameters |
| XSS Detection | Reflected/DOM XSS testing |
| SQL Injection | Error-based, blind, time-based |
| IDOR Detection | Sequential ID testing |
| Open Redirect | URL parameter injection |
| JWT Analyzer | Token parsing, weak secret detection |
| CORS Scanner | Misconfiguration detection |
| API Discovery | OpenAPI spec extraction |
| GraphQL Introspection | Schema extraction |
| WebSocket Proxy | WS message interception |

**Payloads:**
- XSS: 100+ payloads (polyglot, filter evasion)
- SQLi: Union-based, error-based, blind
- Command Injection: Shell metacharacters
- Template Injection: Jinja2, Django, etc.

---

### 4. BLOGWATCHER INTEGRATION (blogwatcher_bridge.py)

**Purpose:** Scrape sites without RSS feeds

**Features:**
- Auto-detect article patterns (title, date, content)
- Extract structured data (JSON-LD, microdata)
- Generate RSS-compatible output
- Feed into blogwatcher database
- Schedule regular rescraping
- Article deduplication (hash-based)

**Article Detection Heuristics:**
1. URL patterns (/blog/, /news/, /article/, dates)
2. HTML structure (article tags, h1 + time + content)
3. Content length (min 500 chars)
4. Date proximity (published within last X days)

---

### 5. OUTPUT ENGINE (output.py)

**Formats:**
- JSON (structured, machine-readable)
- CSV (spreadsheets)
- XML (sitemaps, RSS)
- Markdown (human-readable reports)
- HTML (interactive reports with filters)
- SQL (direct database import)

**Reports:**
- Crawl summary (pages, errors, time)
- Security findings (severity, evidence, remediation)
- SEO audit (titles, meta, headings, links)
- Performance metrics (load times, sizes)

---

## CONFIGURATION SYSTEM

```yaml
# config/webreaper.yaml

crawler:
  max_depth: 3
  max_pages: 10000
  concurrency: 100
  rate_limit: 10  # requests per second
  respect_robots: false
  follow_redirects: true
  timeout: 30

stealth:
  enabled: true
  rotate_ua: true
  randomize_canvas: true
  spoof_webgl: true
  delay:
    min: 1
    max: 5
  tor:
    enabled: false
    circuit_rotate: 10  # requests per circuit

security:
  enabled: true
  xss_detection: true
  sqli_detection: true
  idor_detection: true
  fuzz_parameters: true
  
blogwatcher:
  enabled: true
  output_format: rss
  scrape_interval: 3600  # seconds
  
output:
  format: json
  directory: ./output/
  save_responses: true
```

---

## GRAY AREA FEATURES

**ALL DISABLED BY DEFAULT. USER MUST OPT-IN.**

### Warning Banner:
```
⚠️  LEGAL WARNING  ⚠️
The following features may violate Terms of Service or local laws.
Use only on systems you own or have explicit permission to test.
Developer assumes no liability for misuse.

Enabled features:
- Tor routing
- CAPTCHA solving
- Anti-bot evasion
```

### Features Requiring Explicit Enable:

1. **TOR ROUTING** (`tor_enabled: true`)
   - Routes all traffic through Tor network
   - Automatic circuit rotation
   - Exit node geolocation

2. **CAPTCHA SOLVING** (`captcha_service: 2captcha`)
   - Integrates with solving services
   - Costs real money per solve

3. **AGGRESSIVE EVASION** (`aggressive_mode: true`)
   - Multiple fingerprint randomization
   - Behavioral mimicry
   - Request signature obfuscation

---

## PERFORMANCE TARGETS

| Metric | Target | Screaming Frog Comparison |
|--------|--------|---------------------------|
| Requests/sec | 1000+ | SF: ~100-200 |
| Concurrent connections | 1000 | SF: ~10-50 |
| Pages/minute | 50,000+ | SF: ~5,000 |
| Memory usage | <2GB for 100k pages | SF: ~4GB+ |
| Startup time | <2 seconds | SF: ~10 seconds |

---

## BLOGWATCHER WORKFLOW

```
┌─────────────────┐
│  blogwatcher    │
│  (71 feeds)     │
└────────┬────────┘
         │ checks for new articles
         ▼
┌─────────────────┐
│  Has RSS?       │
└────────┬────────┘
    Yes /    \ No
      /        \
     ▼          ▼
┌────────┐  ┌─────────────────┐
│ Use RSS│  │  WebReaper      │
│ Feed   │  │  (scrape page)  │
└────────┘  └────────┬────────┘
                     │ extract content
                     ▼
              ┌─────────────────┐
              │ Generate RSS    │
              │ Feed            │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  blogwatcher    │
              │  (process)      │
              └─────────────────┘
```

---

## IMPLEMENTATION ROADMAP

### Phase 1: Core (2-3 hours)
- [ ] Project structure
- [ ] Async crawler core
- [ ] URL frontier
- [ ] Basic content extraction
- [ ] CLI interface

### Phase 2: Stealth (2 hours)
- [ ] User-agent rotation
- [ ] Browser fingerprinting
- [ ] Tor integration
- [ ] Delay randomization

### Phase 3: Security (3-4 hours)
- [ ] Request/response interception
- [ ] Vulnerability detection patterns
- [ ] Fuzzing engine
- [ ] Payload library

### Phase 4: Blogwatcher Bridge (2 hours)
- [ ] Article detection
- [ ] RSS generation
- [ ] Scheduling
- [ ] Integration testing

### Phase 5: Polish (2 hours)
- [ ] Documentation
- [ ] Error handling
- [ ] Testing
- [ ] Git commit

**Total: 12-14 hours of work**

---

## FILE STRUCTURE

```
tools/webreaper/
├── webreaper/
│   ├── __init__.py
│   ├── cli.py              # Command line interface
│   ├── config.py           # Configuration management
│   ├── crawler.py          # Core crawler engine
│   ├── frontier.py         # URL frontier/queue
│   ├── fetcher.py          # HTTP request handler
│   ├── parser.py           # HTML parsing
│   ├── output.py           # Output formatting
│   ├── storage.py          # Database layer
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── stealth.py      # Stealth features
│   │   ├── security.py     # Security testing
│   │   └── blogwatcher.py  # Blogwatcher bridge
│   └── utils/
│       ├── __init__.py
│       ├── fingerprints.py # Browser fingerprints
│       ├── payloads.py     # Security payloads
│       └── helpers.py      # Utilities
├── config/
│   └── webreaper.yaml      # Default config
├── tests/
├── requirements.txt
├── setup.py
└── README.md
```

---

## LEGAL DISCLAIMER

```
WEBREAPER SCRAPER - LEGAL NOTICE
================================

This tool is designed for:
✓ Legitimate security testing (with permission)
✓ Scraping your own websites
✓ Research and educational purposes
✓ Open data collection

This tool must NOT be used for:
✗ Unauthorized access to systems
✗ Violating Terms of Service
✗ Stealing proprietary data
✗ DDoS or resource exhaustion attacks
✗ Harassment or stalking

Gray area features (Tor, evasion) are provided for:
- Privacy protection (legitimate use)
- Testing anti-bot systems you own
- Research in controlled environments

USER IS SOLELY RESPONSIBLE FOR LEGAL COMPLIANCE.
```

---

*Architecture complete. Beginning implementation...*
