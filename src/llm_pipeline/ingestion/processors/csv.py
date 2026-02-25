"""CSV processor — CSVLoader, one document per row, no further splitting."""

from langchain_community.document_loaders import CSVLoader

from llm_pipeline.ingestion.processors.base import build_processor_subgraph


def _load(path: str):
    return CSVLoader(path).load()


csv_processor = build_processor_subgraph(_load, None, "csv")
