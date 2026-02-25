"""Tests for workspace routes and scope evaluation."""

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

