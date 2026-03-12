"""Tests for the HTTP NDJSON loader."""

import json
from pathlib import Path

import pytest

from llm_pipeline.http_analytics.loader import discover_files, iter_http_event_chunks
from llm_pipeline.http_analytics.models import RequestCategory


@pytest.fixture
def sample_ndjson(tmp_path: Path) -> Path:
    """Create a small NDJSON file with valid HTTP events."""
    records = [
        {
            "isotime": "2026-03-01T10:00:00+00:00",
            "server": "edge001",
            "remoteaddr": "1.2.3.4",
            "http-host": "app.ontraport.com",
            "request": "GET /page HTTP/1.1",
            "http-status": "200",
            "sizesent": "1024",
            "tts": "0.100",
            "upstream": "10.1.0.1:8080",
            "http-referrer": "",
            "useragent": "Chrome/120",
            "applempp": "FALSE",
        },
        {
            "isotime": "2026-03-01T10:00:01+00:00",
            "server": "edge001",
            "remoteaddr": "5.6.7.8",
            "http-host": "track.ontralink.com",
            "request": "GET /o?abc HTTP/1.1",
            "http-status": "200",
            "sizesent": "43",
            "tts": "0.010",
            "upstream": "10.1.0.2:8080",
            "http-referrer": "",
            "useragent": "",
            "applempp": "TRUE",
        },
        {
            "isotime": "2026-03-01T10:00:02+00:00",
            "server": "edge001",
            "remoteaddr": "9.0.1.2",
            "http-host": "app.ontraport.com",
            "request": "GET /wp-login.php HTTP/1.1",
            "http-status": "404",
            "sizesent": "0",
            "tts": "0.002",
            "upstream": "",
            "http-referrer": "",
            "useragent": "zgrab/0.x",
            "applempp": "FALSE",
        },
    ]
    p = tmp_path / "test.json"
    with p.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return p


class TestDiscoverFiles:
    def test_single_file(self, sample_ndjson: Path):
        files = discover_files(sample_ndjson)
        assert files == [str(sample_ndjson)]

    def test_directory(self, tmp_path: Path):
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")
        (tmp_path / "c.txt").write_text("not json")
        files = discover_files(tmp_path)
        assert len(files) == 2
        assert all(f.endswith(".json") for f in files)

    def test_nonexistent(self, tmp_path: Path):
        files = discover_files(tmp_path / "nope")
        assert files == []


class TestIterHttpEventChunks:
    def test_loads_all_events(self, sample_ndjson: Path):
        chunks = list(iter_http_event_chunks(sample_ndjson, chunk_size=100))
        assert len(chunks) == 1
        assert len(chunks[0]) == 3

    def test_chunking(self, sample_ndjson: Path):
        chunks = list(iter_http_event_chunks(sample_ndjson, chunk_size=2))
        assert len(chunks) == 2
        assert len(chunks[0]) == 2
        assert len(chunks[1]) == 1

    def test_classifications_applied(self, sample_ndjson: Path):
        chunks = list(iter_http_event_chunks(sample_ndjson, chunk_size=100))
        events = chunks[0]
        # First event: page load
        assert events[0].request_category == RequestCategory.PAGE_LOAD
        # Second: tracking pixel
        assert events[1].request_category == RequestCategory.TRACKING_PIXEL
        assert events[1].is_apple_mpp is True
        # Third: PHP probe
        assert events[2].request_category == RequestCategory.PHP_PROBE

    def test_skips_malformed_lines(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text(
            '{"isotime":"2026-03-01T10:00:00+00:00","request":"GET / HTTP/1.1","http-status":"200"}\n'
            "NOT JSON\n"
            '{"isotime":"2026-03-01T10:00:01+00:00","request":"GET /x HTTP/1.1","http-status":"200"}\n'
        )
        chunks = list(iter_http_event_chunks(p, chunk_size=100))
        assert len(chunks) == 1
        assert len(chunks[0]) == 2  # 2 valid, 1 skipped

    def test_empty_file(self, tmp_path: Path):
        p = tmp_path / "empty.json"
        p.write_text("")
        chunks = list(iter_http_event_chunks(p, chunk_size=100))
        assert chunks == []
