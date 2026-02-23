"""Ring buffer for real-time log streaming.

Entries are also forwarded to structlog so they persist to disk.
"""

import logging
import time
from collections import deque
from threading import Lock

_logger = logging.getLogger("webreaper.log_buffer")


class LogBuffer:
    def __init__(self, max_size: int = 1000):
        self._buffer: deque = deque(maxlen=max_size)
        self._lock = Lock()
        self._index = 0

    def add(self, level: str, message: str, source: str = "system"):
        with self._lock:
            self._buffer.append({
                "index": self._index,
                "timestamp": time.time(),
                "level": level,
                "message": message,
                "source": source,
            })
            self._index += 1

        # Forward to structured log so entries survive server restarts
        log_fn = getattr(_logger, level.lower(), _logger.info)
        log_fn("[%s] %s", source, message)

    def get_since(self, index: int) -> list[dict]:
        with self._lock:
            return [entry for entry in self._buffer if entry["index"] >= index]

    def size(self) -> int:
        return self._index

    def recent(self, n: int = 50) -> list[dict]:
        with self._lock:
            return list(self._buffer)[-n:]
