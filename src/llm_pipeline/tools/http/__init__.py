"""HTTP ML-as-a-tool — read-only wrappers around http_analytics storage queries."""

from llm_pipeline.tools.http.compare_http_dimensions import compare_http_dimensions
from llm_pipeline.tools.http.get_http_aggregations import get_http_aggregations
from llm_pipeline.tools.http.get_http_anomalies import get_http_anomalies
from llm_pipeline.tools.http.get_http_data_completeness import get_http_data_completeness
from llm_pipeline.tools.http.get_http_report_summary import get_http_report_summary
from llm_pipeline.tools.http.get_http_trends import get_http_trends

# --- Tool role declarations for auto-discovery ---
TOOL_ROLES = [
    (get_http_aggregations, ["investigator", "reviewer"]),
    (get_http_anomalies, ["investigator", "reviewer", "orchestrator"]),
    (get_http_trends, ["investigator", "reviewer", "orchestrator"]),
    (get_http_report_summary, ["investigator", "reviewer", "orchestrator"]),
    (get_http_data_completeness, ["investigator", "reviewer"]),
    (compare_http_dimensions, ["investigator", "reviewer"]),
]

__all__ = [
    "get_http_aggregations",
    "get_http_anomalies",
    "get_http_trends",
    "get_http_report_summary",
    "get_http_data_completeness",
    "compare_http_dimensions",
    "TOOL_ROLES",
]
