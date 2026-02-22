"""Ring buffer for real-time log streaming."""

import time
from collections import deque
from threading import Lock


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

    def get_since(self, index: int) -> list[dict]:
        with self._lock:
            return [entry for entry in self._buffer if entry["index"] >= index]

    def size(self) -> int:
        return self._index

    def recent(self, n: int = 50) -> list[dict]:
        with self._lock:
            return list(self._buffer)[-n:]
