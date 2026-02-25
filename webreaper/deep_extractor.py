"""Deep page extraction engine — extracts every crumb from a page.

This replaces the shallow extraction in crawler.py with comprehensive
data capture: structured data, technology detection, contact info,
SEO scoring, content analysis, asset inventory, and more.
"""

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


# ── Readability constants ────────────────────────────────────

_SENTENCE_RE = re.compile(r'[.!?]+\s+', re.UNICODE)
_SYLLABLE_RE = re.compile(r'[aeiouy]+', re.IGNORECASE)

# ── Contact extraction patterns ──────────────────────────────

_EMAIL_RE = re.compile(
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
)
_PHONE_RE = re.compile(
    r'(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    r'|'
    r'\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{2,4}[-.\s]?\d{2,4}'
)
_ADDRESS_RE = re.compile(
    r'\d{1,5}\s[\w\s]{1,40}(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|'
    r'Road|Rd|Lane|Ln|Way|Court|Ct|Place|Pl|Circle|Cir)\b',
    re.IGNORECASE,
)

# ── Social platform patterns ─────────────────────────────────

_SOCIAL_DOMAINS = {
    'twitter.com': 'twitter', 'x.com': 'twitter',
    'facebook.com': 'facebook', 'fb.com': 'facebook',
    'linkedin.com': 'linkedin',
    'instagram.com': 'instagram',
    'youtube.com': 'youtube', 'youtu.be': 'youtube',
    'github.com': 'github',
    'tiktok.com': 'tiktok',
    'pinterest.com': 'pinterest',
    'reddit.com': 'reddit',
    'discord.gg': 'discord', 'discord.com': 'discord',
    'mastodon.social': 'mastodon',
    'threads.net': 'threads',
    'bsky.app': 'bluesky',
    'medium.com': 'medium',
    'substack.com': 'substack',
}

# ── Technology fingerprints ──────────────────────────────────

_TECH_PATTERNS: List[Tuple[str, str, str, str]] = [
    # (category, name, search_in, pattern)
    # -- Frameworks --
    ('framework', 'React', 'script', r'react(?:\.production|\.development|dom)'),
    ('framework', 'Next.js', 'html', r'__next|_next/static'),
    ('framework', 'Vue.js', 'script', r'vue(?:\.min)?\.js|__vue'),
    ('framework', 'Nuxt', 'html', r'__nuxt|_nuxt/'),
    ('framework', 'Angular', 'html', r'ng-version|ng-app'),
    ('framework', 'Svelte', 'html', r'svelte'),
    ('framework', 'Astro', 'html', r'astro-island|astro-slot'),
    ('framework', 'Gatsby', 'html', r'gatsby'),
    ('framework', 'Remix', 'html', r'__remix'),
    ('framework', 'jQuery', 'script', r'jquery(?:\.min)?\.js'),
    ('framework', 'Alpine.js', 'html', r'x-data|x-bind|x-on'),
    ('framework', 'HTMX', 'html', r'hx-get|hx-post|hx-trigger'),
    ('framework', 'Tailwind CSS', 'html', r'(?:^|\s)(?:flex|grid|pt-|pb-|px-|py-|mt-|mb-|mx-|my-|bg-|text-|rounded|shadow|hover:|focus:)'),
    ('framework', 'Bootstrap', 'html', r'bootstrap(?:\.min)?\.(?:css|js)|class="[^"]*(?:container|row|col-|btn |navbar)'),
    # -- CMS --
    ('cms', 'WordPress', 'html', r'wp-content|wp-includes|wordpress'),
    ('cms', 'Drupal', 'html', r'drupal|sites/default/files'),
    ('cms', 'Shopify', 'html', r'cdn\.shopify\.com|shopify\.com'),
    ('cms', 'Squarespace', 'html', r'squarespace\.com|sqsp\.net'),
    ('cms', 'Wix', 'html', r'wix\.com|wixstatic\.com'),
    ('cms', 'Webflow', 'html', r'webflow\.com|assets\.website-files\.com'),
    ('cms', 'Ghost', 'html', r'ghost(?:\.org|\.io)|ghost-portal'),
    ('cms', 'Hugo', 'html', r'hugo-|gohugo'),
    ('cms', 'Jekyll', 'html', r'jekyll'),
    # -- Analytics --
    ('analytics', 'Google Analytics', 'script', r'google-analytics\.com|gtag|ga\.js|analytics\.js|googletagmanager'),
    ('analytics', 'Google Tag Manager', 'script', r'googletagmanager\.com/gtm'),
    ('analytics', 'Plausible', 'script', r'plausible\.io'),
    ('analytics', 'Fathom', 'script', r'usefathom\.com|cdn\.usefathom'),
    ('analytics', 'Mixpanel', 'script', r'mixpanel'),
    ('analytics', 'Segment', 'script', r'segment\.com|cdn\.segment'),
    ('analytics', 'Amplitude', 'script', r'amplitude\.com|cdn\.amplitude'),
    ('analytics', 'PostHog', 'script', r'posthog'),
    ('analytics', 'Hotjar', 'script', r'hotjar\.com|static\.hotjar'),
    ('analytics', 'Heap', 'script', r'heap(?:analytics)?'),
    ('analytics', 'Umami', 'script', r'umami\.is|analytics\.umami'),
    # -- Payments --
    ('payments', 'Stripe', 'script', r'stripe\.com|js\.stripe'),
    ('payments', 'PayPal', 'script', r'paypal\.com|paypalobjects'),
    ('payments', 'Gumroad', 'html', r'gumroad\.com'),
    ('payments', 'LemonSqueezy', 'html', r'lemonsqueezy\.com'),
    ('payments', 'Paddle', 'script', r'paddle\.com|cdn\.paddle'),
    # -- CDN / Hosting --
    ('infrastructure', 'Cloudflare', 'header', r'cloudflare'),
    ('infrastructure', 'Vercel', 'header', r'vercel'),
    ('infrastructure', 'Netlify', 'header', r'netlify'),
    ('infrastructure', 'AWS CloudFront', 'header', r'cloudfront'),
    ('infrastructure', 'Fastly', 'header', r'fastly'),
    ('infrastructure', 'Akamai', 'header', r'akamai'),
    ('infrastructure', 'Railway', 'header', r'railway'),
    ('infrastructure', 'Fly.io', 'header', r'fly\.io'),
    # -- Server --
    ('server', 'nginx', 'header', r'nginx'),
    ('server', 'Apache', 'header', r'apache'),
    ('server', 'Caddy', 'header', r'caddy'),
    ('server', 'Node.js', 'header', r'express|node'),
    # -- Chat / Support --
    ('widget', 'Intercom', 'script', r'intercom'),
    ('widget', 'Crisp', 'script', r'crisp\.chat'),
    ('widget', 'Drift', 'script', r'drift\.com|js\.driftt'),
    ('widget', 'Zendesk', 'script', r'zendesk|zdassets'),
    ('widget', 'HubSpot', 'script', r'hubspot|hs-scripts'),
    # -- Auth --
    ('auth', 'Clerk', 'script', r'clerk\.com|clerk\.(?:dev|js)'),
    ('auth', 'Auth0', 'script', r'auth0'),
    ('auth', 'Supabase', 'script', r'supabase'),
    ('auth', 'Firebase', 'script', r'firebase'),
    # -- Fonts --
    ('fonts', 'Google Fonts', 'html', r'fonts\.googleapis\.com|fonts\.gstatic\.com'),
    ('fonts', 'Adobe Fonts', 'html', r'use\.typekit\.net|p\.typekit\.net'),
    ('fonts', 'Font Awesome', 'html', r'font-?awesome|fa-(?:solid|regular|brands)'),
]


@dataclass
class ExtractedAsset:
    """A page resource — image, script, stylesheet, video, document."""
    url: str
    asset_type: str              # image | script | stylesheet | video | audio | document | font
    alt_text: Optional[str] = None
    size_hint: Optional[str] = None    # from Content-Length header if available
    loading: Optional[str] = None      # lazy | eager
    is_external: bool = False
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExtractedLink:
    """A link with full context — where it appears, anchor text, attributes."""
    url: str
    anchor_text: str = ""
    rel: List[str] = field(default_factory=list)
    is_external: bool = False
    is_navigation: bool = False
    is_footer: bool = False
    context: str = ""                  # surrounding text snippet
    nofollow: bool = False
    target: Optional[str] = None


@dataclass
class TechDetection:
    """A detected technology."""
    category: str   # framework | cms | analytics | payments | infrastructure | server | widget | auth | fonts
    name: str
    confidence: float = 0.8    # 0-1


@dataclass
class SEOAudit:
    """SEO health scorecard for a page."""
    score: int                                # 0-100
    title_length: Optional[int] = None
    title_ok: bool = False
    meta_desc_length: Optional[int] = None
    meta_desc_ok: bool = False
    has_h1: bool = False
    h1_count: int = 0
    has_canonical: bool = False
    has_og_tags: bool = False
    has_twitter_card: bool = False
    has_structured_data: bool = False
    has_robots_meta: bool = False
    has_viewport: bool = False
    has_lang: bool = False
    has_hreflang: bool = False
    has_sitemap_link: bool = False
    image_alt_coverage: float = 0.0          # 0-1
    heading_hierarchy_valid: bool = False
    issues: List[str] = field(default_factory=list)
    passes: List[str] = field(default_factory=list)


@dataclass
class ContentAnalysis:
    """Content quality and structure metrics."""
    readability_score: float = 0.0           # Flesch-Kincaid
    reading_level: str = ""                  # Grade level
    avg_sentence_length: float = 0.0
    avg_word_length: float = 0.0
    paragraph_count: int = 0
    sentence_count: int = 0
    unique_word_count: int = 0
    content_to_html_ratio: float = 0.0
    top_words: List[Dict[str, Any]] = field(default_factory=list)
    content_hash: str = ""


@dataclass
class DeepPageData:
    """Complete deep extraction result for a single page."""
    # Core (already captured, enhanced)
    url: str
    status_code: int
    title: Optional[str] = None
    meta_description: Optional[str] = None
    content_text: str = ""
    word_count: int = 0
    response_time_ms: int = 0
    depth: int = 0
    parent_url: Optional[str] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    content_type: Optional[str] = None
    content_length: int = 0

    # ── NEW: All meta tags ───────────────────────────────────
    meta_tags: Dict[str, str] = field(default_factory=dict)

    # ── NEW: OpenGraph full ──────────────────────────────────
    og_data: Dict[str, str] = field(default_factory=dict)

    # ── NEW: Twitter Card ────────────────────────────────────
    twitter_card: Dict[str, str] = field(default_factory=dict)

    # ── NEW: JSON-LD / Structured Data ───────────────────────
    structured_data: List[Dict[str, Any]] = field(default_factory=list)

    # ── NEW: Technology detection ────────────────────────────
    technologies: List[TechDetection] = field(default_factory=list)

    # ── NEW: Links with context ──────────────────────────────
    links: List[ExtractedLink] = field(default_factory=list)
    internal_link_count: int = 0
    external_link_count: int = 0

    # ── NEW: Assets inventory ────────────────────────────────
    assets: List[ExtractedAsset] = field(default_factory=list)
    images: List[ExtractedAsset] = field(default_factory=list)
    scripts: List[ExtractedAsset] = field(default_factory=list)
    stylesheets: List[ExtractedAsset] = field(default_factory=list)

    # ── NEW: Headings hierarchy ──────────────────────────────
    headings: List[Dict[str, Any]] = field(default_factory=list)
    h1: Optional[str] = None
    h1_count: int = 0

    # ── NEW: Forms with full field detail ────────────────────
    forms: List[Dict[str, Any]] = field(default_factory=list)

    # ── NEW: Contact information ─────────────────────────────
    emails: List[str] = field(default_factory=list)
    phone_numbers: List[str] = field(default_factory=list)
    addresses: List[str] = field(default_factory=list)
    social_links: Dict[str, str] = field(default_factory=dict)

    # ── NEW: SEO audit ───────────────────────────────────────
    seo: Optional[SEOAudit] = None

    # ── NEW: Content analysis ────────────────────────────────
    content_analysis: Optional[ContentAnalysis] = None

    # ── NEW: Canonical + hreflang ────────────────────────────
    canonical_url: Optional[str] = None
    hreflang: Dict[str, str] = field(default_factory=dict)

    # ── NEW: Robots directives ───────────────────────────────
    robots_meta: Optional[str] = None
    x_robots_tag: Optional[str] = None

    # ── NEW: Language ────────────────────────────────────────
    language: Optional[str] = None

    # ── NEW: Favicon ─────────────────────────────────────────
    favicon_url: Optional[str] = None

    # ── NEW: Performance hints ───────────────────────────────
    resource_counts: Dict[str, int] = field(default_factory=dict)
    total_resource_count: int = 0


class DeepExtractor:
    """Extracts every crumb of data from an HTML page."""

    def extract(
        self,
        url: str,
        status_code: int,
        html: str,
        headers: Dict[str, str],
        response_time_ms: int,
        depth: int = 0,
        parent_url: Optional[str] = None,
    ) -> DeepPageData:
        """Run full deep extraction on a page."""
        soup = BeautifulSoup(html, 'lxml')

        page = DeepPageData(
            url=url,
            status_code=status_code,
            response_time_ms=response_time_ms,
            depth=depth,
            parent_url=parent_url,
            response_headers=headers,
            content_type=headers.get('content-type', headers.get('Content-Type')),
            content_length=len(html),
        )

        # Core content
        page.title = self._extract_title(soup)
        page.content_text = self._extract_content(soup)
        page.word_count = len(page.content_text.split()) if page.content_text else 0

        # Deep extractions
        page.meta_tags = self._extract_all_meta(soup)
        page.meta_description = page.meta_tags.get('description')
        page.og_data = self._extract_og(soup)
        page.twitter_card = self._extract_twitter_card(soup)
        page.structured_data = self._extract_structured_data(soup)
        page.headings = self._extract_headings(soup)
        page.h1 = next((h['text'] for h in page.headings if h['level'] == 1), None)
        page.h1_count = sum(1 for h in page.headings if h['level'] == 1)
        page.canonical_url = self._extract_canonical(soup)
        page.hreflang = self._extract_hreflang(soup)
        page.robots_meta = self._extract_robots_meta(soup)
        page.x_robots_tag = headers.get('X-Robots-Tag')
        page.language = self._extract_language(soup)
        page.favicon_url = self._extract_favicon(soup, url)

        # Links with context
        page.links = self._extract_links(soup, url)
        page.internal_link_count = sum(1 for l in page.links if not l.is_external)
        page.external_link_count = sum(1 for l in page.links if l.is_external)

        # Assets
        page.images = self._extract_images(soup, url)
        page.scripts = self._extract_scripts(soup, url)
        page.stylesheets = self._extract_stylesheets(soup, url)
        page.assets = page.images + page.scripts + page.stylesheets
        page.resource_counts = {
            'images': len(page.images),
            'scripts': len(page.scripts),
            'stylesheets': len(page.stylesheets),
        }
        page.total_resource_count = len(page.assets)

        # Forms
        page.forms = self._extract_forms(soup, url)

        # Contact info
        page.emails = self._extract_emails(soup, html)
        page.phone_numbers = self._extract_phones(soup)
        page.addresses = self._extract_addresses(soup)
        page.social_links = self._extract_social_links(page.links)

        # Technology detection
        page.technologies = self._detect_technologies(soup, html, headers)

        # SEO audit
        page.seo = self._audit_seo(page, soup)

        # Content analysis
        page.content_analysis = self._analyze_content(page.content_text, html)

        return page

    # ── Meta Tags ────────────────────────────────────────────

    def _extract_all_meta(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract ALL meta tags, not just description."""
        meta = {}
        for tag in soup.find_all('meta'):
            name = tag.get('name') or tag.get('property') or tag.get('http-equiv')
            content = tag.get('content')
            if name and content:
                meta[name.lower()] = content
        return meta

    def _extract_og(self, soup: BeautifulSoup) -> Dict[str, str]:
        og = {}
        for tag in soup.find_all('meta', property=True):
            prop = tag.get('property', '')
            if prop.startswith('og:'):
                og[prop[3:]] = tag.get('content', '')
        return og

    def _extract_twitter_card(self, soup: BeautifulSoup) -> Dict[str, str]:
        tc = {}
        for tag in soup.find_all('meta', attrs={'name': True}):
            name = tag.get('name', '')
            if name.startswith('twitter:'):
                tc[name[8:]] = tag.get('content', '')
        return tc

    # ── Structured Data ──────────────────────────────────────

    def _extract_structured_data(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract JSON-LD structured data."""
        results = []
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '')
                if isinstance(data, list):
                    results.extend(data)
                elif isinstance(data, dict):
                    results.append(data)
            except (json.JSONDecodeError, TypeError):
                continue
        return results

    # ── Canonical + Hreflang ─────────────────────────────────

    def _extract_canonical(self, soup: BeautifulSoup) -> Optional[str]:
        link = soup.find('link', rel='canonical')
        return link.get('href') if link else None

    def _extract_hreflang(self, soup: BeautifulSoup) -> Dict[str, str]:
        hreflang = {}
        for link in soup.find_all('link', rel='alternate'):
            lang = link.get('hreflang')
            href = link.get('href')
            if lang and href:
                hreflang[lang] = href
        return hreflang

    def _extract_robots_meta(self, soup: BeautifulSoup) -> Optional[str]:
        tag = soup.find('meta', attrs={'name': 'robots'})
        return tag.get('content') if tag else None

    def _extract_language(self, soup: BeautifulSoup) -> Optional[str]:
        html_tag = soup.find('html')
        if html_tag:
            return html_tag.get('lang')
        return None

    def _extract_favicon(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        for rel in (['icon'], ['shortcut', 'icon'], ['apple-touch-icon']):
            link = soup.find('link', rel=rel)
            if link and link.get('href'):
                return urljoin(base_url, link['href'])
        return urljoin(base_url, '/favicon.ico')

    # ── Title ────────────────────────────────────────────────

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        h1 = soup.find('h1')
        return h1.get_text(strip=True) if h1 else None

    # ── Content ──────────────────────────────────────────────

    def _extract_content(self, soup: BeautifulSoup) -> str:
        # Work on a copy to avoid mutating the original
        clone = BeautifulSoup(str(soup), 'lxml')
        for tag in clone(['script', 'style', 'noscript', 'iframe', 'svg']):
            tag.decompose()

        for selector in ['main', 'article', '[role="main"]', '.content', '#content']:
            elem = clone.select_one(selector)
            if elem:
                return elem.get_text(separator=' ', strip=True)

        body = clone.find('body')
        return body.get_text(separator=' ', strip=True) if body else ''

    # ── Headings ─────────────────────────────────────────────

    def _extract_headings(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        headings = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            level = int(tag.name[1])
            text = tag.get_text(strip=True)
            if text:
                headings.append({
                    'level': level,
                    'text': text,
                    'id': tag.get('id'),
                })
        return headings

    # ── Links with context ───────────────────────────────────

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[ExtractedLink]:
        base_domain = urlparse(base_url).netloc
        links = []
        seen = set()

        for a in soup.find_all('a', href=True):
            href = a.get('href', '').strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            if parsed.scheme not in ('http', 'https'):
                continue

            if full_url in seen:
                continue
            seen.add(full_url)

            is_external = parsed.netloc != base_domain
            rel_attrs = a.get('rel', [])
            if isinstance(rel_attrs, str):
                rel_attrs = rel_attrs.split()

            # Determine if in nav/footer
            is_nav = self._is_in_tag(a, ['nav', 'header'])
            is_footer = self._is_in_tag(a, ['footer'])

            # Get surrounding context (up to 80 chars before and after)
            context = ''
            parent_text = a.parent.get_text(strip=True) if a.parent else ''
            if parent_text and len(parent_text) < 300:
                context = parent_text

            links.append(ExtractedLink(
                url=full_url,
                anchor_text=a.get_text(strip=True),
                rel=rel_attrs,
                is_external=is_external,
                is_navigation=is_nav,
                is_footer=is_footer,
                context=context[:200],
                nofollow='nofollow' in rel_attrs,
                target=a.get('target'),
            ))

        return links

    def _is_in_tag(self, element: Tag, tag_names: List[str]) -> bool:
        parent = element.parent
        while parent:
            if parent.name in tag_names:
                return True
            parent = parent.parent
        return False

    # ── Assets ───────────────────────────────────────────────

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[ExtractedAsset]:
        images = []
        seen = set()
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if not src:
                continue
            full_url = urljoin(base_url, src)
            if full_url in seen:
                continue
            seen.add(full_url)

            is_ext = urlparse(full_url).netloc != urlparse(base_url).netloc
            attrs = {}
            for attr in ('width', 'height', 'srcset', 'sizes'):
                val = img.get(attr)
                if val:
                    attrs[attr] = str(val)

            images.append(ExtractedAsset(
                url=full_url,
                asset_type='image',
                alt_text=img.get('alt', ''),
                loading=img.get('loading'),
                is_external=is_ext,
                attributes=attrs,
            ))
        return images

    def _extract_scripts(self, soup: BeautifulSoup, base_url: str) -> List[ExtractedAsset]:
        scripts = []
        seen = set()
        for s in soup.find_all('script'):
            src = s.get('src')
            if not src:
                continue
            full_url = urljoin(base_url, src)
            if full_url in seen:
                continue
            seen.add(full_url)

            is_ext = urlparse(full_url).netloc != urlparse(base_url).netloc
            attrs = {}
            for attr in ('async', 'defer', 'type', 'crossorigin', 'integrity'):
                val = s.get(attr)
                if val is not None:
                    attrs[attr] = str(val) if val != '' else 'true'

            scripts.append(ExtractedAsset(
                url=full_url,
                asset_type='script',
                is_external=is_ext,
                attributes=attrs,
            ))
        return scripts

    def _extract_stylesheets(self, soup: BeautifulSoup, base_url: str) -> List[ExtractedAsset]:
        sheets = []
        seen = set()
        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href')
            if not href:
                continue
            full_url = urljoin(base_url, href)
            if full_url in seen:
                continue
            seen.add(full_url)

            is_ext = urlparse(full_url).netloc != urlparse(base_url).netloc
            attrs = {}
            for attr in ('media', 'crossorigin', 'integrity'):
                val = link.get(attr)
                if val:
                    attrs[attr] = str(val)

            sheets.append(ExtractedAsset(
                url=full_url,
                asset_type='stylesheet',
                is_external=is_ext,
                attributes=attrs,
            ))
        return sheets

    # ── Forms ────────────────────────────────────────────────

    def _extract_forms(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        forms = []
        for form in soup.find_all('form'):
            fields = []
            for inp in form.find_all(['input', 'textarea', 'select', 'button']):
                field_data = {
                    'tag': inp.name,
                    'name': inp.get('name'),
                    'type': inp.get('type', 'text'),
                    'required': inp.get('required') is not None,
                    'placeholder': inp.get('placeholder'),
                    'value': inp.get('value'),
                    'id': inp.get('id'),
                }
                # Select options
                if inp.name == 'select':
                    field_data['options'] = [
                        {'value': opt.get('value', ''), 'text': opt.get_text(strip=True)}
                        for opt in inp.find_all('option')
                    ]
                fields.append(field_data)

            has_csrf = any(
                f.get('name', '').lower() in ('csrf', 'csrf_token', '_csrf', '_token', 'csrfmiddlewaretoken', 'authenticity_token')
                or f.get('type') == 'hidden'
                for f in fields
            )
            has_captcha = bool(form.find(class_=re.compile(r'captcha|recaptcha|hcaptcha|turnstile', re.I)))

            forms.append({
                'action': urljoin(base_url, form.get('action', '')),
                'method': (form.get('method') or 'GET').upper(),
                'id': form.get('id'),
                'name': form.get('name'),
                'enctype': form.get('enctype'),
                'fields': fields,
                'field_count': len(fields),
                'csrf_protected': has_csrf,
                'has_captcha': has_captcha,
                'has_file_upload': any(f.get('type') == 'file' for f in fields),
            })
        return forms

    # ── Contact Info ─────────────────────────────────────────

    def _extract_emails(self, soup: BeautifulSoup, html: str) -> List[str]:
        emails = set()
        # From mailto: links
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('mailto:'):
                email = href[7:].split('?')[0].strip()
                if email:
                    emails.add(email.lower())
        # From page text
        for match in _EMAIL_RE.findall(html):
            # Skip common false positives
            if not match.endswith(('.png', '.jpg', '.gif', '.css', '.js')):
                emails.add(match.lower())
        return sorted(emails)

    def _extract_phones(self, soup: BeautifulSoup) -> List[str]:
        phones = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('tel:'):
                phones.add(href[4:].strip())
        text = soup.get_text()
        for match in _PHONE_RE.findall(text):
            phones.add(match.strip())
        return sorted(phones)

    def _extract_addresses(self, soup: BeautifulSoup) -> List[str]:
        addresses = set()
        # From <address> tags
        for addr_tag in soup.find_all('address'):
            text = addr_tag.get_text(strip=True)
            if text:
                addresses.add(text[:200])
        # From regex
        page_text = soup.get_text()
        for match in _ADDRESS_RE.findall(page_text):
            addresses.add(match.strip())
        return sorted(addresses)

    def _extract_social_links(self, links: List[ExtractedLink]) -> Dict[str, str]:
        social = {}
        for link in links:
            domain = urlparse(link.url).netloc.lstrip('www.')
            platform = _SOCIAL_DOMAINS.get(domain)
            if platform and platform not in social:
                social[platform] = link.url
        return social

    # ── Technology Detection ─────────────────────────────────

    def _detect_technologies(
        self,
        soup: BeautifulSoup,
        html: str,
        headers: Dict[str, str],
    ) -> List[TechDetection]:
        techs = []
        seen = set()

        header_str = ' '.join(f'{k}: {v}' for k, v in headers.items()).lower()
        script_str = ' '.join(
            s.get('src', '') for s in soup.find_all('script') if s.get('src')
        ).lower()

        for category, name, search_in, pattern in _TECH_PATTERNS:
            if name in seen:
                continue

            target = ''
            if search_in == 'html':
                target = html
            elif search_in == 'script':
                target = script_str
            elif search_in == 'header':
                target = header_str

            if re.search(pattern, target, re.IGNORECASE):
                seen.add(name)
                techs.append(TechDetection(
                    category=category,
                    name=name,
                    confidence=0.9 if search_in in ('header', 'script') else 0.7,
                ))

        # Generator meta tag
        gen = soup.find('meta', attrs={'name': 'generator'})
        if gen and gen.get('content'):
            gen_content = gen['content']
            if gen_content not in seen:
                techs.append(TechDetection(
                    category='cms',
                    name=gen_content,
                    confidence=1.0,
                ))

        return techs

    # ── SEO Audit ────────────────────────────────────────────

    def _audit_seo(self, page: DeepPageData, soup: BeautifulSoup) -> SEOAudit:
        audit = SEOAudit(score=0)
        score = 0
        max_score = 0

        # Title
        max_score += 10
        if page.title:
            audit.title_length = len(page.title)
            audit.title_ok = 10 <= len(page.title) <= 70
            if audit.title_ok:
                score += 10
                audit.passes.append(f'Title tag present ({audit.title_length} chars)')
            else:
                score += 3
                audit.issues.append(f'Title length {audit.title_length} chars (ideal: 10-70)')
        else:
            audit.issues.append('Missing title tag')

        # Meta description
        max_score += 10
        if page.meta_description:
            audit.meta_desc_length = len(page.meta_description)
            audit.meta_desc_ok = 50 <= len(page.meta_description) <= 160
            if audit.meta_desc_ok:
                score += 10
                audit.passes.append(f'Meta description present ({audit.meta_desc_length} chars)')
            else:
                score += 3
                audit.issues.append(f'Meta description {audit.meta_desc_length} chars (ideal: 50-160)')
        else:
            audit.issues.append('Missing meta description')

        # H1
        max_score += 10
        audit.has_h1 = page.h1_count > 0
        audit.h1_count = page.h1_count
        if page.h1_count == 1:
            score += 10
            audit.passes.append('Single H1 tag present')
        elif page.h1_count > 1:
            score += 5
            audit.issues.append(f'Multiple H1 tags ({page.h1_count})')
        else:
            audit.issues.append('Missing H1 tag')

        # Heading hierarchy
        max_score += 5
        levels = [h['level'] for h in page.headings]
        audit.heading_hierarchy_valid = self._check_heading_hierarchy(levels)
        if audit.heading_hierarchy_valid:
            score += 5
            audit.passes.append('Valid heading hierarchy')
        elif levels:
            score += 2
            audit.issues.append('Heading hierarchy has gaps')

        # Canonical
        max_score += 5
        audit.has_canonical = page.canonical_url is not None
        if audit.has_canonical:
            score += 5
            audit.passes.append('Canonical URL set')
        else:
            audit.issues.append('Missing canonical URL')

        # OG tags
        max_score += 5
        audit.has_og_tags = len(page.og_data) >= 3
        if audit.has_og_tags:
            score += 5
            audit.passes.append(f'Open Graph tags present ({len(page.og_data)} tags)')
        else:
            audit.issues.append('Missing or incomplete Open Graph tags')

        # Twitter card
        max_score += 5
        audit.has_twitter_card = len(page.twitter_card) >= 2
        if audit.has_twitter_card:
            score += 5
            audit.passes.append('Twitter Card tags present')
        else:
            audit.issues.append('Missing Twitter Card tags')

        # Structured data
        max_score += 10
        audit.has_structured_data = len(page.structured_data) > 0
        if audit.has_structured_data:
            score += 10
            audit.passes.append(f'Structured data present ({len(page.structured_data)} blocks)')
        else:
            audit.issues.append('No structured data (JSON-LD)')

        # Robots meta
        max_score += 3
        audit.has_robots_meta = page.robots_meta is not None
        if audit.has_robots_meta:
            score += 3

        # Viewport
        max_score += 5
        audit.has_viewport = 'viewport' in page.meta_tags
        if audit.has_viewport:
            score += 5
            audit.passes.append('Viewport meta tag set')
        else:
            audit.issues.append('Missing viewport meta tag')

        # Language
        max_score += 5
        audit.has_lang = page.language is not None
        if audit.has_lang:
            score += 5
            audit.passes.append(f'Language attribute set ({page.language})')
        else:
            audit.issues.append('Missing lang attribute on <html>')

        # Hreflang
        max_score += 3
        audit.has_hreflang = len(page.hreflang) > 0
        if audit.has_hreflang:
            score += 3

        # Image alt coverage
        max_score += 10
        total_images = len(page.images)
        if total_images > 0:
            with_alt = sum(1 for img in page.images if img.alt_text)
            audit.image_alt_coverage = with_alt / total_images
            alt_score = int(audit.image_alt_coverage * 10)
            score += alt_score
            if audit.image_alt_coverage >= 0.9:
                audit.passes.append(f'Image alt text coverage: {audit.image_alt_coverage:.0%}')
            else:
                audit.issues.append(f'Image alt text coverage: {audit.image_alt_coverage:.0%} ({total_images - with_alt} missing)')
        else:
            score += 10  # No images, no penalty

        # Content length
        max_score += 10
        if page.word_count >= 300:
            score += 10
            audit.passes.append(f'Good content length ({page.word_count} words)')
        elif page.word_count >= 100:
            score += 5
            audit.issues.append(f'Thin content ({page.word_count} words)')
        else:
            audit.issues.append(f'Very thin content ({page.word_count} words)')

        audit.score = round((score / max_score) * 100) if max_score > 0 else 0
        return audit

    def _check_heading_hierarchy(self, levels: List[int]) -> bool:
        if not levels:
            return True
        for i in range(1, len(levels)):
            if levels[i] > levels[i - 1] + 1:
                return False
        return True

    # ── Content Analysis ─────────────────────────────────────

    def _analyze_content(self, text: str, html: str) -> ContentAnalysis:
        analysis = ContentAnalysis()
        if not text or len(text) < 50:
            return analysis

        words = text.split()
        sentences = _SENTENCE_RE.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]

        analysis.sentence_count = max(len(sentences), 1)
        analysis.unique_word_count = len(set(w.lower() for w in words))
        analysis.avg_sentence_length = len(words) / analysis.sentence_count
        analysis.avg_word_length = sum(len(w) for w in words) / max(len(words), 1)
        analysis.paragraph_count = max(html.count('<p'), 1)

        # Content to HTML ratio
        text_len = len(text)
        html_len = len(html)
        analysis.content_to_html_ratio = text_len / html_len if html_len > 0 else 0

        # Flesch-Kincaid readability
        total_syllables = sum(
            max(len(_SYLLABLE_RE.findall(w)), 1) for w in words
        )
        word_count = max(len(words), 1)
        sent_count = analysis.sentence_count

        fk_score = (
            206.835
            - 1.015 * (word_count / sent_count)
            - 84.6 * (total_syllables / word_count)
        )
        analysis.readability_score = round(max(0, min(100, fk_score)), 1)

        if fk_score >= 90:
            analysis.reading_level = '5th grade'
        elif fk_score >= 80:
            analysis.reading_level = '6th grade'
        elif fk_score >= 70:
            analysis.reading_level = '7th grade'
        elif fk_score >= 60:
            analysis.reading_level = '8th-9th grade'
        elif fk_score >= 50:
            analysis.reading_level = '10th-12th grade'
        elif fk_score >= 30:
            analysis.reading_level = 'College'
        else:
            analysis.reading_level = 'Graduate'

        # Top words (excluding common stop words)
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'can', 'shall',
            'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
            'as', 'into', 'through', 'during', 'before', 'after', 'above',
            'below', 'between', 'out', 'off', 'over', 'under', 'again',
            'further', 'then', 'once', 'here', 'there', 'when', 'where',
            'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
            'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
            'own', 'same', 'so', 'than', 'too', 'very', 'just', 'because',
            'but', 'and', 'or', 'if', 'while', 'about', 'up', 'it', 'its',
            'this', 'that', 'these', 'those', 'i', 'me', 'my', 'we', 'our',
            'you', 'your', 'he', 'she', 'they', 'them', 'his', 'her',
            'what', 'which', 'who', 'whom', 'also', 'like', 'get', 'one',
        }
        word_freq: Dict[str, int] = {}
        for w in words:
            clean = re.sub(r'[^a-z]', '', w.lower())
            if clean and len(clean) > 2 and clean not in stop_words:
                word_freq[clean] = word_freq.get(clean, 0) + 1

        top = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20]
        analysis.top_words = [{'word': w, 'count': c} for w, c in top]

        # Content hash for change detection
        analysis.content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        return analysis
