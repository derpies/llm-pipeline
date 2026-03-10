"""Tests for the JSON loader (NDJSON and concatenated)."""

import io
import json

from llm_pipeline.email_analytics.loader import (
    discover_files,
    iter_concatenated_json,
    iter_event_chunks,
    iter_json_objects_from_stream,
    iter_ndjson_objects,
    load_file,
    parse_events,
)


class TestIterConcatenatedJson:
    def test_single_object(self):
        objs = list(iter_concatenated_json('{"a": 1}'))
        assert objs == [{"a": 1}]

    def test_multiple_objects_no_separator(self):
        text = '{"a": 1}{"b": 2}{"c": 3}'
        objs = list(iter_concatenated_json(text))
        assert objs == [{"a": 1}, {"b": 2}, {"c": 3}]

    def test_whitespace_between_objects(self):
        text = '{"a": 1}  \n  {"b": 2}\n{"c": 3}'
        objs = list(iter_concatenated_json(text))
        assert objs == [{"a": 1}, {"b": 2}, {"c": 3}]

    def test_empty_input(self):
        assert list(iter_concatenated_json("")) == []

    def test_whitespace_only(self):
        assert list(iter_concatenated_json("   \n\t  ")) == []

    def test_invalid_json_stops(self):
        text = '{"a": 1}invalid{"c": 3}'
        objs = list(iter_concatenated_json(text))
        assert objs == [{"a": 1}]

    def test_nested_objects(self):
        text = '{"a": {"b": 1}}{"c": [1, 2]}'
        objs = list(iter_concatenated_json(text))
        assert objs == [{"a": {"b": 1}}, {"c": [1, 2]}]


class TestIterJsonObjectsFromStream:
    def test_single_object(self):
        stream = io.StringIO('{"a": 1}')
        objs = list(iter_json_objects_from_stream(stream))
        assert objs == [{"a": 1}]

    def test_multiple_objects(self):
        stream = io.StringIO('{"a": 1}{"b": 2}{"c": 3}')
        objs = list(iter_json_objects_from_stream(stream))
        assert objs == [{"a": 1}, {"b": 2}, {"c": 3}]

    def test_spanning_buffer_boundaries(self):
        """Objects that span a tiny buffer boundary should still parse."""
        text = '{"key": "value"}{"key2": "value2"}'
        stream = io.StringIO(text)
        # buffer_size=8 forces multiple reads per object
        objs = list(iter_json_objects_from_stream(stream, buffer_size=8))
        assert objs == [{"key": "value"}, {"key2": "value2"}]

    def test_very_small_buffer(self):
        """Even a 1-char buffer should work (pathological but correct)."""
        text = '{"x": 1}'
        stream = io.StringIO(text)
        objs = list(iter_json_objects_from_stream(stream, buffer_size=1))
        assert objs == [{"x": 1}]

    def test_empty_input(self):
        stream = io.StringIO("")
        assert list(iter_json_objects_from_stream(stream)) == []

    def test_whitespace_between_objects(self):
        stream = io.StringIO('{"a": 1}  \n  {"b": 2}')
        objs = list(iter_json_objects_from_stream(stream))
        assert objs == [{"a": 1}, {"b": 2}]

    def test_invalid_json_mid_stream(self):
        """Should yield objects before the invalid section, then stop."""
        stream = io.StringIO('{"a": 1}GARBAGE{"b": 2}')
        objs = list(iter_json_objects_from_stream(stream))
        # First object succeeds; garbage causes the rest to be unparseable
        assert {"a": 1} in objs

    def test_large_object_across_boundaries(self):
        """A single large object split across many small buffers."""
        obj = {"data": "x" * 200}
        text = json.dumps(obj)
        stream = io.StringIO(text)
        objs = list(iter_json_objects_from_stream(stream, buffer_size=32))
        assert objs == [obj]


class TestIterNdjsonObjects:
    def test_single_object(self):
        stream = io.StringIO('{"a": 1}\n')
        objs = list(iter_ndjson_objects(stream))
        assert objs == [{"a": 1}]

    def test_multiple_objects(self):
        stream = io.StringIO('{"a": 1}\n{"b": 2}\n{"c": 3}\n')
        objs = list(iter_ndjson_objects(stream))
        assert objs == [{"a": 1}, {"b": 2}, {"c": 3}]

    def test_blank_lines_skipped(self):
        stream = io.StringIO('{"a": 1}\n\n\n{"b": 2}\n')
        objs = list(iter_ndjson_objects(stream))
        assert objs == [{"a": 1}, {"b": 2}]

    def test_empty_input(self):
        stream = io.StringIO("")
        assert list(iter_ndjson_objects(stream)) == []

    def test_whitespace_only_lines(self):
        stream = io.StringIO("   \n\t\n")
        assert list(iter_ndjson_objects(stream)) == []

    def test_invalid_line_skipped(self):
        stream = io.StringIO('{"a": 1}\nNOT JSON\n{"b": 2}\n')
        objs = list(iter_ndjson_objects(stream))
        assert objs == [{"a": 1}, {"b": 2}]

    def test_no_trailing_newline(self):
        stream = io.StringIO('{"a": 1}\n{"b": 2}')
        objs = list(iter_ndjson_objects(stream))
        assert objs == [{"a": 1}, {"b": 2}]

    def test_nested_objects(self):
        stream = io.StringIO('{"a": {"b": [1, 2]}}\n{"c": "d"}\n')
        objs = list(iter_ndjson_objects(stream))
        assert objs == [{"a": {"b": [1, 2]}}, {"c": "d"}]


class TestIterEventChunks:
    """Tests for iter_event_chunks — concatenated format (default for these fixtures)."""

    def test_correct_chunk_sizes(self, tmp_path):
        events = [
            {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered", "message": "250 OK"}
            for _ in range(5)
        ]
        f = tmp_path / "test.json"
        f.write_text("".join(json.dumps(e) for e in events))

        chunks = list(iter_event_chunks(f, chunk_size=2, json_format="concatenated"))
        assert len(chunks) == 3  # 2 + 2 + 1
        assert len(chunks[0][0]) == 2
        assert len(chunks[1][0]) == 2
        assert len(chunks[2][0]) == 1

    def test_inline_classification(self, tmp_path):
        events = [
            {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered", "message": "250 OK"},
            {"timestamp": "2025-01-01T10:05:00Z", "status": "bounced", "message": "550 5.1.1 User unknown"},
        ]
        f = tmp_path / "test.json"
        f.write_text("".join(json.dumps(e) for e in events))

        chunks = list(iter_event_chunks(f, chunk_size=10, json_format="concatenated"))
        assert len(chunks) == 1
        evts, clfs = chunks[0]
        assert len(evts) == 2
        assert len(clfs) == 2
        # Classifications should have been computed
        assert clfs[0].smtp_code == "250"
        assert clfs[1].smtp_code == "550"

    def test_multi_chunk_file(self, tmp_path):
        events = [
            {"timestamp": f"2025-01-01T10:{i:02d}:00Z", "status": "delivered", "message": "250 OK"}
            for i in range(7)
        ]
        f = tmp_path / "test.json"
        f.write_text("".join(json.dumps(e) for e in events))

        all_events = []
        all_clfs = []
        for evts, clfs in iter_event_chunks(f, chunk_size=3, json_format="concatenated"):
            assert len(evts) <= 3
            assert len(evts) == len(clfs)
            all_events.extend(evts)
            all_clfs.extend(clfs)

        assert len(all_events) == 7
        assert len(all_clfs) == 7

    def test_skips_invalid_records(self, tmp_path):
        """Invalid records should be skipped without breaking the stream."""
        valid = {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered"}
        invalid = {"status": "delivered"}  # missing timestamp
        f = tmp_path / "test.json"
        f.write_text(json.dumps(valid) + json.dumps(invalid) + json.dumps(valid))

        chunks = list(iter_event_chunks(f, chunk_size=10, json_format="concatenated"))
        total_events = sum(len(c[0]) for c in chunks)
        assert total_events == 2


class TestIterEventChunksNdjson:
    """Tests for iter_event_chunks with NDJSON format."""

    def test_correct_chunk_sizes(self, tmp_path):
        events = [
            {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered", "message": "250 OK"}
            for _ in range(5)
        ]
        f = tmp_path / "test.ndjson"
        f.write_text("\n".join(json.dumps(e) for e in events) + "\n")

        chunks = list(iter_event_chunks(f, chunk_size=2, json_format="ndjson"))
        assert len(chunks) == 3  # 2 + 2 + 1
        assert len(chunks[0][0]) == 2
        assert len(chunks[1][0]) == 2
        assert len(chunks[2][0]) == 1

    def test_inline_classification(self, tmp_path):
        events = [
            {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered", "message": "250 OK"},
            {"timestamp": "2025-01-01T10:05:00Z", "status": "bounced", "message": "550 5.1.1 User unknown"},
        ]
        f = tmp_path / "test.ndjson"
        f.write_text("\n".join(json.dumps(e) for e in events) + "\n")

        chunks = list(iter_event_chunks(f, chunk_size=10, json_format="ndjson"))
        assert len(chunks) == 1
        evts, clfs = chunks[0]
        assert len(evts) == 2
        assert len(clfs) == 2
        assert clfs[0].smtp_code == "250"
        assert clfs[1].smtp_code == "550"

    def test_skips_invalid_lines(self, tmp_path):
        valid = {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered"}
        f = tmp_path / "test.ndjson"
        f.write_text(
            json.dumps(valid) + "\nNOT JSON\n" + json.dumps(valid) + "\n"
        )

        chunks = list(iter_event_chunks(f, chunk_size=10, json_format="ndjson"))
        total_events = sum(len(c[0]) for c in chunks)
        assert total_events == 2

    def test_skips_invalid_records(self, tmp_path):
        valid = {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered"}
        invalid = {"status": "delivered"}  # valid JSON but missing timestamp
        f = tmp_path / "test.ndjson"
        f.write_text(
            json.dumps(valid) + "\n" + json.dumps(invalid) + "\n" + json.dumps(valid) + "\n"
        )

        chunks = list(iter_event_chunks(f, chunk_size=10, json_format="ndjson"))
        total_events = sum(len(c[0]) for c in chunks)
        assert total_events == 2

    def test_blank_lines_ignored(self, tmp_path):
        events = [
            {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered", "message": "250 OK"},
        ]
        f = tmp_path / "test.ndjson"
        f.write_text("\n\n" + json.dumps(events[0]) + "\n\n")

        chunks = list(iter_event_chunks(f, chunk_size=10, json_format="ndjson"))
        assert sum(len(c[0]) for c in chunks) == 1


class TestParseEvents:
    def test_valid_events(self):
        data = [
            {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered", "message": "250 OK"},
            {"timestamp": "2025-01-01T11:00:00Z", "status": "bounced", "message": "550 nope"},
        ]
        text = "".join(json.dumps(d) for d in data)
        events = parse_events(text)
        assert len(events) == 2
        assert events[0].status == "delivered"
        assert events[1].status == "bounced"

    def test_skips_invalid_records(self):
        # Missing required 'timestamp' field
        text = '{"status": "delivered"}{"timestamp": "2025-01-01T10:00:00Z", "status": "ok"}'
        events = parse_events(text)
        assert len(events) == 1
        assert events[0].status == "ok"


class TestLoadFile:
    def test_load_from_file(self, tmp_path):
        data = {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered", "message": "250 OK"}
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data))
        events = load_file(f)
        assert len(events) == 1
        assert events[0].recipient_domain == ""

    def test_load_multiple_events(self, tmp_path):
        data = [
            {"timestamp": "2025-01-01T10:00:00Z", "status": "delivered", "recipient": "a@x.com"},
            {"timestamp": "2025-01-01T11:00:00Z", "status": "bounced", "recipient": "b@y.com"},
        ]
        f = tmp_path / "test.json"
        f.write_text("".join(json.dumps(d) for d in data))
        events = load_file(f)
        assert len(events) == 2
        assert events[0].recipient_domain == "x.com"
        assert events[1].recipient_domain == "y.com"


class TestDiscoverFiles:
    def test_single_file(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text("{}")
        assert discover_files(f) == [str(f)]

    def test_directory(self, tmp_path):
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")
        (tmp_path / "c.txt").write_text("not json")
        files = discover_files(tmp_path)
        assert len(files) == 2
        assert all(f.endswith(".json") for f in files)

    def test_nonexistent_path(self, tmp_path):
        assert discover_files(tmp_path / "nope") == []

    def test_empty_directory(self, tmp_path):
        assert discover_files(tmp_path) == []
