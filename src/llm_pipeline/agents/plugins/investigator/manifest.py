"""Investigator agent manifest — declares the agent for auto-discovery."""

from llm_pipeline.agents.contracts import AgentManifest
from llm_pipeline.agents.plugins.investigator.agent import build_investigator_graph
from llm_pipeline.agents.plugins.investigator.extract import InvestigatorResultAdapter
from llm_pipeline.agents.prompts import INVESTIGATOR_SYSTEM_PROMPT
from llm_pipeline.agents.state import InvestigatorState

manifest = AgentManifest(
    name="investigator",
    agent_type="investigation",
    tool_role="investigator",
    build_graph=build_investigator_graph,
    state_class=InvestigatorState,
    result_adapter=InvestigatorResultAdapter(),
    system_prompt=INVESTIGATOR_SYSTEM_PROMPT,
    description="Email delivery investigator — examines ML findings using analytical tools",
)
