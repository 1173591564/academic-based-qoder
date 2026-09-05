# Scholar v2 data plane

Scholar v2 is an XML-first, snapshot-scoped data plane:

```text
immutable LaTeXML
  -> relational projection
  -> graph and pgvector projections
  -> validated serving snapshot
  -> Scholar service
  -> fixed 16-tool MCP adapter
```

The XML artifact is authoritative. PostgreSQL full-text rows, graph nodes and
edges, and pgvector embeddings are versioned projections and can be rebuilt.
The MCP server does not fall back to parsed JSON, the legacy vector cache, or
the in-memory graph for corpus queries.

## Storage

`scholar/v2/schema.sql` owns:

- corpus releases, works, versions, artifacts, and quality assessments;
- build-scoped papers, authors, sections, ordered content, formulas, tables,
  references, citation mentions, and bounded chunks;
- embedding models and pgvector rows;
- evidence-bearing graph nodes and edges;
- projection jobs, immutable builds, serving snapshots, and channels.

One active channel pins all projections for a request. Derived graph, vector,
and semantic builds must be sealed, belong to the same release, and declare
the selected relational build as their dependency.

## Bootstrap

Start PostgreSQL:

```sh
docker compose -f infra/scholar/compose.yml up -d
```

Initialize the schema:

```sh
scholar v2 init
```

Import a verified release whose `manifest.csv` contains `paper_id`, `title`,
`size_bytes`, `sha256`, `canonical_sha256`, and `quality_tier`:

```sh
scholar v2 import /path/to/release \
  --release-id bootstrap-205-v1 \
  --artifact-root /immutable/scholar/bootstrap-205-v1
```

Build derived projections:

```sh
scholar v2 build-graph \
  --release-id bootstrap-205-v1 \
  --relational-build <relational-build-id>

scholar v2 build-vectors \
  --release-id bootstrap-205-v1 \
  --relational-build <relational-build-id> \
  --model-version <immutable-model-version>
```

Create and atomically activate a serving snapshot:

```sh
scholar v2 create-snapshot \
  --release-id bootstrap-205-v1 \
  --relational-build <relational-build-id> \
  --graph-build <graph-build-id> \
  --vector-build <vector-build-id>

scholar v2 activate <snapshot-id>
scholar v2 status
```

Re-running the same import or build is idempotent. A changed manifest cannot
replace a sealed release. Build failures remain explicit and never change the
active serving channel.

Online vector queries must use the same provider, model, and dimensions as the
active vector build. A mismatch fails closed for pure vector search and
degrades hybrid search to lexical results.

## Runtime

Each MCP request receives a request ID, deadline, cancellation event, global
and per-tool capacity permits, and one pinned serving snapshot. Database
connections use bounded pool acquisition plus statement and lock timeouts.
Errors use stable codes such as `INVALID_ARGUMENT`, `NOT_FOUND`,
`DEADLINE_EXCEEDED`, `VECTOR_UNAVAILABLE`, and `SNAPSHOT_UNAVAILABLE`.

The readiness endpoint reports only the active schema, release, snapshot,
sealed builds, and unavailable projection capabilities. It never exposes
database diagnostics or credentials.
