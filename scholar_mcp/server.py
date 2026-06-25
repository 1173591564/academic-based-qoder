"""
Scholar Studio MCP Server

IDE-agnostic academic research toolkit — exposes scholar CLI as MCP tools.
Run: python -m scholar_mcp
"""
import subprocess
import json
import sys
import time as _time
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
    instructions="Academic research toolkit with 563+ AI papers, citation graph, Lean4 verification, Hybrid ID, kb-update, and execution layer.",
)


def _resolve(paper_id: str) -> str:
    """Resolve hybrid ID to ULID using cached resolver (if available)."""
    state = get_state()
    if state:
        return state.resolve_id(paper_id) or paper_id
    from scholar.id_resolver import resolve_id
    return resolve_id(paper_id) or paper_id


def _load_parsed(paper_id: str) -> dict | None:
    """Load parsed JSON with LRU cache (if SharedState available)."""
    state = get_state()
    if state:
        return state.get_parsed(paper_id)
    return dbmod.load_parsed(paper_id)


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
    if result.returncode != 0 and result.stderr:
        output += f"\n[ERROR] {result.stderr}"
    return output.strip()


# Stats cache: avoid re-iterating 560+ JSONs on every call
_stats_cache: dict = {"data": None, "ts": 0}
_STATS_CACHE_TTL = 300  # 5 minutes


def _get_stats_cached() -> dict:
    """Get KB stats with TTL cache to avoid repeated full scans."""
    now = _time.time()
    if _stats_cache["data"] is not None and (now - _stats_cache["ts"]) < _STATS_CACHE_TTL:
        return _stats_cache["data"]
    # Compute fresh stats
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
        data = _load_parsed(pid)
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
    stats = {
        "paper_folders": len(paper_dirs),
        "parsed": len(parsed_ids),
        "sections": total_sections,
        "formulas": total_formulas,
        "citations": total_citations,
        "coverage": {
            "year": round(has_year / total, 2),
            "authors": round(has_authors / total, 2),
            "abstract": round(has_abstract / total, 2),
            "venue": round(has_venue / total, 2),
        },
        "by_year": dict(sorted(years.items())),
        "by_venue": dict(sorted(venues.items(), key=lambda x: x[1], reverse=True)[:10]),
        "has_year": has_year,
        "has_authors": has_authors,
        "has_abstract": has_abstract,
        "has_venue": has_venue,
        "total": total,
        "years": years,
        "venues": venues,
    }
    _stats_cache["data"] = stats
    _stats_cache["ts"] = now
    return stats


# ─── Paper Library ────────────────────────────────────────────

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
    data = _load_parsed(ulid)
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
    if not query or not query.strip():
        return json.dumps({"error": "query must be non-empty"}, ensure_ascii=False)
    keyword_lower = query.lower()
    results = []

    # Performance: try PostgreSQL first for fast title/abstract/section search
    state = get_state()
    db = state.get_db() if state else None
    db_results = None
    if db and db.available:
        try:
            db_results = db.search_papers(query)
        except Exception:
            db_results = None

    if db_results is not None:
        # DB path: only load matched papers for scoring
        for row in db_results:
            paper_id = row.get("id", "")
            data = _load_parsed(paper_id)
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
    else:
        # Fallback: file scan (uses LRU cache)
        for paper_id in dbmod.list_parsed():
            data = _load_parsed(paper_id)
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
def scholar_list_papers(year: int | None = None, offset: int = 0) -> str:
    """List all parsed papers with metadata. Optionally filter by year.

    Args:
        year: Optional year filter (e.g., 2023)
        offset: Pagination offset (default 0, shows 30 per page)
    """
    papers = []
    for paper_id in dbmod.list_parsed():
        data = _load_parsed(paper_id)
        if data:
            if year and data.get("year") != year:
                continue
            papers.append(data)
    papers.sort(key=lambda x: x.get("year") or 0, reverse=True)
    total_count = len(papers)
    papers = papers[offset:offset + 30]
    lines = [f"Parsed Papers ({len(papers)} shown, total {total_count}, offset {offset})"]
    for p in papers:
        lines.append(f"  {p.get('paper_id', '')}  {(p.get('title') or 'N/A')[:50]}  {p.get('year', '')}  {p.get('venue', '') or ''}")
    return "\n".join(lines)


@mcp.tool()
def scholar_stats() -> str:
    """Show knowledge base statistics: paper count, field coverage, venue distribution."""
    stats = _get_stats_cached()
    total = stats["total"]
    lines = [
        f"Paper folders:   {stats['paper_folders']}",
        f"Parsed:          {stats['parsed']}",
        f"Total sections:  {stats['sections']}",
        f"Total formulas:  {stats['formulas']}",
        f"Total citations: {stats['citations']}",
        f"",
        f"Metadata Coverage:",
        f"  Year:      {stats['has_year']}/{total} ({stats['has_year']*100//total}%)",
        f"  Authors:   {stats['has_authors']}/{total} ({stats['has_authors']*100//total}%)",
        f"  Abstract:  {stats['has_abstract']}/{total} ({stats['has_abstract']*100//total}%)",
        f"  Venue:     {stats['has_venue']}/{total} ({stats['has_venue']*100//total}%)",
    ]
    if stats["years"]:
        year_str = ", ".join(f"{y}: {c}" for y, c in sorted(stats["years"].items()))
        lines.append(f"\nBy Year: {year_str}")
    if stats["venues"]:
        sorted_venues = sorted(stats["venues"].items(), key=lambda x: x[1], reverse=True)[:10]
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
        data = _load_parsed(paper_id)
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
    # Security: validate output path stays within output/bib/
    bib_root = (scholar_config.OUTPUT_DIR / "bib").resolve()
    out_path = (scholar_config.PROJECT_ROOT / output).resolve()
    if not str(out_path).startswith(str(bib_root)):
        return f"Access denied: output path must be within output/bib/"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(entries), encoding="utf-8")
    return f"Exported {len(entries)} BibTeX entries to {out_path}"


@mcp.tool()
def scholar_year_fix(apply: bool = False) -> str:
    """Fill missing publication years by cross-referencing Lean4 Database.lean.

    Args:
        apply: If True, write changes to JSON files. If False, dry-run preview.
    """
    try:
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
    except Exception as e:
        return f"Year fix failed: {e}"


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
        try:
            if not gdb.available:
                return "Neo4j not available. Run: docker compose up -d neo4j"
            papers = gdb_mod.find_papers_by_concept(gdb, concept)
            related = gdb_mod.find_related_concepts(gdb, concept)
        finally:
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
        try:
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
                return "\n".join(lines)
            else:
                stats = gdb_mod.get_citation_stats(gdb)
                lines = [
                    f"Total papers in graph: {stats['total_papers']}",
                    f"Total citation edges:  {stats['total_citations']}",
                ]
                if stats.get("most_cited"):
                    lines.append("\nMost cited papers:")
                    for p in stats["most_cited"][:10]:
                        lines.append(f"  {(p.get('title') or p.get('ulid', ''))[:50]}  cited by {p.get('cited_by', 0)}")
                return "\n".join(lines)
        finally:
            gdb.close()
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
    try:
        from scholar import rag
        if hybrid:
            results = rag.search_rag_hybrid(query, limit=10)
            title = f"Hybrid Search: '{query}' ({len(results)} results)"
        else:
            results = rag.search_rag(query, limit=10)
            title = f"RAG Search: '{query}' ({len(results)} results)"
        if not results:
            # Provide actionable diagnostic to user
            hints = []
            if not scholar_config.EMBEDDING_API_KEY:
                hints.append("SCHOLAR_EMBEDDING_API_KEY not set — semantic search disabled")
            try:
                from scholar import rag as rag_mod
                conn = rag_mod._get_pg_connection()
                cur = conn.cursor()
                cur.execute("SELECT count(*) FROM chunks")
                chunk_count = cur.fetchone()[0]
                cur.close()
                conn.close()
                if chunk_count == 0:
                    hints.append("RAG index empty — run: scholar rag-index")
            except Exception:
                hints.append("PostgreSQL not available — RAG requires pgvector")
            hint_str = "; ".join(hints) if hints else "Build index first: scholar rag-index"
            return f"No RAG results for '{query}'. {hint_str}"
        lines = [title]
        for r in results:
            lines.append(f"  {r.get('paper_id', '')}  {(r.get('section') or '')[:15]}  {(r.get('content') or '')[:60]}  sim={r.get('similarity', 0):.3f}")
        return "\n".join(lines)
    except Exception as e:
        return f"RAG search failed: {e}"


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
            title_elem = entry.find("atom:title", ns)
            title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else "(no title)"
            author_names = []
            for a in entry.findall("atom:author", ns):
                name_elem = a.find("atom:name", ns)
                if name_elem is not None and name_elem.text:
                    author_names.append(name_elem.text)
            author_str = ", ".join(author_names[:3])
            if len(author_names) > 3:
                author_str += " et al."
            pub_elem = entry.find("atom:published", ns)
            published = pub_elem.text[:4] if pub_elem is not None and pub_elem.text else "????"
            id_elem = entry.find("atom:id", ns)
            arxiv_id = id_elem.text.split("/abs/")[-1] if id_elem is not None and id_elem.text else "unknown"
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
        try:
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
            return "\n".join(lines)
        finally:
            gdb.close()
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
    return f"{'Fixed' if apply else 'Would fix'}: {total} (arXiv: {fixed_arxiv}, Preprint: {fixed_preprint}, Skipped: {skipped})"


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
    try:
        from scholar import auto_notes as an
        if paper_id:
            ulid = _resolve(paper_id)
            result = an.generate_single_note(ulid, force=force)
            # Invalidate cache after write
            state = get_state()
            if state:
                state.invalidate_parsed(ulid)
            return json.dumps(result, ensure_ascii=False)
        else:
            result = an.generate_all_notes(force=force)
            return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def scholar_quality_score(paper_id: str | None = None, all_papers: bool = False) -> str:
    """Score paper quality across 7 dimensions (metadata/structure/citations/reproducibility/problem/innovation/experiments).

    Args:
        paper_id: Optional paper ID (ULID/arXiv/DOI/slug) for single paper scoring.
        all_papers: If True, score all papers.
    """
    try:
        from scholar import quality as q
        if paper_id:
            ulid = _resolve(paper_id)
            result = q.score_single_paper(ulid)
            if result is None:
                return json.dumps({"error": f"Paper not found: {paper_id}"}, ensure_ascii=False)
            # Invalidate cache after write
            state = get_state()
            if state:
                state.invalidate_parsed(ulid)
            return json.dumps(result, ensure_ascii=False)
        elif all_papers:
            result = q.score_all_papers()
            # Invalidate all cached entries
            state = get_state()
            if state:
                state.invalidate_parsed()
            return json.dumps(result, ensure_ascii=False)
        return json.dumps({"error": "Specify a paper_id or set all_papers=True"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def scholar_classify(paper_id: str | None = None, all_papers: bool = False, list_tags: bool = False) -> str:
    """Classify papers into domain/sub-direction/method tags.

    Args:
        paper_id: Optional paper ID (ULID/arXiv/DOI/slug) for single paper.
        all_papers: If True, classify all papers.
        list_tags: If True, list all tags in corpus.
    """
    try:
        from scholar import classify as cl
        if list_tags:
            tags = cl.list_all_tags()
            return json.dumps(tags, ensure_ascii=False)
        elif paper_id:
            ulid = _resolve(paper_id)
            result = cl.classify_single_paper(ulid)
            if result is None:
                return json.dumps({"error": f"Paper not found: {paper_id}"}, ensure_ascii=False)
            # Invalidate cache after write
            state = get_state()
            if state:
                state.invalidate_parsed(ulid)
            return json.dumps(result, ensure_ascii=False)
        elif all_papers:
            result = cl.classify_all_papers()
            # Invalidate all cached entries
            state = get_state()
            if state:
                state.invalidate_parsed()
            return json.dumps(result, ensure_ascii=False)
        return json.dumps({"error": "Specify a paper_id, use all_papers=True, or list_tags=True"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


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
    try:
        ulid = _resolve(paper_id)
        lines = [f"Ingesting {ulid}..."]
        from scholar import config, db as dbmod

        # Step 1: Parse (if not already parsed)
        paper_dir = config.PAPERS_DIR / ulid
        if not paper_dir.exists():
            return f"Paper directory not found: {ulid}"
        parsed_path = config.PARSED_DIR / f"{ulid}.json"
        if not parsed_path.exists():
            from scholar.tex_parser import parse_paper
            data = parse_paper(paper_dir, ulid)
            dbmod.save_parsed(data)
            lines.append(f"  [1] Parsed: {(data.get('title') or 'N/A')[:60]}")
        else:
            lines.append("  [1] Already parsed, skipping")

        # Step 2: Auto-notes
        from scholar import auto_notes as an
        note_result = an.generate_single_note(ulid, force=True)
        lines.append(f"  [2] Notes: {note_result['status']}")

        # Step 3: Quality
        from scholar import quality as q
        q_result = q.score_single_paper(ulid)
        if q_result:
            lines.append(f"  [3] Quality: Grade {q_result['grade']} ({q_result['total']}/{q_result['max_total']})")
        else:
            lines.append("  [3] Quality: failed")

        # Step 4: Classify
        from scholar import classify as cl
        cl_result = cl.classify_single_paper(ulid)
        if cl_result:
            lines.append(f"  [4] Classify: {', '.join(cl_result['domains'])}")
        else:
            lines.append("  [4] Classify: failed")

        # Invalidate cache
        state = get_state()
        if state:
            state.invalidate_parsed(ulid)

        lines.append(f"\nIngested {ulid} successfully.")
        return "\n".join(lines)
    except Exception as e:
        return f"Ingest failed: {e}"


@mcp.tool()
def scholar_survey(topic: str, depth: str = "standard", limit: int = 20) -> str:
    """Full research survey pipeline: hybrid RAG search + graph query + classify + timeline.
    Generates a structured survey report in output/drafts/.

    Args:
        topic: Research topic or question
        depth: 'standard' or 'full'
        limit: Maximum papers to include (default 20)
    """
    try:
        import json, re, time
        from scholar import config

        progress: list[dict] = []  # Track progress of each step
        t0 = time.time()

        # depth='full' doubles the limit for broader coverage
        if depth == "full":
            limit = max(limit, 40)

        seen_ids: list[str] = []

        # 1. Hybrid RAG search
        t1 = time.time()
        rag_count = 0
        try:
            from scholar import rag
            results = rag.search_rag_hybrid(topic, limit=limit)
            for r in results:
                pid = r.get("paper_id") or r.get("ulid") or ""
                if pid and pid not in seen_ids:
                    seen_ids.append(pid)
            rag_count = len(seen_ids)
        except Exception:
            pass
        progress.append({"step": 1, "name": "Hybrid RAG Search", "papers": rag_count, "elapsed_ms": int((time.time() - t1) * 1000)})

        # 2. Keyword fallback
        t2 = time.time()
        if not seen_ids:
            topic_lower = topic.lower()
            for ppath in config.PARSED_DIR.glob("*.json"):
                try:
                    pdata = json.loads(ppath.read_text(encoding="utf-8"))
                    if topic_lower in (pdata.get("title") or "").lower() or topic_lower in (pdata.get("abstract") or "").lower():
                        seen_ids.append(ppath.stem)
                        if len(seen_ids) >= limit:
                            break
                except Exception:
                    continue
        progress.append({"step": 2, "name": "Keyword Fallback", "papers": len(seen_ids), "elapsed_ms": int((time.time() - t2) * 1000)})

        # 3. Graph concept query
        t3 = time.time()
        graph_count = 0
        try:
            from scholar import graph_db
            gdb = graph_db.GraphDB()
            try:
                if gdb.available:
                    concept_rows = gdb.run("""
                        MATCH (c:Innovation)
                        WHERE toLower(c.id) CONTAINS toLower($topic)
                           OR toLower(coalesce(c.line, '')) CONTAINS toLower($topic)
                        WITH c LIMIT 10
                        MATCH (p:Paper)-[:HAS_CONCEPT]->(c)
                        RETURN DISTINCT p.ulid AS ulid
                        LIMIT $max_papers
                    """, topic=topic, max_papers=limit)
                    before = len(seen_ids)
                    for r in concept_rows:
                        cid = r.get("ulid", "")
                        if cid and cid not in seen_ids:
                            seen_ids.append(cid)
                    graph_count = len(seen_ids) - before
            finally:
                try:
                    gdb.close()
                except Exception:
                    pass
        except Exception:
            pass
        progress.append({"step": 3, "name": "Graph Concept Query", "new_papers": graph_count, "elapsed_ms": int((time.time() - t3) * 1000)})

        # 4. Load paper data
        t4 = time.time()
        papers_data: list[dict] = []
        for pid in seen_ids[:limit]:
            data = _load_parsed(pid)
            if data:
                data["ulid"] = pid
                papers_data.append(data)
        progress.append({"step": 4, "name": "Load Paper Data", "loaded": len(papers_data), "elapsed_ms": int((time.time() - t4) * 1000)})

        if not papers_data:
            return json.dumps({"error": f"No papers found for topic: {topic}", "progress": progress}, ensure_ascii=False)

        # 5. Tag summary
        tag_summary: dict[str, int] = {}
        for p in papers_data[:10]:
            tags = p.get("tags", {})
            for d in tags.get("domains", []):
                tag_summary[d] = tag_summary.get(d, 0) + 1

        # 6. Timeline
        by_year: dict[int, list] = {}
        for p in papers_data:
            y = p.get("year", 0)
            if y:
                by_year.setdefault(y, []).append(p)

        # 7. Write report
        out_dir = config.DRAFTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_topic = re.sub(r'[^\w\-]', '_', topic)[:50]
        out_path = out_dir / f"survey_{safe_topic}.md"

        lines = [f"# Research Survey: {topic}\n"]
        lines.append(f"**Papers found:** {len(papers_data)}  ")
        if tag_summary:
            lines.append(f"**Domains:** {', '.join(f'{k}({v})' for k, v in sorted(tag_summary.items(), key=lambda x: -x[1]))}\n")
        if by_year:
            lines.append("## Timeline\n")
            for y in sorted(by_year.keys()):
                titles = [f"- {(p.get('title') or 'Untitled')[:80]}" for p in by_year[y][:5]]
                lines.append(f"### {y} ({len(by_year[y])} papers)\n" + "\n".join(titles) + "\n")
        lines.append("## Papers\n")
        for i, p in enumerate(papers_data, 1):
            title = (p.get("title") or "Untitled")[:100]
            year = p.get("year", "?")
            authors = ", ".join((p.get("authors") or [])[:3])
            venue = p.get("venue", "")
            quality = p.get("quality", {})
            grade = quality.get("grade", "")
            lines.append(f"{i}. **{title}** ({year})")
            lines.append(f"   Authors: {authors}")
            if venue or grade:
                lines.append(f"   {venue}{' | Grade: ' + grade if grade else ''}")
            lines.append("")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        total_elapsed = int((time.time() - t0) * 1000)
        progress.append({"step": 5, "name": "Report Generated", "file": str(out_path), "total_elapsed_ms": total_elapsed})

        result = {
            "status": "ok",
            "topic": topic,
            "papers_found": len(papers_data),
            "domains": tag_summary,
            "years_span": [min(by_year.keys()), max(by_year.keys())] if by_year else [],
            "report_path": str(out_path),
            "progress": progress,
            "total_elapsed_ms": total_elapsed,
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def scholar_landscape(topic: str) -> str:
    """Field landscape analysis: domain tags + year distribution + quality + key papers.
    Generates a landscape report in output/drafts/.

    Args:
        topic: Research field or domain (e.g., NLP, RL, Safety, Transformer)
    """
    try:
        import json, re, time
        from scholar import config
        from scholar import classify as cl

        progress: list[dict] = []
        t0 = time.time()

        # 1. Tag matching
        t1 = time.time()
        all_tags = cl.list_all_tags()
        matched_domain = None
        for d_name, d_count in all_tags.get("domains", {}).items():
            if d_name.lower() == topic.lower() or topic.lower() in d_name.lower():
                matched_domain = d_name
                break
        if not matched_domain:
            for sd_name, sd_count in all_tags.get("sub_directions", {}).items():
                if topic.lower() in sd_name.lower():
                    matched_domain = sd_name
                    break
        progress.append({"step": 1, "name": "Tag Matching", "matched": matched_domain, "elapsed_ms": int((time.time() - t1) * 1000)})

        # 2. Scan papers matching the topic
        t2 = time.time()
        domain_papers: list[dict] = []
        for ppath in sorted(config.PARSED_DIR.glob("*.json")):
            try:
                pdata = json.loads(ppath.read_text(encoding="utf-8"))
                tags = pdata.get("tags", {})
                domains = [d.lower() for d in tags.get("domains", [])]
                subs = [s.lower() for s in tags.get("sub_directions", [])]
                all_tag_str = " ".join(domains + subs).lower()
                if topic.lower() in all_tag_str:
                    pdata["ulid"] = ppath.stem
                    domain_papers.append(pdata)
            except Exception:
                pass
        progress.append({"step": 2, "name": "Paper Collection", "count": len(domain_papers), "elapsed_ms": int((time.time() - t2) * 1000)})

        if not domain_papers:
            return json.dumps({"error": f"No papers found for topic: {topic}", "progress": progress}, ensure_ascii=False)

        # 3. Year distribution
        t3 = time.time()
        year_dist: dict[int, int] = {}
        for p in domain_papers:
            y = p.get("year", 0)
            if y:
                year_dist[y] = year_dist.get(y, 0) + 1
        progress.append({"step": 3, "name": "Year Distribution", "years": len(year_dist), "elapsed_ms": int((time.time() - t3) * 1000)})

        # 4. Quality distribution
        t4 = time.time()
        grades: dict[str, int] = {}
        for p in domain_papers:
            g = p.get("quality", {}).get("grade", "N/A")
            grades[g] = grades.get(g, 0) + 1
        progress.append({"step": 4, "name": "Quality Distribution", "elapsed_ms": int((time.time() - t4) * 1000)})

        # 5. Write report
        out_dir = config.DRAFTS_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_topic = re.sub(r'[^\w\-]', '_', topic)[:50]
        out_path = out_dir / f"landscape_{safe_topic}.md"

        lines = [f"# Landscape Analysis: {topic}\n"]
        lines.append(f"**Total papers:** {len(domain_papers)}")
        lines.append(f"**Matched:** {matched_domain or topic}\n")
        lines.append("## Year Distribution\n")
        for y in sorted(year_dist.keys()):
            lines.append(f"- {y}: {year_dist[y]} papers")
        lines.append("\n## Quality Distribution\n")
        for g in ["A", "B", "C", "D", "F", "N/A"]:
            if g in grades:
                lines.append(f"- Grade {g}: {grades[g]}")
        lines.append("\n## Key Papers\n")
        sorted_papers = sorted(domain_papers, key=lambda p: p.get("quality", {}).get("total", 0), reverse=True)
        for i, p in enumerate(sorted_papers[:20], 1):
            title = (p.get("title") or "Untitled")[:80]
            year = p.get("year", "?")
            grade = p.get("quality", {}).get("grade", "?")
            lines.append(f"{i}. **{title}** ({year}) -- Grade {grade}")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        total_elapsed = int((time.time() - t0) * 1000)
        progress.append({"step": 5, "name": "Report Generated", "file": str(out_path), "total_elapsed_ms": total_elapsed})

        result = {
            "status": "ok",
            "topic": topic,
            "matched_domain": matched_domain,
            "papers_found": len(domain_papers),
            "year_range": [min(year_dist.keys()), max(year_dist.keys())] if year_dist else [],
            "grades": grades,
            "report_path": str(out_path),
            "progress": progress,
            "total_elapsed_ms": total_elapsed,
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def read_auto_note(paper_id: str) -> str:
    """Read the auto-generated reading note for a paper.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    ulid = _resolve(paper_id)
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
    ulid = _resolve(paper_id)
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
    ulid = _resolve(paper_id)
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
    # Check .scholar/ shared source first, then fallback to any IDE directory
    path = PROJECT_ROOT / ".scholar" / "skills" / skill_name / "SKILL.md"
    if not path.exists():
        # Fallback: dynamically scan all IDE config directories
        for ide_dir in PROJECT_ROOT.glob(".*/skills/"):
            candidate = ide_dir / skill_name / "SKILL.md"
            if candidate.exists():
                path = candidate
                break
    if not path.exists():
        # Collect available skills from .scholar/ and all IDE directories
        available = set()
        scholar_skills = PROJECT_ROOT / ".scholar" / "skills"
        if scholar_skills.exists():
            available.update(p.name for p in scholar_skills.iterdir() if p.is_dir())
        for ide_dir in PROJECT_ROOT.glob(".*/skills/"):
            if ide_dir.exists():
                available.update(p.name for p in ide_dir.iterdir() if p.is_dir())
        return f"Skill '{skill_name}' not found. Available: {', '.join(sorted(available))}"
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
    if action in ("logs", "mark-analyzed"):
        # Complex operations — delegate to CLI
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
    except Exception as e:
        return f"Interests {action} failed: {e}"
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
def scholar_lean_verify(theorem: str = "") -> str:
    """Run Lean4 verification on AiEvolution theorems (7 formalized proofs).

    Args:
        theorem: Specific theorem name (e.g., 'transformer_replaces_rnn'). Empty = verify all 7.
    """
    args = ["lean-verify", "--json"]
    if theorem:
        args.extend(["--theorem", theorem])
    return _run_scholar(*args, timeout=180)


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
    ulid = _resolve(paper_id)
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
    ulid = _resolve(paper_id)
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


# ─── Output File Discovery ──────────────────────────────────────

@mcp.tool()
def scholar_list_output_files(category: str = "") -> str:
    """List files in the output directory (notes, drafts, experiments, digests, bib).
    
    Args:
        category: Subdirectory name (notes/drafts/experiments/digests/bib). Empty = all.
    """
    try:
        categories = [category] if category else ["notes", "drafts", "experiments", "digests", "bib"]
        lines = []
        for cat in categories:
            cat_dir = scholar_config.NOTES_DIR.parent / cat
            if not cat_dir.exists():
                continue
            files = sorted(cat_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if files:
                lines.append(f"\n=== {cat} ({len(files)} files) ===")
                for f in files[:20]:
                    size = f.stat().st_size
                    lines.append(f"  {f.name}  ({size} bytes)")
        return "\n".join(lines) if lines else "No output files found."
    except Exception as e:
        return f"List output files failed: {e}"


@mcp.tool()
def scholar_read_output_file(path: str) -> str:
    """Read any file from the output directory.
    
    Args:
        path: Relative path from output/ (e.g., 'notes/01KT6MTBK1PQMNZM8ZYQPTVN6C.md')
    """
    try:
        output_root = (scholar_config.PROJECT_ROOT / "output").resolve()
        full_path = (output_root / path).resolve()
        # Security: prevent path traversal outside output/
        if not str(full_path).startswith(str(output_root)):
            return f"Access denied: path '{path}' resolves outside output directory"
        if not full_path.exists():
            return f"File not found: {path}"
        if full_path.stat().st_size > 500_000:
            return f"File too large ({full_path.stat().st_size} bytes). Use scholar_read_parsed_paper for JSON data."
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Read output file failed: {e}"


# ─── Structured Data Tools (Frontend-optimized, return JSON) ───

@mcp.tool()
def scholar_get_citation_graph(paper_id: str = "", depth: int = 2) -> str:
    """Return citation network as structured JSON {nodes, edges} for graph visualization.
    Frontend-optimized: use with Cytoscape.js or D3.js.

    Args:
        paper_id: Paper ID to center on. Empty = global top-cited subgraph.
        depth: Citation depth (1=direct, 2=2-hop). Default 2.
    """
    try:
        from scholar import graph_db as gdb_mod
        gdb = gdb_mod.GraphDB()
        try:
            if not gdb.available:
                return json.dumps({"error": "Neo4j not available", "nodes": [], "edges": []}, ensure_ascii=False)

            nodes = []
            edges = []
            seen_ulids = set()

            if paper_id:
                ulid = _resolve(paper_id)
                # Get forward and backward citations
                forward = gdb_mod.get_forward_citations(gdb, ulid)
                backward = gdb_mod.get_backward_citations(gdb, ulid)

                # Center node
                center_data = _load_parsed(ulid)
                nodes.append({
                    "id": ulid,
                    "title": (center_data.get("title") or "")[:80] if center_data else ulid,
                    "year": center_data.get("year") if center_data else None,
                    "in_degree": len(backward),
                    "is_center": True,
                })
                seen_ulids.add(ulid)

                for p in forward[:20]:
                    pid = p.get("ulid", "")
                    if pid and pid not in seen_ulids:
                        nodes.append({
                            "id": pid,
                            "title": (p.get("title") or "")[:80],
                            "year": p.get("year"),
                            "in_degree": 0,
                            "is_center": False,
                        })
                        seen_ulids.add(pid)
                    edges.append({"source": ulid, "target": pid, "type": "forward"})

                for p in backward[:20]:
                    pid = p.get("ulid", "")
                    if pid and pid not in seen_ulids:
                        nodes.append({
                            "id": pid,
                            "title": (p.get("title") or "")[:80],
                            "year": p.get("year"),
                            "in_degree": 0,
                            "is_center": False,
                        })
                        seen_ulids.add(pid)
                    edges.append({"source": pid, "target": ulid, "type": "backward"})
            else:
                # Global: top cited papers
                stats = gdb_mod.get_citation_stats(gdb)
                for p in stats.get("most_cited", [])[:30]:
                    pid = p.get("ulid", "")
                    if pid and pid not in seen_ulids:
                        nodes.append({
                            "id": pid,
                            "title": (p.get("title") or "")[:80],
                            "year": None,
                            "in_degree": p.get("cited_by", 0),
                            "is_center": False,
                        })
                        seen_ulids.add(pid)

            return json.dumps({
                "nodes": nodes,
                "edges": edges,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            }, ensure_ascii=False)
        finally:
            gdb.close()
    except Exception as e:
        return json.dumps({"error": str(e), "nodes": [], "edges": []}, ensure_ascii=False)


@mcp.tool()
def scholar_get_paper_card(paper_id: str) -> str:
    """Return structured paper metadata as JSON for card/reader rendering.
    Frontend-optimized: includes title, authors, abstract, sections TOC, formulas count, quality.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    try:
        ulid = _resolve(paper_id)
        data = _load_parsed(ulid)
        if data is None:
            return json.dumps({"error": f"Paper not found: {paper_id}"}, ensure_ascii=False)

        sections_toc = [
            {"heading": s.get("heading", "(untitled)"), "level": s.get("level", 1), "content_length": len(s.get("content", ""))}
            for s in data.get("sections", [])
        ]

        quality = data.get("quality", {})
        tags = data.get("tags", {})

        return json.dumps({
            "paper_id": ulid,
            "title": data.get("title", "N/A"),
            "authors": data.get("authors", []),
            "year": data.get("year"),
            "venue": data.get("venue"),
            "abstract": data.get("abstract", ""),
            "arxiv_id": data.get("arxiv_id"),
            "doi": data.get("doi"),
            "sections_count": len(data.get("sections", [])),
            "sections_toc": sections_toc,
            "formulas_count": len(data.get("formulas", [])),
            "citations_count": len(data.get("citations", [])),
            "quality_grade": quality.get("grade", ""),
            "quality_total": quality.get("total", 0),
            "domains": tags.get("domains", []),
            "sub_directions": tags.get("sub_directions", []),
            "methods": tags.get("methods", []),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def scholar_get_quality_radar(paper_id: str) -> str:
    """Return 7-dimension quality scores as JSON for radar chart rendering.
    Frontend-optimized: use with Recharts RadarChart.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    try:
        ulid = _resolve(paper_id)
        quality_path = scholar_config.NOTES_DIR / f"{ulid}-quality.json"
        if not quality_path.exists():
            return json.dumps({"error": f"Quality score not found. Run: scholar quality-score {paper_id}"}, ensure_ascii=False)
        data = json.loads(quality_path.read_text(encoding="utf-8"))
        dimensions = []
        for key, label in [
            ("metadata", "元数据"), ("structure", "结构"), ("citations", "引用"),
            ("reproducibility", "可复现"), ("problem", "问题定义"),
            ("innovation", "创新性"), ("experiments", "实验"),
        ]:
            dim = data.get(key, {})
            dimensions.append({
                "name": label,
                "key": key,
                "score": dim.get("score", 0),
                "max": dim.get("max", 10),
                "detail": dim.get("detail", ""),
            })
        return json.dumps({
            "paper_id": ulid,
            "grade": data.get("grade", ""),
            "total": data.get("total", 0),
            "max_total": data.get("max_total", 70),
            "dimensions": dimensions,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def scholar_get_kb_dashboard() -> str:
    """Return knowledge base statistics as JSON for dashboard rendering.
    Frontend-optimized: use with Recharts charts.
    """
    try:
        stats = _get_stats_cached()
        return json.dumps({
            "paper_folders": stats["paper_folders"],
            "parsed": stats["parsed"],
            "sections": stats["sections"],
            "formulas": stats["formulas"],
            "citations": stats["citations"],
            "coverage": stats["coverage"],
            "by_year": stats["by_year"],
            "by_venue": stats["by_venue"],
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def scholar_get_experiment_metrics(paper_id: str) -> str:
    """Return experiment results as structured JSON for chart rendering.
    Frontend-optimized: use with Recharts BarChart for metric comparison.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    try:
        ulid = _resolve(paper_id)
        exp_dir = scholar_config.EXPERIMENTS_DIR / ulid

        # Read our experiment results
        results_path = exp_dir / "results.json"
        our_metrics = []
        runtime = None
        mode = None
        if results_path.exists():
            data = json.loads(results_path.read_text(encoding="utf-8"))
            our_metrics = data.get("metrics", [])
            runtime = data.get("runtime_seconds")
            mode = data.get("mode")

        # Read paper data for title (paper-reported metrics are usually in sections)
        paper_data = _load_parsed(ulid)
        paper_title = (paper_data or {}).get("title", ulid)

        # Build comparison (our results vs paper-reported metrics)
        try:
            from scholar.commands.execution_ops import _extract_paper_metrics
            paper_metrics = _extract_paper_metrics(paper_data or {})
        except Exception:
            paper_metrics = []
        paper_metrics_by_name = {m["name"]: m["value"] for m in paper_metrics}

        comparison = []
        for m in our_metrics:
            theirs = paper_metrics_by_name.get(m["name"])
            gap = None
            if theirs is not None:
                gap = round(m["value"] - theirs, 4) if m.get("type") == "higher_better" else round(theirs - m["value"], 4)
            comparison.append({
                "name": m["name"],
                "ours": m["value"],
                "theirs": theirs,
                "gap": gap,
                "type": m.get("type", ""),
            })

        # Read run log status
        log_path = exp_dir / "run_log.txt"
        has_log = log_path.exists()

        return json.dumps({
            "paper_id": ulid,
            "paper_title": paper_title,
            "has_experiment": exp_dir.exists(),
            "has_results": results_path.exists(),
            "has_log": has_log,
            "mode": mode,
            "runtime_seconds": runtime,
            "our_metrics": our_metrics,
            "comparison": comparison,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def scholar_get_timeline(topic: str = "", limit: int = 50) -> str:
    """Return papers as timeline data for visualization.
    Frontend-optimized: use with Recharts LineChart/ScatterChart.

    Args:
        topic: Topic filter (empty = global timeline)
        limit: Max papers per year
    """
    try:
        if topic:
            pids = dbmod.search_parsed(topic, limit=200)
        else:
            pids = dbmod.list_parsed()

        years_data = {}
        for pid in pids:
            data = _load_parsed(pid)
            if not data:
                continue
            year = data.get("year")
            if not year:
                continue
            if year not in years_data:
                years_data[year] = []
            years_data[year].append({
                "id": pid,
                "title": (data.get("title") or "")[:80],
            })

        years = []
        for y in sorted(years_data.keys()):
            papers = years_data[y][:limit]
            years.append({
                "year": y,
                "count": len(years_data[y]),
                "papers": papers,
            })

        return json.dumps({
            "topic": topic or "all",
            "total": sum(y["count"] for y in years),
            "years": years,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def scholar_reclassify(paper_id: str, tags: str) -> str:
    """Write LLM-generated classification tags to paper JSON.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
        tags: JSON string, e.g. '{"domain": ["NLP"], "method": ["Transformer"]}'
    """
    try:
        ulid = _resolve(paper_id)
        json_path = scholar_config.PARSED_DIR / f"{ulid}.json"
        if not json_path.exists():
            return json.dumps({"error": f"Paper not found: {paper_id}"}, ensure_ascii=False)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        parsed_tags = json.loads(tags)
        data["tags"] = parsed_tags
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        return json.dumps({"paper_id": ulid, "tags": parsed_tags, "updated": True}, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid tags JSON: {e}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def scholar_enhance_quality(paper_id: str, quality: str) -> str:
    """Write LLM-generated quality assessment to paper JSON + quality file.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
        quality: JSON string with quality scores
    """
    try:
        ulid = _resolve(paper_id)
        parsed_quality = json.loads(quality)

        # Write to quality file
        quality_path = scholar_config.NOTES_DIR / f"{ulid}-quality.json"
        quality_path.parent.mkdir(parents=True, exist_ok=True)
        quality_path.write_text(json.dumps(parsed_quality, ensure_ascii=False, indent=2), encoding="utf-8")

        # Also update parsed JSON
        json_path = scholar_config.PARSED_DIR / f"{ulid}.json"
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            data["quality"] = parsed_quality
            json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        return json.dumps({"paper_id": ulid, "quality": parsed_quality, "updated": True}, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid quality JSON: {e}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
