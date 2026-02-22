"""Real-time metrics aggregation for dashboard."""

import time
from threading import Lock


class MetricsService:
    def __init__(self):
        self._lock = Lock()
        self._counters = {
            "pages_crawled": 0,
            "pages_failed": 0,
            "bytes_downloaded": 0,
            "security_findings": 0,
            "active_jobs": 0,
        }
        self._gauges = {
            "queue_depth": 0,
            "requests_per_sec": 0.0,
            "avg_response_time_ms": 0.0,
        }
        self._history: list[dict] = []

    def increment(self, counter: str, value: int = 1):
        with self._lock:
            if counter in self._counters:
                self._counters[counter] += value

    def set_gauge(self, gauge: str, value: float):
        with self._lock:
            self._gauges[gauge] = value

    def snapshot(self) -> dict:
        with self._lock:
            snap = {
                "timestamp": time.time(),
                **self._counters,
                **self._gauges,
            }
            self._history.append(snap)
            if len(self._history) > 3600:
                self._history = self._history[-3600:]
            return snap

    def history(self, minutes: int = 60) -> list[dict]:
        cutoff = time.time() - (minutes * 60)
        return [s for s in self._history if s["timestamp"] > cutoff]
