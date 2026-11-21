import time
from collections import deque


class SlidingWindowLimiter:
    """In-memory brake: at most `limit` events per `window_s` seconds (per process)."""

    def __init__(self, limit: int, window_s: float) -> None:
        self.limit, self.window_s = limit, window_s
        self._events: deque[float] = deque()

    def allow(self) -> bool:
        now = time.monotonic()
        while self._events and self._events[0] < now - self.window_s:
            self._events.popleft()
        if len(self._events) >= self.limit:
            return False
        self._events.append(now)
        return True
