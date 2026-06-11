-- Scholar Database Schema
-- PostgreSQL 16 + pgvector

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Papers: core metadata
-- ============================================================
CREATE TABLE IF NOT EXISTS papers (
    id            TEXT PRIMARY KEY,           -- ULID folder name
    title         TEXT,
    authors       TEXT[],
    year          INT,
    venue         TEXT,
    abstract      TEXT,
    arxiv_id      TEXT,
    doi           TEXT,
    has_tex       BOOLEAN DEFAULT FALSE,
    parsed_ok     BOOLEAN DEFAULT FALSE,
    parsed_path   TEXT,                       -- path to parsed JSON
    section_count INT DEFAULT 0,
    formula_count INT DEFAULT 0,
    citation_count INT DEFAULT 0,
    read_status   TEXT DEFAULT 'unread',      -- unread | reading | read
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Sections: structured body text
-- ============================================================
CREATE TABLE IF NOT EXISTS sections (
    id         SERIAL PRIMARY KEY,
    paper_id   TEXT REFERENCES papers(id) ON DELETE CASCADE,
    heading    TEXT,
    level      INT DEFAULT 1,
    content    TEXT NOT NULL,
    position   INT DEFAULT 0,                -- order within paper
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sections_paper ON sections(paper_id);

-- ============================================================
-- Formulas: extracted LaTeX equations
-- ============================================================
CREATE TABLE IF NOT EXISTS formulas (
    id         SERIAL PRIMARY KEY,
    paper_id   TEXT REFERENCES papers(id) ON DELETE CASCADE,
    latex      TEXT NOT NULL,
    label      TEXT,
    env_type   TEXT,                         -- equation, align, gather, etc.
    context    TEXT,                         -- surrounding text
    lean_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_formulas_paper ON formulas(paper_id);

-- ============================================================
-- Citations: reference relationships
-- ============================================================
CREATE TABLE IF NOT EXISTS citations (
    id         SERIAL PRIMARY KEY,
    from_paper TEXT REFERENCES papers(id) ON DELETE CASCADE,
    to_ref     TEXT NOT NULL,                -- citation key (e.g. "vaswani2017")
    to_paper   TEXT,                         -- resolved paper id (nullable)
    resolved   BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_paper, to_ref)
);
CREATE INDEX IF NOT EXISTS idx_citations_from ON citations(from_paper);
CREATE INDEX IF NOT EXISTS idx_citations_to ON citations(to_paper);

-- ============================================================
-- Concepts: extracted key concepts
-- ============================================================
CREATE TABLE IF NOT EXISTS concepts (
    id         SERIAL PRIMARY KEY,
    name       TEXT UNIQUE NOT NULL,
    definition TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Paper-Concept links
-- ============================================================
CREATE TABLE IF NOT EXISTS paper_concepts (
    paper_id   TEXT REFERENCES papers(id) ON DELETE CASCADE,
    concept_id INT REFERENCES concepts(id) ON DELETE CASCADE,
    relevance  FLOAT DEFAULT 1.0,
    PRIMARY KEY (paper_id, concept_id)
);

-- ============================================================
-- Embeddings (for future RAG use)
-- ============================================================
CREATE TABLE IF NOT EXISTS chunks (
    id         SERIAL PRIMARY KEY,
    paper_id   TEXT REFERENCES papers(id) ON DELETE CASCADE,
    section_id INT REFERENCES sections(id) ON DELETE SET NULL,
    section    TEXT,                          -- section heading name
    content    TEXT NOT NULL,
    embedding  vector(1024),                  -- Zhipu embedding-2 dimension
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chunks_paper ON chunks(paper_id);

-- ============================================================
-- Innovations (sync with Lean4 Database.lean)
-- ============================================================
CREATE TABLE IF NOT EXISTS innovations (
    id          TEXT PRIMARY KEY,
    line        TEXT NOT NULL,               -- ResearchLine enum
    core        BOOLEAN DEFAULT TRUE,
    year        INT,
    scalability INT DEFAULT 3,
    simplicity  INT DEFAULT 3,
    stability   INT DEFAULT 3,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Replacement relations (sync with Lean4 replacesDb)
-- ============================================================
CREATE TABLE IF NOT EXISTS replacements (
    id          SERIAL PRIMARY KEY,
    from_innov  TEXT REFERENCES innovations(id),
    to_innov    TEXT REFERENCES innovations(id),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_innov, to_innov)
);
