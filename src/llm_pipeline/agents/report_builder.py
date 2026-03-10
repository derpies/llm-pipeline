"""Re-export from canonical location for backward compatibility.

The report builder has moved to llm_pipeline.domains.email_delivery.report_builder.
"""

from llm_pipeline.domains.email_delivery.report_builder import (  # noqa: F401
    assemble_full_report,
    assemble_investigation_notes,
    assemble_structured_report,
    build_compliance,
    build_confirmed_issues,
    build_data_completeness,
    build_segment_health,
    build_trend_summary,
)
