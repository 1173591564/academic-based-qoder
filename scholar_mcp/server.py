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
    instructions="Academic research toolkit with 440+ AI papers, citation graph, and Lean4 verification.",
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
def scholar_parse(ulid: str) -> str:
    """Parse a single paper's TeX source into structured JSON.

    Args:
        ulid: The paper's ULID identifier (e.g., 01KT6MT...)
    """
    return _run_scholar("parse", ulid)


@mcp.tool()
def scholar_parse_all() -> str:
    """Batch parse all unparsed papers. May take several minutes."""
    return _run_scholar("parse-all", timeout=600)


@mcp.tool()
def scholar_info(ulid: str) -> str:
    """Show detailed information about a parsed paper.

    Args:
        ulid: The paper's ULID identifier
    """
    return _run_scholar("info", ulid)


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
def scholar_cite_network(ulid: str | None = None) -> str:
    """Analyze citation network. Without ULID: global stats. With ULID: per-paper analysis.

    Args:
        ulid: Optional paper ULID for per-paper forward/backward citation analysis
    """
    args = ["cite-network"]
    if ulid:
        args.append(ulid)
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
def scholar_auto_notes(ulid: str | None = None, force: bool = False) -> str:
    """Generate structured reading notes. Without ULID: batch mode for all papers.

    Args:
        ulid: Optional paper ULID for single paper. Omit for batch.
        force: If True, overwrite existing notes.
    """
    args = ["auto-notes"]
    if ulid:
        args.append(ulid)
    if force:
        args.append("--force")
    return _run_scholar(*args, timeout=300)


@mcp.tool()
def scholar_quality_score(ulid: str | None = None, all_papers: bool = False) -> str:
    """Score paper quality across 7 dimensions (metadata/structure/citations/reproducibility/problem/innovation/experiments).

    Args:
        ulid: Optional paper ULID for single paper scoring.
        all_papers: If True, score all papers.
    """
    args = ["quality-score"]
    if ulid:
        args.append(ulid)
    elif all_papers:
        args.append("--all")
    return _run_scholar(*args, timeout=300)


@mcp.tool()
def scholar_classify(ulid: str | None = None, all_papers: bool = False, list_tags: bool = False) -> str:
    """Classify papers into domain/sub-direction/method tags.

    Args:
        ulid: Optional paper ULID for single paper.
        all_papers: If True, classify all papers.
        list_tags: If True, list all tags in corpus.
    """
    args = ["classify"]
    if ulid:
        args.append(ulid)
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
def scholar_ingest(ulid: str) -> str:
    """Ingest a single new paper: parse -> auto-notes -> quality-score -> classify.

    Args:
        ulid: The paper's ULID identifier
    """
    return _run_scholar("ingest", ulid, timeout=120)


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
def read_auto_note(ulid: str) -> str:
    """Read the auto-generated reading note for a paper.

    Args:
        ulid: The paper's ULID identifier
    """
    path = PROJECT_ROOT / "output" / "notes" / f"{ulid}.md"
    if not path.exists():
        return f"Note for {ulid} not found. Run: python -m scholar auto-notes {ulid}"
    return path.read_text(encoding="utf-8")


@mcp.tool()
def read_quality_score(ulid: str) -> str:
    """Read the quality score JSON for a paper (7 dimensions, A-F grade).

    Args:
        ulid: The paper's ULID identifier
    """
    path = PROJECT_ROOT / "output" / "notes" / f"{ulid}-quality.json"
    if not path.exists():
        return f"Quality score for {ulid} not found. Run: python -m scholar quality-score {ulid}"
    return path.read_text(encoding="utf-8")


# ─── File Access ────────────────────────────────────────────────

@mcp.tool()
def read_parsed_paper(ulid: str) -> str:
    """Read the full parsed JSON data for a paper (title, authors, sections, formulas, citations).

    Args:
        ulid: The paper's ULID identifier
    """
    path = PROJECT_ROOT / "output" / "parsed" / f"{ulid}.json"
    if not path.exists():
        return f"Paper {ulid} not found or not yet parsed."
    return path.read_text(encoding="utf-8")


@mcp.tool()
def read_skill(skill_name: str) -> str:
    """Read a skill's SKILL.md for step-by-step workflow instructions.

    Args:
        skill_name: Skill name (e.g., 'deep-read', 'research-survey', 'cold-start')
    """
    path = PROJECT_ROOT / ".qoder" / "skills" / skill_name / "SKILL.md"
    if not path.exists():
        return f"Skill '{skill_name}' not found. Available: {', '.join(p.name for p in (PROJECT_ROOT / '.qoder' / 'skills').iterdir() if p.is_dir())}"
    return path.read_text(encoding="utf-8")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
