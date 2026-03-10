"""Thread-safe token usage tracker with per-model cost computation."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Price per 1M tokens (input, output) by model pattern
_PRICE_TABLE: list[tuple[str, float, float]] = [
    ("haiku", 0.80, 4.00),
    ("opus", 15.00, 75.00),
    ("sonnet", 3.00, 15.00),
    ("gpt-4o", 2.50, 10.00),
]
_DEFAULT_PRICE = (3.00, 15.00)  # fallback


def _lookup_price(model: str) -> tuple[float, float]:
    """Return (input_price_per_1M, output_price_per_1M) for a model string."""
    model_lower = model.lower()
    for pattern, inp, out in _PRICE_TABLE:
        if pattern in model_lower:
            return inp, out
    return _DEFAULT_PRICE


@dataclass
class _CallRecord:
    model: str
    input_tokens: int
    output_tokens: int


@dataclass
class TokenTracker:
    """Accumulates token usage across LLM calls. Thread-safe."""

    _records: list[_CallRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, response, model: str = "") -> None:
        """Extract usage_metadata from an AIMessage and record it."""
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            logger.warning("No usage_metadata on response (model=%s)", model)
            return

        input_tokens = usage.get("input_tokens", 0) if isinstance(usage, dict) else getattr(usage, "input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0) if isinstance(usage, dict) else getattr(usage, "output_tokens", 0)

        with self._lock:
            self._records.append(_CallRecord(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ))

    @property
    def total_input_tokens(self) -> int:
        with self._lock:
            return sum(r.input_tokens for r in self._records)

    @property
    def total_output_tokens(self) -> int:
        with self._lock:
            return sum(r.output_tokens for r in self._records)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def call_count(self) -> int:
        with self._lock:
            return len(self._records)

    @property
    def total_cost_usd(self) -> float:
        """Compute total cost from per-call records using the price table."""
        with self._lock:
            total = 0.0
            for r in self._records:
                inp_price, out_price = _lookup_price(r.model)
                total += (r.input_tokens * inp_price + r.output_tokens * out_price) / 1_000_000
            return total

    def check_spend_limit(self, max_usd: float) -> tuple[bool, str]:
        """Return (exceeded, message). exceeded=True when over limit."""
        cost = self.total_cost_usd
        if cost >= max_usd:
            return True, f"spend: ${cost:.2f}/${max_usd:.2f}"
        return False, ""

    def summary(self) -> str:
        """One-line spend summary, e.g. '$0.47 | 12,340 in + 3,210 out | 8 calls'."""
        return (
            f"${self.total_cost_usd:.2f} | "
            f"{self.total_input_tokens:,} in + {self.total_output_tokens:,} out | "
            f"{self.call_count} calls"
        )


# --- Module-level singleton API ---

_tracker: TokenTracker | None = None
_singleton_lock = threading.Lock()


def get_tracker() -> TokenTracker:
    """Return the global TokenTracker singleton (lazy-init)."""
    global _tracker
    if _tracker is None:
        with _singleton_lock:
            if _tracker is None:
                _tracker = TokenTracker()
    return _tracker


def reset_tracker() -> TokenTracker:
    """Replace the global tracker with a fresh one and return it."""
    global _tracker
    with _singleton_lock:
        _tracker = TokenTracker()
    return _tracker
