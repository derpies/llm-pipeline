# agents/

Multi-agent investigation system. Orchestrates ML-driven analysis of email delivery data through a plan → investigate → evaluate → synthesize cycle with circuit breaker enforcement.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `contracts.py` | AgentManifest, InvestigationOutput, ResultAdapter — contracts for pluggable agents |
| `models.py` | Pydantic models: InvestigationTopic, Finding, Hypothesis, CircuitBreakerBudget, etc. |
| `state.py` | LangGraph state schemas: InvestigationCycleState (top-level), InvestigatorState (per-agent) |
| `prompts.py` | System prompts for chat, orchestrator, and investigator agents |
| `roles.py` | Per-role specialist config: prompt supplements, KB prefixes, grounding retrieval |
| `registry.py` | Auto-discovery registry — scans `plugins/` for AgentManifest declarations |
| `chat.py` | Conversational chat agent graph (user-facing, tool-enabled) |
| `orchestrator.py` | Orchestrator nodes: plan (topic generation), evaluate (follow-up decision), checkpoint (digest) |
| `graph.py` | Top-level investigation cycle graph: fan-out/fan-in with dynamic agent registration |
| `report_models.py` | StructuredReport (Document 1, fixed-schema) + InvestigationNotes (Document 2, overflow) |
| `report_builder.py` | Deterministic report assembly from ML data + findings (pure functions, no LLM) |
| `report_renderer.py` | Render InvestigationReport to JSON and markdown |
| `storage.py` | Postgres persistence for investigation results, reports, and markdown output |
| `investigator.py` | Backward-compat stub — re-exports from `plugins/investigator/` |

### plugins/investigator/

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `manifest.py` | AgentManifest instance for auto-discovery registration |
| `agent.py` | Investigator agent: tool loop with run_id patching, role-specific prompts, circuit breaker |
| `extract.py` | Parse findings/hypotheses from message history tool calls; ResultAdapter implementation |

## Key Concepts

**Investigation cycle** — The orchestrator reads an ML report, generates investigation topics, fans out to specialist investigators, evaluates results, and optionally loops for follow-up. Circuit breaker (iteration count, wall clock, spend) prevents runaway cycles.

**Fan-out/fan-in** — Each topic dispatches to an agent node via LangGraph `Send`. Results aggregate back to the orchestrator via `Annotated[list, operator.add]` reducers in state. The investigator's internal `messages` list is private — only findings, hypotheses, and digest lines flow back.

**Pluggable agents** — Investigation agents register via `AgentManifest` in `plugins/{name}/manifest.py`. The registry auto-discovers them; `graph.py` dynamically creates one node per agent type. Currently one type (investigator), but the architecture supports adding more without modifying the graph.

**Specialist roles** — Five investigator roles (reputation, compliance, engagement, ISP, diagnostics) with role-specific prompt supplements and pre-fetched grounding context from the knowledge store's Grounded tier.

**Two-document report** — Document 1 (`StructuredReport`) is fixed-schema and mechanically diff-able across runs. Document 2 (`InvestigationNotes`) captures hypotheses, observations, and process notes that don't fit the fixed schema.

**Two graph patterns** — Tool-loop agents (investigator, chat) use `MessagesState` + `ToolNode` and iterate until the LLM stops calling tools. Single-call agents (orchestrator nodes) make one LLM call, parse the response, and return state updates.

## Contracts

- **Imports from**: `email_analytics.models` (AnalysisReport, ML data types), `tools.registry` (tool lookup), `knowledge.retrieval` (grounding context), `models.llm` (LLM factory), `config` (settings)
- **Exports**: `build_chat_graph`, `build_investigation_graph`, `AgentManifest`, `InvestigationOutput`, data models (Finding, Hypothesis, InvestigationTopic, etc.), report models, storage functions
- **Consumed by**: `cli` (chat/investigate/report commands), `knowledge.store` (investigation → knowledge conversion)
