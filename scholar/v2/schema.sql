CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS scholar_v2_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scholar_v2_corpus_releases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    expected_works INT NOT NULL CHECK (expected_works >= 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL CHECK (status IN ('importing', 'sealed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sealed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS scholar_v2_works (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    abstract TEXT NOT NULL DEFAULT '',
    year INT,
    venue TEXT NOT NULL DEFAULT '',
    language TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS scholar_v2_works_title_idx
    ON scholar_v2_works USING gin (to_tsvector('simple', title || ' ' || abstract));
CREATE INDEX IF NOT EXISTS scholar_v2_works_year_idx ON scholar_v2_works(year);

CREATE TABLE IF NOT EXISTS scholar_v2_work_aliases (
    alias TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    alias_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scholar_v2_work_identifiers (
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    scheme TEXT NOT NULL,
    value TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (scheme, value)
);
CREATE INDEX IF NOT EXISTS scholar_v2_work_identifiers_work_idx
    ON scholar_v2_work_identifiers(work_id);

CREATE TABLE IF NOT EXISTS scholar_v2_work_versions (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    release_id TEXT NOT NULL REFERENCES scholar_v2_corpus_releases(id),
    version_label TEXT NOT NULL,
    source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (release_id, work_id)
);

CREATE TABLE IF NOT EXISTS scholar_v2_artifacts (
    id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL REFERENCES scholar_v2_corpus_releases(id),
    work_version_id TEXT NOT NULL REFERENCES scholar_v2_work_versions(id),
    kind TEXT NOT NULL CHECK (kind IN ('latexml_xml', 'tex_source', 'pdf', 'asset')),
    media_type TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    raw_sha256 TEXT NOT NULL,
    canonical_sha256 TEXT,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (release_id, raw_sha256)
);
CREATE INDEX IF NOT EXISTS scholar_v2_artifacts_work_idx
    ON scholar_v2_artifacts(work_version_id);

CREATE TABLE IF NOT EXISTS scholar_v2_quality_assessments (
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES scholar_v2_artifacts(id) ON DELETE CASCADE,
    assessor TEXT NOT NULL,
    assessor_version TEXT NOT NULL,
    text_status TEXT NOT NULL,
    math_status TEXT NOT NULL,
    citation_status TEXT NOT NULL,
    render_status TEXT NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (artifact_id, assessor, assessor_version)
);

CREATE TABLE IF NOT EXISTS scholar_v2_authors (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS scholar_v2_projection_builds (
    id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL REFERENCES scholar_v2_corpus_releases(id),
    projection_type TEXT NOT NULL CHECK (
        projection_type IN ('relational', 'lexical', 'vector', 'graph', 'semantic')
    ),
    config_hash TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'running', 'sealed', 'failed', 'cancelled')
    ),
    source_count INT NOT NULL DEFAULT 0,
    output_count BIGINT NOT NULL DEFAULT 0,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    sealed_at TIMESTAMPTZ,
    UNIQUE (release_id, projection_type, config_hash)
);

CREATE TABLE IF NOT EXISTS scholar_v2_papers (
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    artifact_id TEXT NOT NULL REFERENCES scholar_v2_artifacts(id),
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    abstract TEXT NOT NULL DEFAULT '',
    year INT,
    venue TEXT NOT NULL DEFAULT '',
    language TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (build_id, work_id)
);
CREATE INDEX IF NOT EXISTS scholar_v2_papers_fts_idx
    ON scholar_v2_papers USING gin (
        to_tsvector('simple', title || ' ' || abstract)
    );
CREATE INDEX IF NOT EXISTS scholar_v2_papers_year_idx
    ON scholar_v2_papers(build_id, year);

CREATE TABLE IF NOT EXISTS scholar_v2_paper_authors (
    build_id TEXT NOT NULL,
    work_id TEXT NOT NULL,
    author_id TEXT NOT NULL REFERENCES scholar_v2_authors(id),
    display_name TEXT NOT NULL,
    ordinal INT NOT NULL CHECK (ordinal >= 0),
    role TEXT NOT NULL DEFAULT 'author',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (build_id, work_id, author_id, role),
    UNIQUE (build_id, work_id, ordinal, role),
    FOREIGN KEY (build_id, work_id)
        REFERENCES scholar_v2_papers(build_id, work_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS scholar_v2_paper_authors_author_idx
    ON scholar_v2_paper_authors(author_id);

CREATE TABLE IF NOT EXISTS scholar_v2_sections (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    artifact_id TEXT NOT NULL REFERENCES scholar_v2_artifacts(id),
    parent_id TEXT REFERENCES scholar_v2_sections(id) DEFERRABLE INITIALLY DEFERRED,
    xml_id TEXT,
    node_kind TEXT NOT NULL,
    semantic_role TEXT,
    level INT NOT NULL CHECK (level >= 0),
    ordinal INT NOT NULL CHECK (ordinal >= 0),
    title TEXT NOT NULL DEFAULT '',
    xml_pointer TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (build_id, work_id, ordinal)
);
CREATE INDEX IF NOT EXISTS scholar_v2_sections_work_idx
    ON scholar_v2_sections(build_id, work_id, ordinal);
CREATE INDEX IF NOT EXISTS scholar_v2_sections_parent_idx
    ON scholar_v2_sections(build_id, parent_id);
CREATE INDEX IF NOT EXISTS scholar_v2_sections_parent_fk_idx
    ON scholar_v2_sections(parent_id);

CREATE TABLE IF NOT EXISTS scholar_v2_content_nodes (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    artifact_id TEXT NOT NULL REFERENCES scholar_v2_artifacts(id),
    section_id TEXT REFERENCES scholar_v2_sections(id) DEFERRABLE INITIALLY DEFERRED,
    parent_id TEXT REFERENCES scholar_v2_content_nodes(id) DEFERRABLE INITIALLY DEFERRED,
    xml_id TEXT,
    node_kind TEXT NOT NULL,
    semantic_role TEXT,
    granularity TEXT NOT NULL,
    ordinal INT NOT NULL CHECK (ordinal >= 0),
    title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    tex TEXT,
    xml_pointer TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (build_id, work_id, ordinal)
);
CREATE INDEX IF NOT EXISTS scholar_v2_content_nodes_work_idx
    ON scholar_v2_content_nodes(build_id, work_id, ordinal);
CREATE INDEX IF NOT EXISTS scholar_v2_content_nodes_section_idx
    ON scholar_v2_content_nodes(section_id);
CREATE INDEX IF NOT EXISTS scholar_v2_content_nodes_parent_idx
    ON scholar_v2_content_nodes(parent_id);
CREATE INDEX IF NOT EXISTS scholar_v2_content_nodes_fts_idx
    ON scholar_v2_content_nodes USING gin (
        to_tsvector('simple', title || ' ' || text)
    );

CREATE TABLE IF NOT EXISTS scholar_v2_formulas (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    content_node_id TEXT NOT NULL REFERENCES scholar_v2_content_nodes(id) ON DELETE CASCADE,
    xml_id TEXT,
    mode TEXT,
    tex TEXT NOT NULL DEFAULT '',
    presentation_mathml TEXT,
    content_mathml TEXT,
    cmml_valid BOOLEAN,
    xml_pointer TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS scholar_v2_formulas_work_idx
    ON scholar_v2_formulas(build_id, work_id);
CREATE INDEX IF NOT EXISTS scholar_v2_formulas_content_node_idx
    ON scholar_v2_formulas(content_node_id);

CREATE TABLE IF NOT EXISTS scholar_v2_tables (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    content_node_id TEXT NOT NULL REFERENCES scholar_v2_content_nodes(id) ON DELETE CASCADE,
    xml_id TEXT,
    caption TEXT NOT NULL DEFAULT '',
    xml_pointer TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS scholar_v2_tables_content_node_idx
    ON scholar_v2_tables(content_node_id);

CREATE TABLE IF NOT EXISTS scholar_v2_table_cells (
    id TEXT PRIMARY KEY,
    table_id TEXT NOT NULL REFERENCES scholar_v2_tables(id) ON DELETE CASCADE,
    row_index INT NOT NULL CHECK (row_index >= 0),
    column_index INT NOT NULL CHECK (column_index >= 0),
    row_span INT NOT NULL DEFAULT 1 CHECK (row_span > 0),
    column_span INT NOT NULL DEFAULT 1 CHECK (column_span > 0),
    text TEXT NOT NULL DEFAULT '',
    is_header BOOLEAN NOT NULL DEFAULT false,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (table_id, row_index, column_index)
);

CREATE TABLE IF NOT EXISTS scholar_v2_references (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    artifact_id TEXT NOT NULL REFERENCES scholar_v2_artifacts(id),
    xml_id TEXT,
    citation_key TEXT,
    raw_text TEXT NOT NULL,
    title TEXT,
    authors JSONB NOT NULL DEFAULT '[]'::jsonb,
    year INT,
    identifiers JSONB NOT NULL DEFAULT '{}'::jsonb,
    resolved_work_id TEXT REFERENCES scholar_v2_works(id),
    resolution_confidence DOUBLE PRECISION,
    xml_pointer TEXT NOT NULL,
    UNIQUE (build_id, work_id, xml_id)
);
CREATE INDEX IF NOT EXISTS scholar_v2_references_resolved_work_idx
    ON scholar_v2_references(resolved_work_id);

CREATE TABLE IF NOT EXISTS scholar_v2_citation_mentions (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    content_node_id TEXT REFERENCES scholar_v2_content_nodes(id) ON DELETE CASCADE,
    reference_id TEXT REFERENCES scholar_v2_references(id) DEFERRABLE INITIALLY DEFERRED,
    target_xml_id TEXT NOT NULL,
    context_text TEXT NOT NULL DEFAULT '',
    intent TEXT,
    intent_confidence DOUBLE PRECISION,
    xml_pointer TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS scholar_v2_citation_mentions_work_idx
    ON scholar_v2_citation_mentions(build_id, work_id);
CREATE INDEX IF NOT EXISTS scholar_v2_citation_mentions_content_node_idx
    ON scholar_v2_citation_mentions(content_node_id);
CREATE INDEX IF NOT EXISTS scholar_v2_citation_mentions_reference_idx
    ON scholar_v2_citation_mentions(reference_id);

CREATE TABLE IF NOT EXISTS scholar_v2_chunks (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    artifact_id TEXT NOT NULL REFERENCES scholar_v2_artifacts(id),
    section_id TEXT REFERENCES scholar_v2_sections(id),
    source_node_ids JSONB NOT NULL,
    chunk_kind TEXT NOT NULL,
    semantic_role TEXT,
    ordinal INT NOT NULL CHECK (ordinal >= 0),
    content TEXT NOT NULL,
    token_estimate INT NOT NULL DEFAULT 0,
    xml_pointer_start TEXT NOT NULL,
    xml_pointer_end TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (build_id, work_id, ordinal)
);
CREATE INDEX IF NOT EXISTS scholar_v2_chunks_work_idx
    ON scholar_v2_chunks(build_id, work_id, ordinal);
CREATE INDEX IF NOT EXISTS scholar_v2_chunks_fts_idx
    ON scholar_v2_chunks USING gin (to_tsvector('simple', content));

CREATE TABLE IF NOT EXISTS scholar_v2_embedding_models (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    model_version TEXT NOT NULL,
    dimensions INT NOT NULL CHECK (dimensions = 1024),
    distance_metric TEXT NOT NULL DEFAULT 'cosine',
    config_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scholar_v2_chunk_embeddings (
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL REFERENCES scholar_v2_chunks(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL REFERENCES scholar_v2_embedding_models(id),
    embedding vector(1024) NOT NULL,
    content_sha256 TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (build_id, chunk_id, model_id)
);
CREATE INDEX IF NOT EXISTS scholar_v2_chunk_embeddings_hnsw_idx
    ON scholar_v2_chunk_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS scholar_v2_chunk_embeddings_chunk_idx
    ON scholar_v2_chunk_embeddings(chunk_id);

CREATE TABLE IF NOT EXISTS scholar_v2_semantic_entities (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL CHECK (
        entity_type IN ('claim', 'method_module', 'dataset', 'metric', 'setting', 'result')
    ),
    canonical_name TEXT,
    text TEXT NOT NULL,
    normalized_value JSONB,
    evidence_node_ids JSONB NOT NULL,
    extractor TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS scholar_v2_semantic_entities_work_idx
    ON scholar_v2_semantic_entities(build_id, work_id, entity_type);

CREATE TABLE IF NOT EXISTS scholar_v2_experiment_results (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    work_id TEXT NOT NULL REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    dataset_entity_id TEXT REFERENCES scholar_v2_semantic_entities(id),
    metric_entity_id TEXT REFERENCES scholar_v2_semantic_entities(id),
    setting_entity_id TEXT REFERENCES scholar_v2_semantic_entities(id),
    method_entity_id TEXT REFERENCES scholar_v2_semantic_entities(id),
    value DOUBLE PRECISION,
    value_text TEXT NOT NULL,
    split TEXT,
    higher_is_better BOOLEAN,
    comparable_key TEXT,
    evidence_node_ids JSONB NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS scholar_v2_experiment_results_dataset_idx
    ON scholar_v2_experiment_results(dataset_entity_id);
CREATE INDEX IF NOT EXISTS scholar_v2_experiment_results_metric_idx
    ON scholar_v2_experiment_results(metric_entity_id);
CREATE INDEX IF NOT EXISTS scholar_v2_experiment_results_setting_idx
    ON scholar_v2_experiment_results(setting_entity_id);
CREATE INDEX IF NOT EXISTS scholar_v2_experiment_results_method_idx
    ON scholar_v2_experiment_results(method_entity_id);

CREATE TABLE IF NOT EXISTS scholar_v2_graph_nodes (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    node_type TEXT NOT NULL,
    natural_key TEXT NOT NULL,
    work_id TEXT REFERENCES scholar_v2_works(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (build_id, node_type, natural_key)
);
CREATE INDEX IF NOT EXISTS scholar_v2_graph_nodes_work_idx
    ON scholar_v2_graph_nodes(work_id);

CREATE TABLE IF NOT EXISTS scholar_v2_graph_edges (
    id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id) ON DELETE CASCADE,
    source_node_id TEXT NOT NULL REFERENCES scholar_v2_graph_nodes(id) ON DELETE CASCADE,
    target_node_id TEXT NOT NULL REFERENCES scholar_v2_graph_nodes(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL,
    direct BOOLEAN NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 1,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence_node_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    extractor TEXT,
    extractor_version TEXT,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (build_id, source_node_id, target_node_id, edge_type)
);
CREATE INDEX IF NOT EXISTS scholar_v2_graph_edges_source_idx
    ON scholar_v2_graph_edges(build_id, source_node_id, edge_type);
CREATE INDEX IF NOT EXISTS scholar_v2_graph_edges_target_idx
    ON scholar_v2_graph_edges(build_id, target_node_id, edge_type);

CREATE TABLE IF NOT EXISTS scholar_v2_serving_snapshots (
    id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL REFERENCES scholar_v2_corpus_releases(id),
    relational_build_id TEXT NOT NULL REFERENCES scholar_v2_projection_builds(id),
    lexical_build_id TEXT REFERENCES scholar_v2_projection_builds(id),
    vector_build_id TEXT REFERENCES scholar_v2_projection_builds(id),
    graph_build_id TEXT REFERENCES scholar_v2_projection_builds(id),
    semantic_build_id TEXT REFERENCES scholar_v2_projection_builds(id),
    status TEXT NOT NULL CHECK (status IN ('draft', 'validating', 'ready', 'retired')),
    validation JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ready_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS scholar_v2_serving_channels (
    name TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES scholar_v2_serving_snapshots(id),
    revision BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS scholar_v2_serving_channels_snapshot_idx
    ON scholar_v2_serving_channels(snapshot_id);

CREATE TABLE IF NOT EXISTS scholar_v2_projection_jobs (
    id TEXT PRIMARY KEY,
    dedup_key TEXT NOT NULL UNIQUE,
    job_type TEXT NOT NULL,
    release_id TEXT REFERENCES scholar_v2_corpus_releases(id),
    build_id TEXT REFERENCES scholar_v2_projection_builds(id),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'running', 'retry', 'succeeded', 'failed', 'cancelled')
    ),
    priority INT NOT NULL DEFAULT 0,
    attempt_count INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    run_after TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    last_error_code TEXT,
    last_error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
DROP INDEX IF EXISTS scholar_v2_jobs_runnable_idx;
CREATE INDEX scholar_v2_jobs_runnable_idx
    ON scholar_v2_projection_jobs(priority DESC, created_at)
    WHERE status IN ('pending', 'retry', 'running');

INSERT INTO scholar_v2_schema_migrations(version)
VALUES ('scholar-v2-001')
ON CONFLICT (version) DO NOTHING;
