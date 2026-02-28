"""Pure parsing functions for composite email delivery log fields.

No external dependencies — these operate on raw strings and return
dataclasses/enums. Used by DeliveryEvent's model_validator to populate
derived fields at parse time.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ListIdType(enum.StrEnum):
    ENGAGEMENT = "engagement"
    PRIVATE = "private"
    ISOLATION = "isolation"
    BESPOKE = "bespoke"
    UNKNOWN = "unknown"


class ComplianceStatus(enum.StrEnum):
    COMPLIANT = "compliant"
    NOT_CHECKED = "not_checked"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# XMRID / clicktrackingid parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ParsedXMRID:
    """The 7 dot-delimited sub-fields of clicktrackingid[0]."""

    object_id: str
    account_id: str
    contact_id: str
    log_id: str
    message_id: str
    drip_id: str
    step_id: str
    is_zero_cohort: bool  # True when account_id or contact_id is "0"


@dataclass(frozen=True, slots=True)
class ParsedClickTracking:
    """All 6 semicolon-delimited fields of clicktrackingid, parsed."""

    xmrid: ParsedXMRID
    last_active: float  # unix timestamp (raw value)
    contact_added: float  # unix timestamp
    op_queue_time: float  # unix timestamp
    op_queue_id: str
    marketing: int  # 0 = transactional, 1 = marketing
    last_active_adjusted: float  # after applying the 0 → contact_added+15d rule


_FIFTEEN_DAYS_SECONDS = 15 * 24 * 3600


def _parse_xmrid(raw: str) -> ParsedXMRID | None:
    """Parse the dot-delimited XMRID string (clicktrackingid field 0).

    XMRID has exactly 7 dot-delimited sub-fields.  However, we split from
    the left with maxsplit=6 because later sub-fields (like op-queue-id)
    can themselves contain dots.
    """
    parts = raw.split(".", 6)
    if len(parts) != 7:
        return None

    account_id = parts[1]
    contact_id = parts[2]
    is_zero = account_id == "0" or contact_id == "0"

    return ParsedXMRID(
        object_id=parts[0],
        account_id=account_id,
        contact_id=contact_id,
        log_id=parts[3],
        message_id=parts[4],
        drip_id=parts[5],
        step_id=parts[6],
        is_zero_cohort=is_zero,
    )


def parse_clicktrackingid(raw: str) -> ParsedClickTracking | None:
    """Parse a full clicktrackingid value into its component fields.

    Returns None if the string is empty or structurally invalid.
    """
    if not raw:
        return None

    parts = raw.split(";")
    if len(parts) != 6:
        return None

    xmrid = _parse_xmrid(parts[0])
    if xmrid is None:
        return None

    try:
        last_active = float(parts[1])
        contact_added = float(parts[2])
        op_queue_time = float(parts[3])
        marketing = int(parts[5])
    except (ValueError, IndexError):
        return None

    # last-active = 0 → treat as contact_added + 15 days
    if last_active == 0 and contact_added > 0:
        last_active_adjusted = contact_added + _FIFTEEN_DAYS_SECONDS
    else:
        last_active_adjusted = last_active

    return ParsedClickTracking(
        xmrid=xmrid,
        last_active=last_active,
        contact_added=contact_added,
        op_queue_time=op_queue_time,
        op_queue_id=parts[4],
        marketing=marketing,
        last_active_adjusted=last_active_adjusted,
    )


# ---------------------------------------------------------------------------
# listid classification
# ---------------------------------------------------------------------------

# Engagement segment suffixes — the trailing code after SEG_E_
_ENGAGEMENT_SEGMENTS = frozenset({"UK", "VH", "H", "M", "L", "VL", "RO", "NM", "DS"})

_SEG_E_PATTERN = re.compile(r"^SEG_E_([A-Z]+)$")
_PRIVATE_PATTERN = re.compile(r"^PRIVATE_")
_ISO_PATTERN = re.compile(r"^ISO")


def classify_listid(listid: str) -> tuple[ListIdType, str]:
    """Classify a listid into its type and extract the segment code.

    Returns (ListIdType, segment_code).  segment_code is the engagement
    suffix (e.g. "VH") for engagement segments, or "" for other types.
    """
    if not listid:
        return ListIdType.UNKNOWN, ""

    m = _SEG_E_PATTERN.match(listid)
    if m:
        seg = m.group(1)
        if seg in _ENGAGEMENT_SEGMENTS:
            return ListIdType.ENGAGEMENT, seg
        # Looks like SEG_E_ but unknown suffix — still engagement
        return ListIdType.ENGAGEMENT, seg

    if _PRIVATE_PATTERN.match(listid):
        return ListIdType.PRIVATE, ""

    if _ISO_PATTERN.match(listid):
        return ListIdType.ISOLATION, ""

    return ListIdType.BESPOKE, ""


# ---------------------------------------------------------------------------
# Compliance header parsing
# ---------------------------------------------------------------------------


def parse_compliance_header(header_value: str | None) -> ComplianceStatus:
    """Parse the ``x-op-mail-domains`` header into a compliance status.

    Two known patterns:
    - ``"compliant-from:...; compliant-mailfrom:...;"`` → COMPLIANT
    - ``"no-compliant-check: ..."`` → NOT_CHECKED
    - Anything else (empty, missing, unexpected) → UNKNOWN
    """
    if not header_value:
        return ComplianceStatus.UNKNOWN

    lower = header_value.lower()
    if "compliant-from:" in lower and "compliant-mailfrom:" in lower:
        return ComplianceStatus.COMPLIANT
    if "no-compliant-check" in lower:
        return ComplianceStatus.NOT_CHECKED

    return ComplianceStatus.UNKNOWN
