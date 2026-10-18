"""In-memory rate limiter for authentication endpoints."""

import time
from collections import defaultdict
from threading import Lock


class InMemoryRateLimiter:
    """Thread-safe sliding-window rate limiter keyed by client identifier."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.lock = Lock()

    def is_allowed(self, client_id: str) -> bool:
        """Check whether a client is allowed to proceed and record the attempt.

        Args:
            client_id: Unique client key, such as client IP address.

        Returns:
            bool: True if under the limit, False if rate limited.
        """
        now = time.time()
        cutoff = now - self.window_seconds
        with self.lock:
            timestamps = self.requests[client_id]
            # Prune timestamps older than window
            valid_timestamps = [ts for ts in timestamps if ts > cutoff]
            if len(valid_timestamps) >= self.max_requests:
                self.requests[client_id] = valid_timestamps
                return False
            valid_timestamps.append(now)
            self.requests[client_id] = valid_timestamps
            return True

    def reset(self) -> None:
        """Clear all recorded request history (useful during testing)."""
        with self.lock:
            self.requests.clear()


# Global limiter for login endpoint (10 requests/minute per IP)
login_rate_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)


def get_login_rate_limiter() -> InMemoryRateLimiter:
    """Return the singleton login rate limiter instance."""
    return login_rate_limiter
