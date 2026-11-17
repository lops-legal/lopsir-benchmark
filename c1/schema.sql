CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE SCHEMA IF NOT EXISTS c1;
CREATE TABLE IF NOT EXISTS c1.records (
    record_id text PRIMARY KEY, entity_id text NOT NULL, collection text NOT NULL,
    authority text, kind text, number text, year integer, article text, norm_key text,
    reference text NOT NULL, title text, body text, source_link text, source_path text
);
CREATE TABLE IF NOT EXISTS c1.entities (
    entity_id text PRIMARY KEY, collection text NOT NULL, authority text,
    kind text, number text, year integer, article text, norm_key text,
    reference text NOT NULL, title text, source_link text
);
CREATE TABLE IF NOT EXISTS c1.source_snapshots (
    filename text PRIMARY KEY, sha256 text NOT NULL, rows bigint NOT NULL,
    imported_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS c1.query_audit (
    experiment_id text, method text, query_id text, repetition integer,
    query_text text, fields jsonb, returned integer, total_ms double precision,
    status text, PRIMARY KEY (experiment_id,method,query_id,repetition)
);
