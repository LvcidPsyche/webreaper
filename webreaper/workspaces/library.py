"""Workspace library helpers for filing and categorizing scraped pages."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


CATEGORY_FOLDERS = {
    "api": "api",
    "article": "articles",
    "careers": "company/careers",
    "company": "company",
    "contact": "contacts",
    "documentation": "docs",
    "download": "downloads",
    "landing": "site/root",
    "legal": "legal",
    "pricing": "product/pricing",
    "product": "product",
    "research": "research",
    "general": "general",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _path_keywords(page: Mapping[str, Any]) -> str:
    return " ".join(
        [
            _lower(page.get("path")),
            _lower(page.get("title")),
            _lower(page.get("h1")),
            _lower(page.get("meta_description")),
            _lower(page.get("canonical_url")),
        ]
    )


def content_family(content_type: Any) -> str:
    normalized = _lower(content_type).split(";", 1)[0]
    if not normalized:
        return "unknown"
    if normalized.startswith("text/html"):
        return "html"
    if normalized.startswith("image/"):
        return "image"
    if any(token in normalized for token in ("json", "xml")):
        return "machine-readable"
    if any(token in normalized for token in ("pdf", "msword", "officedocument", "spreadsheet", "presentation", "zip")):
        return "document"
    return normalized


def suggest_page_category(page: Mapping[str, Any]) -> str:
    keywords = _path_keywords(page)
    path = _lower(page.get("path"))
    family = content_family(page.get("content_type"))

    if family in {"document", "image"}:
        return "download"
    if any(token in keywords for token in ("privacy", "terms", "cookie", "legal", "gdpr")):
        return "legal"
    if any(token in keywords for token in ("contact", "support", "help desk")) or any(page.get(field) for field in ("emails_found", "phone_numbers", "addresses_found")):
        return "contact"
    if any(token in keywords for token in ("docs", "documentation", "reference", "guide", "tutorial", "handbook")):
        return "documentation"
    if family == "machine-readable" or path.startswith("/api") or any(token in path for token in ("/openapi", "/swagger")):
        return "api"
    if any(token in keywords for token in ("pricing", "plans", "quote", "subscription")):
        return "pricing"
    if any(token in keywords for token in ("careers", "jobs", "hiring")):
        return "careers"
    if any(token in keywords for token in ("about", "team", "company", "mission")):
        return "company"
    if any(token in keywords for token in ("blog", "news", "article", "changelog", "update")):
        return "article"
    if any(token in keywords for token in ("research", "whitepaper", "report", "case study")):
        return "research"
    if any(token in keywords for token in ("product", "platform", "feature", "solution")):
        return "product"
    if path in {"", "/"} or int(page.get("depth") or 0) == 0:
        return "landing"
    return "general"


def suggest_folder(page: Mapping[str, Any], category: str) -> str:
    domain = _text(page.get("domain")) or "unknown-domain"
    return f"{domain}/{CATEGORY_FOLDERS.get(category, 'general')}"


def suggest_labels(page: Mapping[str, Any], category: str) -> list[str]:
    labels = [
        f"domain:{_text(page.get('domain')) or 'unknown'}",
        f"category:{category}",
        f"status:{int(page.get('status_code') or 0) or 'unknown'}",
        f"fetch:{_text(page.get('fetch_mode')) or 'http'}",
        f"content:{content_family(page.get('content_type'))}",
    ]
    if _text(page.get("path")).startswith("/blog"):
        labels.append("section:blog")
    if _text(page.get("path")).startswith("/docs"):
        labels.append("section:docs")
    return sorted({label for label in labels if label and not label.endswith(":unknown")})


def _merge_labels(*label_sets: Iterable[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for labels in label_sets:
        for label in labels:
            normalized = _text(label)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def build_library_item(
    *,
    page: Mapping[str, Any],
    crawl: Mapping[str, Any] | None = None,
    filing: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    suggested_category = suggest_page_category(page)
    suggested_folder = suggest_folder(page, suggested_category)
    suggested_labels = suggest_labels(page, suggested_category)

    manual_category = _text((filing or {}).get("category")) or None
    manual_folder = _text((filing or {}).get("folder")) or None
    manual_labels = list((filing or {}).get("labels") or [])

    effective_category = manual_category or suggested_category
    effective_folder = manual_folder or suggest_folder(page, effective_category)
    effective_labels = _merge_labels(manual_labels, suggested_labels)

    return {
        "page_id": _text(page.get("id")),
        "workspace_id": _text(page.get("workspace_id")),
        "crawl_id": _text(page.get("crawl_id")),
        "crawl_target_url": _text((crawl or {}).get("target_url")),
        "crawl_status": _text((crawl or {}).get("status")) or None,
        "url": _text(page.get("url")),
        "domain": _text(page.get("domain")),
        "path": _text(page.get("path")) or "/",
        "title": _text(page.get("title")),
        "h1": _text(page.get("h1")),
        "meta_description": _text(page.get("meta_description")),
        "status_code": page.get("status_code"),
        "content_type": _text(page.get("content_type")),
        "content_family": content_family(page.get("content_type")),
        "word_count": int(page.get("word_count") or 0),
        "depth": int(page.get("depth") or 0),
        "fetch_mode": _text(page.get("fetch_mode")) or "http",
        "scraped_at": page.get("scraped_at").isoformat() if hasattr(page.get("scraped_at"), "isoformat") else page.get("scraped_at"),
        "suggested_category": suggested_category,
        "suggested_folder": suggested_folder,
        "suggested_labels": suggested_labels,
        "category": effective_category,
        "folder": effective_folder,
        "labels": effective_labels,
        "category_source": "manual" if manual_category else "suggested",
        "folder_source": "manual" if manual_folder else "suggested",
        "filing_id": _text((filing or {}).get("id")) or None,
        "starred": bool((filing or {}).get("starred")),
        "notes": _text((filing or {}).get("notes")) or None,
        "has_manual_filing": filing is not None,
    }


def filter_library_items(
    items: list[dict[str, Any]],
    *,
    search: str | None = None,
    category: str | None = None,
    folder: str | None = None,
    domain: str | None = None,
    starred: bool | None = None,
    status_code: int | None = None,
) -> list[dict[str, Any]]:
    filtered = list(items)
    if search:
        needle = _lower(search)
        filtered = [
            item for item in filtered
            if needle in _lower(item.get("url"))
            or needle in _lower(item.get("title"))
            or needle in _lower(item.get("h1"))
            or needle in _lower(item.get("meta_description"))
        ]
    if category:
        filtered = [item for item in filtered if _lower(item.get("category")) == _lower(category)]
    if folder:
        filtered = [item for item in filtered if _lower(item.get("folder")) == _lower(folder)]
    if domain:
        filtered = [item for item in filtered if _lower(item.get("domain")) == _lower(domain)]
    if starred is not None:
        filtered = [item for item in filtered if bool(item.get("starred")) is bool(starred)]
    if status_code is not None:
        filtered = [item for item in filtered if int(item.get("status_code") or 0) == status_code]
    return filtered


def summarize_library(items: list[dict[str, Any]]) -> dict[str, Any]:
    category_counts = Counter(item["category"] for item in items)
    folder_counts = Counter(item["folder"] for item in items)
    domain_counts = Counter(item["domain"] for item in items if item.get("domain"))
    content_counts = Counter(item["content_family"] for item in items)

    return {
        "total_pages": len(items),
        "filed_pages": sum(1 for item in items if item.get("has_manual_filing")),
        "starred_pages": sum(1 for item in items if item.get("starred")),
        "domains": len(domain_counts),
        "by_category": [{"category": name, "count": count} for name, count in category_counts.most_common()],
        "by_folder": [{"folder": name, "count": count} for name, count in folder_counts.most_common()],
        "by_domain": [{"domain": name, "count": count} for name, count in domain_counts.most_common()],
        "by_content_family": [{"content_family": name, "count": count} for name, count in content_counts.most_common()],
        "avg_word_count": round(sum(item.get("word_count", 0) for item in items) / len(items), 1) if items else 0.0,
    }
