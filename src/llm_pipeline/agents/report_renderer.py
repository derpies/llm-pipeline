"""Re-export from canonical location for backward compatibility.

The report renderer has moved to llm_pipeline.domains.email_delivery.report_renderer.
"""

from llm_pipeline.domains.email_delivery.report_renderer import (  # noqa: F401
    render_json,
    render_markdown,
)
