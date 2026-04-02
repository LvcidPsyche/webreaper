"""Tests for workspace routes and scope evaluation."""

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routes import workspaces
from webreaper.workspaces.scope import evaluate_scope


def test_scope_evaluator_include_exclude_rules():
    rules = [
        {"id": "inc1", "mode": "include", "type": "host_glob", "value": "*.example.com"},
        {"id": "inc2", "mode": "include", "type": "host", "value": "example.com"},
        {"id": "exc1", "mode": "exclude", "type": "path_prefix", "value": "/admin"},
    ]
    assert evaluate_scope("https://example.com/docs", rules).allowed is True
    denied = evaluate_scope("https://app.example.com/admin", rules)
    assert denied.allowed is False
    assert denied.reason == "excluded"
    outside = evaluate_scope("https://other.com", rules)
    assert outside.allowed is False
    assert outside.reason == "no_include_match"


def _make_app(db):
    app = FastAPI()
    app.include_router(workspaces.router, prefix="/api/workspaces")
    app.state.db = db
    return app


def test_workspace_crud_and_scope_check(temp_db):
    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        create = client.post("/api/workspaces", json={
            "name": "Acme",
            "scope_rules": [
                {"id": "host1", "mode": "include", "type": "host", "value": "example.com"},
                {"id": "exc", "mode": "exclude", "type": "path_prefix", "value": "/private"},
            ],
            "tags": ["prod"],
            "risk_policy": {"allow_active_scan": False},
        })
        assert create.status_code == 200
        ws = create.json()
        ws_id = ws["id"]

        get_resp = client.get(f"/api/workspaces/{ws_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Acme"

        check_ok = client.post(f"/api/workspaces/{ws_id}/scope/check", json={"url": "https://example.com/public"})
        assert check_ok.status_code == 200
        assert check_ok.json()["allowed"] is True

        check_block = client.post(f"/api/workspaces/{ws_id}/scope/check", json={"url": "https://example.com/private"})
        assert check_block.status_code == 200
        assert check_block.json()["allowed"] is False

        upd = client.put(f"/api/workspaces/{ws_id}", json={"tags": ["prod", "recon"], "archived": True})
        assert upd.status_code == 200
        assert upd.json()["archived"] is True

        all_resp = client.get("/api/workspaces?include_archived=true")
        assert all_resp.status_code == 200
        assert any(item["id"] == ws_id for item in all_resp.json())


def test_workspace_library_can_auto_file_override_and_export(temp_db):
    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        create = client.post("/api/workspaces", json={"name": "Library WS", "tags": ["scraping"]})
        assert create.status_code == 200
        workspace_id = create.json()["id"]

        async def _seed():
            crawl_id = await temp_db.create_crawl(
                target_url="https://example.com",
                workspace_id=workspace_id,
                genre="research",
            )
            docs_page_id = await temp_db.save_page(
                crawl_id=crawl_id,
                workspace_id=workspace_id,
                url="https://example.com/docs/api",
                domain="example.com",
                path="/docs/api",
                status_code=200,
                content_type="text/html",
                response_time_ms=45,
                title="API Reference",
                meta_description="API docs for the platform",
                content_text="Reference docs",
                word_count=900,
                headings=[{"level": 1, "text": "API Reference"}],
                headings_count=1,
                images_count=0,
                links_count=5,
                external_links_count=0,
                h1="API Reference",
                h2s=["Authentication"],
                response_headers={},
                depth=1,
            )
            pricing_page_id = await temp_db.save_page(
                crawl_id=crawl_id,
                workspace_id=workspace_id,
                url="https://example.com/pricing",
                domain="example.com",
                path="/pricing",
                status_code=200,
                content_type="text/html",
                response_time_ms=55,
                title="Pricing",
                meta_description="Plans and pricing",
                content_text="Pricing details",
                word_count=420,
                headings=[{"level": 1, "text": "Pricing"}],
                headings_count=1,
                images_count=0,
                links_count=3,
                external_links_count=0,
                h1="Pricing",
                h2s=["Enterprise"],
                response_headers={},
                depth=1,
            )
            contact_page_id = await temp_db.save_page(
                crawl_id=crawl_id,
                workspace_id=workspace_id,
                url="https://example.com/contact",
                domain="example.com",
                path="/contact",
                status_code=200,
                content_type="text/html",
                response_time_ms=40,
                title="Contact Us",
                meta_description="Get in touch",
                content_text="Talk to sales",
                word_count=180,
                headings=[{"level": 1, "text": "Contact"}],
                headings_count=1,
                images_count=0,
                links_count=1,
                external_links_count=0,
                h1="Contact",
                h2s=[],
                response_headers={},
                depth=1,
                emails_found=["team@example.com"],
                phone_numbers=["+1-555-0000"],
            )
            return docs_page_id, pricing_page_id, contact_page_id

        docs_page_id, pricing_page_id, contact_page_id = asyncio.run(_seed())

        summary = client.get(f"/api/workspaces/{workspace_id}/library/summary")
        assert summary.status_code == 200
        summary_payload = summary.json()
        assert summary_payload["summary"]["total_pages"] == 3
        assert summary_payload["summary"]["filed_pages"] == 0

        docs_items = client.get(f"/api/workspaces/{workspace_id}/library/items?category=documentation")
        assert docs_items.status_code == 200
        docs_payload = docs_items.json()
        assert docs_payload["total"] == 1
        assert docs_payload["items"][0]["page_id"] == docs_page_id

        manual = client.put(
            f"/api/workspaces/{workspace_id}/library/pages/{pricing_page_id}",
            json={
                "folder": "example.com/accounts/high-value",
                "category": "lead",
                "labels": ["priority:high", "owner:sales"],
                "starred": True,
                "notes": "Target this company page for outbound research",
            },
        )
        assert manual.status_code == 200
        manual_item = manual.json()["item"]
        assert manual_item["category"] == "lead"
        assert manual_item["folder"] == "example.com/accounts/high-value"
        assert manual_item["starred"] is True

        auto_file = client.post(f"/api/workspaces/{workspace_id}/library/auto-file", json={})
        assert auto_file.status_code == 200
        auto_file_payload = auto_file.json()
        assert auto_file_payload["created"] == 2
        assert auto_file_payload["skipped"] == 1

        contact_items = client.get(f"/api/workspaces/{workspace_id}/library/items?category=contact")
        assert contact_items.status_code == 200
        contact_payload = contact_items.json()
        assert contact_payload["total"] == 1
        assert contact_payload["items"][0]["page_id"] == contact_page_id

        lead_items = client.get(f"/api/workspaces/{workspace_id}/library/items?folder=example.com/accounts/high-value")
        assert lead_items.status_code == 200
        lead_payload = lead_items.json()
        assert lead_payload["total"] == 1
        assert lead_payload["items"][0]["page_id"] == pricing_page_id
        assert "priority:high" in lead_payload["items"][0]["labels"]

        summary_after = client.get(f"/api/workspaces/{workspace_id}/library/summary")
        assert summary_after.status_code == 200
        summary_after_payload = summary_after.json()
        assert summary_after_payload["summary"]["filed_pages"] == 3
        assert summary_after_payload["summary"]["starred_pages"] == 1
        assert any(item["category"] == "lead" for item in summary_after_payload["summary"]["by_category"])

        export_json = client.get(f"/api/workspaces/{workspace_id}/library/export?fmt=json")
        assert export_json.status_code == 200
        assert '"category": "lead"' in export_json.text
        assert '"page_id": "{}"'.format(pricing_page_id) in export_json.text

        export_csv = client.get(f"/api/workspaces/{workspace_id}/library/export?fmt=csv")
        assert export_csv.status_code == 200
        assert "page_id,url,domain,title,status_code,category,folder,labels,starred,word_count,content_family,scraped_at" in export_csv.text
        assert "example.com/accounts/high-value" in export_csv.text
