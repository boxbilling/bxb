"""Simple in-memory sliding-window rate limiter."""

import time
from collections import defaultdict
from threading import Lock


class RateLimiter:
    """In-memory sliding-window rate limiter keyed by an arbitrary string.

    Tracks request timestamps in a rolling window and rejects calls that
    exceed the configured limit.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        """Return True if the request is within the rate limit, False otherwise."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._requests[key]
            # Prune expired entries
            self._requests[key] = [t for t in timestamps if t > cutoff]
            timestamps = self._requests[key]

            if len(timestamps) >= self.max_requests:
                return False

            timestamps.append(now)
            return True

    def reset(self) -> None:
        """Clear all tracked state (useful for testing)."""
        with self._lock:
            self._requests.clear()
