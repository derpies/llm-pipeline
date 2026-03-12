"""Shared fixtures for HTTP analytics tests."""

from datetime import UTC, datetime

import pytest

from llm_pipeline.http_analytics.models import (
    HttpAccessEvent,
    HttpAggregationBucket,
)


def _ts(minute: int, hour: int = 10, day: int = 1) -> datetime:
    """Helper: UTC datetime for 2026-03-{day}T{hour}:{minute}:00."""
    return datetime(2026, 3, day, hour, minute, 0, tzinfo=UTC)


def _make_event(
    request: str = "GET /page HTTP/1.1",
    http_host: str = "app.ontraport.com",
    http_status: str = "200",
    tts: str = "0.100",
    useragent: str = "Mozilla/5.0 Chrome/120",
    upstream: str = "10.1.0.1:8080",
    isotime: str = "2026-03-01T10:00:00+00:00",
    **kwargs,
) -> HttpAccessEvent:
    """Build a minimal HttpAccessEvent with sensible defaults."""
    data = {
        "isotime": isotime,
        "server": "edge001",
        "remoteaddr": "192.168.1.1",
        "http-host": http_host,
        "request": request,
        "http-status": http_status,
        "sizesent": "1024",
        "tts": tts,
        "upstream": upstream,
        "http-referrer": "",
        "useragent": useragent,
        "applempp": "FALSE",
        "xff": "",
        "trueip": "",
        "accountid": "12345",
        "session": "",
    }
    data.update(kwargs)
    return HttpAccessEvent.model_validate(data)


@pytest.fixture
def sample_events() -> list[HttpAccessEvent]:
    """A small set of HTTP access events covering varied request types."""
    return [
        _make_event(
            request="GET /page HTTP/1.1",
            http_status="200",
            tts="0.100",
            isotime="2026-03-01T10:00:10+00:00",
        ),
        _make_event(
            request="GET /o?123 HTTP/1.1",
            http_status="200",
            tts="0.010",
            isotime="2026-03-01T10:00:20+00:00",
        ),
        _make_event(
            request="GET /c/link HTTP/1.1",
            http_status="302",
            tts="0.050",
            isotime="2026-03-01T10:00:30+00:00",
        ),
        _make_event(
            request="GET /wp-login.php HTTP/1.1",
            http_status="404",
            tts="0.005",
            useragent="",
            upstream="",
            isotime="2026-03-01T10:00:40+00:00",
        ),
        _make_event(
            request="GET /api/v1/data HTTP/1.1",
            http_status="500",
            tts="5.000",
            isotime="2026-03-01T10:00:50+00:00",
        ),
        _make_event(
            request="GET /assets/style.css HTTP/1.1",
            http_status="200",
            tts="0.020",
            isotime="2026-03-01T10:01:05+00:00",
        ),
        _make_event(
            request="GET /page HTTP/1.1",
            http_status="679",
            tts="0.200",
            isotime="2026-03-01T10:01:10+00:00",
        ),
    ]


@pytest.fixture
def historical_http_buckets() -> list[HttpAggregationBucket]:
    """30 days of stable HTTP aggregation data for anomaly baseline."""
    buckets = []
    for day in range(1, 31):
        buckets.append(
            HttpAggregationBucket(
                time_window=_ts(0, day=day),
                dimension="http_host",
                dimension_value="app.ontraport.com",
                total=1000,
                status_2xx=900,
                status_3xx=30,
                status_4xx=50,
                status_5xx=10,
                status_679=5,
                status_other=5,
                success_rate=0.90,
                client_error_rate=0.05,
                server_error_rate=0.01,
                known_content_error_rate=0.005,
                tts_p50=0.1,
                tts_p90=0.5,
                tts_p95=1.0,
                tts_p99=2.0,
                tts_max=5.0,
                tts_mean=0.3,
            )
        )
    return buckets
