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

# Use scholar.config for consistent path resolution across dev/frozen/workspace modes
from scholar import config as scholar_config
from scholar import db as dbmod
from scholar._state import init_shared_state, get_state

mcp = FastMCP(
    "Scholar Studio",
    instructions="Academic research toolkit with 555+ AI papers, citation graph, Lean4 verification, Hybrid ID, kb-update, and execution layer.",
)


def _resolve(paper_id: str) -> str:
    """Resolve hybrid ID to ULID using cached resolver (if available)."""
    state = get_state()
    if state:
        return state.resolve_id(paper_id) or paper_id
    from scholar.id_resolver import resolve_id
    return resolve_id(paper_id) or paper_id


def _run_scholar(*args: str, timeout: int = 120) -> str:
    """Run a scholar CLI command and return stdout."""
    cmd = [sys.executable, "-m", "scholar"] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(scholar_config.WORKSPACE_DIR),
    )
    output = result.stdout
    if result.returncode != 0 and result.stderr:
        output += f"\n[ERROR] {result.stderr}"
    return output.strip()


# ─── Paper Library ───────────────────────────────────────────────

@mcp.tool()
def scholar_scan() -> str:
    """Scan all papers and show parsing status (parsed/unparsed/failed)."""
    paper_dirs = sorted(scholar_config.PAPERS_DIR.iterdir())
    paper_dirs = [d for d in paper_dirs if d.is_dir()]
    parsed_ids = set(dbmod.list_parsed())
    lines = [f"Paper Library: {len(paper_dirs)} papers"]
    for d in paper_dirs[:30]:
        ulid = d.name
        src = any((d / n).exists() for n in ["source.tar.gz", "source.tgz", "source.tar", "source.zip"])
        pdf = (d / "paper.pdf").exists()
        parsed = ulid in parsed_ids
        status = "OK" if parsed else "--"
        lines.append(f"  [{status}] {ulid}  src={'Y' if src else 'N'}  pdf={'Y' if pdf else 'N'}")
    if len(paper_dirs) > 30:
        lines.append(f"  ... and {len(paper_dirs) - 30} more")
    total_parsed = sum(1 for d in paper_dirs if d.name in parsed_ids)
    lines.append(f"\nTotal: {len(paper_dirs)} | Parsed: {total_parsed}")
    return "\n".join(lines)


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
    ulid = _resolve(paper_id)
    data = dbmod.load_parsed(ulid)
    if data is None:
        return f"Paper not parsed yet. Run: scholar parse {paper_id}"
    lines = [
        f"Title:     {data.get('title', 'N/A')}",
        f"Authors:   {', '.join(data.get('authors', []))}",
        f"Year:      {data.get('year', 'N/A')}",
        f"Venue:     {data.get('venue', 'N/A')}",
        f"Sections:  {len(data.get('sections', []))}",
        f"Formulas:  {len(data.get('formulas', []))}",
        f"Citations: {len(data.get('citations', []))}",
    ]
    abstract = data.get("abstract")
    if abstract:
        lines.append(f"\nAbstract: {abstract[:500]}")
    return "\n".join(lines)


@mcp.tool()
def scholar_search(query: str) -> str:
    """Full-text search across all parsed papers (title, abstract, sections).

    Args:
        query: Search keyword or phrase
    """
    keyword_lower = query.lower()
    results = []
    for paper_id in dbmod.list_parsed():
        data = dbmod.load_parsed(paper_id)
        if not data:
            continue
        score = 0
        if keyword_lower in (data.get("title") or "").lower():
            score += 10
        if keyword_lower in (data.get("abstract") or "").lower():
            score += 5
        for s in data.get("sections", []):
            if keyword_lower in s.get("content", "").lower():
                score += 1
                if score >= 3:
                    break
        if score > 0:
            results.append({"paper_id": paper_id, "title": data.get("title", "N/A"), "year": data.get("year"), "score": score})
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:20]
    if not results:
        return f"No results for '{query}'"
    lines = [f"Search: '{query}' ({len(results)} results)"]
    for r in results:
        lines.append(f"  {r['paper_id']}  {(r['title'] or 'N/A')[:60]}  {r.get('year', '')}")
    return "\n".join(lines)


@mcp.tool()
def scholar_list_papers(year: int | None = None) -> str:
    """List all parsed papers with metadata. Optionally filter by year.

    Args:
        year: Optional year filter (e.g., 2023)
    """
    papers = []
    for paper_id in dbmod.list_parsed():
        data = dbmod.load_parsed(paper_id)
        if data:
            if year and data.get("year") != year:
                continue
            papers.append(data)
    papers.sort(key=lambda x: x.get("year") or 0, reverse=True)
    papers = papers[:30]
    lines = [f"Parsed Papers ({len(papers)} shown)"]
    for p in papers:
        lines.append(f"  {p.get('paper_id', '')}  {(p.get('title') or 'N/A')[:50]}  {p.get('year', '')}  {p.get('venue', '') or ''}")
    return "\n".join(lines)


@mcp.tool()
def scholar_stats() -> str:
    """Show knowledge base statistics: paper count, field coverage, venue distribution."""
    paper_dirs = [d for d in scholar_config.PAPERS_DIR.iterdir() if d.is_dir()]
    parsed_ids = dbmod.list_parsed()
    total_formulas = 0
    total_citations = 0
    total_sections = 0
    has_year = 0
    has_authors = 0
    has_abstract = 0
    has_venue = 0
    years = {}
    venues = {}
    for pid in parsed_ids:
        data = dbmod.load_parsed(pid)
        if not data:
            continue
        y = data.get("year")
        if y:
            years[y] = years.get(y, 0) + 1
            has_year += 1
        if data.get("authors"):
            has_authors += 1
        if data.get("abstract"):
            has_abstract += 1
        v = data.get("venue")
        if v:
            venues[v] = venues.get(v, 0) + 1
            has_venue += 1
        total_formulas += len(data.get("formulas", []))
        total_citations += len(data.get("citations", []))
        total_sections += len(data.get("sections", []))
    total = len(parsed_ids) or 1
    lines = [
        f"Paper folders:   {len(paper_dirs)}",
        f"Parsed:          {len(parsed_ids)}",
        f"Total sections:  {total_sections}",
        f"Total formulas:  {total_formulas}",
        f"Total citations: {total_citations}",
        f"",
        f"Metadata Coverage:",
        f"  Year:      {has_year}/{total} ({has_year*100//total}%)",
        f"  Authors:   {has_authors}/{total} ({has_authors*100//total}%)",
        f"  Abstract:  {has_abstract}/{total} ({has_abstract*100//total}%)",
        f"  Venue:     {has_venue}/{total} ({has_venue*100//total}%)",
    ]
    if years:
        year_str = ", ".join(f"{y}: {c}" for y, c in sorted(years.items()))
        lines.append(f"\nBy Year: {year_str}")
    if venues:
        sorted_venues = sorted(venues.items(), key=lambda x: x[1], reverse=True)[:10]
        venue_str = ", ".join(f"{v}: {c}" for v, c in sorted_venues)
        lines.append(f"By Venue: {venue_str}")
    return "\n".join(lines)


@mcp.tool()
def scholar_export_bib(output: str = "output/bib/references.bib") -> str:
    """Export BibTeX entries for all parsed papers.

    Args:
        output: Output .bib file path (default: output/bib/references.bib)
    """
    entries = []
    for paper_id in dbmod.list_parsed():
        data = dbmod.load_parsed(paper_id)
        if not data:
            continue
        title = data.get("title", "Untitled")
        authors = " and ".join(data.get("authors", ["Unknown"]))
        year = data.get("year", "")
        venue = data.get("venue", "")
        entry = f"@article{{{paper_id},\n  title = {{{title}}},\n  author = {{{authors}}},"
        if year:
            entry += f"\n  year = {{{year}}},"
        if venue:
            entry += f"\n  journal = {{{venue}}},"
        entry += "\n}\n"
        entries.append(entry)
    out_path = scholar_config.PROJECT_ROOT / output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(entries), encoding="utf-8")
    return f"Exported {len(entries)} BibTeX entries to {out_path}"


@mcp.tool()
def scholar_year_fix(apply: bool = False) -> str:
    """Fill missing publication years by cross-referencing Lean4 Database.lean.

    Args:
        apply: If True, write changes to JSON files. If False, dry-run preview.
    """
    from scholar import year_fix as yf
    stats, updates = yf.complete_years(dry_run=not apply)
    lines = [
        f"Lean4 papers: {stats['lean_papers']}",
        f"Matched: {stats['matched']}",
        f"{'Filled' if apply else 'Would fill'}: {stats['filled']}",
        f"Still missing: {stats['still_missing']}",
    ]
    if stats['still_missing'] > 0:
        arxiv_result = yf.complete_years_arxiv(dry_run=not apply, limit=stats['still_missing'])
        lines.append(f"arXiv fallback: queried={arxiv_result['queried']}, filled={arxiv_result['filled']}")
    return "\n".join(lines)


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
    try:
        from scholar import graph_db as gdb_mod
        gdb = gdb_mod.GraphDB()
        if not gdb.available:
            return "Neo4j not available. Run: docker compose up -d neo4j"
        papers = gdb_mod.find_papers_by_concept(gdb, concept)
        related = gdb_mod.find_related_concepts(gdb, concept)
        gdb.close()
        lines = [f"Papers with concept: {concept} ({len(papers)})"]
        for p in papers[:20]:
            lines.append(f"  {(p.get('title') or 'N/A')[:50]}  {p.get('year', '')}  {p.get('venue', '') or ''}")
        if related:
            lines.append("\nRelated concepts:")
            for r in related:
                lines.append(f"  {r['id']} (weight: {r['weight']})")
        return "\n".join(lines)
    except Exception as e:
        return f"Graph query failed: {e}"


@mcp.tool()
def scholar_cite_network(paper_id: str | None = None) -> str:
    """Analyze citation network. Without paper_id: global stats. With paper_id: per-paper analysis.

    Args:
        paper_id: Optional paper ID (ULID/arXiv/DOI/slug) for per-paper forward/backward citation analysis
    """
    try:
        from scholar import graph_db as gdb_mod
        gdb = gdb_mod.GraphDB()
        if not gdb.available:
            return "Neo4j not available. Run: docker compose up -d neo4j"
        if paper_id:
            ulid = _resolve(paper_id)
            forward = gdb_mod.get_forward_citations(gdb, ulid)
            backward = gdb_mod.get_backward_citations(gdb, ulid)
            lines = [f"Forward citations ({len(forward)}):"]
            for p in forward[:10]:
                lines.append(f"  -> [{p.get('year', '?')}] {(p.get('title') or 'N/A')[:50]}")
            lines.append(f"\nBackward citations ({len(backward)}):")
            for p in backward[:10]:
                lines.append(f"  <- [{p.get('year', '?')}] {(p.get('title') or 'N/A')[:50]}")
            gdb.close()
            return "\n".join(lines)
        else:
            stats = gdb_mod.get_citation_stats(gdb)
            gdb.close()
            lines = [
                f"Total papers in graph: {stats['total_papers']}",
                f"Total citation edges:  {stats['total_citations']}",
            ]
            if stats.get("most_cited"):
                lines.append("\nMost cited papers:")
                for p in stats["most_cited"][:10]:
                    lines.append(f"  {(p.get('title') or p.get('ulid', ''))[:50]}  cited by {p.get('cited_by', 0)}")
            return "\n".join(lines)
    except Exception as e:
        return f"Citation network analysis failed: {e}"


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
    from scholar import rag
    if hybrid:
        results = rag.search_rag_hybrid(query, limit=10)
        title = f"Hybrid Search: '{query}' ({len(results)} results)"
    else:
        results = rag.search_rag(query, limit=10)
        title = f"RAG Search: '{query}' ({len(results)} results)"
    if not results:
        return f"No RAG results for '{query}'. Build index first: scholar rag-index"
    lines = [title]
    for r in results:
        lines.append(f"  {r.get('paper_id', '')}  {(r.get('section') or '')[:15]}  {(r.get('content') or '')[:60]}  sim={r.get('similarity', 0):.3f}")
    return "\n".join(lines)


# ─── External ───────────────────────────────────────────────────

@mcp.tool()
def scholar_arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv for papers. Useful for finding recent work not in local library.

    Args:
        query: Search query (supports arXiv query syntax)
        max_results: Maximum number of results (default: 10)
    """
    try:
        import xml.etree.ElementTree as ET
        xml_data = scholar_config.arxiv_request(f"all:{query}", max_results=max_results)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_data)
        entries = root.findall("atom:entry", ns)
        if not entries:
            return "No results found."
        lines = [f"arXiv Results ({len(entries)}):"]
        for i, entry in enumerate(entries):
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += " et al."
            published = entry.find("atom:published", ns).text[:4]
            arxiv_id = entry.find("atom:id", ns).text.split("/abs/")[-1]
            lines.append(f"  {i+1}. {title[:55]}  {author_str[:30]}  {published}  {arxiv_id}")
        return "\n".join(lines)
    except Exception as e:
        return f"arXiv search failed: {e}"


# ─── Metadata Completion ─────────────────────────────────────────

@mcp.tool()
def scholar_graph_stats() -> str:
    """Show detailed graph statistics: nodes, edges, centrality top-10, isolated nodes."""
    try:
        from scholar import graph_db as gdb_mod
        gdb = gdb_mod.GraphDB()
        if not gdb.available:
            return "Neo4j not available. Run: docker compose up -d neo4j"
        paper_count = gdb.run("MATCH (p:Paper) RETURN count(p) AS c")[0]["c"]
        innov_count = gdb.run("MATCH (i:Innovation) RETURN count(i) AS c")[0]["c"]
        cites_count = gdb.run("MATCH ()-[c:CITES]->() RETURN count(c) AS c")[0]["c"]
        concept_count = gdb.run("MATCH ()-[h:HAS_CONCEPT]->() RETURN count(h) AS c")[0]["c"]
        lines = [
            f"Paper nodes:      {paper_count}",
            f"Innovation nodes: {innov_count}",
            f"CITES edges:      {cites_count}",
            f"HAS_CONCEPT:      {concept_count}",
        ]
        top_cited = gdb.run("MATCH (p:Paper) WHERE p.in_degree > 0 RETURN p.title AS title, p.in_degree AS score ORDER BY score DESC LIMIT 10")
        if top_cited:
            lines.append("\nTop cited papers:")
            for r in top_cited:
                lines.append(f"  {(r.get('title') or 'N/A')[:60]}  cited by {r.get('score', 0)}")
        gdb.close()
        return "\n".join(lines)
    except Exception as e:
        return f"Graph stats failed: {e}"


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
def scholar_venue_fix(apply: bool = False) -> str:
    """Fill missing venue fields using heuristics (arxiv_id → 'arXiv', title-only → 'Preprint').

    Args:
        apply: If True, write changes. If False, dry-run preview.
    """
    import json as _json
    parsed_dir = scholar_config.PARSED_DIR
    fixed_arxiv = 0
    fixed_preprint = 0
    skipped = 0
    for json_file in sorted(parsed_dir.glob("*.json")):
        try:
            data = _json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            skipped += 1
            continue
        if data.get("venue"):
            continue
        venue = None
        if data.get("arxiv_id"):
            venue = "arXiv"
            fixed_arxiv += 1
        elif data.get("title"):
            venue = "Preprint"
            fixed_preprint += 1
        else:
            skipped += 1
            continue
        if apply and venue:
            data["venue"] = venue
            json_file.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    total = fixed_arxiv + fixed_preprint
    return f"{'Fixed' if apply else 'Would fix'}: {total} (arXiv: {fixed_arxiv}, Preprint: {fixed_preprint})"


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
    path = scholar_config.NOTES_DIR / f"{ulid}.md"
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
    path = scholar_config.NOTES_DIR / f"{ulid}-quality.json"
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
    path = scholar_config.PARSED_DIR / f"{ulid}.json"
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
def scholar_interests(action: str = "list", keywords: str = "", category: str = "general", max_results: int = 10, week: str = "", interests_found: int = 0, project: str = "") -> str:
    """Manage research directions and analyze conversation logs.

    Args:
        action: list, add, remove, logs (get unanalyzed week log), mark-analyzed
        keywords: Comma-separated keywords (for add)
        category: Interest category name
        max_results: Max results per search (for add, default 10)
        week: Week ID like 2026-W24 (for mark-analyzed)
        interests_found: Number of interests found (for mark-analyzed)
        project: Project name (for mark-analyzed, empty = current project)
    """
    from scholar import research_loop as rl
    if action == "list":
        data = rl.load_interests()
        if not data["interests"]:
            return "No interests configured. Use: interests add --keywords \"...\" --category \"...\""
        lines = [f"Research Interests ({len(data['interests'])} directions):"]
        for i, item in enumerate(data["interests"], 1):
            lines.append(f"  {i}. [{item['category']}] {item['keywords']}")
            lines.append(f"     Searches: {item.get('search_count', 0)} | Last: {item.get('last_searched', 'never')}")
        return "\n".join(lines)
    elif action == "add":
        if not keywords:
            return "Error: keywords required for add action"
        rl.add_interest(keywords, category, max_results)
        return f"Added direction [{category}]: {keywords}"
    elif action == "remove":
        _, removed = rl.remove_interest(category)
        if removed:
            return f"Removed direction [{category}]"
        return f"Direction [{category}] not found"
    elif action in ("logs", "mark-analyzed"):
        # Complex operations — delegate to CLI
        args = ["interests", action]
        if week:
            args.extend(["--week", week])
        if action == "mark-analyzed":
            args.extend(["--found", str(interests_found)])
        if project:
            args.extend(["--project", project])
        return _run_scholar(*args, timeout=30)
    return f"Unknown action: {action}. Available: list, add, remove, logs, mark-analyzed"


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
    exp_dir = scholar_config.EXPERIMENTS_DIR / ulid
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
    for log_path in [scholar_config.PDFS_DIR / f"{ulid}.log",
                     scholar_config.DRAFTS_DIR / f"{ulid}.log"]:
        if log_path.exists():
            return log_path.read_text(encoding="utf-8")
    # Also check experiments dir
    log_path = scholar_config.EXPERIMENTS_DIR / ulid / "compile.log"
    if log_path.exists():
        return log_path.read_text(encoding="utf-8")
    return f"No compile log found for {paper_id}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
