---
description: Scholar CLI commands reference — all available tools
alwaysApply: true
---

# Available Tools

**Preferred**: Use MCP tools (scholar-mcp server) — they provide typed parameters and direct results.
**Fallback**: Execute CLI commands via terminal.

## MCP Server (recommended)
The scholar MCP server exposes 29 tools. Start it with:
```bash
cd <project-root> && python -m scholar_mcp
```
Configure in Qoder Settings > MCP:
```json
{
  "mcpServers": {
    "scholar": {
      "command": "python",
      "args": ["-m", "scholar_mcp"],
      "cwd": "<project-root>"
    }
  }
}
```

## CLI Commands (via terminal)

### Paper Library
```bash
python -m scholar scan                    # Scan all papers, show status
python -m scholar parse <ULID>            # Parse single paper's TeX source
python -m scholar parse-all               # Batch parse all papers
python -m scholar info <ULID>             # View paper details
python -m scholar search "<keyword>"      # Full-text search in parsed data
python -m scholar list-papers [--year N]  # List parsed papers (optional year filter)
python -m scholar stats                   # Knowledge base statistics + metadata coverage
python -m scholar export-bib              # Export BibTeX
```

### Metadata Completion
```bash
python -m scholar year-fix [--apply]      # Fill missing years (Lean4 cross-ref + arXiv API)
python -m scholar author-fix [--apply]    # Fill missing authors (arXiv API)
```

### Graph & Network (requires Neo4j: cd infra && docker compose up -d neo4j)
```bash
python -m scholar graph-build             # Build citation + concept graph + Lean4 relations
python -m scholar graph-stats             # Detailed graph stats: centrality, components, isolated
python -m scholar graph-query <concept>   # Query concept-related papers
python -m scholar cite-network            # Global citation network stats
python -m scholar cite-network <ULID>     # Forward/backward citation analysis
python -m scholar cite-resolve [--apply]  # Resolve citation refs (internal + arXiv + Neo4j nodes)
```

### RAG Semantic Search (requires: set SCHOLAR_EMBEDDING_API_KEY=xxx)
```bash
python -m scholar rag-index               # Build vector index (Zhipu embedding-2 + HNSW)
python -m scholar rag-search "<query>"    # Semantic search
python -m scholar rag-search "<q>" --hybrid  # Hybrid: vector + BM25 + RRF fusion
```

### Batch Preprocessing
```bash
python -m scholar auto-notes              # Generate reading notes for ALL papers
python -m scholar auto-notes <ULID>       # Generate note for single paper
python -m scholar quality-score --all     # Score all papers (7 dimensions, A-F grade)
python -m scholar quality-score <ULID>    # Score single paper
python -m scholar classify --all          # Classify all papers (domain/sub/method tags)
python -m scholar classify <ULID>         # Classify single paper
python -m scholar classify --list-tags    # List all tags in corpus
```

### Orchestration
```bash
python -m scholar bootstrap               # Full init: parse→year-fix→graph→rag→notes→quality→classify
python -m scholar ingest <ULID>            # Incremental: parse→author-fix→graph-update→rag→notes→quality→classify
python -m scholar survey "<topic>" [--depth full]  # Full survey: RAG+graph+classify+timeline → output/drafts/
python -m scholar landscape "<topic>"      # Field landscape: tags+year+quality+key papers → output/drafts/
```

### External
```bash
python -m scholar arxiv-search "<query>" [--max 10]  # Search arXiv
```

### Local Tools
```bash
cd LEAN && lake build                     # Compile Lean4 project
pdflatex output/drafts/<file>.tex         # Compile LaTeX output
```

## Pre-generated Data Paths
- Reading notes: `output/notes/<ULID>.md`
- Quality scores: `output/notes/<ULID>-quality.json`
- Paper JSON (with tags): `output/parsed/<ULID>.json`
