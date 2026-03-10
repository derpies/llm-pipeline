"""Generic database primitives — Base, engine, and schema init.

These are domain-agnostic. Every SQLAlchemy model in the project
inherits from Base, and every module that needs Postgres uses get_engine().
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase

from llm_pipeline.config import settings

logger = logging.getLogger(__name__)

_engine = None


class Base(DeclarativeBase):
    pass


def get_engine():
    global _engine
    if _engine is None:
        url = settings.database_url
        # Ensure we use psycopg3 driver, not the legacy psycopg2
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        _engine = create_engine(url)
    return _engine


def init_db() -> None:
    """Create all tables registered on Base.metadata. Idempotent.

    Imports model modules so their tables are registered with Base
    before calling create_all, then runs lightweight migrations.
    """
    import llm_pipeline.agents.storage_models  # noqa: F401
    import llm_pipeline.email_analytics.models  # noqa: F401
    import llm_pipeline.knowledge.models  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(engine)

    # Add columns to existing tables (safe: IF NOT EXISTS is idempotent)
    _migrate_add_columns(engine)
    logger.info("Database tables created/verified")


def _migrate_add_columns(engine) -> None:
    """Add columns that were introduced after the initial schema.

    Each statement uses ADD COLUMN IF NOT EXISTS (Postgres 9.6+),
    so this is safe to run repeatedly.
    """
    migrations = [
        # Investigation run quality gate columns
        "ALTER TABLE investigation_runs ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'success'",
        "ALTER TABLE investigation_runs ADD COLUMN IF NOT EXISTS is_dry_run BOOLEAN DEFAULT FALSE",
        "ALTER TABLE investigation_runs ADD COLUMN IF NOT EXISTS ml_run_id VARCHAR(64)",
        "ALTER TABLE investigation_runs ADD COLUMN IF NOT EXISTS quality_warnings TEXT DEFAULT '[]'",
        # Investigation finding quality gate columns
        "ALTER TABLE investigation_findings ADD COLUMN IF NOT EXISTS is_fallback BOOLEAN DEFAULT FALSE",
        "ALTER TABLE investigation_findings ADD COLUMN IF NOT EXISTS quality_warnings TEXT DEFAULT '[]'",
        # Latency p99/max columns on aggregations
        "ALTER TABLE email_aggregations ADD COLUMN IF NOT EXISTS pre_edge_latency_p99 FLOAT",
        "ALTER TABLE email_aggregations ADD COLUMN IF NOT EXISTS pre_edge_latency_max FLOAT",
        "ALTER TABLE email_aggregations ADD COLUMN IF NOT EXISTS delivery_time_p99 FLOAT",
        "ALTER TABLE email_aggregations ADD COLUMN IF NOT EXISTS delivery_time_max FLOAT",
    ]

    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception as e:
                # Table might not exist yet (first run) — create_all handles that
                logger.debug("Migration skipped (expected on fresh DB): %s", e)
        conn.commit()
