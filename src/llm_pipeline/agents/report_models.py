"""Re-export from canonical location for backward compatibility.

The report models have moved to llm_pipeline.domains.email_delivery.report_models.
"""

from llm_pipeline.domains.email_delivery.report_models import (  # noqa: F401
    CompletenessRow,
    ComplianceRow,
    ConfirmedIssue,
    InvestigationNotes,
    InvestigationReport,
    Observation,
    SegmentHealthRow,
    StructuredReport,
    TrendRow,
    TrendSummary,
)
