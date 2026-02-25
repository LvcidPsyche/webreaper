"""Tests for repeater APIs and decoder utilities."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

from server.routes import repeater
from webreaper.repeater.service import RepeaterService


class _FakeAsyncClient:
    calls = 0

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, headers=None, content=None):
        _FakeAsyncClient.calls += 1
        n = _FakeAsyncClient.calls
        req = httpx.Request(method, url, headers=headers or {}, content=(content or "").encode() if isinstance(content, str) else content)
        body = f'{{"run":{n}}}'
        return httpx.Response(
            200 if n == 1 else 201,
            request=req,
            headers={"content-type": "application/json", "x-run": str(n)},
            content=body.encode(),
        )


def _make_app(db):
    app = FastAPI()
    app.include_router(repeater.router, prefix="/api/repeater")
    app.state.db = db
    app.state.repeater_service = RepeaterService()
    return app


def test_repeater_tab_lifecycle_send_and_diff(temp_db, monkeypatch):
    monkeypatch.setattr("webreaper.repeater.service.httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.calls = 0

    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        create = client.post("/api/repeater/tabs", json={
            "name": "Login replay",
            "method": "POST",
            "url": "https://example.com/api/login",
            "headers": {"content-type": "application/json"},
            "body": '{"email":"a@b.com"}',
        })
        assert create.status_code == 200, create.text
        tab = create.json()
        tab_id = tab["id"]
        assert tab["method"] == "POST"

        upd = client.put(f"/api/repeater/tabs/{tab_id}", json={"name": "Login replay v2"})
        assert upd.status_code == 200
        assert upd.json()["name"] == "Login replay v2"

        first = client.post(f"/api/repeater/tabs/{tab_id}/send", json={"timeout_ms": 3000, "follow_redirects": True})
        assert first.status_code == 200, first.text
        first_json = first.json()
        assert first_json["run"]["status"] == "success"
        assert first_json["transaction"]["source"] == "repeater"
        assert first_json["run"]["diff_summary"]["baseline"] is True

        second = client.post(f"/api/repeater/tabs/{tab_id}/send", json={"timeout_ms": 3000, "follow_redirects": False})
        assert second.status_code == 200
        second_json = second.json()
        assert second_json["run"]["status"] == "success"
        assert second_json["run"]["diff_summary"]["baseline"] is False
        assert second_json["run"]["diff_summary"]["changed"] is True
        assert second_json["run"]["diff_summary"]["status_changed"] is True

        runs = client.get(f"/api/repeater/tabs/{tab_id}/runs")
        assert runs.status_code == 200
        data = runs.json()
        assert len(data) == 2
        assert data[0]["transaction"]["response_status"] in (200, 201)


def test_send_to_repeater_from_transaction(temp_db):
    tx_id = __import__("asyncio").run(temp_db.save_http_transaction({
        "workspace_id": None,
        "source": "proxy",
        "method": "GET",
        "scheme": "https",
        "host": "example.com",
        "path": "/search",
        "query": "q=test",
        "url": "https://example.com/search?q=test",
        "request_headers": {"accept": "*/*"},
        "request_body": None,
        "response_status": 200,
        "response_headers": {"content-type": "text/html"},
        "response_body": "ok",
        "duration_ms": 25,
        "tags": ["proxy"],
        "intercept_state": "none",
        "truncated": False,
    }))

    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        res = client.post("/api/repeater/send-to-repeater", json={"transaction_id": tx_id})
        assert res.status_code == 200, res.text
        tab = res.json()
        assert tab["source_transaction_id"] == tx_id
        assert tab["url"] == "https://example.com/search?q=test"
        assert tab["method"] == "GET"


def test_repeater_decoder_endpoints(temp_db):
    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        b64 = client.post("/api/repeater/decode", json={"operation": "base64_encode", "input": "hi"})
        assert b64.status_code == 200
        assert b64.json()["output"] == "aGk="

        hex_dec = client.post("/api/repeater/decode", json={"operation": "hex_decode", "input": "6869"})
        assert hex_dec.status_code == 200
        assert hex_dec.json()["output"] == "hi"

        jwt = "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxMjMifQ."
        parsed = client.post("/api/repeater/decode", json={"operation": "jwt_parse", "input": jwt})
        assert parsed.status_code == 200
        body = parsed.json()
        assert body["ok"] is True
        assert body["output"]["payload"]["sub"] == "123"

        bad = client.post("/api/repeater/decode", json={"operation": "hex_decode", "input": "zz"})
        assert bad.status_code == 200
        assert bad.json()["ok"] is False
