"""Tests for the append-only manifest writer."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from llm_pipeline.agents.manifest import append_manifest


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    return tmp_path / "manifest.jsonl"


def _make_times():
    started = datetime(2026, 3, 10, 14, 0, 0, tzinfo=UTC)
    completed = started + timedelta(seconds=120)
    return started, completed


class TestAppendManifest:
    def test_creates_file_and_writes_one_line(self, manifest_path: Path):
        started, completed = _make_times()
        result = append_manifest(
            run_id="abc-123",
            command="investigate",
            source_files=["raw-logs/file1"],
            started_at=started,
            completed_at=completed,
            status="success",
            summary="2 findings",
            cost_usd=1.23,
            output_files=["output/abc-123.md"],
            manifest_path=manifest_path,
        )

        assert result == manifest_path
        assert manifest_path.exists()
        lines = manifest_path.read_text().strip().splitlines()
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["run_id"] == "abc-123"
        assert entry["command"] == "investigate"
        assert entry["source_files"] == ["raw-logs/file1"]
        assert entry["duration_seconds"] == 120
        assert entry["status"] == "success"
        assert entry["summary"] == "2 findings"
        assert entry["cost_usd"] == 1.23
        assert entry["output_files"] == ["output/abc-123.md"]

    def test_appends_multiple_entries(self, manifest_path: Path):
        started, completed = _make_times()
        for i in range(3):
            append_manifest(
                run_id=f"run-{i}",
                command="analyze_email",
                source_files=[f"file-{i}"],
                started_at=started,
                completed_at=completed,
                status="success",
                summary=f"run {i}",
                cost_usd=0.0,
                output_files=[],
                manifest_path=manifest_path,
            )

        lines = manifest_path.read_text().strip().splitlines()
        assert len(lines) == 3
        run_ids = [json.loads(line)["run_id"] for line in lines]
        assert run_ids == ["run-0", "run-1", "run-2"]

    def test_optional_fields_default_empty(self, manifest_path: Path):
        started, completed = _make_times()
        append_manifest(
            run_id="x",
            command="investigate",
            source_files=[],
            started_at=started,
            completed_at=completed,
            status="success",
            summary="",
            cost_usd=0.0,
            output_files=[],
            manifest_path=manifest_path,
        )

        entry = json.loads(manifest_path.read_text().strip())
        assert entry["label"] == ""
        assert entry["ml_run_id"] == ""

    def test_label_and_ml_run_id(self, manifest_path: Path):
        started, completed = _make_times()
        append_manifest(
            run_id="x",
            command="investigate",
            source_files=[],
            started_at=started,
            completed_at=completed,
            status="success",
            summary="",
            cost_usd=0.0,
            output_files=[],
            label="B-with-knowledge",
            ml_run_id="ml-456",
            manifest_path=manifest_path,
        )

        entry = json.loads(manifest_path.read_text().strip())
        assert entry["label"] == "B-with-knowledge"
        assert entry["ml_run_id"] == "ml-456"

    def test_creates_parent_directories(self, tmp_path: Path):
        deep_path = tmp_path / "a" / "b" / "manifest.jsonl"
        started, completed = _make_times()
        append_manifest(
            run_id="x",
            command="test",
            source_files=[],
            started_at=started,
            completed_at=completed,
            status="success",
            summary="",
            cost_usd=0.0,
            output_files=[],
            manifest_path=deep_path,
        )
        assert deep_path.exists()

    def test_cost_rounded_to_4_decimals(self, manifest_path: Path):
        started, completed = _make_times()
        append_manifest(
            run_id="x",
            command="test",
            source_files=[],
            started_at=started,
            completed_at=completed,
            status="success",
            summary="",
            cost_usd=1.23456789,
            output_files=[],
            manifest_path=manifest_path,
        )

        entry = json.loads(manifest_path.read_text().strip())
        assert entry["cost_usd"] == 1.2346
