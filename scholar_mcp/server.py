"""
Scholar Studio MCP Server

Exposes the scholar CLI as native MCP tools for Qoder IDE integration.
Run: python -m scholar_mcp
"""
import subprocess
import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Project root: parent of scholar_mcp/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

mcp = FastMCP(
    "Scholar Studio",
    instructions="Academic research toolkit with 445+ AI papers, citation graph, Lean4 verification, Hybrid ID, kb-update, and execution layer.",
)


def _run_scholar(*args: str, timeout: int = 120) -> str:
    """Run a scholar CLI command and return stdout."""
    cmd = [sys.executable, "-m", "scholar"] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )
    output = result.stdout
    if result.returncode != 0 and result.stderr:
        output += f"\n[ERROR] {result.stderr}"
    return output.strip()


# ─── Paper Library ───────────────────────────────────────────────

@mcp.tool()
def scholar_scan() -> str:
    """Scan all papers and show parsing status (parsed/unparsed/failed)."""
    return _run_scholar("scan")


@mcp.tool()
def scholar_parse(paper_id: str) -> str:
    """Parse a single paper's TeX source into structured JSON.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug, e.g., 01KT6MT...)
    """
    return _run_scholar("parse", paper_id)


@mcp.tool()
def scholar_parse_all() -> str:
    """Batch parse all unparsed papers. May take several minutes."""
    return _run_scholar("parse-all", timeout=600)


@mcp.tool()
def scholar_info(paper_id: str) -> str:
    """Show detailed information about a parsed paper.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    return _run_scholar("info", paper_id)


@mcp.tool()
def scholar_search(query: str) -> str:
    """Full-text search across all parsed papers (title, abstract, sections).

    Args:
        query: Search keyword or phrase
    """
    return _run_scholar("search", query)


@mcp.tool()
def scholar_list_papers(year: int | None = None) -> str:
    """List all parsed papers with metadata. Optionally filter by year.

    Args:
        year: Optional year filter (e.g., 2023)
    """
    args = ["list-papers"]
    if year is not None:
        args.extend(["--year", str(year)])
    return _run_scholar(*args)


@mcp.tool()
def scholar_stats() -> str:
    """Show knowledge base statistics: paper count, field coverage, venue distribution."""
    return _run_scholar("stats")


@mcp.tool()
def scholar_export_bib(output: str = "output/bib/references.bib") -> str:
    """Export BibTeX entries for all parsed papers.

    Args:
        output: Output .bib file path (default: output/bib/references.bib)
    """
    return _run_scholar("export-bib", "--output", output)


@mcp.tool()
def scholar_year_fix(apply: bool = False) -> str:
    """Fill missing publication years by cross-referencing Lean4 Database.lean.

    Args:
        apply: If True, write changes to JSON files. If False, dry-run preview.
    """
    args = ["year-fix"]
    if apply:
        args.append("--apply")
    return _run_scholar(*args)


# ─── Graph & Network ────────────────────────────────────────────

@mcp.tool()
def scholar_graph_build() -> str:
    """Build citation network + concept graph + Lean4 replacement relations in Neo4j.
    Requires Neo4j running (cd infra && docker compose up -d neo4j).
    """
    return _run_scholar("graph-build", timeout=300)


@mcp.tool()
def scholar_graph_query(concept: str) -> str:
    """Query papers and related concepts for a given concept in the graph.

    Args:
        concept: Concept identifier (e.g., 'transformer', 'diffusion', 'rlhf')
    """
    return _run_scholar("graph-query", concept)


@mcp.tool()
def scholar_cite_network(paper_id: str | None = None) -> str:
    """Analyze citation network. Without paper_id: global stats. With paper_id: per-paper analysis.

    Args:
        paper_id: Optional paper ID (ULID/arXiv/DOI/slug) for per-paper forward/backward citation analysis
    """
    args = ["cite-network"]
    if paper_id:
        args.append(paper_id)
    return _run_scholar(*args)


# ─── RAG ────────────────────────────────────────────────────────

@mcp.tool()
def scholar_rag_index() -> str:
    """Build RAG vector index for all parsed papers using Zhipu embedding-2.
    Requires SCHOLAR_EMBEDDING_API_KEY environment variable.
    """
    return _run_scholar("rag-index", timeout=600)


@mcp.tool()
def scholar_rag_search(query: str, hybrid: bool = False) -> str:
    """Semantic search across all papers using RAG vector index.

    Args:
        query: Natural language search query
        hybrid: If True, use hybrid search (vector + BM25 + RRF fusion)
    """
    args = ["rag-search", query]
    if hybrid:
        args.append("--hybrid")
    return _run_scholar(*args)


# ─── External ───────────────────────────────────────────────────

@mcp.tool()
def scholar_arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv for papers. Useful for finding recent work not in local library.

    Args:
        query: Search query (supports arXiv query syntax)
        max_results: Maximum number of results (default: 10)
    """
    return _run_scholar("arxiv-search", query, "--max", str(max_results))


# ─── Metadata Completion ─────────────────────────────────────────

@mcp.tool()
def scholar_graph_stats() -> str:
    """Show detailed graph statistics: nodes, edges, centrality top-10, isolated nodes."""
    return _run_scholar("graph-stats")


@mcp.tool()
def scholar_author_fix(apply: bool = False) -> str:
    """Fill missing authors using arXiv API title search.

    Args:
        apply: If True, write changes. If False, dry-run preview.
    """
    args = ["author-fix"]
    if apply:
        args.append("--apply")
    return _run_scholar(*args)


@mcp.tool()
def scholar_cite_resolve(apply: bool = False) -> str:
    """Resolve citation references: internal matching + arXiv API + Neo4j external nodes.

    Args:
        apply: If True, write changes. If False, dry-run preview.
    """
    args = ["cite-resolve"]
    if apply:
        args.append("--apply")
    return _run_scholar(*args)


# ─── Batch Preprocessing ─────────────────────────────────────────

@mcp.tool()
def scholar_auto_notes(paper_id: str | None = None, force: bool = False) -> str:
    """Generate structured reading notes. Without paper_id: batch mode for all papers.

    Args:
        paper_id: Optional paper ID (ULID/arXiv/DOI/slug) for single paper. Omit for batch.
        force: If True, overwrite existing notes.
    """
    args = ["auto-notes"]
    if paper_id:
        args.append(paper_id)
    if force:
        args.append("--force")
    return _run_scholar(*args, timeout=300)


@mcp.tool()
def scholar_quality_score(paper_id: str | None = None, all_papers: bool = False) -> str:
    """Score paper quality across 7 dimensions (metadata/structure/citations/reproducibility/problem/innovation/experiments).

    Args:
        paper_id: Optional paper ID (ULID/arXiv/DOI/slug) for single paper scoring.
        all_papers: If True, score all papers.
    """
    args = ["quality-score"]
    if paper_id:
        args.append(paper_id)
    elif all_papers:
        args.append("--all")
    return _run_scholar(*args, timeout=300)


@mcp.tool()
def scholar_classify(paper_id: str | None = None, all_papers: bool = False, list_tags: bool = False) -> str:
    """Classify papers into domain/sub-direction/method tags.

    Args:
        paper_id: Optional paper ID (ULID/arXiv/DOI/slug) for single paper.
        all_papers: If True, classify all papers.
        list_tags: If True, list all tags in corpus.
    """
    args = ["classify"]
    if paper_id:
        args.append(paper_id)
    elif all_papers:
        args.append("--all")
    elif list_tags:
        args.append("--list-tags")
    return _run_scholar(*args, timeout=300)


# ─── Orchestration ────────────────────────────────────────────────

@mcp.tool()
def scholar_bootstrap() -> str:
    """Full initialization: parse -> year-fix -> graph-build -> rag-index -> auto-notes -> quality -> classify.
    Run this once after setting up the project.
    """
    return _run_scholar("bootstrap", timeout=1200)


@mcp.tool()
def scholar_ingest(paper_id: str) -> str:
    """Ingest a single new paper: parse -> auto-notes -> quality-score -> classify.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    return _run_scholar("ingest", paper_id, timeout=120)


@mcp.tool()
def scholar_survey(topic: str, depth: str = "standard", limit: int = 20) -> str:
    """Full research survey pipeline: hybrid RAG search + graph query + classify + timeline.
    Generates a structured survey report in output/drafts/.

    Args:
        topic: Research topic or question
        depth: 'standard' or 'full'
        limit: Maximum papers to include (default 20)
    """
    args = ["survey", topic, "--depth", depth, "--limit", str(limit)]
    return _run_scholar(*args, timeout=300)


@mcp.tool()
def scholar_landscape(topic: str) -> str:
    """Field landscape analysis: domain tags + year distribution + quality + key papers.
    Generates a landscape report in output/drafts/.

    Args:
        topic: Research field or domain (e.g., NLP, RL, Safety, Transformer)
    """
    return _run_scholar("landscape", topic, timeout=300)


@mcp.tool()
def read_auto_note(paper_id: str) -> str:
    """Read the auto-generated reading note for a paper.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    from scholar.id_resolver import resolve_id
    ulid = resolve_id(paper_id) or paper_id
    path = PROJECT_ROOT / "output" / "notes" / f"{ulid}.md"
    if not path.exists():
        return f"Note for {paper_id} not found. Run: python -m scholar auto-notes {paper_id}"
    return path.read_text(encoding="utf-8")


@mcp.tool()
def read_quality_score(paper_id: str) -> str:
    """Read the quality score JSON for a paper (7 dimensions, A-F grade).

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    from scholar.id_resolver import resolve_id
    ulid = resolve_id(paper_id) or paper_id
    path = PROJECT_ROOT / "output" / "notes" / f"{ulid}-quality.json"
    if not path.exists():
        return f"Quality score for {paper_id} not found. Run: python -m scholar quality-score {paper_id}"
    return path.read_text(encoding="utf-8")


# ─── File Access ────────────────────────────────────────────────

@mcp.tool()
def read_parsed_paper(paper_id: str) -> str:
    """Read the full parsed JSON data for a paper (title, authors, sections, formulas, citations).

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    from scholar.id_resolver import resolve_id
    ulid = resolve_id(paper_id) or paper_id
    path = PROJECT_ROOT / "output" / "parsed" / f"{ulid}.json"
    if not path.exists():
        return f"Paper {paper_id} not found or not yet parsed."
    return path.read_text(encoding="utf-8")


@mcp.tool()
def read_skill(skill_name: str) -> str:
    """Read a skill's SKILL.md for step-by-step workflow instructions.

    Args:
        skill_name: Skill name (e.g., 'paper-deep-dive', 'research-survey', 'cold-start')
    """
    path = PROJECT_ROOT / ".qoder" / "skills" / skill_name / "SKILL.md"
    if not path.exists():
        return f"Skill '{skill_name}' not found. Available: {', '.join(p.name for p in (PROJECT_ROOT / '.qoder' / 'skills').iterdir() if p.is_dir())}"
    return path.read_text(encoding="utf-8")


# ─── KB Update ────────────────────────────────────────────────

@mcp.tool()
def scholar_arxiv_download(query: str, max_results: int = 10) -> str:
    """Download paper TeX sources from arXiv to local knowledge base.

    Args:
        query: arXiv search query
        max_results: Maximum papers to download (default: 10)
    """
    return _run_scholar("arxiv-download", query, "--max", str(max_results), timeout=600)


@mcp.tool()
def scholar_batch_ingest(ulids: str = "") -> str:
    """Batch ingest papers: parse -> metadata enrich -> graph update -> notes -> quality -> classify.

    Args:
        ulids: Comma-separated ULIDs to ingest (empty = all unparsed)
    """
    args = ["batch-ingest"]
    if ulids:
        args.extend(["--ulids", ulids])
    return _run_scholar(*args, timeout=600)


@mcp.tool()
def scholar_kb_update(query: str = "", max_results: int = 10) -> str:
    """One-command knowledge base update: search arXiv -> download -> batch ingest.

    Args:
        query: arXiv search query (empty = process local unparsed papers only)
        max_results: Maximum papers to download (default: 10)
    """
    args = ["kb-update", "--max", str(max_results)]
    if query:
        args.extend(["--query", query])
    return _run_scholar(*args, timeout=600)


@mcp.tool()
def scholar_metadata_enrich(apply: bool = False, limit: int = 0) -> str:
    """Backfill arxiv_id and DOI for existing papers via arXiv API search.

    Args:
        apply: If True, write changes. If False, dry-run preview.
        limit: Max papers to process (0=all)
    """
    args = ["metadata-enrich"]
    if apply:
        args.append("--apply")
    if limit > 0:
        args.extend(["--limit", str(limit)])
    return _run_scholar(*args, timeout=600)


# ─── Research Loop ──────────────────────────────────────────────

@mcp.tool()
def scholar_interests(action: str = "list", keywords: str = "", category: str = "general", max_results: int = 10, week: str = "", interests_found: int = 0) -> str:
    """Manage research directions and analyze conversation logs.

    Args:
        action: list, add, remove, logs (get unanalyzed week log), mark-analyzed
        keywords: Comma-separated keywords (for add)
        category: Interest category name
        max_results: Max results per search (for add, default 10)
        week: Week ID like 2026-W24 (for mark-analyzed)
        interests_found: Number of interests found (for mark-analyzed)
    """
    args = ["interests", action]
    if keywords:
        args.extend(["--keywords", keywords])
    if category != "general":
        args.extend(["--category", category])
    if action == "add":
        args.extend(["--max", str(max_results)])
    if week:
        args.extend(["--week", week])
    if action == "mark-analyzed":
        args.extend(["--found", str(interests_found)])
    return _run_scholar(*args, timeout=30)


@mcp.tool()
def scholar_research_sync(category: str = "", max_results: int = 10) -> str:
    """Search arXiv for a research direction and run full ingest pipeline.

    Args:
        category: Specific direction to sync (empty = all directions)
        max_results: Max papers per direction
    """
    args = ["research-sync", "--max", str(max_results)]
    if category:
        args.extend(["--category", category])
    return _run_scholar(*args, timeout=600)


# ─── Execution Layer ──────────────────────────────────────────

@mcp.tool()
def scholar_compile_paper(tex_file: str, report: bool = False, engine: str = "") -> str:
    """Compile a LaTeX paper to PDF with structured error reporting (FATAL/WARN/INFO).

    Args:
        tex_file: Path to .tex file (relative to project root)
        report: If True, only parse existing log without compiling
        engine: LaTeX engine override (e.g. 'xelatex'), defaults to config LATEX_CMD
    """
    args = ["compile-paper", tex_file]
    if report:
        args.append("--report")
    if engine:
        args.extend(["--engine", engine])
    return _run_scholar(*args, timeout=300)


@mcp.tool()
def scholar_exp_run(paper_id: str, mode: str = "quick", gpu: bool = False) -> str:
    """Run experiment code for a paper and collect metrics.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
        mode: 'quick' (CPU + synthetic data) or 'full'
        gpu: If True, use GPU
    """
    args = ["exp-run", paper_id, "--mode", mode]
    if gpu:
        args.append("--gpu")
    return _run_scholar(*args, timeout=3600)


@mcp.tool()
def scholar_exp_compare(paper_id: str, baseline_id: str = "") -> str:
    """Compare experiment results with paper-reported metrics.

    Args:
        paper_id: Paper ID
        baseline_id: Optional baseline paper ID for comparison
    """
    args = ["exp-compare", paper_id]
    if baseline_id:
        args.extend(["--baseline-id", baseline_id])
    return _run_scholar(*args, timeout=120)


@mcp.tool()
def scholar_exp_setup(paper_id: str, use_docker: bool = False) -> str:
    """Set up experiment environment (conda or Docker) for a paper.

    Args:
        paper_id: Paper ID
        use_docker: If True, use Docker instead of conda
    """
    args = ["exp-setup", paper_id]
    if use_docker:
        args.append("--docker")
    return _run_scholar(*args, timeout=120)


@mcp.tool()
def scholar_exp_debug(run_log: str) -> str:
    """Diagnose experiment failure from run log.

    Args:
        run_log: Path to run_log.txt file
    """
    return _run_scholar("exp-debug", run_log, timeout=60)


@mcp.tool()
def scholar_dataset_download(dataset_name: str, source: str = "auto") -> str:
    """Download a dataset used by a paper (HuggingFace / Papers with Code).

    Args:
        dataset_name: Dataset name or identifier
        source: Source: auto, huggingface, paperswithcode
    """
    return _run_scholar("dataset-download", dataset_name, "--source", source, timeout=600)


@mcp.tool()
def scholar_read_experiment_report(paper_id: str) -> str:
    """Read the experiment run log and results for a paper.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    from scholar.id_resolver import resolve_id
    ulid = resolve_id(paper_id) or paper_id
    exp_dir = PROJECT_ROOT / "output" / "experiments" / ulid
    log_path = exp_dir / "run_log.txt"
    results_path = exp_dir / "results.json"

    output = ""
    if log_path.exists():
        output += "=== Run Log ===\n" + log_path.read_text(encoding="utf-8")
    if results_path.exists():
        output += "\n=== Results ===\n" + results_path.read_text(encoding="utf-8")
    if not output:
        return f"No experiment results found for {paper_id}"
    return output


@mcp.tool()
def scholar_read_compile_log(paper_id: str) -> str:
    """Read the LaTeX compilation log for a paper's draft.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    from scholar.id_resolver import resolve_id
    ulid = resolve_id(paper_id) or paper_id
    # Check common compile output locations
    for subdir in ["pdfs", "drafts"]:
        log_path = PROJECT_ROOT / "output" / subdir / f"{ulid}.log"
        if log_path.exists():
            return log_path.read_text(encoding="utf-8")
    # Also check experiments dir
    log_path = PROJECT_ROOT / "output" / "experiments" / ulid / "compile.log"
    if log_path.exists():
        return log_path.read_text(encoding="utf-8")
    return f"No compile log found for {paper_id}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
