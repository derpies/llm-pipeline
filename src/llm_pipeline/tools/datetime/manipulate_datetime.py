"""Multi-operation datetime tool — now, parse, format, shift, diff, range, convert_timezone, epoch.

Single tool with an operation parameter to keep the agent tool list compact.
Uses python-dateutil for flexible input parsing and relativedelta for
calendar-aware shifts (months/years). zoneinfo for timezone conversion.
Naive inputs default to UTC.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta
from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

# --- Constants ---

VALID_OPERATIONS = (
    "now", "parse", "format", "shift", "diff", "range",
    "convert_timezone", "epoch",
)
# Fixed-duration units use timedelta; months/years use relativedelta
VALID_SHIFT_UNITS = (
    "seconds", "minutes", "hours", "days", "weeks", "months", "years",
)
_TIMEDELTA_UNITS = frozenset(("seconds", "minutes", "hours", "days", "weeks"))
VALID_RANGE_UNITS = ("day", "week", "month", "quarter", "year")

# --- Helpers ---


def _parse_dt(datetime_str: str) -> datetime:
    """Parse a datetime string into a tz-aware datetime (defaults to UTC)."""
    dt = dateutil_parser.parse(datetime_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _midnight(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

# --- Operation handlers ---


def _now(**_: object) -> str:
    return tool_result(
        ToolStatus.OK,
        datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )


def _parse(datetime_str: str, **_: object) -> str:
    dt = _parse_dt(datetime_str)
    return tool_result(ToolStatus.OK, _iso(dt.astimezone(UTC)))


def _format(
    datetime_str: str, format_pattern: str | None = None, **_: object
) -> str:
    if not format_pattern:
        return tool_result(
            ToolStatus.ERROR,
            "format_pattern is required for 'format'.",
        )
    dt = _parse_dt(datetime_str)
    return tool_result(ToolStatus.OK, dt.strftime(format_pattern))


def _shift(
    datetime_str: str,
    shift_amount: int | None = None,
    shift_unit: str | None = None,
    **_: object,
) -> str:
    if shift_amount is None or not shift_unit:
        return tool_result(
            ToolStatus.ERROR,
            "shift_amount and shift_unit are required for 'shift'.",
        )
    if shift_unit not in VALID_SHIFT_UNITS:
        valid = ", ".join(VALID_SHIFT_UNITS)
        return tool_result(
            ToolStatus.ERROR,
            f"Invalid shift_unit '{shift_unit}'. Must be one of: {valid}",
        )
    dt = _parse_dt(datetime_str)
    if shift_unit in _TIMEDELTA_UNITS:
        delta = timedelta(**{shift_unit: shift_amount})
    else:
        # months/years — variable-length, needs relativedelta
        delta = relativedelta(**{shift_unit: shift_amount})
    return tool_result(ToolStatus.OK, _iso(dt + delta))


def _diff(
    datetime_str: str,
    other_datetime_str: str | None = None,
    **_: object,
) -> str:
    if not other_datetime_str:
        return tool_result(
            ToolStatus.ERROR,
            "other_datetime_str is required for 'diff'.",
        )
    dt1 = _parse_dt(datetime_str)
    dt2 = _parse_dt(other_datetime_str)
    delta = dt2 - dt1
    total_seconds = delta.total_seconds()
    abs_seconds = abs(total_seconds)

    days = int(abs_seconds // 86400)
    hours = int((abs_seconds % 86400) // 3600)
    minutes = int((abs_seconds % 3600) // 60)
    secs = int(abs_seconds % 60)

    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs or not parts:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")

    sign = "-" if total_seconds < 0 else "+"
    human = f"{sign}{', '.join(parts)}"

    result = {"human_readable": human, "total_seconds": total_seconds}
    return tool_result(ToolStatus.OK, json.dumps(result))


def _range(
    datetime_str: str, range_unit: str | None = None, **_: object
) -> str:
    if not range_unit:
        return tool_result(
            ToolStatus.ERROR,
            "range_unit is required for 'range'.",
        )
    if range_unit not in VALID_RANGE_UNITS:
        valid = ", ".join(VALID_RANGE_UNITS)
        return tool_result(
            ToolStatus.ERROR,
            f"Invalid range_unit '{range_unit}'. Must be: {valid}",
        )

    dt = _parse_dt(datetime_str)

    if range_unit == "day":
        start = _midnight(dt)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
    elif range_unit == "week":
        monday = dt - timedelta(days=dt.weekday())
        start = _midnight(monday)
        end = start + timedelta(days=7) - timedelta(microseconds=1)
    elif range_unit == "month":
        start = _midnight(dt).replace(day=1)
        if dt.month == 12:
            end_excl = start.replace(year=dt.year + 1, month=1)
        else:
            end_excl = start.replace(month=dt.month + 1)
        end = end_excl - timedelta(microseconds=1)
    elif range_unit == "quarter":
        q_start = ((dt.month - 1) // 3) * 3 + 1
        start = _midnight(dt).replace(month=q_start, day=1)
        q_end = q_start + 3
        if q_end > 12:
            end_excl = start.replace(
                year=dt.year + 1, month=q_end - 12
            )
        else:
            end_excl = start.replace(month=q_end)
        end = end_excl - timedelta(microseconds=1)
    elif range_unit == "year":
        start = _midnight(dt).replace(month=1, day=1)
        end_excl = start.replace(year=dt.year + 1)
        end = end_excl - timedelta(microseconds=1)

    result = {"start": _iso(start), "end": _iso(end)}
    return tool_result(ToolStatus.OK, json.dumps(result))


def _convert_timezone(
    datetime_str: str,
    target_timezone: str | None = None,
    **_: object,
) -> str:
    if not target_timezone:
        return tool_result(
            ToolStatus.ERROR,
            "target_timezone is required for 'convert_timezone'.",
        )
    try:
        tz = ZoneInfo(target_timezone)
    except (ZoneInfoNotFoundError, KeyError):
        return tool_result(
            ToolStatus.ERROR, f"Unknown timezone '{target_timezone}'."
        )
    dt = _parse_dt(datetime_str)
    return tool_result(ToolStatus.OK, _iso(dt.astimezone(tz)))


def _epoch(datetime_str: str, **_: object) -> str:
    """Convert between epoch timestamps and ISO 8601.

    If the input looks like a numeric epoch (integer or float seconds),
    convert to ISO 8601 UTC. Otherwise parse as a datetime and return
    the epoch timestamp.
    """
    stripped = datetime_str.strip()
    try:
        epoch_val = float(stripped)
        # Numeric input → epoch to ISO
        dt = datetime.fromtimestamp(epoch_val, tz=UTC)
        result = {"iso": _iso(dt), "epoch": epoch_val}
        return tool_result(ToolStatus.OK, json.dumps(result))
    except ValueError:
        pass
    # Non-numeric input → ISO to epoch
    dt = _parse_dt(datetime_str)
    epoch_val = dt.timestamp()
    result = {"iso": _iso(dt.astimezone(UTC)), "epoch": epoch_val}
    return tool_result(ToolStatus.OK, json.dumps(result))


# --- Dispatch + public tool ---

_DISPATCH = {
    "now": _now,
    "parse": _parse,
    "format": _format,
    "shift": _shift,
    "diff": _diff,
    "range": _range,
    "convert_timezone": _convert_timezone,
    "epoch": _epoch,
}


@tool
def manipulate_datetime(
    operation: str,
    datetime_str: str | None = None,
    other_datetime_str: str | None = None,
    shift_amount: int | None = None,
    shift_unit: str | None = None,
    format_pattern: str | None = None,
    target_timezone: str | None = None,
    range_unit: str | None = None,
) -> str:
    """Datetime Swiss army knife: now, parse, format, shift, diff, range, convert_timezone, epoch.

    Operations:
    - now: Current UTC datetime (no datetime_str needed).
    - parse: Normalize to ISO 8601 UTC.
    - format: strftime with format_pattern.
    - shift: Add/subtract time (shift_amount + shift_unit).
    - diff: Difference between two datetimes (other_datetime_str).
    - range: Start/end of containing period (range_unit).
    - convert_timezone: Convert to target_timezone (IANA name).
    - epoch: Convert between epoch seconds and ISO 8601. Pass a
      numeric string to get ISO, or a datetime string to get epoch.
      Returns JSON with both "iso" and "epoch" fields.

    Args:
        operation: One of the operations listed above.
        datetime_str: Input datetime (flexible: ISO, human-readable, epoch).
        other_datetime_str: Second datetime for diff.
        shift_amount: Integer (positive=forward, negative=backward).
        shift_unit: seconds, minutes, hours, days, weeks, months, years.
        format_pattern: strftime pattern for format.
        target_timezone: IANA tz name (e.g. "America/New_York").
        range_unit: day, week, month, quarter, year.
    """
    if operation not in VALID_OPERATIONS:
        valid = ", ".join(VALID_OPERATIONS)
        return tool_result(
            ToolStatus.ERROR,
            f"Unknown operation '{operation}'. Must be one of: {valid}",
        )

    if not datetime_str and operation != "now":
        return tool_result(ToolStatus.ERROR, "datetime_str is required.")

    handler = _DISPATCH[operation]
    try:
        return handler(
            datetime_str=datetime_str,
            other_datetime_str=other_datetime_str,
            shift_amount=shift_amount,
            shift_unit=shift_unit,
            format_pattern=format_pattern,
            target_timezone=target_timezone,
            range_unit=range_unit,
        )
    except (ValueError, OverflowError) as exc:
        return tool_result(
            ToolStatus.ERROR, f"Failed to process datetime: {exc}"
        )
