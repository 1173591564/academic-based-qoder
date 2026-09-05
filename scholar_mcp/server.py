"""
Scholar Studio MCP Server (v0.2.3)

Model-facing surface: 16 focused tools organised as a reading ladder.

  L1 find papers      scholar_search (lexical) / scholar_vec_search (semantic)
  L2 paper digest     scholar_info (abstract + section TOC)
  L3 read sections    scholar_section (single section body)
  L4 locate passages  scholar_passages (vector chunk search, optional scope)
  horizontal          scholar_cite_network / scholar_graph_query /
                      scholar_lineage / scholar_graph_stats
  utilities           scholar_list_papers / scholar_arxiv_search /
                      read_parsed_paper (digest default, full gated) /
                      scholar_read_output_file / read_skill /
                      scholar_auto_notes / scholar_interests

Context economy contract: every tool returns a bounded result; full-paper
dumps require an explicit full=True escape hatch. The corpus tools query a
single version-pinned PostgreSQL/pgvector snapshot.

Run: python -m scholar_mcp
"""

import logging
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from scholar import config as scholar_config
from scholar import research_loop as rl
from scholar_mcp import v2_adapter
from scholar_mcp.transport import run_transport

mcp = FastMCP(
    "Scholar Studio",
    host=os.getenv("SCHOLAR_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("SCHOLAR_MCP_PORT", "8000")),
    instructions=(
        "Academic research toolkit over the server's configured corpus. "
        "Reading ladder: search/vec-search for relevance → scholar_info for "
        "abstract+TOC → scholar_section for the sections you actually need. "
        "Never read full papers unless truly required."
    ),
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)

# ─── shared helpers ─────────────────────────────────────────────────────────

MAX_FULL_JSON_CHARS = 200_000
SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _corpus_call(operation, *args) -> str:
    try:
        return operation(*args)
    except Exception as error:
        return v2_adapter.error_text(error)


def _run_scholar(*args: str, timeout: int = 120) -> str:
    """Run a scholar CLI command and return stdout."""
    cmd = [sys.executable, "-m", "scholar"] + list(args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(scholar_config.WORKSPACE_DIR),
        )
    except subprocess.TimeoutExpired:
        return f"[ERROR] Command timed out after {timeout}s: {' '.join(args)}"
    output = result.stdout
    if result.returncode != 0:
        return f"[ERROR] Scholar command failed with exit code {result.returncode}."
    return output.strip()


# ─── L1: find papers ────────────────────────────────────────────────────────


@mcp.tool()
def scholar_search(query: str, limit: int = 10) -> str:
    """Lexical search across paper titles and abstracts.

    Args:
        query: Keywords or a short phrase (multi-word works best)
        limit: Max results (default 10)
    """
    return _corpus_call(v2_adapter.search, query, max(1, min(limit, 20)))


@mcp.tool()
def scholar_vec_search(question: str, k: int = 8) -> str:
    """Semantic paper search: match a natural-language research question to
    chunk embeddings, then return distinct matching papers.

    Args:
        question: The user's academic question in natural language
        k: Max papers to return (default 8)
    """
    return _corpus_call(v2_adapter.vector_search, question, max(1, min(k, 20)))


# ─── L2: paper digest ───────────────────────────────────────────────────────


@mcp.tool()
def scholar_info(paper_id: str) -> str:
    """Paper digest: metadata + abstract + section TOC (no section bodies).

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    return _corpus_call(v2_adapter.paper_info, paper_id)


# ─── L3: read a single section ──────────────────────────────────────────────


@mcp.tool()
def scholar_section(paper_id: str, section: str, span: int = 1) -> str:
    """Read ONE section's content (bounded). Prefer digest TOC indices.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
        section: Section heading text, or TOC index like "7" or "[7]"
        span: How many consecutive sections to include from the start
              position (default 1 = only the matched one)
    """
    return _corpus_call(v2_adapter.section, paper_id, section, max(1, min(span, 5)))


# ─── L4: passage location (optional) ────────────────────────────────────────


@mcp.tool()
def scholar_passages(
    query: str,
    k: int = 10,
    paper_id: str | None = None,
    section: str | None = None,
    hybrid: bool = False,
) -> str:
    """Locate matching passages with vector or hybrid retrieval.

    Args:
        query: Text to locate (keywords or a phrase)
        k: Max passages (default 10)
        paper_id: Optional scope to one paper
        section: Optional substring filter on section name
        hybrid: Fuse vector and lexical results; falls back to lexical if the
                active vector provider is unavailable
    """
    return _corpus_call(
        v2_adapter.passages,
        query,
        max(1, min(k, 20)),
        paper_id,
        section,
        hybrid,
    )


# ─── Horizontal: citation / concept graph ──────────────────────────────────


@mcp.tool()
def scholar_cite_network(paper_id: str | None = None) -> str:
    """Citation network. Without paper_id: aggregate graph counts. With
    paper_id: internal-library outgoing and incoming citations.

    Args:
        paper_id: Optional Paper ID (ULID/arXiv/DOI/slug)
    """
    return _corpus_call(v2_adapter.cite_network, paper_id)


@mcp.tool()
def scholar_graph_query(concept: str) -> str:
    """Find lexical paper candidates for a concept.

    This compatibility tool does not infer semantic concept relationships.

    Args:
        concept: Concept name (e.g., 'transformer', 'MoE', 'diffusion')
    """
    return _corpus_call(v2_adapter.graph_query, concept)


@mcp.tool()
def scholar_lineage(paper_a: str, paper_b: str) -> str:
    """Shortest citation path between two papers (any direction, multi-hop).

    Args:
        paper_a: Paper ID (ULID/arXiv/DOI/slug)
        paper_b: Paper ID (ULID/arXiv/DOI/slug)
    """
    return _corpus_call(v2_adapter.lineage, paper_a, paper_b)


@mcp.tool()
def scholar_graph_stats() -> str:
    """Graph counts for papers, authors, citations, and authorship edges."""
    return _corpus_call(v2_adapter.graph_stats)


# ─── Utilities ──────────────────────────────────────────────────────────────


@mcp.tool()
def scholar_list_papers(year: int | None = None, offset: int = 0) -> str:
    """List parsed papers (30 per page), newest first. Optional year filter.

    Args:
        year: Optional year filter (e.g., 2023)
        offset: Pagination offset
    """
    return _corpus_call(v2_adapter.list_papers, year, max(0, offset))


@mcp.tool()
def scholar_arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv for papers outside the local library.

    Args:
        query: arXiv search query
        max_results: Max results (default 10)
    """
    try:
        xml_data = scholar_config.arxiv_request(f"all:{query}", max_results=max_results)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_data)
        entries = root.findall("atom:entry", ns)
        if not entries:
            return "No results found."
        lines = [f"arXiv Results ({len(entries)}):"]
        for i, entry in enumerate(entries):
            title_elem = entry.find("atom:title", ns)
            title = (
                title_elem.text.strip().replace("\n", " ")
                if title_elem is not None and title_elem.text
                else "(no title)"
            )
            author_names = []
            for a in entry.findall("atom:author", ns):
                name_elem = a.find("atom:name", ns)
                if name_elem is not None and name_elem.text:
                    author_names.append(name_elem.text)
            author_str = ", ".join(author_names[:3])
            if len(author_names) > 3:
                author_str += " et al."
            pub_elem = entry.find("atom:published", ns)
            published = (
                pub_elem.text[:4] if pub_elem is not None and pub_elem.text else "????"
            )
            id_elem = entry.find("atom:id", ns)
            arxiv_id = (
                id_elem.text.split("/abs/")[-1]
                if id_elem is not None and id_elem.text
                else "unknown"
            )
            lines.append(
                f"  {i + 1}. {title[:55]}  {author_str[:30]}  {published}  {arxiv_id}"
            )
        return "\n".join(lines)
    except Exception as error:
        logger.warning("arXiv search failed (%s)", type(error).__name__)
        return "arXiv search failed."


@mcp.tool()
def read_parsed_paper(paper_id: str, full: bool = False) -> str:
    """Read a paper. Default: bounded digest (abstract + section TOC).
    full=True dumps the complete parsed JSON — only when truly necessary.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
        full: Escape hatch for the complete parsed JSON (capped at 200KB)
    """
    return _corpus_call(
        v2_adapter.parsed_paper,
        paper_id,
        full,
        MAX_FULL_JSON_CHARS,
    )


@mcp.tool()
def scholar_read_output_file(path: str) -> str:
    """Read any file from the output directory (notes, logs, results).

    Args:
        path: Relative path from output/ (e.g., 'notes/01KT6MTBK1PQMNZM8ZYQPTVN6C.md')
    """
    try:
        output_root = (scholar_config.OUTPUT_DIR).resolve()
        if Path(path).is_absolute():
            return "Access denied: path must be relative to the output directory"
        full_path = (output_root / path).resolve()
        if not full_path.is_relative_to(output_root):
            return "Access denied: path resolves outside the output directory"
        if not full_path.exists():
            return f"File not found: {path}"
        if not full_path.is_file():
            return f"File not found: {path}"
        if full_path.stat().st_size > 500_000:
            return (
                f"File too large ({full_path.stat().st_size} bytes). "
                f"Read it in chunks via the workspace file tools."
            )
        return full_path.read_text(encoding="utf-8")
    except OSError as error:
        logger.warning("output file read failed (%s)", type(error).__name__)
        return "Read output file failed."


@mcp.tool()
def read_skill(skill_name: str) -> str:
    """Read a skill's SKILL.md for step-by-step workflow instructions.

    Args:
        skill_name: Skill name (e.g., 'paper-deep-dive', 'research-survey')
    """
    roots = [
        PROJECT_ROOT / ".scholar" / "skills",
        scholar_config.SCHOLAR_HOME / ".scholar" / "skills",
        Path(__file__).resolve().parent.parent / "scholar" / "templates" / "skills",
    ]
    available = {
        child.name
        for root in roots
        if root.exists()
        for child in root.iterdir()
        if child.is_dir() and SKILL_NAME_PATTERN.fullmatch(child.name)
    }
    if not SKILL_NAME_PATTERN.fullmatch(skill_name) or skill_name not in available:
        return f"Skill not found. Available: {', '.join(sorted(available))}"
    for root in roots:
        resolved_root = root.resolve()
        candidate = (resolved_root / skill_name / "SKILL.md").resolve()
        if candidate.is_relative_to(resolved_root) and candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8")
            except OSError as error:
                logger.warning("skill read failed (%s)", type(error).__name__)
                return "Skill read failed."
    return f"Skill not found. Available: {', '.join(sorted(available))}"


@mcp.tool()
def scholar_auto_notes(paper_id: str | None = None, force: bool = False) -> str:
    """Generate structured reading notes (JSON status). Single paper or batch.

    Args:
        paper_id: Optional Paper ID; omit for batch over all papers
        force: Overwrite existing notes
    """
    return _corpus_call(v2_adapter.auto_notes, paper_id, force)


@mcp.tool()
def scholar_interests(
    action: str = "list",
    keywords: str = "",
    category: str = "general",
    max_results: int = 10,
    week: str = "",
    interests_found: int = 0,
    project: str = "",
) -> str:
    """Manage research directions (list/add/remove/logs/mark-analyzed).

    Args:
        action: One of list, add, remove, logs, mark-analyzed
        keywords: Comma-separated keywords (for add)
        category: Interest category name
        max_results: Max results per search (for add)
        week: Week ID like 2026-W24 (for mark-analyzed)
        interests_found: Count found (for mark-analyzed)
        project: Project name (for mark-analyzed)
    """
    if action in ("logs", "mark-analyzed"):
        args = ["interests", action]
        if week:
            args.extend(["--week", week])
        if action == "mark-analyzed":
            args.extend(["--found", str(interests_found)])
        if project:
            args.extend(["--project", project])
        return _run_scholar(*args, timeout=30)
    try:
        if action == "list":
            data = rl.load_interests()
            if not data["interests"]:
                return (
                    "No interests configured. Use: interests add "
                    '--keywords "..." --category "..."'
                )
            lines = [f"Research Interests ({len(data['interests'])} directions):"]
            for i, item in enumerate(data["interests"], 1):
                lines.append(f"  {i}. [{item['category']}] {item['keywords']}")
                lines.append(
                    f"     Searches: {item.get('search_count', 0)} | "
                    f"Last: {item.get('last_searched', 'never')}"
                )
            return "\n".join(lines)
        if action == "add":
            if not keywords:
                return "Error: keywords required for add action"
            rl.add_interest(keywords, category, max_results)
            return f"Added direction [{category}]: {keywords}"
        if action == "remove":
            _, removed = rl.remove_interest(category)
            return (
                f"Removed direction [{category}]"
                if removed
                else f"Direction [{category}] not found"
            )
    except Exception as error:
        logger.warning("interests action failed (%s)", type(error).__name__)
        return f"Interests {action} failed."
    return (
        f"Unknown action: {action}. Available: list, add, remove, logs, mark-analyzed"
    )


def main():
    """stdio 为默认（dsh 本地挂载）；streamable-http 供服务器集中部署
    （队友 MCP over HTTP，数据与索引全部留在服务器，本地零论文数据）。
    host/port 由 SCHOLAR_MCP_HOST / SCHOLAR_MCP_PORT 控制；
    HTTP 默认要求 SCHOLAR_MCP_TOKEN；仅显式启用
    SCHOLAR_MCP_ALLOW_INSECURE_LOOPBACK=1 时允许回环无鉴权。"""
    run_transport(mcp)


if __name__ == "__main__":
    main()
