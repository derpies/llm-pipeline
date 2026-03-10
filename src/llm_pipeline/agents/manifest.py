"""Append-only JSONL manifest for tracking pipeline runs.

Each completed command appends one JSON line to output/manifest.jsonl,
mapping run IDs to input files, timing, cost, and a one-line summary.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MANIFEST_PATH = Path("output/manifest.jsonl")


def append_manifest(
    run_id: str,
    command: str,
    source_files: list[str],
    started_at: datetime,
    completed_at: datetime,
    status: str,
    summary: str,
    cost_usd: float,
    output_files: list[str],
    label: str = "",
    ml_run_id: str = "",
    manifest_path: Path | None = None,
) -> Path:
    """Append a single manifest entry as one JSON line.

    Returns the path to the manifest file.
    """
    path = manifest_path or DEFAULT_MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "run_id": run_id,
        "command": command,
        "source_files": source_files,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": int((completed_at - started_at).total_seconds()),
        "status": status,
        "label": label,
        "ml_run_id": ml_run_id,
        "summary": summary,
        "cost_usd": round(cost_usd, 4),
        "output_files": output_files,
    }

    line = json.dumps(entry, default=str, separators=(",", ":"))

    with open(path, "a") as f:
        f.write(line + "\n")
        f.flush()

    logger.info("Manifest appended run_id=%s command=%s path=%s", run_id, command, path)
    return path
