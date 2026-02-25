"""Tests for SSE stream routes and event envelopes."""

import json
from types import SimpleNamespace

import pytest

from server.routes import stream


class _DummyMetrics:
    def snapshot(self):
        return {
            "pages_crawled": 12,
            "security_findings": 1,
            "active_jobs": 1,
            "queue_depth": 5,
            "requests_per_second": 4.2,
            "error_rate": 0.0,
            "status_codes": {"2xx": 12},
            "throughput_history": [],
            "uptime_seconds": 30,
        }


class _DummyLogBuffer:
    def __init__(self):
        self._entries = [
            {
                "id": "log-1",
                "level": "info",
                "source": "test",
                "message": "hello",
                "timestamp": "2026-02-25T00:00:00Z",
            }
        ]
        self._served = False

    def size(self):
        return 0

    def get_since(self, index):
        if index == 0 and not self._served:
            self._served = True
            return self._entries
        return []


class _DummyRequest:
    def __init__(self):
        self.app = SimpleNamespace(state=SimpleNamespace())
        self.app.state.log_buffer = _DummyLogBuffer()
        self.app.state.metrics = _DummyMetrics()
        self.app.state.active_jobs = {
        "job-1": SimpleNamespace(
            stats={
                "pages_crawled": 3,
                "pages_failed": 1,
                "queue_size": 9,
                "current_url": "https://example.com/a",
            }
        )
        }
        self._disconnect_checks = 0

    async def is_disconnected(self):
        # False on first check so the generator yields one event, then True
        # on subsequent loop checks if iteration continues.
        self._disconnect_checks += 1
        return self._disconnect_checks > 1


@pytest.fixture
def sse_passthrough(monkeypatch):
    """Patch EventSourceResponse so route handlers return the raw generator."""
    monkeypatch.setattr(stream, "EventSourceResponse", lambda gen: gen)
    return monkeypatch


async def _first_event_dict(gen) -> tuple[str, dict]:
    item = await anext(gen)
    return item["event"], json.loads(item["data"])


@pytest.mark.asyncio
async def test_stream_metrics_uses_named_event_and_envelope(sse_passthrough):
    req = _DummyRequest()
    gen = await stream.stream_metrics(req)
    event_name, envelope = await _first_event_dict(gen)

    assert event_name == "metrics"
    assert envelope["type"] == "metrics"
    assert "ts" in envelope
    assert envelope["payload"]["pages_crawled"] == 12


@pytest.mark.asyncio
async def test_stream_logs_uses_named_event_and_envelope(sse_passthrough):
    req = _DummyRequest()
    gen = await stream.stream_logs(req)
    event_name, envelope = await _first_event_dict(gen)

    assert event_name == "log"
    assert envelope["type"] == "log"
    assert envelope["payload"]["message"] == "hello"


@pytest.mark.asyncio
async def test_stream_job_progress_uses_named_event_and_envelope(sse_passthrough):
    req = _DummyRequest()
    gen = await stream.stream_job(req, "job-1")
    event_name, envelope = await _first_event_dict(gen)

    assert event_name == "progress"
    assert envelope["type"] == "progress"
    assert envelope["payload"]["job_id"] == "job-1"
    assert envelope["payload"]["queue_size"] == 9


@pytest.mark.asyncio
async def test_stream_job_not_found_emits_error_event(sse_passthrough):
    req = _DummyRequest()
    gen = await stream.stream_job(req, "missing-job")
    event_name, envelope = await _first_event_dict(gen)

    assert event_name == "error"
    assert envelope["type"] == "error"
    assert envelope["payload"]["error"] == "Job not found"
    assert envelope["payload"]["job_id"] == "missing-job"
