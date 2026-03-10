"""Structured logging setup using structlog."""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import structlog

from llm_pipeline.config import settings


def setup_logging(command: str = "", run_id: str = "") -> None:
    """Configure structlog for the application.

    Logs to stderr (human-readable) and to a persistent JSON file
    in settings.log_dir. File logs are always JSON and always DEBUG
    level for full traceability.

    Filename pattern: {timestamp}-{command}[-{run_id}].log
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_format == "json":
        console_renderer: structlog.types.Processor = (
            structlog.processors.JSONRenderer()
        )
    else:
        console_renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Console handler — uses configured level and format
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            console_renderer,
        ],
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(settings.log_level)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(console_handler)

    # File handler — always JSON, always DEBUG for full audit trail
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    parts = [ts]
    if command:
        parts.append(command)
    if run_id:
        parts.append(run_id)
    filename = "-".join(parts) + ".log"
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    file_handler = logging.FileHandler(log_dir / filename)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    # Root level must be DEBUG so file handler receives everything
    root.setLevel(logging.DEBUG)
