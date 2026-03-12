"""Rule-based classifiers for HTTP access log fields.

Three classifiers:
- classify_request: request line → (method, path, RequestCategory)
- classify_useragent: UA string → UaCategory
- classify_host: hostname → HostCategory
"""

from __future__ import annotations

import re

from llm_pipeline.http_analytics.models import (
    HostCategory,
    RequestCategory,
    UaCategory,
)

# ---------------------------------------------------------------------------
# Request classification
# ---------------------------------------------------------------------------

_STATIC_EXTENSIONS = re.compile(
    r"\.(css|js|png|jpg|jpeg|gif|ico|svg|woff2?|ttf|eot|map|webp|avif)(\?|$)",
    re.IGNORECASE,
)

_REQUEST_RULES: list[tuple[re.Pattern, RequestCategory]] = [
    (re.compile(r"\.php\b", re.IGNORECASE), RequestCategory.PHP_PROBE),
    (re.compile(r"^/o\?", re.IGNORECASE), RequestCategory.TRACKING_PIXEL),
    (re.compile(r"^/c/", re.IGNORECASE), RequestCategory.CLICK_TRACKING),
    (re.compile(r"^/api/", re.IGNORECASE), RequestCategory.API_CALL),
    (re.compile(r"^/ws\b", re.IGNORECASE), RequestCategory.WEBSOCKET),
]


def classify_request(request_line: str) -> tuple[str, str, RequestCategory]:
    """Parse an HTTP request line and classify it.

    Returns (method, path, category).
    """
    if not request_line:
        return ("", "", RequestCategory.OTHER)

    parts = request_line.split(None, 2)
    method = parts[0] if len(parts) >= 1 else ""
    path = parts[1] if len(parts) >= 2 else request_line

    # Check ordered rules against the path
    for pattern, category in _REQUEST_RULES:
        if pattern.search(path):
            return (method, path, category)

    # Static assets
    if _STATIC_EXTENSIONS.search(path):
        return (method, path, RequestCategory.STATIC_ASSET)

    # Default to page_load for GET of HTML-like paths, otherwise other
    if method.upper() == "GET" and (
        path == "/"
        or path.endswith(".html")
        or path.endswith(".htm")
        or "/" in path.rstrip("/")
    ):
        return (method, path, RequestCategory.PAGE_LOAD)

    return (method, path, RequestCategory.OTHER)


# ---------------------------------------------------------------------------
# User-agent classification
# ---------------------------------------------------------------------------

_SCANNER_PATTERNS = re.compile(
    r"(zgrab|masscan|nikto|sqlmap|nmap|nuclei|dirbuster|gobuster|wfuzz|"
    r"hydra|burp\s*suite|openvas|nessus|qualys|acunetix|w3af|skipfish)",
    re.IGNORECASE,
)

_BOT_PATTERNS = re.compile(
    r"(bot|crawl|spider|slurp|mediapartners|adsbot|feedfetch|"
    r"facebookexternalhit|twitterbot|linkedinbot|whatsapp|"
    r"telegrambot|discordbot|bingpreview|yandex|baidu|sogou|"
    r"semrush|ahrefs|mj12bot|dotbot|rogerbot|petalbot|bytespider)",
    re.IGNORECASE,
)

_CURL_PATTERNS = re.compile(r"^(curl|wget|httpie|python-requests|go-http|java/)", re.IGNORECASE)

_EMAIL_CLIENT_PATTERNS = re.compile(
    r"(thunderbird|outlook|apple\s*mail|yahoo\s*mail|gmail|mailbird|"
    r"postbox|airmail|spark|canary\s*mail|newton\s*mail)",
    re.IGNORECASE,
)

_REAL_BROWSER_PATTERNS = re.compile(
    r"(chrome|firefox|safari|edge|opera|vivaldi|brave).*\d",
    re.IGNORECASE,
)


def classify_useragent(ua: str, is_apple_mpp: bool = False) -> UaCategory:
    """Classify a user-agent string."""
    if not ua or not ua.strip():
        return UaCategory.EMPTY

    if is_apple_mpp:
        return UaCategory.APPLE_MPP

    if _SCANNER_PATTERNS.search(ua):
        return UaCategory.SCANNER

    if _CURL_PATTERNS.search(ua):
        return UaCategory.CURL

    if _BOT_PATTERNS.search(ua):
        return UaCategory.BOT_CRAWLER

    if _EMAIL_CLIENT_PATTERNS.search(ua):
        return UaCategory.EMAIL_CLIENT

    if _REAL_BROWSER_PATTERNS.search(ua):
        return UaCategory.REAL_BROWSER

    return UaCategory.OTHER


# ---------------------------------------------------------------------------
# Host classification
# ---------------------------------------------------------------------------


def classify_host(host: str) -> HostCategory:
    """Classify an HTTP host by known domain suffixes."""
    if not host:
        return HostCategory.CUSTOM_DOMAIN

    h = host.lower().rstrip(".")

    if h.endswith(".ontraport.com") or h == "ontraport.com":
        return HostCategory.ONTRAPORT_COM
    if h.endswith(".ontralink.com") or h == "ontralink.com":
        return HostCategory.ONTRALINK_COM
    if h.endswith(".ontraport.net") or h == "ontraport.net":
        return HostCategory.ONTRAPORT_NET

    return HostCategory.CUSTOM_DOMAIN
