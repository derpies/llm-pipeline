"""FastAPI application for the LLM Pipeline read-only dashboard API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llm_pipeline.api.routers import domains, investigations, knowledge, ml, runs
from llm_pipeline.models.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="LLM Pipeline API",
    description="Read-only API for the investigation dashboard",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(domains.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(investigations.router, prefix="/api")
app.include_router(ml.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
