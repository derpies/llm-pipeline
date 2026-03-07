"""Tests for token usage tracking and cost computation."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from llm_pipeline.models.token_tracker import (
    TokenTracker,
    _lookup_price,
    get_tracker,
    reset_tracker,
)


def _mock_response(input_tokens: int = 100, output_tokens: int = 50) -> MagicMock:
    """Create a mock AIMessage with usage_metadata."""
    resp = MagicMock()
    resp.usage_metadata = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    return resp


class TestTokenTracker:
    def test_record_accumulates_tokens(self):
        t = TokenTracker()
        t.record(_mock_response(100, 50), model="claude-sonnet-4-20250514")
        t.record(_mock_response(200, 80), model="claude-sonnet-4-20250514")

        assert t.total_input_tokens == 300
        assert t.total_output_tokens == 130
        assert t.total_tokens == 430
        assert t.call_count == 2

    def test_cost_computation_sonnet(self):
        t = TokenTracker()
        # 1M input tokens at $3, 0 output
        t.record(_mock_response(1_000_000, 0), model="claude-sonnet-4-20250514")
        assert t.total_cost_usd == pytest.approx(3.00)

        # Add 1M output tokens at $15
        t.record(_mock_response(0, 1_000_000), model="claude-sonnet-4-20250514")
        assert t.total_cost_usd == pytest.approx(18.00)

    def test_cost_computation_opus(self):
        t = TokenTracker()
        t.record(_mock_response(1_000_000, 1_000_000), model="claude-opus-4-20250514")
        # $15 input + $75 output = $90
        assert t.total_cost_usd == pytest.approx(90.00)

    def test_cost_computation_haiku(self):
        t = TokenTracker()
        t.record(_mock_response(1_000_000, 1_000_000), model="claude-haiku-4-5-20251001")
        # $0.80 input + $4.00 output = $4.80
        assert t.total_cost_usd == pytest.approx(4.80)

    def test_cost_computation_gpt4o(self):
        t = TokenTracker()
        t.record(_mock_response(1_000_000, 1_000_000), model="gpt-4o-2024-08-06")
        # $2.50 input + $10.00 output = $12.50
        assert t.total_cost_usd == pytest.approx(12.50)

    def test_cost_computation_mixed_models(self):
        t = TokenTracker()
        t.record(_mock_response(1000, 500), model="claude-sonnet-4-20250514")
        t.record(_mock_response(1000, 500), model="claude-opus-4-20250514")
        # sonnet: (1000*3 + 500*15)/1M = 0.0105
        # opus: (1000*15 + 500*75)/1M = 0.0525
        assert t.total_cost_usd == pytest.approx(0.063)

    def test_check_spend_limit_under(self):
        t = TokenTracker()
        t.record(_mock_response(100, 50), model="claude-sonnet-4-20250514")
        exceeded, msg = t.check_spend_limit(10.0)
        assert not exceeded
        assert msg == ""

    def test_check_spend_limit_exceeded(self):
        t = TokenTracker()
        # Record enough to exceed $10
        t.record(_mock_response(2_000_000, 1_000_000), model="claude-opus-4-20250514")
        # $30 + $75 = $105
        exceeded, msg = t.check_spend_limit(10.0)
        assert exceeded
        assert "spend:" in msg
        assert "$10.00" in msg

    def test_summary_format(self):
        t = TokenTracker()
        t.record(_mock_response(12340, 3210), model="claude-sonnet-4-20250514")
        s = t.summary()
        assert "12,340 in" in s
        assert "3,210 out" in s
        assert "1 calls" in s
        assert "$" in s

    def test_missing_usage_metadata_no_crash(self):
        t = TokenTracker()
        resp = MagicMock(spec=[])  # no usage_metadata attr
        del resp.usage_metadata  # ensure it's truly absent
        t.record(resp, model="claude-sonnet-4-20250514")
        assert t.total_tokens == 0
        assert t.call_count == 0

    def test_none_usage_metadata(self):
        t = TokenTracker()
        resp = MagicMock()
        resp.usage_metadata = None
        t.record(resp, model="claude-sonnet-4-20250514")
        assert t.total_tokens == 0
        assert t.call_count == 0

    def test_unknown_model_uses_default_pricing(self):
        t = TokenTracker()
        t.record(_mock_response(1_000_000, 1_000_000), model="some-unknown-model-v3")
        # default: $3 input + $15 output = $18
        assert t.total_cost_usd == pytest.approx(18.00)

    def test_empty_model_string(self):
        t = TokenTracker()
        t.record(_mock_response(1_000_000, 0), model="")
        # falls back to default ($3/1M input)
        assert t.total_cost_usd == pytest.approx(3.00)

    def test_thread_safety(self):
        t = TokenTracker()
        errors: list[Exception] = []

        def record_many():
            try:
                for _ in range(100):
                    t.record(_mock_response(10, 5), model="claude-sonnet-4-20250514")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_many) for _ in range(10)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert not errors
        assert t.call_count == 1000
        assert t.total_input_tokens == 10_000
        assert t.total_output_tokens == 5_000


class TestSingleton:
    def test_get_tracker_returns_same_instance(self):
        reset_tracker()
        a = get_tracker()
        b = get_tracker()
        assert a is b

    def test_reset_tracker_clears_state(self):
        reset_tracker()
        t = get_tracker()
        t.record(_mock_response(100, 50), model="claude-sonnet-4-20250514")
        assert t.call_count == 1

        t2 = reset_tracker()
        assert t2.call_count == 0
        assert get_tracker() is t2
        assert get_tracker() is not t


class TestPriceLookup:
    def test_sonnet_pattern(self):
        assert _lookup_price("claude-sonnet-4-20250514") == (3.0, 15.0)

    def test_opus_pattern(self):
        assert _lookup_price("claude-opus-4-20250514") == (15.0, 75.0)

    def test_haiku_pattern(self):
        assert _lookup_price("claude-haiku-4-5-20251001") == (0.8, 4.0)

    def test_gpt4o_pattern(self):
        assert _lookup_price("gpt-4o-2024-08-06") == (2.5, 10.0)

    def test_unknown_fallback(self):
        assert _lookup_price("mystery-model") == (3.0, 15.0)
