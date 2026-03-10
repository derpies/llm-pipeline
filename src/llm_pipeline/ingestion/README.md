# ingestion/

Document ingestion pipeline. Classifies files by format, routes to format-specific processors, chunks into embeddable pieces, and stores in the vector store.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `classify.py` | Extension → DocType mapping. `classify_path()` and `collect_documents()` for directory scanning |
| `state.py` | LangGraph state schemas: DocumentItem, ProcessedChunk, IngestionState with operator.add reducers |
| `graph.py` | LangGraph pipeline: classify → fan-out to processors → review → store. Uses `Send` for dynamic routing |

### processors/

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `base.py` | Shared processor subgraph factory: `build_processor_subgraph(loader, splitter, doc_type)` — load → chunk → END |
| `txt.py` | TextLoader + RecursiveCharacterTextSplitter for TXT/Markdown |
| `pdf.py` | PyPDFLoader + RecursiveCharacterTextSplitter for PDFs |
| `csv.py` | CSVLoader, one document per row, no splitting |
| `image.py` | Vision LLM description → text. Encodes image as base64, calls LLM |
| `code.py` | TextLoader + language-aware RecursiveCharacterTextSplitter (Python, JS, Rust, Go, Java, C++) |

## Contracts

- **Imports from**: `rag.ingest` (vector store), `models.llm` (vision LLM for image processor), `config` (chunk sizes)
- **Exports**: `build_ingestion_graph()` (graph entry point), `collect_documents()`, processor subgraphs
- **Consumed by**: `cli.py` (ingest command)
