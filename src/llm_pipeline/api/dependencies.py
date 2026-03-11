"""FastAPI dependency injection for DB sessions and Weaviate client."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from llm_pipeline.models.db import get_engine


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session, closing it after the request."""
    engine = get_engine()
    with Session(engine) as session:
        yield session


def get_weaviate():
    """Return the singleton Weaviate client."""
    from llm_pipeline.knowledge.store import get_weaviate_client

    return get_weaviate_client()
