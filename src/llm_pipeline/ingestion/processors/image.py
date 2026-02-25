"""Image processor — Vision LLM description → text chunks."""

import base64
import mimetypes

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from llm_pipeline.config import settings
from llm_pipeline.ingestion.processors.base import build_processor_subgraph
from llm_pipeline.models.llm import get_llm


def _load(path: str):
    """Send image to vision LLM, get a text description back."""
    mime_type = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    llm = get_llm()
    message = HumanMessage(
        content=[
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
            },
            {
                "type": "text",
                "text": (
                    "Describe this image in detail. Include all visible text, "
                    "diagrams, charts, or other information that would be useful "
                    "for someone searching for this content later."
                ),
            },
        ]
    )
    response = llm.invoke([message])
    return [Document(page_content=response.content, metadata={"source": path})]


def _split(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    return splitter.split_documents(docs)


image_processor = build_processor_subgraph(_load, _split, "image")
