"""Tests for proxy service control/history APIs."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routes import proxy
from webreaper.proxy.service import ProxyService


def _make_app(db):
    app = FastAPI()
    app.include_router(proxy.router, prefix="/api/proxy")
    app.state.db = db
    app.state.proxy_service = ProxyService()
    return app


def test_proxy_session_lifecycle_and_history(temp_db):
    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        start = client.post("/api/proxy/sessions", json={
            "workspace_id": None,
            "name": "Local Proxy",
            "host": "127.0.0.1",
            "port": 8081,
            "intercept_enabled": False,
            "body_capture_limit_kb": 1,
        })
        assert start.status_code == 200
        sess = start.json()
        sid = sess["id"]
        assert sess["status"] == "running"

        toggle = client.post(f"/api/proxy/sessions/{sid}/intercept", json={"enabled": True})
        assert toggle.status_code == 200
        assert toggle.json()["intercept_enabled"] is True

        capture = client.post("/api/proxy/capture", json={
            "session_id": sid,
            "source": "proxy",
            "request": {
                "method": "POST",
                "url": "https://example.com/api/login?next=/app",
                "headers": {"content-type": "application/json"},
                "body": "x" * 5000,
            },
            "response": {
                "status": 200,
                "headers": {"content-type": "application/json"},
                "body": '{"ok":true}',
                "duration_ms": 123,
            },
            "tags": ["auth", "login"],
            "intercept_state": "forwarded",
        })
        assert capture.status_code == 200
        tx_id = capture.json()["id"]
        assert tx_id

        queue = client.get(f"/api/proxy/intercept/queue?session_id={sid}")
        assert queue.status_code == 200
        items = queue.json()["items"]
        assert len(items) >= 1
        assert any(item["id"] == tx_id for item in items)

        edit = client.post(f"/api/proxy/intercept/{tx_id}/edit", json={
            "request": {"body": "{\"edited\":true}"},
            "tags": ["edited"],
        })
        assert edit.status_code == 200
        assert edit.json()["intercept_state"] == "edited"

        capture2 = client.post("/api/proxy/capture", json={
            "session_id": sid,
            "source": "proxy",
            "request": {
                "method": "GET",
                "url": "https://example.com/api/me",
                "headers": {},
            },
            "response": {"status": 200, "headers": {}, "body": "ok", "duration_ms": 10},
            "intercept_state": "none",
        })
        assert capture2.status_code == 200
        tx2 = capture2.json()["id"]

        forward = client.post(f"/api/proxy/intercept/{tx2}/forward")
        assert forward.status_code == 200
        assert forward.json()["intercept_state"] == "forwarded"

        history = client.get(f"/api/proxy/history?session_id={sid}&method=POST&host=example.com")
        assert history.status_code == 200
        data = history.json()
        assert data["total"] >= 1
        tx = data["transactions"][0]
        assert tx["method"] == "POST"
        assert tx["host"] == "example.com"
        assert tx["intercept_state"] == "edited"
        assert tx["truncated"] in (True, 1)

        stop = client.post(f"/api/proxy/sessions/{sid}/stop")
        assert stop.status_code == 200
        assert stop.json()["status"] == "stopped"
