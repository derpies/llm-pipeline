# summarization/

Document generation from ML analysis output. Converts structured ML findings into plain-language LLM-generated documents (executive summary, anomaly narrative, trend narrative, dimensional summary), then embeds and stores them.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `state.py` | LangGraph state: SummarizationState with input (report, run_id), accumulated documents/errors, output result |
| `models.py` | DocumentType enum, GeneratedDocument, SummarizationResult |
| `prompts.py` | Prompt templates per document type — audience: email operations team, 100–400 words, plain language |
| `serializers.py` | Pure functions converting structured ML findings into text blocks for LLM context (no LLM calls) |
| `embed.py` | Convert GeneratedDocument → LangChain Document with metadata, split if needed, store in vector store |
| `graph.py` | LangGraph pipeline: fan-out (one node per document type) → embed → END |

## Contracts

- **Imports from**: `email_analytics.models` (AnalysisReport), `rag.ingest` (vector store, embeddings), `models.llm` (LLM factory), `config` (settings)
- **Exports**: `build_summarization_graph()`, `SummarizationResult`, `GeneratedDocument`
- **Consumed by**: `cli.py` (summarize flag on analyze_email)
