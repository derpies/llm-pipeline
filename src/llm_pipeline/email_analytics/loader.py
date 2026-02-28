"""File loading and JSON parsing for email delivery events.

Supports two formats:
- **NDJSON** (newline-delimited): one JSON object per line — fast ``readline()`` path.
- **Concatenated JSON**: ``{…}{…}{…}`` with no delimiter — ``raw_decode()`` path.

Includes streaming variants for production-scale files (millions of records).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Literal

from llm_pipeline.email_analytics.models import DeliveryEvent, SmtpClassification

logger = logging.getLogger(__name__)

JsonFormat = Literal["ndjson", "concatenated"]


def iter_concatenated_json(text: str) -> Iterator[dict]:
    """Yield individual JSON objects from concatenated (non-delimited) JSON text.

    Uses json.JSONDecoder.raw_decode() to handle ``{...}{...}{...}`` without
    any separator between objects.
    """
    decoder = json.JSONDecoder()
    idx = 0
    length = len(text)

    while idx < length:
        # Skip whitespace between objects
        while idx < length and text[idx] in " \t\n\r":
            idx += 1
        if idx >= length:
            break

        try:
            obj, end_idx = decoder.raw_decode(text, idx)
            yield obj
            idx = end_idx
        except json.JSONDecodeError as exc:
            logger.warning("JSON decode error at position %d: %s", idx, exc)
            break


def parse_events(text: str) -> list[DeliveryEvent]:
    """Parse concatenated JSON text into DeliveryEvent instances.

    Skips records that fail validation and logs warnings.
    """
    events: list[DeliveryEvent] = []
    for raw in iter_concatenated_json(text):
        try:
            events.append(DeliveryEvent.model_validate(raw))
        except Exception as exc:
            logger.warning("Skipping invalid event: %s", exc)
    return events


def load_file(path: str | Path) -> list[DeliveryEvent]:
    """Load delivery events from a single JSON file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    return parse_events(text)


def iter_json_objects_from_stream(
    file_handle: IO[str],
    buffer_size: int = 65536,
) -> Iterator[dict]:
    """Yield JSON objects from a stream, reading *buffer_size* chars at a time.

    Handles objects that span buffer boundaries by accumulating unprocessed
    text between reads.  Uses ``json.JSONDecoder.raw_decode()`` for parsing.
    """
    decoder = json.JSONDecoder()
    buf = ""

    while True:
        chunk = file_handle.read(buffer_size)
        if not chunk and not buf:
            break
        buf += chunk
        eof = not chunk  # True when the file is exhausted

        idx = 0
        length = len(buf)

        while idx < length:
            # Skip whitespace
            while idx < length and buf[idx] in " \t\n\r":
                idx += 1
            if idx >= length:
                break

            try:
                obj, end_idx = decoder.raw_decode(buf, idx)
                yield obj
                idx = end_idx
            except json.JSONDecodeError:
                if eof:
                    # No more data coming — whatever remains is unparseable
                    if idx < length:
                        logger.warning(
                            "Unparseable trailing data (%d chars) at end of stream",
                            length - idx,
                        )
                    buf = ""
                    break
                # Might be an incomplete object — keep the tail for next read
                break

        buf = buf[idx:]

        if eof:
            break


def iter_ndjson_objects(file_handle: IO[str]) -> Iterator[dict]:
    """Yield JSON objects from a newline-delimited JSON (NDJSON) stream.

    One ``json.loads()`` per line — no buffering beyond a single line,
    so memory is bounded by the longest line in the file.  Blank lines
    and lines that fail to parse are skipped with a warning.
    """
    for lineno, line in enumerate(file_handle, 1):
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("NDJSON decode error on line %d: %s", lineno, exc)


def iter_event_chunks(
    path: str | Path,
    chunk_size: int | None = None,
    json_format: JsonFormat | None = None,
) -> Iterator[tuple[list[DeliveryEvent], list[SmtpClassification]]]:
    """Stream a file in chunks, yielding (events, classifications) tuples.

    Each yielded tuple contains at most *chunk_size* validated events and
    their corresponding SMTP classifications.  Loading, validation, and
    classification happen in a single streaming pass — raw events never
    accumulate beyond *chunk_size*.

    *json_format* selects the parser: ``"ndjson"`` (one object per line) or
    ``"concatenated"`` (``{…}{…}{…}``).  Defaults to ``settings.email_json_format``.
    """
    from llm_pipeline.config import settings
    from llm_pipeline.email_analytics.smtp_classifier import classify_smtp_response

    chunk_size = chunk_size or settings.email_batch_size
    json_format = json_format or settings.email_json_format

    p = Path(path)
    events: list[DeliveryEvent] = []
    classifications: list[SmtpClassification] = []

    with p.open(encoding="utf-8", errors="replace") as fh:
        if json_format == "ndjson":
            obj_iter = iter_ndjson_objects(fh)
        else:
            obj_iter = iter_json_objects_from_stream(
                fh, buffer_size=settings.email_stream_buffer_size
            )

        for raw in obj_iter:
            try:
                event = DeliveryEvent.model_validate(raw)
            except Exception as exc:
                logger.warning("Skipping invalid event: %s", exc)
                continue

            events.append(event)
            classifications.append(classify_smtp_response(event.message))

            if len(events) >= chunk_size:
                yield events, classifications
                events = []
                classifications = []

    if events:
        yield events, classifications


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
