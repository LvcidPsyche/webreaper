"""HTML report generator for crawl results."""

from pathlib import Path
from typing import Optional
from datetime import datetime, timezone


async def generate_html_report(db_manager, crawl_id: Optional[str], output_path: Path):
    """Generate a self-contained HTML report from database."""

    # Fetch crawl data
    crawls = await db_manager.get_crawl_stats()

    if crawl_id:
        crawl = next((c for c in crawls if str(c['id']).startswith(crawl_id)), None)
        if not crawl:
            raise ValueError(f"Crawl ID not found: {crawl_id}")
        selected_crawls = [crawl]
    else:
        selected_crawls = crawls[:5]  # Most recent 5

    # Fetch pages and findings for selected crawls
    async with db_manager.get_session() as session:
        from sqlalchemy import text

        crawl_ids_sql = ", ".join(f"'{str(c['id'])}'" for c in selected_crawls)

        pages_result = await session.execute(text(f"""
            SELECT url, title, status_code, word_count, depth, domain, response_time_ms
            FROM pages
            WHERE crawl_id IN ({crawl_ids_sql})
            ORDER BY scraped_at DESC
            LIMIT 1000
        """))
        pages = [dict(r._mapping) for r in pages_result.fetchall()]

        findings_result = await session.execute(text(f"""
            SELECT finding_type, severity, url, evidence, remediation
            FROM security_findings
            WHERE crawl_id IN ({crawl_ids_sql}) AND false_positive = FALSE
            ORDER BY
                CASE severity
                    WHEN 'Critical' THEN 1
                    WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3
                    WHEN 'Low' THEN 4
                    ELSE 5
                END
            LIMIT 500
        """))
        findings = [dict(r._mapping) for r in findings_result.fetchall()]

    html = _build_html(selected_crawls, pages, findings)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def _sev_badge(sev: str) -> str:
    colors = {
        "Critical": "#dc2626",
        "High": "#ea580c",
        "Medium": "#d97706",
        "Low": "#65a30d",
        "Info": "#6b7280",
    }
    c = colors.get(sev, "#6b7280")
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{sev}</span>'


def _build_html(crawls, pages, findings) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Crawl summary rows
    crawl_rows = ""
    for c in crawls:
        status_color = "#16a34a" if c['status'] == 'completed' else "#d97706"
        rps = f"{c['requests_per_sec']:.1f}" if c['requests_per_sec'] else "—"
        started = str(c['started_at'])[:16] if c['started_at'] else "—"
        crawl_rows += f"""
        <tr>
            <td style="font-family:monospace">{str(c['id'])[:8]}</td>
            <td><a href="{c['target_url']}" target="_blank">{str(c['target_url'])[:50]}</a></td>
            <td style="color:{status_color}">{c['status']}</td>
            <td>{c['pages_crawled'] or 0}</td>
            <td>{c['pages_failed'] or 0}</td>
            <td>{rps}</td>
            <td>{c['genre'] or '—'}</td>
            <td style="color:#9ca3af">{started}</td>
        </tr>"""

    # Page rows
    page_rows = ""
    for p in pages[:200]:
        status = p.get('status_code', 0)
        sc = "#16a34a" if status == 200 else ("#d97706" if status in (301, 302) else "#dc2626")
        page_rows += f"""
        <tr>
            <td><a href="{p['url']}" target="_blank">{str(p['url'])[:60]}</a></td>
            <td style="color:{sc}">{status}</td>
            <td>{p.get('title') or '—'}</td>
            <td>{p.get('word_count') or 0}</td>
            <td>{p.get('depth') or 0}</td>
            <td>{p.get('response_time_ms') or 0}ms</td>
        </tr>"""

    # Findings rows
    finding_rows = ""
    for f in findings:
        finding_rows += f"""
        <tr>
            <td>{f['finding_type']}</td>
            <td>{_sev_badge(f['severity'])}</td>
            <td><a href="{f['url']}" target="_blank">{str(f['url'])[:50]}</a></td>
            <td style="font-family:monospace;font-size:12px">{(f.get('evidence') or '')[:80]}</td>
            <td style="color:#6b7280;font-size:12px">{f.get('remediation') or '—'}</td>
        </tr>"""

    # Severity summary
    from collections import Counter
    sev_count = Counter(f['severity'] for f in findings)
    sev_pills = " ".join(
        f'<span style="margin-right:8px">{_sev_badge(s)} {n}</span>'
        for s, n in [("Critical", sev_count.get("Critical", 0)),
                     ("High", sev_count.get("High", 0)),
                     ("Medium", sev_count.get("Medium", 0)),
                     ("Low", sev_count.get("Low", 0))]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WebReaper Report — {now}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0 }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px }}
  h1 {{ color: #38bdf8; margin-bottom: 4px; font-size: 24px }}
  h2 {{ color: #94a3b8; margin: 32px 0 12px; font-size: 16px; text-transform: uppercase; letter-spacing: 1px }}
  .meta {{ color: #64748b; font-size: 13px; margin-bottom: 32px }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 16px }}
  th {{ background: #1e293b; color: #94a3b8; text-align: left; padding: 8px 12px; font-weight: 500; border-bottom: 1px solid #334155 }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; vertical-align: top }}
  tr:hover td {{ background: #1e293b }}
  a {{ color: #38bdf8; text-decoration: none }}
  a:hover {{ text-decoration: underline }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 12px }}
  .sev-summary {{ margin-bottom: 12px }}
  .stat {{ display: inline-block; margin-right: 24px; text-align: center }}
  .stat-value {{ font-size: 28px; font-weight: bold; color: #38bdf8 }}
  .stat-label {{ font-size: 12px; color: #64748b; text-transform: uppercase }}
</style>
</head>
<body>
<h1>🕷️ WebReaper Report</h1>
<p class="meta">Generated {now} &nbsp;|&nbsp; {len(crawls)} crawl(s) &nbsp;|&nbsp; {len(pages)} pages &nbsp;|&nbsp; {len(findings)} findings</p>

<div class="card">
  <div class="stat"><div class="stat-value">{len(pages)}</div><div class="stat-label">Pages</div></div>
  <div class="stat"><div class="stat-value">{len(findings)}</div><div class="stat-label">Findings</div></div>
  <div class="stat"><div class="stat-value">{sum(c['pages_crawled'] or 0 for c in crawls)}</div><div class="stat-label">Total Crawled</div></div>
  <div class="stat"><div class="stat-value">{len(crawls)}</div><div class="stat-label">Crawls</div></div>
</div>

<h2>Crawl History</h2>
<table>
<thead><tr><th>ID</th><th>URL</th><th>Status</th><th>Pages</th><th>Failed</th><th>Req/s</th><th>Genre</th><th>Started</th></tr></thead>
<tbody>{crawl_rows}</tbody>
</table>

<h2>Security Findings ({len(findings)})</h2>
<div class="sev-summary">{sev_pills}</div>
<table>
<thead><tr><th>Type</th><th>Severity</th><th>URL</th><th>Evidence</th><th>Remediation</th></tr></thead>
<tbody>{finding_rows if finding_rows else '<tr><td colspan="5" style="color:#64748b">No findings</td></tr>'}</tbody>
</table>

<h2>Pages ({len(pages)})</h2>
<table>
<thead><tr><th>URL</th><th>Status</th><th>Title</th><th>Words</th><th>Depth</th><th>Response</th></tr></thead>
<tbody>{page_rows if page_rows else '<tr><td colspan="6" style="color:#64748b">No pages</td></tr>'}</tbody>
</table>

<p style="color:#334155;font-size:12px;margin-top:32px">Generated by WebReaper</p>
</body>
</html>"""
