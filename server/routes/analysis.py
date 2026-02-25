"""Analysis API — deep data querying, technology radar, SEO audit, content analysis."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query
from sqlalchemy import text

router = APIRouter()
logger = logging.getLogger("webreaper.analysis")


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


# ── Technology Radar ─────────────────────────────────────────


@router.get("/technologies/{crawl_id}")
async def technology_radar(request: Request, crawl_id: str):
    """Technology stack detected across all pages in a crawl."""
    db = _db(request)
    async with db.get_session() as session:
        result = await session.execute(text("""
            SELECT
                category, name,
                COUNT(DISTINCT domain) as domain_count,
                COUNT(DISTINCT page_id) as page_count,
                ROUND(AVG(confidence), 2) as avg_confidence
            FROM technologies
            WHERE crawl_id = :cid
            GROUP BY category, name
            ORDER BY domain_count DESC, page_count DESC
        """), {"cid": crawl_id})
        techs = [dict(r._mapping) for r in result.fetchall()]

    # Group by category
    by_category = {}
    for t in techs:
        cat = t["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(t)

    return {
        "crawl_id": crawl_id,
        "total_technologies": len(techs),
        "by_category": by_category,
        "flat": techs,
    }


# ── SEO Overview ─────────────────────────────────────────────


@router.get("/seo/{crawl_id}")
async def seo_overview(request: Request, crawl_id: str):
    """SEO audit overview for all pages in a crawl."""
    db = _db(request)
    async with db.get_session() as session:
        # Score distribution
        score_result = await session.execute(text("""
            SELECT
                CASE
                    WHEN seo_score >= 90 THEN 'excellent'
                    WHEN seo_score >= 70 THEN 'good'
                    WHEN seo_score >= 50 THEN 'needs_work'
                    WHEN seo_score >= 30 THEN 'poor'
                    ELSE 'critical'
                END as grade,
                COUNT(*) as count,
                ROUND(AVG(seo_score), 1) as avg_score
            FROM pages
            WHERE crawl_id = :cid AND seo_score IS NOT NULL
            GROUP BY grade
            ORDER BY avg_score DESC
        """), {"cid": crawl_id})
        score_dist = [dict(r._mapping) for r in score_result.fetchall()]

        # Common issues
        issue_result = await session.execute(text("""
            SELECT seo_issues FROM pages
            WHERE crawl_id = :cid AND seo_issues IS NOT NULL
        """), {"cid": crawl_id})
        issue_rows = issue_result.fetchall()

        issue_counts = {}
        for row in issue_rows:
            issues = row[0]
            if isinstance(issues, str):
                try:
                    issues = json.loads(issues)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(issues, list):
                for issue in issues:
                    issue_counts[issue] = issue_counts.get(issue, 0) + 1

        common_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        # Aggregate metrics
        agg_result = await session.execute(text("""
            SELECT
                ROUND(AVG(seo_score), 1) as avg_seo_score,
                COUNT(CASE WHEN has_canonical = 1 THEN 1 END) as pages_with_canonical,
                COUNT(CASE WHEN language IS NOT NULL THEN 1 END) as pages_with_lang,
                COUNT(*) as total_pages,
                ROUND(AVG(readability_score), 1) as avg_readability,
                ROUND(AVG(word_count), 0) as avg_word_count
            FROM pages WHERE crawl_id = :cid
        """), {"cid": crawl_id})
        agg = dict(agg_result.fetchone()._mapping)

        # Worst performing pages
        worst_result = await session.execute(text("""
            SELECT id, url, title, seo_score, seo_issues
            FROM pages
            WHERE crawl_id = :cid AND seo_score IS NOT NULL
            ORDER BY seo_score ASC
            LIMIT 10
        """), {"cid": crawl_id})
        worst_pages = []
        for r in worst_result.fetchall():
            row = dict(r._mapping)
            if isinstance(row.get('seo_issues'), str):
                try:
                    row['seo_issues'] = json.loads(row['seo_issues'])
                except (json.JSONDecodeError, TypeError):
                    pass
            worst_pages.append(row)

    return {
        "crawl_id": crawl_id,
        "overview": agg,
        "score_distribution": score_dist,
        "common_issues": [{"issue": i, "count": c} for i, c in common_issues],
        "worst_pages": worst_pages,
    }


# ── Content Analysis ─────────────────────────────────────────


@router.get("/content/{crawl_id}")
async def content_analysis(request: Request, crawl_id: str):
    """Content quality analysis across a crawl."""
    db = _db(request)
    async with db.get_session() as session:
        # Readability distribution
        read_result = await session.execute(text("""
            SELECT
                reading_level,
                COUNT(*) as count,
                ROUND(AVG(readability_score), 1) as avg_score
            FROM pages
            WHERE crawl_id = :cid AND reading_level IS NOT NULL
            GROUP BY reading_level
            ORDER BY avg_score DESC
        """), {"cid": crawl_id})
        readability_dist = [dict(r._mapping) for r in read_result.fetchall()]

        # Word count distribution
        wc_result = await session.execute(text("""
            SELECT
                CASE
                    WHEN word_count < 100 THEN 'thin (<100)'
                    WHEN word_count < 300 THEN 'short (100-300)'
                    WHEN word_count < 1000 THEN 'medium (300-1k)'
                    WHEN word_count < 2000 THEN 'long (1k-2k)'
                    ELSE 'very long (2k+)'
                END as bucket,
                COUNT(*) as count,
                ROUND(AVG(word_count), 0) as avg_words
            FROM pages
            WHERE crawl_id = :cid AND word_count IS NOT NULL
            GROUP BY bucket
            ORDER BY MIN(word_count)
        """), {"cid": crawl_id})
        word_count_dist = [dict(r._mapping) for r in wc_result.fetchall()]

        # Content-to-HTML ratio
        ratio_result = await session.execute(text("""
            SELECT
                ROUND(AVG(content_to_html_ratio), 3) as avg_ratio,
                ROUND(MIN(content_to_html_ratio), 3) as min_ratio,
                ROUND(MAX(content_to_html_ratio), 3) as max_ratio
            FROM pages
            WHERE crawl_id = :cid AND content_to_html_ratio IS NOT NULL
        """), {"cid": crawl_id})
        ratio = dict(ratio_result.fetchone()._mapping)

        # Top words across entire crawl
        top_words_result = await session.execute(text("""
            SELECT top_words FROM pages
            WHERE crawl_id = :cid AND top_words IS NOT NULL
            LIMIT 200
        """), {"cid": crawl_id})

        aggregated_words = {}
        for row in top_words_result.fetchall():
            words = row[0]
            if isinstance(words, str):
                try:
                    words = json.loads(words)
                except (json.JSONDecodeError, TypeError):
                    continue
            if isinstance(words, list):
                for item in words:
                    if isinstance(item, dict):
                        w = item.get('word', '')
                        c = item.get('count', 0)
                        aggregated_words[w] = aggregated_words.get(w, 0) + c

        top_words = sorted(aggregated_words.items(), key=lambda x: x[1], reverse=True)[:30]

        # Languages detected
        lang_result = await session.execute(text("""
            SELECT language, COUNT(*) as count
            FROM pages
            WHERE crawl_id = :cid AND language IS NOT NULL
            GROUP BY language
            ORDER BY count DESC
        """), {"cid": crawl_id})
        languages = [dict(r._mapping) for r in lang_result.fetchall()]

    return {
        "crawl_id": crawl_id,
        "readability_distribution": readability_dist,
        "word_count_distribution": word_count_dist,
        "content_to_html_ratio": ratio,
        "top_words": [{"word": w, "count": c} for w, c in top_words],
        "languages": languages,
    }


# ── Contact Info Discovery ───────────────────────────────────


@router.get("/contacts/{crawl_id}")
async def contact_discovery(request: Request, crawl_id: str):
    """All discovered contact information across a crawl."""
    db = _db(request)
    async with db.get_session() as session:
        result = await session.execute(text("""
            SELECT url, domain, emails_found, phone_numbers, addresses_found, social_links
            FROM pages
            WHERE crawl_id = :cid
            AND (
                emails_found IS NOT NULL
                OR phone_numbers IS NOT NULL
                OR addresses_found IS NOT NULL
                OR social_links IS NOT NULL
            )
        """), {"cid": crawl_id})
        rows = result.fetchall()

    all_emails = {}
    all_phones = {}
    all_social = {}
    all_addresses = set()

    for row in rows:
        url = row[0]
        domain = row[1]

        for field_idx, field_name in [(2, 'emails'), (3, 'phones')]:
            data = row[field_idx]
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    data = []
            store = all_emails if field_name == 'emails' else all_phones
            if isinstance(data, list):
                for item in data:
                    if item not in store:
                        store[item] = {'sources': [], 'domain': domain}
                    store[item]['sources'].append(url)

        addresses = row[4]
        if isinstance(addresses, str):
            try:
                addresses = json.loads(addresses)
            except (json.JSONDecodeError, TypeError):
                addresses = []
        if isinstance(addresses, list):
            for addr in addresses:
                all_addresses.add(addr)

        social = row[5]
        if isinstance(social, str):
            try:
                social = json.loads(social)
            except (json.JSONDecodeError, TypeError):
                social = {}
        if isinstance(social, dict):
            for platform, link in social.items():
                if platform not in all_social:
                    all_social[platform] = link

    return {
        "crawl_id": crawl_id,
        "emails": [{"email": e, "domain": d["domain"], "found_on": len(d["sources"])} for e, d in all_emails.items()],
        "phones": [{"number": p, "domain": d["domain"], "found_on": len(d["sources"])} for p, d in all_phones.items()],
        "social_profiles": all_social,
        "addresses": sorted(all_addresses),
        "totals": {
            "emails": len(all_emails),
            "phones": len(all_phones),
            "social_profiles": len(all_social),
            "addresses": len(all_addresses),
        },
    }


# ── Asset Inventory ──────────────────────────────────────────


@router.get("/assets/{crawl_id}")
async def asset_inventory(
    request: Request,
    crawl_id: str,
    asset_type: Optional[str] = Query(None, description="image | script | stylesheet"),
    external_only: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
):
    """Browse all assets discovered in a crawl."""
    db = _db(request)

    where = ["crawl_id = :cid"]
    params = {"cid": crawl_id, "offset": (page - 1) * per_page, "limit": per_page}

    if asset_type:
        where.append("asset_type = :atype")
        params["atype"] = asset_type
    if external_only:
        where.append("is_external = 1")

    where_sql = " AND ".join(where)

    async with db.get_session() as session:
        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM assets WHERE {where_sql}"),
            {k: v for k, v in params.items() if k not in ("offset", "limit")},
        )
        total = count_result.scalar() or 0

        rows_result = await session.execute(text(f"""
            SELECT id, page_id, url, asset_type, alt_text, is_external, loading, attributes
            FROM assets
            WHERE {where_sql}
            ORDER BY asset_type, url
            LIMIT :limit OFFSET :offset
        """), params)
        rows = [dict(r._mapping) for r in rows_result.fetchall()]

        # Summary by type
        summary_result = await session.execute(text("""
            SELECT
                asset_type,
                COUNT(*) as count,
                COUNT(CASE WHEN is_external = 1 THEN 1 END) as external_count
            FROM assets
            WHERE crawl_id = :cid
            GROUP BY asset_type
            ORDER BY count DESC
        """), {"cid": crawl_id})
        summary = [dict(r._mapping) for r in summary_result.fetchall()]

    # Parse JSON attributes
    for r in rows:
        if isinstance(r.get('attributes'), str):
            try:
                r['attributes'] = json.loads(r['attributes'])
            except (json.JSONDecodeError, TypeError):
                pass

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "summary": summary,
        "assets": rows,
    }


# ── Link Analysis ────────────────────────────────────────────


@router.get("/links/{crawl_id}")
async def link_analysis(
    request: Request,
    crawl_id: str,
    external_only: bool = Query(False),
    broken_only: bool = Query(False),
):
    """Link analysis with anchor text and context."""
    db = _db(request)

    where = ["crawl_id = :cid"]
    params = {"cid": crawl_id}
    if external_only:
        where.append("is_external = 1")
    if broken_only:
        where.append("is_broken = 1")
    where_sql = " AND ".join(where)

    async with db.get_session() as session:
        # Link summary
        summary_result = await session.execute(text("""
            SELECT
                COUNT(*) as total_links,
                COUNT(CASE WHEN is_external = 1 THEN 1 END) as external_links,
                COUNT(CASE WHEN is_broken = 1 THEN 1 END) as broken_links,
                COUNT(DISTINCT target_url) as unique_targets,
                COUNT(DISTINCT target_domain) as unique_domains
            FROM links WHERE crawl_id = :cid
        """), {"cid": crawl_id})
        summary = dict(summary_result.fetchone()._mapping)

        # Top linked domains
        domain_result = await session.execute(text("""
            SELECT target_domain, COUNT(*) as link_count
            FROM links
            WHERE crawl_id = :cid AND is_external = 1
            GROUP BY target_domain
            ORDER BY link_count DESC
            LIMIT 20
        """), {"cid": crawl_id})
        top_domains = [dict(r._mapping) for r in domain_result.fetchall()]

        # Links list
        rows_result = await session.execute(text(f"""
            SELECT id, source_page_id, target_url, target_domain, anchor_text,
                   is_external, is_broken, status_code, link_type
            FROM links
            WHERE {where_sql}
            ORDER BY target_domain, target_url
            LIMIT 500
        """), params)
        links = [dict(r._mapping) for r in rows_result.fetchall()]

    return {
        "crawl_id": crawl_id,
        "summary": summary,
        "top_external_domains": top_domains,
        "links": links,
    }


# ── Deep Page Detail ─────────────────────────────────────────


@router.get("/page/{page_id}")
async def deep_page_detail(request: Request, page_id: str):
    """Full deep extraction data for a single page."""
    db = _db(request)
    async with db.get_session() as session:
        result = await session.execute(text("""
            SELECT * FROM pages WHERE id = :id
        """), {"id": page_id})
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Page not found")

    data = dict(row._mapping)

    # Parse all JSON columns
    json_cols = [
        'headings', 'h2s', 'response_headers', 'meta_tags', 'og_data',
        'twitter_card', 'structured_data', 'technologies', 'emails_found',
        'phone_numbers', 'addresses_found', 'social_links', 'seo_issues',
        'seo_passes', 'top_words', 'hreflang',
    ]
    for col in json_cols:
        val = data.get(col)
        if isinstance(val, str):
            try:
                data[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass

    # Coerce datetimes
    for k in ('scraped_at', 'created_at'):
        v = data.get(k)
        if v is not None and not isinstance(v, str):
            data[k] = v.isoformat()

    return data


# ── Structured Data Viewer ───────────────────────────────────


@router.get("/structured-data/{crawl_id}")
async def structured_data_viewer(request: Request, crawl_id: str):
    """All JSON-LD structured data found across a crawl."""
    db = _db(request)
    async with db.get_session() as session:
        result = await session.execute(text("""
            SELECT url, domain, structured_data
            FROM pages
            WHERE crawl_id = :cid AND structured_data IS NOT NULL
        """), {"cid": crawl_id})
        rows = result.fetchall()

    schemas = []
    type_counts = {}
    for row in rows:
        sd = row[2]
        if isinstance(sd, str):
            try:
                sd = json.loads(sd)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(sd, list):
            for item in sd:
                if isinstance(item, dict):
                    schema_type = item.get('@type', 'Unknown')
                    type_counts[schema_type] = type_counts.get(schema_type, 0) + 1
                    schemas.append({
                        'url': row[0],
                        'domain': row[1],
                        'type': schema_type,
                        'data': item,
                    })

    return {
        "crawl_id": crawl_id,
        "total_schemas": len(schemas),
        "type_distribution": [{"type": t, "count": c} for t, c in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)],
        "schemas": schemas[:200],  # Cap at 200 to avoid massive responses
    }


# ── Endpoint Inventory ───────────────────────────────────────


@router.get("/endpoints/{crawl_id}")
async def endpoint_inventory(
    request: Request,
    crawl_id: str,
    host: Optional[str] = None,
    method: Optional[str] = None,
    param: Optional[str] = None,
    q: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
):
    """Normalized endpoint inventory derived from crawl links/forms."""
    db = _db(request)
    async with db.get_session() as session:
        result = await session.execute(text("""
            SELECT id, host, scheme, method, path, query_params, body_param_names, content_types, sources, first_seen_at, last_seen_at
            FROM endpoints
            WHERE crawl_id = :cid
            ORDER BY host, path, method
        """), {"cid": crawl_id})
        rows = [dict(r._mapping) for r in result.fetchall()]

    def _json_list(v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    normalized = []
    for row in rows:
        row["query_params"] = _json_list(row.get("query_params"))
        row["body_param_names"] = _json_list(row.get("body_param_names"))
        row["content_types"] = _json_list(row.get("content_types"))
        row["sources"] = _json_list(row.get("sources"))
        for key in ("first_seen_at", "last_seen_at"):
            if row.get(key) is not None and not isinstance(row[key], str):
                row[key] = row[key].isoformat()
        normalized.append(row)

    if host:
        normalized = [r for r in normalized if r.get("host") == host]
    if method:
        normalized = [r for r in normalized if (r.get("method") or "").upper() == method.upper()]
    if param:
        p = param.lower()
        normalized = [
            r for r in normalized
            if p in {str(x).lower() for x in r.get("query_params", []) + r.get("body_param_names", [])}
        ]
    if source:
        s = source.lower()
        normalized = [r for r in normalized if s in {str(x).lower() for x in r.get("sources", [])}]
    if q:
        ql = q.lower()
        normalized = [r for r in normalized if ql in f"{r.get('host','')}{r.get('path','')}".lower()]

    total = len(normalized)
    page = normalized[offset:offset + limit]

    return {
        "crawl_id": crawl_id,
        "total": total,
        "offset": offset,
        "limit": limit,
        "endpoints": page,
    }
