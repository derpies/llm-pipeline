"""Tests for datetime tools — manipulate_datetime operations and error handling."""

import json

from llm_pipeline.tools.datetime.manipulate_datetime import manipulate_datetime


def _invoke(tool_input: dict) -> str:
    """Invoke the tool and return the raw string result."""
    return manipulate_datetime.invoke(tool_input)


def _ok(result: str) -> str:
    """Assert result is OK and return the content after the prefix."""
    assert result.startswith("[OK] "), f"Expected [OK], got: {result}"
    return result[len("[OK] "):]


def _error(result: str) -> str:
    """Assert result is ERROR and return the content."""
    assert result.startswith("[ERROR] "), f"Expected [ERROR], got: {result}"
    return result[len("[ERROR] "):]


# --- now ---

class TestNow:
    def test_returns_utc(self):
        content = _ok(_invoke({"operation": "now"}))
        assert "UTC" in content

    def test_no_datetime_str_needed(self):
        # Should not error when datetime_str is omitted
        result = _invoke({"operation": "now"})
        assert result.startswith("[OK] ")


# --- parse ---

class TestParse:
    def test_iso8601(self):
        content = _ok(_invoke({"operation": "parse", "datetime_str": "2026-02-11T15:00:00-05:00"}))
        assert content == "2026-02-11T20:00:00+00:00"

    def test_human_readable(self):
        content = _ok(_invoke({"operation": "parse", "datetime_str": "Feb 11, 2026 3pm"}))
        assert "2026-02-11" in content
        assert "15:00:00" in content

    def test_naive_assumes_utc(self):
        content = _ok(_invoke({"operation": "parse", "datetime_str": "2026-02-11 10:00:00"}))
        assert content == "2026-02-11T10:00:00+00:00"

    def test_invalid_string(self):
        result = _invoke({"operation": "parse", "datetime_str": "not-a-date"})
        _error(result)


# --- format ---

class TestFormat:
    def test_basic_format(self):
        content = _ok(_invoke({
            "operation": "format",
            "datetime_str": "2026-02-11T20:00:00+00:00",
            "format_pattern": "%B %d, %Y",
        }))
        assert content == "February 11, 2026"

    def test_time_format(self):
        content = _ok(_invoke({
            "operation": "format",
            "datetime_str": "2026-02-11T15:30:00+00:00",
            "format_pattern": "%H:%M",
        }))
        assert content == "15:30"

    def test_missing_pattern(self):
        result = _invoke({"operation": "format", "datetime_str": "2026-02-11"})
        _error(result)


# --- shift ---

class TestShift:
    def test_add_days(self):
        content = _ok(_invoke({
            "operation": "shift",
            "datetime_str": "2026-02-11T00:00:00+00:00",
            "shift_amount": 3,
            "shift_unit": "days",
        }))
        assert content == "2026-02-14T00:00:00+00:00"

    def test_subtract_hours(self):
        content = _ok(_invoke({
            "operation": "shift",
            "datetime_str": "2026-02-11T12:00:00+00:00",
            "shift_amount": -5,
            "shift_unit": "hours",
        }))
        assert content == "2026-02-11T07:00:00+00:00"

    def test_add_weeks(self):
        content = _ok(_invoke({
            "operation": "shift",
            "datetime_str": "2026-02-11T00:00:00+00:00",
            "shift_amount": 2,
            "shift_unit": "weeks",
        }))
        assert content == "2026-02-25T00:00:00+00:00"

    def test_missing_params(self):
        result = _invoke({"operation": "shift", "datetime_str": "2026-02-11"})
        _error(result)

    def test_invalid_unit(self):
        result = _invoke({
            "operation": "shift",
            "datetime_str": "2026-02-11",
            "shift_amount": 1,
            "shift_unit": "fortnights",
        })
        _error(result)


# --- diff ---

class TestDiff:
    def test_positive_diff(self):
        content = _ok(_invoke({
            "operation": "diff",
            "datetime_str": "2026-02-11T00:00:00+00:00",
            "other_datetime_str": "2026-02-14T03:00:00+00:00",
        }))
        data = json.loads(content)
        assert data["total_seconds"] == 3 * 86400 + 3 * 3600
        assert "3 days" in data["human_readable"]
        assert "3 hours" in data["human_readable"]
        assert data["human_readable"].startswith("+")

    def test_negative_diff(self):
        content = _ok(_invoke({
            "operation": "diff",
            "datetime_str": "2026-02-14T00:00:00+00:00",
            "other_datetime_str": "2026-02-11T00:00:00+00:00",
        }))
        data = json.loads(content)
        assert data["total_seconds"] == -3 * 86400
        assert data["human_readable"].startswith("-")

    def test_zero_diff(self):
        content = _ok(_invoke({
            "operation": "diff",
            "datetime_str": "2026-02-11T00:00:00+00:00",
            "other_datetime_str": "2026-02-11T00:00:00+00:00",
        }))
        data = json.loads(content)
        assert data["total_seconds"] == 0.0

    def test_missing_other(self):
        result = _invoke({"operation": "diff", "datetime_str": "2026-02-11"})
        _error(result)


# --- range ---

class TestRange:
    def test_day(self):
        content = _ok(_invoke({
            "operation": "range",
            "datetime_str": "2026-02-11T14:30:00+00:00",
            "range_unit": "day",
        }))
        data = json.loads(content)
        assert data["start"] == "2026-02-11T00:00:00+00:00"
        assert data["end"].startswith("2026-02-11T23:59:59")

    def test_week(self):
        # 2026-02-11 is a Wednesday
        content = _ok(_invoke({
            "operation": "range",
            "datetime_str": "2026-02-11T14:30:00+00:00",
            "range_unit": "week",
        }))
        data = json.loads(content)
        assert data["start"] == "2026-02-09T00:00:00+00:00"  # Monday
        assert data["end"].startswith("2026-02-15T23:59:59")  # Sunday

    def test_month(self):
        content = _ok(_invoke({
            "operation": "range",
            "datetime_str": "2026-02-11T14:30:00+00:00",
            "range_unit": "month",
        }))
        data = json.loads(content)
        assert data["start"] == "2026-02-01T00:00:00+00:00"
        assert data["end"].startswith("2026-02-28T23:59:59")

    def test_quarter(self):
        content = _ok(_invoke({
            "operation": "range",
            "datetime_str": "2026-02-11T14:30:00+00:00",
            "range_unit": "quarter",
        }))
        data = json.loads(content)
        assert data["start"] == "2026-01-01T00:00:00+00:00"
        assert data["end"].startswith("2026-03-31T23:59:59")

    def test_year(self):
        content = _ok(_invoke({
            "operation": "range",
            "datetime_str": "2026-02-11T14:30:00+00:00",
            "range_unit": "year",
        }))
        data = json.loads(content)
        assert data["start"] == "2026-01-01T00:00:00+00:00"
        assert data["end"].startswith("2026-12-31T23:59:59")

    def test_q4_wraps_year(self):
        content = _ok(_invoke({
            "operation": "range",
            "datetime_str": "2026-11-15T00:00:00+00:00",
            "range_unit": "quarter",
        }))
        data = json.loads(content)
        assert data["start"] == "2026-10-01T00:00:00+00:00"
        assert data["end"].startswith("2026-12-31T23:59:59")

    def test_missing_unit(self):
        result = _invoke({"operation": "range", "datetime_str": "2026-02-11"})
        _error(result)

    def test_invalid_unit(self):
        result = _invoke({
            "operation": "range",
            "datetime_str": "2026-02-11",
            "range_unit": "decade",
        })
        _error(result)


# --- convert_timezone ---

class TestConvertTimezone:
    def test_utc_to_eastern(self):
        content = _ok(_invoke({
            "operation": "convert_timezone",
            "datetime_str": "2026-02-11T20:00:00+00:00",
            "target_timezone": "America/New_York",
        }))
        assert "2026-02-11T15:00:00" in content
        assert "-05:00" in content

    def test_utc_to_tokyo(self):
        content = _ok(_invoke({
            "operation": "convert_timezone",
            "datetime_str": "2026-02-11T00:00:00+00:00",
            "target_timezone": "Asia/Tokyo",
        }))
        assert "2026-02-11T09:00:00" in content

    def test_invalid_tz(self):
        result = _invoke({
            "operation": "convert_timezone",
            "datetime_str": "2026-02-11",
            "target_timezone": "Mars/Olympus_Mons",
        })
        _error(result)

    def test_missing_tz(self):
        result = _invoke({"operation": "convert_timezone", "datetime_str": "2026-02-11"})
        _error(result)


# --- epoch ---

class TestEpoch:
    def test_epoch_to_iso(self):
        # 2026-02-11T00:00:00 UTC
        content = _ok(_invoke({
            "operation": "epoch",
            "datetime_str": "1770768000",
        }))
        data = json.loads(content)
        assert data["iso"] == "2026-02-11T00:00:00+00:00"
        assert data["epoch"] == 1770768000.0

    def test_float_epoch(self):
        content = _ok(_invoke({
            "operation": "epoch",
            "datetime_str": "1770768000.5",
        }))
        data = json.loads(content)
        assert "2026-02-11" in data["iso"]
        assert data["epoch"] == 1770768000.5

    def test_iso_to_epoch(self):
        content = _ok(_invoke({
            "operation": "epoch",
            "datetime_str": "2026-02-11T00:00:00+00:00",
        }))
        data = json.loads(content)
        assert data["epoch"] == 1770768000.0
        assert data["iso"] == "2026-02-11T00:00:00+00:00"

    def test_human_readable_to_epoch(self):
        content = _ok(_invoke({
            "operation": "epoch",
            "datetime_str": "Feb 11, 2026 00:00:00",
        }))
        data = json.loads(content)
        assert data["epoch"] == 1770768000.0

    def test_zero_epoch(self):
        content = _ok(_invoke({
            "operation": "epoch",
            "datetime_str": "0",
        }))
        data = json.loads(content)
        assert data["iso"] == "1970-01-01T00:00:00+00:00"
        assert data["epoch"] == 0.0


# --- shift with months/years ---

class TestShiftCalendar:
    def test_add_months(self):
        content = _ok(_invoke({
            "operation": "shift",
            "datetime_str": "2026-01-31T00:00:00+00:00",
            "shift_amount": 1,
            "shift_unit": "months",
        }))
        # Jan 31 + 1 month → Feb 28 (relativedelta clamps)
        assert "2026-02-28" in content

    def test_subtract_months(self):
        content = _ok(_invoke({
            "operation": "shift",
            "datetime_str": "2026-03-15T00:00:00+00:00",
            "shift_amount": -2,
            "shift_unit": "months",
        }))
        assert "2026-01-15" in content

    def test_add_years(self):
        content = _ok(_invoke({
            "operation": "shift",
            "datetime_str": "2026-02-11T12:00:00+00:00",
            "shift_amount": 1,
            "shift_unit": "years",
        }))
        assert "2027-02-11T12:00:00" in content

    def test_subtract_years(self):
        content = _ok(_invoke({
            "operation": "shift",
            "datetime_str": "2026-02-11T00:00:00+00:00",
            "shift_amount": -1,
            "shift_unit": "years",
        }))
        assert "2025-02-11" in content

    def test_leap_year_clamping(self):
        # 2024-02-29 + 1 year → 2025-02-28 (no Feb 29 in 2025)
        content = _ok(_invoke({
            "operation": "shift",
            "datetime_str": "2024-02-29T00:00:00+00:00",
            "shift_amount": 1,
            "shift_unit": "years",
        }))
        assert "2025-02-28" in content


# --- general error handling ---

class TestGeneral:
    def test_unknown_operation(self):
        result = _invoke({"operation": "explode", "datetime_str": "2026-02-11"})
        _error(result)

    def test_missing_datetime_str(self):
        result = _invoke({"operation": "parse"})
        _error(result)
