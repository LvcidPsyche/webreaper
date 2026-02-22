"""Blogwatcher integration bridge."""

import json
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..config import BlogwatcherConfig


class BlogwatcherBridge:
    """Bridge to scrape RSS-less sites and generate feeds."""
    
    def __init__(self, config: BlogwatcherConfig):
        self.config = config
        self.articles: List[Dict[str, Any]] = []
    
    def extract_articles(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract articles from HTML page."""
        soup = BeautifulSoup(html, 'lxml')
        articles = []
        
        # Try multiple article detection strategies
        strategies = [
            self._extract_by_article_tag,
            self._extract_by_classes,
            self._extract_by_headings,
            self._extract_generic,
        ]
        
        for strategy in strategies:
            found = strategy(soup, base_url)
            if found:
                articles.extend(found)
                if len(articles) >= 10:  # Limit per page
                    break
        
        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)
        
        return unique_articles
    
    def _extract_by_article_tag(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Extract using HTML5 article tags."""
        articles = []
        
        for article_tag in soup.find_all('article'):
            article = self._parse_article_element(article_tag, base_url)
            if article:
                articles.append(article)
        
        return articles
    
    def _extract_by_classes(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Extract using common class names."""
        articles = []
        class_names = ['post', 'entry', 'blog-post', 'article-item', 'news-item']
        
        for class_name in class_names:
            for elem in soup.find_all(class_=re.compile(class_name, re.I)):
                article = self._parse_article_element(elem, base_url)
                if article:
                    articles.append(article)
        
        return articles
    
    def _extract_by_headings(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Extract by finding headings with dates nearby."""
        articles = []
        
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            # Look for date near heading
            date = None
            for sibling in heading.find_next_siblings(limit=3):
                date = self._extract_date(sibling.get_text())
                if date:
                    break
            
            if not date:
                # Check parent for date
                parent = heading.find_parent()
                if parent:
                    date = self._extract_date(parent.get_text())
            
            # Find link in heading
            link = heading.find('a')
            if link and link.get('href'):
                url = urljoin(base_url, link.get('href'))
                articles.append({
                    'title': heading.get_text(strip=True),
                    'url': url,
                    'date': date or datetime.now().isoformat(),
                    'summary': self._extract_summary(heading),
                })
        
        return articles
    
    def _extract_generic(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """Generic extraction as fallback."""
        articles = []
        
        # Find all links that look like article links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Skip navigation, ads, etc.
            if len(text) < 20 or len(text) > 200:
                continue
            
            # Check if URL looks like article
            if self._is_article_url(href):
                url = urljoin(base_url, href)
                articles.append({
                    'title': text,
                    'url': url,
                    'date': datetime.now().isoformat(),
                    'summary': '',
                })
        
        return articles[:20]  # Limit results
    
    def _parse_article_element(self, elem: BeautifulSoup, base_url: str) -> Optional[Dict[str, Any]]:
        """Parse a single article element."""
        # Extract title
        title = None
        for selector in self.config.title_selectors:
            title_elem = elem.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                break
        
        if not title:
            title = elem.get_text(strip=True)[:100]
        
        # Extract URL
        url = None
        link = elem.find('a', href=True)
        if link:
            url = urljoin(base_url, link.get('href'))
        
        if not url:
            return None
        
        # Extract date
        date = None
        for selector in self.config.date_selectors:
            date_elem = elem.select_one(selector)
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                date = self._extract_date(date_text)
                if date:
                    break
        
        # Extract summary
        summary = ''
        for selector in self.config.content_selectors:
            content_elem = elem.select_one(selector)
            if content_elem:
                summary = content_elem.get_text(strip=True)[:300]
                break
        
        return {
            'title': title,
            'url': url,
            'date': date or datetime.now().isoformat(),
            'summary': summary,
        }
    
    def _is_article_url(self, url: str) -> bool:
        """Check if URL looks like an article."""
        patterns = [
            r'/blog/',
            r'/news/',
            r'/article/',
            r'/post/',
            r'/\d{4}/\d{2}/',  # Date pattern
            r'/\d{4}-\d{2}-',
            r'\?p=\d+',
        ]
        
        for pattern in patterns:
            if re.search(pattern, url, re.I):
                return True
        
        return False
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from text."""
        # Common date patterns
        patterns = [
            (r'(\d{4}-\d{2}-\d{2})', '%Y-%m-%d'),
            (r'(\d{2}/\d{2}/\d{4})', '%m/%d/%Y'),
            (r'(\d{2}\.\d{2}\.\d{4})', '%d.%m.%Y'),
            (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', '%B %d %Y'),
        ]
        
        for pattern, fmt in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    date_str = match.group(0)
                    parsed = datetime.strptime(date_str, fmt)
                    return parsed.isoformat()
                except ValueError:
                    continue
        
        return None
    
    def _extract_summary(self, heading: BeautifulSoup) -> str:
        """Extract summary text after heading."""
        summary = []
        for sibling in heading.find_next_siblings(limit=2):
            text = sibling.get_text(strip=True)
            if text and len(text) > 20:
                summary.append(text)
                if len(' '.join(summary)) > 200:
                    break
        
        return ' '.join(summary)[:300]
    
    def generate_rss(self, articles: List[Dict[str, Any]], feed_title: str, feed_url: str) -> str:
        """Generate RSS 2.0 feed from articles."""
        rss = ['<?xml version="1.0" encoding="UTF-8"?>']
        rss.append('<rss version="2.0">')
        rss.append('<channel>')
        rss.append(f'<title>{feed_title}</title>')
        rss.append(f'<link>{feed_url}</link>')
        rss.append(f'<description>Generated by WebReaper</description>')
        rss.append(f'<lastBuildDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")}</lastBuildDate>')
        
        for article in articles:
            rss.append('<item>')
            rss.append(f'<title>{self._escape_xml(article["title"])}</title>')
            rss.append(f'<link>{article["url"]}</link>')
            rss.append(f'<guid>{article["url"]}</guid>')
            if article.get('summary'):
                rss.append(f'<description>{self._escape_xml(article["summary"])}</description>')
            if article.get('date'):
                rss.append(f'<pubDate>{article["date"]}</pubDate>')
            rss.append('</item>')
        
        rss.append('</channel>')
        rss.append('</rss>')
        
        return '\n'.join(rss)
    
    def generate_json_feed(self, articles: List[Dict[str, Any]], feed_title: str, feed_url: str) -> str:
        """Generate JSON Feed format."""
        feed = {
            "version": "https://jsonfeed.org/version/1.1",
            "title": feed_title,
            "home_page_url": feed_url,
            "feed_url": feed_url + "/feed.json",
            "items": []
        }
        
        for article in articles:
            item = {
                "id": hashlib.md5(article["url"].encode()).hexdigest(),
                "url": article["url"],
                "title": article["title"],
            }
            if article.get('summary'):
                item["content_text"] = article["summary"]
            if article.get('date'):
                item["date_published"] = article["date"]
            
            feed["items"].append(item)
        
        return json.dumps(feed, indent=2)
    
    @staticmethod
    def _escape_xml(text: str) -> str:
        """Escape XML special characters."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))
    
    def save_feed(self, articles: List[Dict[str, Any]], output_path: Path, feed_title: str, feed_url: str):
        """Save feed to file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.config.output_format == "rss":
            content = self.generate_rss(articles, feed_title, feed_url)
            output_path = output_path.with_suffix('.xml')
        else:
            content = self.generate_json_feed(articles, feed_title, feed_url)
            output_path = output_path.with_suffix('.json')
        
        with open(output_path, 'w') as f:
            f.write(content)
        
        return output_path
