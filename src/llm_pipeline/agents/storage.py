"""Postgres persistence and markdown output for investigation cycle results."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis
from llm_pipeline.agents.report_models import InvestigationReport
from llm_pipeline.email_analytics.models import (
    InvestigationFindingRecord,
    InvestigationHypothesisRecord,
    InvestigationRunRecord,
)
from llm_pipeline.email_analytics.storage import get_engine

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output/investigations")


def _safe_json_loads(value, default):
    """Parse JSON string, returning default for non-string or invalid values."""
    if not isinstance(value, str):
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def validate_finding(f: Finding) -> list[str]:
    """Return quality warnings for a finding (non-blocking)."""
    warnings: list[str] = []
    if not f.statement.strip():
        warnings.append("empty_statement")
    elif len(f.statement.strip()) < 10:
        warnings.append("statement_too_short")
    if f.status == FindingStatus.CONFIRMED and not f.evidence:
        warnings.append("confirmed_without_evidence")
    if f.tool_use_failed:
        warnings.append("tool_use_failed")
    return warnings


def validate_hypothesis(h: Hypothesis) -> list[str]:
    """Return quality warnings for a hypothesis (non-blocking)."""
    warnings: list[str] = []
    if not h.statement.strip():
        warnings.append("empty_statement")
    return warnings


def store_investigation_results(
    run_id: str,
    findings: list[Finding],
    hypotheses: list[Hypothesis],
    checkpoint_digest: str,
    iteration_count: int,
    started_at: datetime,
    completed_at: datetime | None = None,
    label: str = "",
    status: str = "success",
    is_dry_run: bool = False,
    ml_run_id: str | None = None,
    quality_warnings: list[str] | None = None,
) -> None:
    """Persist investigation results to Postgres (atomic commit)."""
    logger.info(
        "store_investigation started run_id=%s findings=%d hypotheses=%d status=%s",
        run_id,
        len(findings),
        len(hypotheses),
        status,
    )
    t0 = time.monotonic()
    engine = get_engine()
    run_warnings = list(quality_warnings or [])

    with Session(engine) as session:
        run = InvestigationRunRecord(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at or datetime.now(UTC),
            iteration_count=iteration_count,
            finding_count=len(findings),
            hypothesis_count=len(hypotheses),
            checkpoint_digest=checkpoint_digest,
            label=label,
            status=status,
            is_dry_run=is_dry_run,
            ml_run_id=ml_run_id,
            quality_warnings=json.dumps(run_warnings),
        )
        session.add(run)

        for f in findings:
            finding_warnings = validate_finding(f)
            if finding_warnings:
                logger.warning(
                    "Finding quality warnings for '%s': %s",
                    f.topic_title,
                    finding_warnings,
                )
                run_warnings.extend(f"{f.topic_title}: {w}" for w in finding_warnings)

            session.add(
                InvestigationFindingRecord(
                    run_id=run_id,
                    topic_title=f.topic_title,
                    statement=f.statement,
                    status=f.status.value,
                    evidence=json.dumps(f.evidence),
                    metrics_cited=json.dumps(f.metrics_cited),
                    is_fallback=f.tool_use_failed,
                    quality_warnings=json.dumps(finding_warnings),
                )
            )

        for h in hypotheses:
            hyp_warnings = validate_hypothesis(h)
            if hyp_warnings:
                logger.warning(
                    "Hypothesis quality warnings for '%s': %s",
                    h.topic_title,
                    hyp_warnings,
                )
                run_warnings.extend(f"{h.topic_title}: {w}" for w in hyp_warnings)

            session.add(
                InvestigationHypothesisRecord(
                    run_id=run_id,
                    topic_title=h.topic_title,
                    statement=h.statement,
                    reasoning=h.reasoning,
                )
            )

        # Update run-level warnings with aggregated finding/hypothesis warnings
        run.quality_warnings = json.dumps(run_warnings)

        session.commit()
        elapsed = time.monotonic() - t0
        logger.info(
            "store_investigation completed run_id=%s "
            "findings=%d hypotheses=%d warnings=%d elapsed_s=%.2f",
            run_id,
            len(findings),
            len(hypotheses),
            len(run_warnings),
            elapsed,
        )


def load_investigation(run_id: str, *, label: str | None = None) -> dict | None:
    """Load a complete investigation result from Postgres.

    When multiple investigations share the same run_id (e.g. A/B tests),
    pass ``label`` to disambiguate. Without a label, returns the most recent.

    Returns dict with run metadata, Finding/Hypothesis objects, and digest,
    or None if no investigation found.
    """
    engine = get_engine()

    with Session(engine) as session:
        stmt = select(InvestigationRunRecord).where(InvestigationRunRecord.run_id == run_id)
        if label is not None:
            stmt = stmt.where(InvestigationRunRecord.label == label)
        stmt = stmt.order_by(InvestigationRunRecord.id.desc()).limit(1)
        run = session.execute(stmt).scalar_one_or_none()
        if run is None:
            return None

        # Use the DB row id to scope findings/hypotheses by creation time
        run_db_id = run.id

        # Findings/hypotheses are committed in the same transaction as the
        # run record, so they share the exact same DB-assigned created_at.
        finding_rows = (
            session.execute(
                select(InvestigationFindingRecord).where(
                    InvestigationFindingRecord.run_id == run_id,
                    InvestigationFindingRecord.created_at == run.created_at,
                )
            )
            .scalars()
            .all()
        )

        hypothesis_rows = (
            session.execute(
                select(InvestigationHypothesisRecord).where(
                    InvestigationHypothesisRecord.run_id == run_id,
                    InvestigationHypothesisRecord.created_at == run.created_at,
                )
            )
            .scalars()
            .all()
        )

        findings = [
            Finding(
                topic_title=r.topic_title,
                statement=r.statement,
                status=FindingStatus(r.status),
                evidence=json.loads(r.evidence),
                metrics_cited=json.loads(r.metrics_cited),
                created_at=r.created_at,
                run_id=run_id,
            )
            for r in finding_rows
        ]

        hypotheses = [
            Hypothesis(
                topic_title=r.topic_title,
                statement=r.statement,
                reasoning=r.reasoning,
                created_at=r.created_at,
                run_id=run_id,
            )
            for r in hypothesis_rows
        ]

        return {
            "run_id": run.run_id,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "iteration_count": run.iteration_count,
            "findings": findings,
            "hypotheses": hypotheses,
            "checkpoint_digest": run.checkpoint_digest,
            "label": getattr(run, "label", ""),
            "status": getattr(run, "status", "success"),
            "is_dry_run": getattr(run, "is_dry_run", False),
            "ml_run_id": getattr(run, "ml_run_id", None),
            "quality_warnings": _safe_json_loads(getattr(run, "quality_warnings", "[]"), []),
        }


def write_investigation_markdown(
    run_id: str,
    findings: list[Finding],
    hypotheses: list[Hypothesis],
    checkpoint_digest: str,
    iteration_count: int,
    started_at: datetime,
    completed_at: datetime | None = None,
    label: str = "",
    spend_summary: str = "",
    output_dir: Path | None = None,
    status: str = "success",
    is_dry_run: bool = False,
) -> Path:
    """Write investigation results to a human-readable markdown file.

    Returns the path to the written file.
    """
    t0 = time.monotonic()
    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    ts = (completed_at or started_at or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    parts = [run_id, ts]
    if label:
        parts.append(label)
    slug = "-".join(parts)
    path = out / f"{slug}.md"

    completed = completed_at or datetime.now(UTC)
    duration = completed - started_at
    mins, secs = divmod(int(duration.total_seconds()), 60)

    lines: list[str] = []

    # Header
    lines.append(f"# Investigation Report — {run_id}")
    if label:
        lines.append(f"**Label:** {label}")
    lines.append("")
    lines.append(f"**Status:** {status.upper()}")
    if is_dry_run:
        lines.append("**Mode:** DRY RUN (no real LLM calls)")
    lines.append(f"**Started:** {started_at:%Y-%m-%d %H:%M:%S UTC}")
    lines.append(f"**Completed:** {completed:%Y-%m-%d %H:%M:%S UTC}")
    lines.append(f"**Duration:** {mins}m {secs}s")
    lines.append(f"**Iterations:** {iteration_count}")
    if spend_summary:
        lines.append(f"**Spend:** {spend_summary}")
    lines.append("")

    # Summary counts
    by_status: dict[str, list[Finding]] = {}
    for f in findings:
        by_status.setdefault(f.status.value, []).append(f)

    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- **{len(findings)}** findings: "
        + ", ".join(f"{len(v)} {k}" for k, v in sorted(by_status.items()))
    )
    lines.append(f"- **{len(hypotheses)}** hypotheses (untested)")
    lines.append("")

    # Findings by status
    for status in FindingStatus:
        group = by_status.get(status.value, [])
        if not group:
            continue

        lines.append(f"## Findings — {status.value.upper()}")
        lines.append("")

        for f in group:
            fallback_tag = " [FALLBACK]" if f.tool_use_failed else ""
            lines.append(f"### {f.topic_title}{fallback_tag}")
            lines.append("")
            lines.append(f"> {f.statement}")
            lines.append("")
            if f.metrics_cited:
                lines.append("**Metrics cited:**")
                for k, v in f.metrics_cited.items():
                    lines.append(f"- `{k}`: {v}")
                lines.append("")
            if f.evidence:
                lines.append("**Evidence:**")
                for e in f.evidence:
                    lines.append(f"- {e}")
                lines.append("")

    # Hypotheses
    if hypotheses:
        lines.append("## Hypotheses (untested)")
        lines.append("")
        for h in hypotheses:
            lines.append(f"### {h.topic_title}")
            lines.append("")
            lines.append(f"> {h.statement}")
            lines.append("")
            if h.reasoning:
                lines.append(f"**Reasoning:** {h.reasoning}")
                lines.append("")

    # Quality warnings
    all_warnings = []
    for f in findings:
        all_warnings.extend(validate_finding(f))
    for h in hypotheses:
        all_warnings.extend(validate_hypothesis(h))
    if all_warnings:
        lines.append("## Quality Warnings")
        lines.append("")
        for w in all_warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Checkpoint digest (raw)
    if checkpoint_digest:
        lines.append("---")
        lines.append("")
        lines.append("## Raw Checkpoint Digest")
        lines.append("")
        lines.append("```")
        lines.append(checkpoint_digest)
        lines.append("```")
        lines.append("")

    path.write_text("\n".join(lines))
    elapsed = time.monotonic() - t0
    logger.info(
        "write_investigation_markdown completed run_id=%s path=%s elapsed_s=%.2f",
        run_id,
        path,
        elapsed,
    )
    return path


def store_investigation_report(
    run_id: str,
    report: InvestigationReport,
) -> None:
    """Render and persist an InvestigationReport to Postgres."""
    from llm_pipeline.agents.report_renderer import render_json, render_markdown
    from llm_pipeline.email_analytics.models import InvestigationReportRecord

    logger.info("store_investigation_report started run_id=%s", run_id)
    t0 = time.monotonic()

    report_json = render_json(report)
    report_md = render_markdown(report)

    engine = get_engine()
    with Session(engine) as session:
        session.add(
            InvestigationReportRecord(
                run_id=run_id,
                report_json=report_json,
                report_markdown=report_md,
            )
        )
        session.commit()

    elapsed = time.monotonic() - t0
    logger.info(
        "store_investigation_report completed run_id=%s elapsed_s=%.2f",
        run_id,
        elapsed,
    )


def load_investigation_report(run_id: str) -> InvestigationReport | None:
    """Load an InvestigationReport from Postgres by run_id."""
    from sqlalchemy import select as sa_select

    from llm_pipeline.agents.report_models import InvestigationReport
    from llm_pipeline.email_analytics.models import InvestigationReportRecord

    engine = get_engine()
    with Session(engine) as session:
        stmt = (
            sa_select(InvestigationReportRecord)
            .where(InvestigationReportRecord.run_id == run_id)
            .order_by(InvestigationReportRecord.id.desc())
            .limit(1)
        )
        row = session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None

        return InvestigationReport.model_validate_json(row.report_json)


def write_investigation_report_files(
    run_id: str,
    report: InvestigationReport,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Write report JSON and markdown files to disk.

    Returns (json_path, md_path).
    """
    from llm_pipeline.agents.report_renderer import render_json, render_markdown

    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / f"{run_id}-report.json"
    md_path = out / f"{run_id}-report.md"

    json_path.write_text(render_json(report))
    md_path.write_text(render_markdown(report))

    logger.info(
        "write_investigation_report_files run_id=%s json=%s md=%s",
        run_id,
        json_path,
        md_path,
    )
    return json_path, md_path
