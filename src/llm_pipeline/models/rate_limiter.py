"""Sliding-window rate limiter for LLM API input tokens."""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter that tracks input tokens over a 60-second window.

    Call acquire() before each LLM call to block until the window has capacity.
    Call record() after each call with the actual input token count.
    """

    def __init__(self, max_tokens_per_minute: int) -> None:
        self.max_tokens = max_tokens_per_minute
        self._window: list[tuple[float, int]] = []  # (monotonic_ts, input_tokens)
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        """Remove entries older than 60 seconds. Caller must hold _lock."""
        cutoff = now - 60.0
        # Find first entry that's still in the window
        i = 0
        while i < len(self._window) and self._window[i][0] < cutoff:
            i += 1
        if i:
            del self._window[:i]

    def _window_total(self) -> int:
        """Sum of tokens in the current window. Caller must hold _lock."""
        return sum(tokens for _, tokens in self._window)

    def acquire(self) -> None:
        """Block until the current window has room for another call.

        No-op when max_tokens is 0 (disabled) or in dry-run mode.
        """
        if self.max_tokens <= 0:
            return

        from llm_pipeline.config import settings

        if settings.llm_provider == "dry-run":
            return

        while True:
            with self._lock:
                now = time.monotonic()
                self._prune(now)
                total = self._window_total()

                if total < self.max_tokens:
                    return  # capacity available

                # Sleep until the oldest entry expires
                if self._window:
                    oldest_ts = self._window[0][0]
                    sleep_seconds = (oldest_ts + 60.0) - now + 0.5
                else:
                    sleep_seconds = 1.0

            # Sleep outside the lock
            sleep_seconds = max(sleep_seconds, 0.1)
            logger.info(
                "Rate limiter: sleeping %.1fs (window: %d/%d tokens)",
                sleep_seconds,
                total,
                self.max_tokens,
            )
            time.sleep(sleep_seconds)

    def record(self, input_tokens: int) -> None:
        """Record tokens used after a successful call."""
        if input_tokens <= 0:
            return
        with self._lock:
            self._window.append((time.monotonic(), input_tokens))


# --- Module-level singleton API ---

_limiter: RateLimiter | None = None
_singleton_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """Return the global RateLimiter singleton (lazy-init from settings)."""
    global _limiter
    if _limiter is None:
        with _singleton_lock:
            if _limiter is None:
                from llm_pipeline.config import settings

                _limiter = RateLimiter(settings.rate_limit_tokens_per_minute)
    return _limiter


def reset_rate_limiter() -> RateLimiter:
    """Replace the global rate limiter with a fresh one and return it."""
    global _limiter
    with _singleton_lock:
        from llm_pipeline.config import settings

        _limiter = RateLimiter(settings.rate_limit_tokens_per_minute)
    return _limiter
