# datetime/

Date and time utilities available to all agents (`role="*"`).

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Re-exports, TOOL_ROLES declarations |
| `manipulate_datetime.py` | All datetime operations in a single tool |

## Key Concepts

`manipulate_datetime` is a single tool with an `operation` parameter. This keeps
the agent tool list compact — since datetime tools use `role="*"`, every agent
gets them.

Input parsing uses `python-dateutil` for flexible string handling (ISO 8601,
human-readable, partial dates, epoch timestamps). Calendar-aware shifts
(months/years) use `dateutil.relativedelta`. Timezone conversion uses `zoneinfo`
(stdlib). Naive datetimes default to UTC.

### Operations

| Operation | Required params | Output |
|-----------|----------------|--------|
| `now` | _(none)_ | Current UTC datetime string |
| `parse` | `datetime_str` | ISO 8601 UTC string |
| `format` | `datetime_str`, `format_pattern` | Formatted string |
| `shift` | `datetime_str`, `shift_amount`, `shift_unit` | ISO 8601 string |
| `diff` | `datetime_str`, `other_datetime_str` | JSON: `human_readable` + `total_seconds` |
| `range` | `datetime_str`, `range_unit` | JSON: `start` + `end` of containing period |
| `convert_timezone` | `datetime_str`, `target_timezone` | ISO 8601 in target tz |
| `epoch` | `datetime_str` | JSON: `iso` + `epoch` (bidirectional conversion) |

`shift_unit` accepts fixed-duration units (seconds, minutes, hours, days, weeks)
and calendar-aware units (months, years). The latter use `relativedelta` to handle
variable-length months and leap years correctly.

## Contracts

- **Imports from**: `tools.result` (ToolStatus, tool_result), `dateutil.parser`, `dateutil.relativedelta`, `zoneinfo`
- **Exports**: `manipulate_datetime`, `TOOL_ROLES`
- **Consumed by**: All agents via `get_tools("*")` auto-discovery
