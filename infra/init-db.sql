-- Postgres initialization for llm-pipeline
-- Runs once on first database creation via docker-entrypoint-initdb.d

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Schema layout:
--   public     — Email analytics (existing tables)
--   knowledge  — Four-tier knowledge hierarchy
--   vectors    — pgvector embeddings (replaces ChromaDB)
--   pipeline   — Operational metadata (cycle runs, lineage, audit trail)
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS vectors;
CREATE SCHEMA IF NOT EXISTS pipeline;
