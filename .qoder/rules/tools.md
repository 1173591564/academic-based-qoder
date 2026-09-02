---
description: Scholar CLI commands reference — all available tools
alwaysApply: true
---

# Available Tools

**Preferred**: Use MCP tools (scholar-mcp server) — they provide typed parameters and direct results.
**Fallback**: Execute CLI commands via terminal.

## MCP Server (recommended)
The scholar MCP server exposes 16 tools. Start it with:
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

### Paper Library (supports Hybrid ID: ULID / arXiv ID / DOI / slug)
```bash
python -m scholar scan                    # Scan all papers, show status
python -m scholar parse <paper_id>        # Parse single paper's TeX source
python -m scholar parse-all               # Batch parse all papers
python -m scholar info <paper_id>         # View paper details
python -m scholar search "<keyword>"      # Full-text search in parsed data
python -m scholar list-papers [--year N]  # List parsed papers (optional year filter)
python -m scholar stats                   # Knowledge base statistics + metadata coverage
python -m scholar export-bib              # Export BibTeX
```

### Metadata Completion
```bash
python -m scholar year-fix [--apply]      # Fill missing years (Lean4 cross-ref + arXiv API)
python -m scholar author-fix [--apply]    # Fill missing authors (arXiv API)
python -m scholar venue-fix [--apply]     # Fill missing venue (arxiv_id → 'arXiv', title → 'Preprint')
python -m scholar metadata-enrich [--apply]  # Backfill arxiv_id/DOI/year/venue via arXiv API
```

### Graph & Network (in-memory; no external graph service required)
```bash
python -m scholar graph-build             # Build citation + concept graph + Lean4 relations
python -m scholar graph-stats             # Detailed graph stats: centrality, components, isolated
python -m scholar graph-query <concept>   # Query concept-related papers
python -m scholar cite-network            # Global citation network stats
python -m scholar cite-network <paper_id> # Forward/backward citation analysis
python -m scholar cite-resolve [--apply]  # Resolve citation refs (internal + arXiv sidecar)
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
python -m scholar auto-notes <paper_id>   # Generate note for single paper
python -m scholar quality-score --all     # Score all papers (7 dimensions, A-F grade)
python -m scholar quality-score <paper_id>  # Score single paper
python -m scholar classify --all          # Classify all papers (domain/sub/method tags)
python -m scholar classify <paper_id>     # Classify single paper
python -m scholar classify --list-tags    # List all tags in corpus
```

### KB Update (arXiv download + batch ingest)
```bash
python -m scholar arxiv-download "<query>" [--max 10] [--pdf]  # Download TeX from arXiv
python -m scholar batch-ingest [--ulids "id1,id2"]  # Batch ingest: parse→enrich→graph→notes→quality→classify
python -m scholar kb-update --query "<topic>" --max 10  # One-command: search→download→ingest
```

### Research Loop (方向管理 + 自动同步)
```bash
python -m scholar interests list              # 查看研究方向
python -m scholar interests add --keywords "..." --category "..."  # 添加方向
python -m scholar interests remove --category "..."  # 删除方向
python -m scholar interests logs              # 查看未分析的对话日志
python -m scholar interests mark-analyzed --week YYYY-WNN --found N  # 标记完成
python -m scholar research-sync [--category "..."] [--max 10]  # 方向级同步：搜索→下载→全流程入库
```

### Execution Layer (LaTeX compile + experiments + datasets)
```bash
python -m scholar compile-paper <file.tex> [--report] [--engine xelatex]  # Compile LaTeX with structured error report (FATAL/WARN/INFO)
python -m scholar exp-run <paper_id> [--mode quick] [--gpu]  # Run experiment code
python -m scholar exp-compare <paper_id>  # Compare results with paper metrics
python -m scholar exp-setup <paper_id> [--conda|--docker]  # Set up experiment environment
python -m scholar exp-debug <run_log.txt>  # Diagnose experiment failures
python -m scholar dataset-download <name> [--source auto]  # Download datasets (HuggingFace)
python -m scholar lean-sync [--apply] [--build] [--max-papers 100]  # Sync parsed papers → Lean4 Database.lean (--build runs lake build)
python -m scholar lean-templates [--output FILE]  # Generate Lean4 theorem templates
python -m scholar exp-codegen <paper_id>  # Generate experiment code template from paper JSON
```

### Orchestration
```bash
python -m scholar bootstrap               # Full init: parse→year-fix→graph→rag→notes→quality→classify
python -m scholar ingest <paper_id>        # Incremental: parse→author-fix→graph-update→rag→notes→quality→classify
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
- Experiment code: `output/experiments/<ULID>/`
- Experiment logs: `output/experiments/<ULID>/run_log.txt`
- Compiled PDFs: `output/pdfs/`
- Datasets: `output/datasets/<name>/`
- Sync reports: `output/digests/sync-YYYY-MM-DD.md`
- Conversation logs: `output/logs/week-YYYY-WNN.jsonl`
- Research interests: `output/research-interests.json`
