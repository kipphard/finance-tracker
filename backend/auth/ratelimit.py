"""Tiny in-process, per-key sliding-window rate limiter.

The app runs as a single uvicorn process, so module-level state is consistent across requests
(no Redis needed). Used to throttle public demo-sandbox creation per client IP.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request


def client_ip(request: Request) -> str:
    """Best-effort real client IP behind Cloudflare / nginx."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max = max_events
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Record an event for `key`; return False if it exceeds max_events within the window."""
        now = time.monotonic()
        dq = self._hits[key]
        cutoff = now - self.window
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= self.max:
            return False
        dq.append(now)
        return True
