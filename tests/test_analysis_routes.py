"""Tests for analysis API routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routes import analysis


def _make_app(db):
    app = FastAPI()
    app.include_router(analysis.router, prefix="/api/analysis")
    app.state.db = db
    return app


def test_endpoint_inventory_route_filters(temp_db):
    # Seed endpoint inventory via DB helper
    import asyncio

    async def _seed():
        crawl_id = await temp_db.create_crawl(target_url="https://example.com")
        page_id = await temp_db.save_page(
            crawl_id=crawl_id,
            url="https://example.com",
            domain="example.com",
            path="/",
            status_code=200,
            response_time_ms=10,
            title="Home",
            meta_description=None,
            content_text="ok",
            word_count=1,
            headings=[],
            headings_count=0,
            images_count=0,
            links_count=0,
            external_links_count=0,
            h1=None,
            h2s=[],
            response_headers={},
            depth=0,
        )
        await temp_db.upsert_endpoints(
            crawl_id=crawl_id,
            page_id=page_id,
            endpoints=temp_db.derive_endpoints_from_page(
                "https://example.com",
                forms=[{"action": "https://example.com/api/login", "method": "POST", "fields": [{"name": "email"}]}],
                links=[{"url": "https://example.com/users?page=2"}],
            ),
        )
        return crawl_id

    crawl_id = asyncio.run(_seed())

    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get(f"/api/analysis/endpoints/{crawl_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2

        filtered = client.get(f"/api/analysis/endpoints/{crawl_id}?method=POST&param=email")
        assert filtered.status_code == 200
        endpoints = filtered.json()["endpoints"]
        assert len(endpoints) >= 1
        assert all(e["method"] == "POST" for e in endpoints)
