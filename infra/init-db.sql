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

-- Domain isolation: add domain_name to investigation tables
ALTER TABLE IF EXISTS investigation_runs ADD COLUMN IF NOT EXISTS domain_name VARCHAR(64) DEFAULT '';
ALTER TABLE IF EXISTS investigation_findings ADD COLUMN IF NOT EXISTS domain_name VARCHAR(64) DEFAULT '';
ALTER TABLE IF EXISTS investigation_hypotheses ADD COLUMN IF NOT EXISTS domain_name VARCHAR(64) DEFAULT '';
ALTER TABLE IF EXISTS investigation_reports ADD COLUMN IF NOT EXISTS domain_name VARCHAR(64) DEFAULT '';

-- Human review columns for investigation runs (Phase 4)
ALTER TABLE IF EXISTS investigation_runs ADD COLUMN IF NOT EXISTS review_status VARCHAR(32) DEFAULT 'pending';
ALTER TABLE IF EXISTS investigation_runs ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(256) DEFAULT '';
ALTER TABLE IF EXISTS investigation_runs ADD COLUMN IF NOT EXISTS review_notes TEXT DEFAULT '';
ALTER TABLE IF EXISTS investigation_runs ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
