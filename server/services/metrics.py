"""Real-time metrics aggregation for dashboard."""

import time
from threading import Lock


class MetricsService:
    def __init__(self):
        self._lock = Lock()
        self._start_time = time.time()
        self._counters = {
            "pages_crawled": 0,
            "pages_failed": 0,
            "bytes_downloaded": 0,
            "security_findings": 0,
            "active_jobs": 0,
        }
        self._gauges = {
            "queue_depth": 0,
            "requests_per_second": 0.0,
            "avg_response_time_ms": 0.0,
        }
        self._status_codes: dict[str, int] = {}
        self._history: list[dict] = []

    def increment(self, counter: str, value: int = 1):
        with self._lock:
            if counter in self._counters:
                self._counters[counter] += value

    def increment_status(self, code: int):
        """Track HTTP status code distribution for dashboard donut chart."""
        bucket = f"{code // 100}xx"
        with self._lock:
            self._status_codes[bucket] = self._status_codes.get(bucket, 0) + 1

    def set_gauge(self, gauge: str, value: float):
        # Accept legacy requests_per_sec name
        if gauge == "requests_per_sec":
            gauge = "requests_per_second"
        with self._lock:
            self._gauges[gauge] = value

    def snapshot(self) -> dict:
        with self._lock:
            pages_crawled = self._counters["pages_crawled"]
            pages_failed = self._counters["pages_failed"]
            total = pages_crawled + pages_failed
            error_rate = round((pages_failed / total * 100) if total > 0 else 0.0, 2)

            throughput_history = [
                {
                    "timestamp": s["timestamp"],
                    "pages_per_second": s.get("requests_per_second", 0.0),
                }
                for s in self._history[-20:]
            ]

            snap = {
                "timestamp": time.time(),
                "pages_crawled": pages_crawled,
                "security_findings": self._counters["security_findings"],
                "active_jobs": self._counters["active_jobs"],
                "queue_depth": self._gauges["queue_depth"],
                "requests_per_second": self._gauges["requests_per_second"],
                "error_rate": error_rate,
                "status_codes": dict(self._status_codes),
                "throughput_history": throughput_history,
                "uptime_seconds": int(time.time() - self._start_time),
            }
            self._history.append(snap)
            if len(self._history) > 3600:
                self._history = self._history[-3600:]
            return snap

    def history(self, minutes: int = 60) -> list[dict]:
        cutoff = time.time() - (minutes * 60)
        return [s for s in self._history if s["timestamp"] > cutoff]
