"""NDJSON streaming loader for HTTP access log events.

Reads line-by-line, validates into HttpAccessEvent, yields chunks of
configurable size. Memory is bounded by chunk_size × event_size.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

from llm_pipeline.http_analytics.models import HttpAccessEvent

logger = logging.getLogger(__name__)


def discover_files(path: str | Path) -> list[str]:
    """List JSON files at the given path.

    If *path* is a file, returns it as a single-element list.
    If *path* is a directory, returns all ``*.json`` files (non-recursive).
    """
    p = Path(path)
    if p.is_file():
        return [str(p)]
    if p.is_dir():
        return sorted(str(f) for f in p.glob("*.json"))
    return []


def iter_http_event_chunks(
    path: str | Path,
    chunk_size: int | None = None,
) -> Iterator[list[HttpAccessEvent]]:
    """Stream an NDJSON file in chunks, yielding lists of validated events.

    Each yielded list contains at most *chunk_size* events. Malformed lines
    and validation failures are skipped with a warning.
    """
    from llm_pipeline.config import settings

    chunk_size = chunk_size or getattr(settings, "http_batch_size", 50000)

    p = Path(path)
    events: list[HttpAccessEvent] = []
    skipped = 0

    with p.open(encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("NDJSON decode error on line %d: %s", lineno, exc)
                skipped += 1
                continue

            try:
                event = HttpAccessEvent.model_validate(raw)
            except Exception as exc:
                logger.warning("Skipping invalid HTTP event on line %d: %s", lineno, exc)
                skipped += 1
                continue

            events.append(event)

            if len(events) >= chunk_size:
                yield events
                events = []

    if events:
        yield events

    if skipped:
        logger.info("Skipped %d malformed/invalid records from %s", skipped, path)
