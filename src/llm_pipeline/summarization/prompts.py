"""Prompt templates for document generation per document type."""

EXECUTIVE_SUMMARY_PROMPT = """\
You are an email deliverability analyst. Write a concise executive summary of \
email delivery health for the analysis period described below.

Your audience is an email operations team. Be specific — reference actual \
metrics, domains, and percentages. Explain what the numbers mean operationally, \
not just what they are.

Structure your summary as:
1. Overall delivery health (1-2 sentences)
2. Key concerns (anomalies that need attention)
3. Notable trends (what's changing over time)
4. Top dimensions overview (largest mailbox providers / IPs / campaigns)

Stay concise: 200-400 words. Do not use bullet points — write in prose paragraphs.

=== DATA ===
{digest}
"""

ANOMALY_NARRATIVE_PROMPT = """\
You are an email deliverability analyst. Write a plain-language description of \
the anomaly below. Explain what changed, by how much relative to the baseline, \
and what the likely operational impact is.

Your audience is an email operations team. Be specific with numbers. \
If the anomaly suggests a likely cause (e.g., a blacklisting, a provider \
policy change, a reputation issue), mention it as a possibility.

Stay concise: 100-200 words. Write in prose, not bullet points.

=== DATA ===
{anomaly_context}
"""

TREND_NARRATIVE_PROMPT = """\
You are an email deliverability analyst. Write a plain-language description of \
the trend below. Explain the direction and magnitude of the change, how \
statistically significant it appears, and what the operational implications are.

Your audience is an email operations team. Be specific with numbers and \
time ranges. If the trend suggests a developing issue or an improvement, \
say so clearly.

Stay concise: 100-200 words. Write in prose, not bullet points.

=== DATA ===
{trend_context}
"""

DIMENSIONAL_SUMMARY_PROMPT = """\
You are an email deliverability analyst. Write a plain-language summary of \
email delivery performance for the specific dimension slice below. Cover \
volume, delivery rates, any anomalies detected, and any trends observed.

Your audience is an email operations team. Be specific with numbers. \
Highlight anything that needs attention or action.

Stay concise: 200-400 words. Write in prose, not bullet points.

=== DATA ===
{dimension_context}
"""
