"""ML-as-a-tool — read-only wrappers around email_analytics storage queries."""

from llm_pipeline.tools.ml.compare_dimensions import compare_dimensions
from llm_pipeline.tools.ml.get_aggregations import get_aggregations
from llm_pipeline.tools.ml.get_anomalies import get_anomalies
from llm_pipeline.tools.ml.get_data_completeness import get_data_completeness
from llm_pipeline.tools.ml.get_ml_report_summary import get_ml_report_summary
from llm_pipeline.tools.ml.get_trends import get_trends

# --- Tool role declarations for auto-discovery ---
TOOL_ROLES = [
    (get_aggregations, ["investigator"]),
    (get_anomalies, ["investigator", "orchestrator"]),
    (get_trends, ["investigator", "orchestrator"]),
    (get_ml_report_summary, ["investigator", "orchestrator"]),
    (get_data_completeness, ["investigator"]),
    (compare_dimensions, ["investigator"]),
]

__all__ = [
    "get_aggregations",
    "get_anomalies",
    "get_trends",
    "get_ml_report_summary",
    "get_data_completeness",
    "compare_dimensions",
    "TOOL_ROLES",
]
