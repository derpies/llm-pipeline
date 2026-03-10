"""SMTP response classification via ordered regex patterns.

First-match-wins against a priority-ordered pattern list. Each pattern
yields a category, confidence score, and optional provider hint.
"""

from __future__ import annotations

import re

from llm_pipeline.email_analytics.models import SmtpCategory, SmtpClassification

# ---------------------------------------------------------------------------
# Pattern registry — ordered from most-specific to most-generic.
# Each entry: (compiled_regex, category, confidence, provider_hint, label)
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[re.Pattern, SmtpCategory, float, str, str]] = []


def _p(pattern: str, cat: SmtpCategory, conf: float, provider: str = "", label: str = "") -> None:
    _PATTERNS.append((re.compile(pattern, re.IGNORECASE), cat, conf, provider, label or pattern))


# --- Throttling ---
_p(r"421.*too many connections", SmtpCategory.THROTTLING, 0.95, "", "too_many_connections")
_p(r"421.*try again later", SmtpCategory.THROTTLING, 0.90, "", "try_again_later")
_p(r"451.*too many", SmtpCategory.THROTTLING, 0.90, "", "451_too_many")
_p(r"rate.{0,20}limit", SmtpCategory.THROTTLING, 0.85, "", "rate_limit")
_p(r"throttl", SmtpCategory.THROTTLING, 0.85, "", "throttle")
_p(r"too many (emails|messages|connections)", SmtpCategory.THROTTLING, 0.85, "", "too_many")
_p(r"deferr.{0,20}(due to|because)", SmtpCategory.THROTTLING, 0.75, "", "deferred_due_to")

# --- Yahoo-specific ---
_p(r"yahoo.*temporarily deferred", SmtpCategory.THROTTLING, 0.95, "yahoo", "yahoo_temp_deferred")
_p(r"mta\d+\.am0\.yahoodns", SmtpCategory.THROTTLING, 0.90, "yahoo", "yahoo_mta")
_p(r"resources\.mail\.yahoo", SmtpCategory.POLICY, 0.85, "yahoo", "yahoo_resources")

# --- Gmail-specific ---
_p(r"gmail.*rate", SmtpCategory.THROTTLING, 0.90, "gmail", "gmail_rate")
_p(
    r"our system has detected.{0,50}unusual rate",
    SmtpCategory.THROTTLING,
    0.90,
    "gmail",
    "gmail_unusual_rate",
)
_p(r"550-5\.7\.26", SmtpCategory.AUTH_FAILURE, 0.95, "gmail", "gmail_dmarc")
_p(r"421-4\.7\.28", SmtpCategory.AUTH_FAILURE, 0.90, "gmail", "gmail_auth")

# --- Microsoft-specific ---
_p(r"outlook.*temporarily", SmtpCategory.THROTTLING, 0.90, "microsoft", "outlook_temp")
_p(r"protection\.outlook", SmtpCategory.POLICY, 0.85, "microsoft", "outlook_protection")
_p(
    r"(hotmail|outlook|live)\.com.*block",
    SmtpCategory.BLACKLIST,
    0.90,
    "microsoft",
    "ms_block",
)

# --- Blacklist ---
_p(r"blacklist", SmtpCategory.BLACKLIST, 0.90, "", "blacklist")
_p(r"blocklist", SmtpCategory.BLACKLIST, 0.90, "", "blocklist")
_p(r"(rbl|dnsbl|spamhaus|barracuda)", SmtpCategory.BLACKLIST, 0.90, "", "dnsbl")
_p(r"block.{0,20}(list|listed)", SmtpCategory.BLACKLIST, 0.85, "", "block_listed")
_p(r"rejected.*spam", SmtpCategory.BLACKLIST, 0.80, "", "rejected_spam")
_p(r"ip.{0,20}(blocked|rejected|banned)", SmtpCategory.BLACKLIST, 0.85, "", "ip_blocked")

# --- Reputation ---
_p(r"reputat", SmtpCategory.REPUTATION, 0.85, "", "reputation")
_p(r"poor.{0,20}sender", SmtpCategory.REPUTATION, 0.80, "", "poor_sender")
_p(r"sender.{0,20}score", SmtpCategory.REPUTATION, 0.80, "", "sender_score")
_p(r"low.{0,20}quality", SmtpCategory.REPUTATION, 0.75, "", "low_quality")

# --- Auth failure ---
_p(r"(spf|dkim|dmarc).{0,20}fail", SmtpCategory.AUTH_FAILURE, 0.90, "", "auth_fail")
_p(r"550.{0,5}5\.7\.1", SmtpCategory.AUTH_FAILURE, 0.85, "", "550_5_7_1")
_p(r"authentication.{0,20}(fail|required)", SmtpCategory.AUTH_FAILURE, 0.85, "", "auth_required")
_p(r"not.{0,20}authenticated", SmtpCategory.AUTH_FAILURE, 0.80, "", "not_auth")

# --- Content rejection ---
_CR = SmtpCategory.CONTENT_REJECTION
_p(r"content.{0,20}reject", _CR, 0.85, "", "content_reject")
_p(r"message.{0,20}(rejected|refused).*content", _CR, 0.80, "", "msg_content")
_p(r"(spam|junk).{0,20}(content|detected)", _CR, 0.80, "", "spam_content")
_p(r"(virus|malware|phishing)", _CR, 0.90, "", "malware")
_p(r"(attachment|file).{0,20}(block|reject)", _CR, 0.85, "", "attachment_block")

# --- Recipient unknown ---
_RU = SmtpCategory.RECIPIENT_UNKNOWN
_p(r"550.{0,5}5\.1\.1", _RU, 0.95, "", "550_5_1_1")
_p(
    r"(user|mailbox|recipient).{0,20}(not found|unknown|invalid|doesn.t exist)",
    _RU, 0.90, "", "user_unknown",
)
_p(r"no such user", _RU, 0.95, "", "no_such_user")
_p(r"(address|account).{0,20}(rejected|invalid|disabled)", _RU, 0.85, "", "addr_invalid")
_p(r"mailbox.{0,20}(full|quota|exceeded)", SmtpCategory.POLICY, 0.85, "", "mailbox_full")

# --- Policy ---
_p(r"policy", SmtpCategory.POLICY, 0.70, "", "policy")
_p(r"(denied|reject).{0,30}(policy|rule)", SmtpCategory.POLICY, 0.80, "", "denied_policy")
_p(r"(compliance|regulation)", SmtpCategory.POLICY, 0.75, "", "compliance")

# --- Network ---
_p(r"connection.{0,20}(timed? ?out|reset|refused)", SmtpCategory.NETWORK, 0.90, "", "conn_error")
_p(r"(timed? ?out|timeout)", SmtpCategory.NETWORK, 0.80, "", "timeout")
_p(r"(unreachable|no route)", SmtpCategory.NETWORK, 0.85, "", "unreachable")
_p(r"(dns|mx).{0,20}(fail|error|not found)", SmtpCategory.NETWORK, 0.85, "", "dns_error")

# --- Success ---
_p(r"^250 ", SmtpCategory.SUCCESS, 0.95, "", "250_ok")
_p(r"(queued|accepted|delivered)", SmtpCategory.SUCCESS, 0.80, "", "queued")


# ---------------------------------------------------------------------------
# SMTP code extraction
# ---------------------------------------------------------------------------

_SMTP_CODE_RE = re.compile(r"\b([2-5]\d{2})[\s.-]")


def extract_smtp_code(message: str) -> str:
    """Extract the first 3-digit SMTP response code from a message string."""
    m = _SMTP_CODE_RE.search(message)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Provider detection from message or MX hostname
# ---------------------------------------------------------------------------

_PROVIDER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"yahoo|yahoodns", re.IGNORECASE), "yahoo"),
    (re.compile(r"gmail|google", re.IGNORECASE), "gmail"),
    (re.compile(r"outlook|hotmail|live\.com|microsoft|protection\.outlook",
                re.IGNORECASE), "microsoft"),
    (re.compile(r"aol\.com", re.IGNORECASE), "aol"),
    (re.compile(r"comcast", re.IGNORECASE), "comcast"),
    (re.compile(r"apple|icloud|me\.com", re.IGNORECASE), "apple"),
]


def detect_provider(message: str) -> str:
    """Detect the receiving provider from message text."""
    for pattern, provider in _PROVIDER_PATTERNS:
        if pattern.search(message):
            return provider
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_smtp_response(message: str) -> SmtpClassification:
    """Classify an SMTP response message into a category.

    Uses first-match-wins against an ordered pattern list.
    """
    if not message or not message.strip():
        return SmtpClassification(
            category=SmtpCategory.OTHER,
            confidence=0.0,
            smtp_code="",
            provider_hint="",
            matched_pattern="empty",
        )

    smtp_code = extract_smtp_code(message)
    provider = detect_provider(message)

    for regex, category, confidence, pattern_provider, label in _PATTERNS:
        if regex.search(message):
            return SmtpClassification(
                category=category,
                confidence=confidence,
                smtp_code=smtp_code,
                provider_hint=pattern_provider or provider,
                matched_pattern=label,
            )

    return SmtpClassification(
        category=SmtpCategory.OTHER,
        confidence=0.1,
        smtp_code=smtp_code,
        provider_hint=provider,
        matched_pattern="no_match",
    )
