"""
Scholar Studio MCP Server (v0.2.0)

Model-facing surface: 15 focused tools organised as a reading ladder.

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
dumps require an explicit full=True escape hatch. Maintenance operations
(parse/ingest/rag-index/graph-build/…) live in the CLI, not here — run
`scholar sync` to refresh all derived indexes from parsed JSON.

Run: python -m scholar_mcp
"""

import json
import re
import subprocess
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from scholar import config as scholar_config
from scholar import db as dbmod
from scholar import graph_mem, vecstore
from scholar._state import init_shared_state, get_state  # noqa: F401 (re-exported)

mcp = FastMCP(
    "Scholar Studio",
    host=os.getenv("SCHOLAR_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("SCHOLAR_MCP_PORT", "8000")),
    instructions=(
        "Academic research toolkit over a local paper library (563+ AI papers). "
        "Reading ladder: search/vec-search for relevance → scholar_info for "
        "abstract+TOC → scholar_section for the sections you actually need. "
        "Never read full papers unless truly required."
    ),
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ─── shared helpers ─────────────────────────────────────────────────────────

MAX_SECTION_CHARS = 16_000
MAX_FULL_JSON_CHARS = 200_000
ABSTRACT_SNIPPET = 200  # L1 hit lines
DIGEST_ABSTRACT = 400  # L2 digest


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


# ─── lexical scoring (same semantics as the dsh plugin layer) ───────────────

_STOPWORDS = set(
    (
        "the a an and or of for to in on with by from as at is are was were be been this that these those "
        "it its their his her our your my not no do does did done can could should would will shall may "
        "might must how what why when where which who whom whose about into over under between within "
        "without during through using use used based paper papers method methods model models approach "
        "approaches result results new novel please explain describe tell say make give show help like "
        "also more most some any all both each other than then you i we they he she them us him me here "
        "there have has had having let get got"
    ).split()
)


def _extract_terms(text: str) -> list[str]:
    """Latin words (>=3 chars, stopwords removed) + CJK bigrams, deduped."""
    if not text:
        return []
    terms: list[str] = []
    for raw in re.findall(r"[a-z][a-z0-9+#.-]{2,}", text.lower()):
        w = raw.rstrip(".+-")
        if len(w) >= 3 and w not in _STOPWORDS:
            terms.append(w)
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    terms.extend(cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1))
    return list(dict.fromkeys(terms))


def _score_paper(data: dict, terms: list[str]) -> tuple[int, int]:
    """Returns (score, matched_terms). title×4 / tags×2 / abstract×1 (cap 3)."""
    title = (data.get("title") or "").lower()
    abstract = (data.get("abstract") or "").lower()
    tags = data.get("tags") or {}
    tag_text = " ".join(
        v
        for key in ("domains", "sub_directions", "methods", "tags")
        for v in (tags.get(key) or [])
        if isinstance(v, str)
    ).lower()
    if not title and not abstract:
        return 0, 0
    score = 0
    matched = 0
    for term in terms:
        hit = False
        if term in title:
            score += 4
            hit = True
        if tag_text and term in tag_text:
            score += 2
            hit = True
        c, from_ = 0, 0
        while True:
            from_ = abstract.find(term, from_)
            if from_ == -1 or c >= 3:
                break
            score += 1
            c += 1
            from_ += len(term)
        if c:
            hit = True
        if hit:
            matched += 1
    if len(terms) >= 2:
        phrase = terms[0] + " " + terms[1]
        if phrase in title or phrase in abstract:
            score += 3
    return score, matched


# ─── L1: find papers ────────────────────────────────────────────────────────


@mcp.tool()
def scholar_search(query: str, limit: int = 10) -> str:
    """Lexical search across the library (title/abstract/tags).

    Args:
        query: Keywords or a short phrase (multi-word works best)
        limit: Max results (default 10)
    """
    terms = _extract_terms(query)
    if not terms:
        return f"No usable terms in '{query}'"
    min_matched = 1 if len(terms) == 1 else 2
    hits = []
    for pid in dbmod.list_parsed():
        data = _load_parsed(pid)
        if not data:
            continue
        score, matched = _score_paper(data, terms)
        if score >= 5 and matched >= min_matched:
            hits.append((score, data))
    hits.sort(key=lambda x: x[0], reverse=True)
    hits = hits[: max(1, min(limit, 20))]
    if not hits:
        return f"No results for '{query}'. Try scholar_vec_search with a natural-language question."
    lines = [f"Search: '{query}' ({len(hits)} results, scored)"]
    for score, data in hits:
        snippet = (data.get("abstract") or "").replace("\n", " ")[:ABSTRACT_SNIPPET]
        line = (
            f"  [{data.get('paper_id', '')}] {(data.get('title') or 'N/A')[:70]} "
            f"({data.get('year', '')} {data.get('venue') or ''}) score={score}"
        )
        if snippet:
            line += f"\n      {snippet}…"
        lines.append(line)
    lines.append(
        "Next: scholar_info <paper_id> for the section TOC; "
        "scholar_section for specific sections."
    )
    return "\n".join(lines)


@mcp.tool()
def scholar_vec_search(question: str, k: int = 8) -> str:
    """Semantic paper search: match a natural-language research question to
    papers by their contribution (one embedding per paper over title+abstract).

    Args:
        question: The user's academic question in natural language
        k: Max papers to return (default 8)
    """
    try:
        rows = vecstore.search_papers_semantic(question, k=max(1, min(k, 20)))
    except vecstore.EmbedUnavailable as e:
        return f"Semantic search unavailable: {e}. Fall back to scholar_search."
    except Exception as e:
        return f"Semantic search failed: {e}. Fall back to scholar_search."
    if not rows:
        return (
            f"No paper vectors yet — run `scholar sync` to build them, "
            f"or use scholar_search meanwhile."
        )
    lines = [f"Semantic matches for: '{question}' ({len(rows)} papers)"]
    for r in rows:
        data = _load_parsed(r["paper_id"]) or {}
        title = (data.get("title") or "N/A")[:70]
        year = data.get("year", "")
        abstract = (data.get("abstract") or "").replace("\n", " ")[:ABSTRACT_SNIPPET]
        lines.append(f"  [{r['paper_id']}] {title} ({year}) sim={r['similarity']}")
        if abstract:
            lines.append(f"      {abstract}…")
    lines.append("Next: scholar_info <paper_id> for TOC; scholar_section to read.")
    return "\n".join(lines)


# ─── L2: paper digest ───────────────────────────────────────────────────────


def _digest_lines(data: dict) -> list[str]:
    sections = data.get("sections", [])
    lines = [
        f"Title:     {data.get('title', 'N/A')}",
        f"Authors:   {', '.join(data.get('authors', []) or [])[:120]}",
        f"Year:      {data.get('year', 'N/A')}  Venue: {data.get('venue', 'N/A')}",
        f"Formulas:  {len(data.get('formulas', []))}  "
        f"Citations: {len(data.get('citations', []))}  Sections: {len(sections)}",
    ]
    abstract = (data.get("abstract") or "").strip()
    if abstract:
        lines.append(
            f"\nAbstract: {abstract[:DIGEST_ABSTRACT]}"
            f"{'…' if len(abstract) > DIGEST_ABSTRACT else ''}"
        )
    if sections:
        lines.append(f"\nSection TOC (use scholar_section with the [index]):")
        for i, s in enumerate(sections):
            heading = (s.get("heading") or "(untitled)")[:60]
            lines.append(
                f"  [{i}] (L{s.get('level', 1)}, "
                f"{len(s.get('content', ''))}c) {heading}"
            )
    return lines


@mcp.tool()
def scholar_info(paper_id: str) -> str:
    """Paper digest: metadata + abstract + section TOC (no section bodies).

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
    """
    ulid = _resolve(paper_id)
    data = _load_parsed(ulid)
    if not data:
        return f"Paper not parsed: {paper_id}"
    return "\n".join(_digest_lines(data))


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
    ulid = _resolve(paper_id)
    data = _load_parsed(ulid)
    if not data:
        return f"Paper not parsed: {paper_id}"
    sections = data.get("sections", [])
    if not sections:
        return "Paper has no sections."
    raw = (section or "").strip()
    idx: int | None = None
    m = re.fullmatch(r"\[?(\d+)\]?", raw)
    if m:
        i = int(m.group(1))
        if 0 <= i < len(sections):
            idx = i
    if idx is None:
        exact = [i for i, s in enumerate(sections) if (s.get("heading") or "") == raw]
        ci = [
            i
            for i, s in enumerate(sections)
            if not exact and (s.get("heading") or "").lower() == raw.lower()
        ]
        subs = [
            i
            for i, s in enumerate(sections)
            if not exact and not ci and raw.lower() in (s.get("heading") or "").lower()
        ]
        cands = exact or ci or subs
        if not cands:
            toc = "\n".join(
                f"  [{i}] {(s.get('heading') or '(untitled)')[:60]}"
                for i, s in enumerate(sections)
            )
            return f"Section '{section}' not found. TOC:\n{toc}"
        if len(cands) > 1:
            listing = "\n".join(
                f"  [{i}] (L{sections[i].get('level', 1)}, "
                f"{len(sections[i].get('content', ''))}c) "
                f"{(sections[i].get('heading') or '(untitled)')[:60]}"
                for i in cands[:10]
            )
            return (
                f"Ambiguous heading '{section}' matches {len(cands)} "
                f"sections. Retry with the [index]:\n{listing}"
            )
        idx = cands[0]
    span = max(1, min(span, 5))
    end = min(idx + span, len(sections))
    parts = []
    total = 0
    for i in range(idx, end):
        s = sections[i]
        content = s.get("content", "")
        parts.append(
            f"[{i}] {s.get('heading') or '(untitled)'} "
            f"(L{s.get('level', 1)})\n{content}"
        )
        total += len(content) + 8
        if total > MAX_SECTION_CHARS:
            parts.append(
                f"…[truncated at {MAX_SECTION_CHARS} chars — narrow your span]"
            )
            break
    return "\n\n".join(parts)


# ─── L4: passage location (optional) ────────────────────────────────────────


@mcp.tool()
def scholar_passages(
    query: str,
    k: int = 10,
    paper_id: str | None = None,
    section: str | None = None,
    hybrid: bool = False,
) -> str:
    """Locate passages mentioning the query (vector chunk search).

    Args:
        query: Text to locate (keywords or a phrase)
        k: Max passages (default 10)
        paper_id: Optional scope to one paper
        section: Optional substring filter on section name
        hybrid: Use vector+BM25 fusion (paper-level dedup, no scoping)
    """
    try:
        if hybrid:
            from scholar import rag

            results = rag.search_rag_hybrid(query, limit=max(1, min(k, 20)))
            results = [
                {
                    "paper_id": r.get("paper_id", ""),
                    "section": r.get("section", ""),
                    "content": (r.get("content") or "")[:160],
                    "similarity": r.get("similarity", 0),
                }
                for r in results
            ]
        else:
            results = vecstore.search_passages(
                query,
                k=max(1, min(k, 20)),
                paper_id=_resolve(paper_id) if paper_id else None,
                section=section,
            )
    except vecstore.EmbedUnavailable as e:
        return f"Passage search unavailable: {e}. Use scholar_search instead."
    except Exception as e:
        return f"Passage search failed: {e}"
    if not results:
        return (
            f"No passages for '{query}'. If the vector index is empty, "
            f"run `scholar sync`."
        )
    lines = [f"Passages matching '{query}' ({len(results)})"]
    for r in results:
        lines.append(
            f"  [{r['paper_id']}] {(r.get('section') or '')[:20]}  "
            f"{(r.get('content') or '')[:120]}  sim={r.get('similarity')}"
        )
    lines.append("Next: scholar_section <paper_id> <heading> for the full section.")
    return "\n".join(lines)


# ─── Horizontal: citation / concept graph (in-memory, was Neo4j) ───────────


@mcp.tool()
def scholar_cite_network(paper_id: str | None = None) -> str:
    """Citation network. Without paper_id: global stats+hubs. With paper_id:
    what this paper cites (forward) and who cites it (backward).

    Args:
        paper_id: Optional Paper ID (ULID/arXiv/DOI/slug)
    """
    try:
        gm = graph_mem.ensure_graph()
    except Exception as e:
        return f"Graph unavailable: {e}"
    if not paper_id:
        st = gm.stats()
        lines = [
            f"Papers: {st['papers']}  CITES edges (library-internal): "
            f"{st['cites_edges']}  Resolved refs: {st['resolved_refs']}",
            "\nMost cited:",
        ]
        for p in st["most_cited"]:
            lines.append(
                f"  [{p['ulid']}] {(p.get('title') or '')[:60]}  "
                f"cited by {p['in_degree']}"
            )
        lines.append("\nBridge papers (connect fields):")
        for p in st["top_bridge"][:5]:
            lines.append(
                f"  [{p['ulid']}] {(p.get('title') or '')[:60]}  "
                f"bridge={p['bridge_score']}"
            )
        return "\n".join(lines)
    ulid = _resolve(paper_id)
    if ulid not in gm.papers:
        return f"Paper not in graph: {paper_id}"
    fwd = gm.forward_citations(ulid)
    bwd = gm.backward_citations(ulid)
    lines = [
        f"[{ulid}] {(gm.papers[ulid].get('title') or '')[:70]}",
        f"\nForward citations ({len(fwd['cited'])} in-library):",
    ]
    for p in fwd["cited"][:10]:
        lines.append(f"  -> [{p.get('year', '?')}] {(p.get('title') or '')[:60]}")
    if fwd["unresolved_refs"]:
        lines.append(f"  (…+{len(fwd['unresolved_refs'])} refs outside the library)")
    lines.append(f"\nBackward citations ({len(bwd)}):")
    for p in bwd[:10]:
        lines.append(f"  <- [{p.get('year', '?')}] {(p.get('title') or '')[:60]}")
    lines.append("Next: scholar_lineage <a> <b> traces the citation path.")
    return "\n".join(lines)


@mcp.tool()
def scholar_graph_query(concept: str) -> str:
    """Papers tagged with a concept + related concepts (co-occurrence).

    Args:
        concept: Concept name (e.g., 'transformer', 'MoE', 'diffusion')
    """
    try:
        gm = graph_mem.ensure_graph()
    except Exception as e:
        return f"Graph unavailable: {e}"
    papers = gm.papers_by_concept(concept)
    if not papers:
        return (
            f"Concept '{concept}' not found. Concepts come from paper tags "
            f"and the alias vocabulary — try a broader name."
        )
    lines = [f"Papers with concept '{concept}' ({len(papers)})"]
    for p in papers[:20]:
        lines.append(
            f"  [{p['ulid']}] {(p.get('title') or '')[:60]}  "
            f"{p.get('year', '')}  {p.get('venue', '')}"
        )
    related = gm.related_concepts(concept, top_n=8)
    if related:
        lines.append("\nRelated concepts:")
        lines.extend(f"  {r['id']} (weight {r['weight']})" for r in related)
    return "\n".join(lines)


@mcp.tool()
def scholar_lineage(paper_a: str, paper_b: str) -> str:
    """Shortest citation path between two papers (any direction, multi-hop).

    Args:
        paper_a: Paper ID (ULID/arXiv/DOI/slug)
        paper_b: Paper ID (ULID/arXiv/DOI/slug)
    """
    try:
        gm = graph_mem.ensure_graph()
    except Exception as e:
        return f"Graph unavailable: {e}"
    ua, ub = _resolve(paper_a), _resolve(paper_b)
    result = gm.lineage(ua, ub)
    if result["hops"] < 0:
        return (
            f"No citation path between '{paper_a}' and '{paper_b}' "
            f"(library-internal edges only)."
        )
    lines = [f"Citation path ({result['hops']} hops):"]
    for i, node in enumerate(result["path"]):
        lines.append(
            f"  {'  ' * i}[{node['ulid']}] "
            f"{(node.get('title') or '')[:60]}  {node.get('year', '')}"
        )
    return "\n".join(lines)


@mcp.tool()
def scholar_graph_stats() -> str:
    """Graph statistics: papers, citation edges, refs resolution, concepts, hubs."""
    try:
        gm = graph_mem.ensure_graph()
    except Exception as e:
        return f"Graph unavailable: {e}"
    st = gm.stats()
    return (
        f"Papers:            {st['papers']}\n"
        f"CITES edges:       {st['cites_edges']} (library-internal)\n"
        f"Refs resolved:     {st['resolved_refs']}\n"
        f"Refs unresolved:   {st['unresolved_refs']}\n"
        f"Concepts:          {st['concepts']} ({st['concept_links']} links)\n"
        f"Innovations:       {st['innovations']}  Replacements: {st['replacements']}"
    )


# ─── Utilities ──────────────────────────────────────────────────────────────


@mcp.tool()
def scholar_list_papers(year: int | None = None, offset: int = 0) -> str:
    """List parsed papers (30 per page), newest first. Optional year filter.

    Args:
        year: Optional year filter (e.g., 2023)
        offset: Pagination offset
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
    papers = papers[offset : offset + 30]
    lines = [
        f"Parsed Papers ({len(papers)} shown, total {total_count}, offset {offset})"
    ]
    for p in papers:
        lines.append(
            f"  {p.get('paper_id', '')}  "
            f"{(p.get('title') or 'N/A')[:50]}  {p.get('year', '')}  "
            f"{p.get('venue', '') or ''}"
        )
    return "\n".join(lines)


@mcp.tool()
def scholar_arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv for papers outside the local library.

    Args:
        query: arXiv search query
        max_results: Max results (default 10)
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
    except Exception as e:
        return f"arXiv search failed: {e}"


@mcp.tool()
def read_parsed_paper(paper_id: str, full: bool = False) -> str:
    """Read a paper. Default: bounded digest (abstract + section TOC).
    full=True dumps the complete parsed JSON — only when truly necessary.

    Args:
        paper_id: Paper ID (ULID/arXiv/DOI/slug)
        full: Escape hatch for the complete parsed JSON (capped at 200KB)
    """
    ulid = _resolve(paper_id)
    data = _load_parsed(ulid)
    if not data:
        return f"Paper not parsed: {paper_id}"
    if not full:
        return (
            "\n".join(_digest_lines(data))
            + "\n\n(reading ladder: use scholar_section for specific "
            "sections instead of full JSON)"
        )
    path = scholar_config.PARSED_DIR / f"{ulid}.json"
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Read failed: {e}"
    if len(raw) > MAX_FULL_JSON_CHARS:
        return (
            raw[:MAX_FULL_JSON_CHARS]
            + f"\n…[truncated at {MAX_FULL_JSON_CHARS} of {len(raw)} chars]"
        )
    return raw


@mcp.tool()
def scholar_read_output_file(path: str) -> str:
    """Read any file from the output directory (notes, logs, results).

    Args:
        path: Relative path from output/ (e.g., 'notes/01KT6MTBK1PQMNZM8ZYQPTVN6C.md')
    """
    try:
        output_root = (scholar_config.OUTPUT_DIR).resolve()
        full_path = (output_root / path).resolve()
        if not str(full_path).startswith(str(output_root)):
            return f"Access denied: path '{path}' resolves outside output directory"
        if not full_path.exists():
            return f"File not found: {path}"
        if full_path.stat().st_size > 500_000:
            return (
                f"File too large ({full_path.stat().st_size} bytes). "
                f"Read it in chunks via the workspace file tools."
            )
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Read output file failed: {e}"


@mcp.tool()
def read_skill(skill_name: str) -> str:
    """Read a skill's SKILL.md for step-by-step workflow instructions.

    Args:
        skill_name: Skill name (e.g., 'paper-deep-dive', 'research-survey')
    """
    path = PROJECT_ROOT / ".scholar" / "skills" / skill_name / "SKILL.md"
    if not path.exists():
        for ide_dir in PROJECT_ROOT.glob(".*/skills/"):
            candidate = ide_dir / skill_name / "SKILL.md"
            if candidate.exists():
                path = candidate
                break
    if not path.exists():
        available = set()
        scholar_skills = PROJECT_ROOT / ".scholar" / "skills"
        if scholar_skills.exists():
            available.update(p.name for p in scholar_skills.iterdir() if p.is_dir())
        for ide_dir in PROJECT_ROOT.glob(".*/skills/"):
            if ide_dir.exists():
                available.update(p.name for p in ide_dir.iterdir() if p.is_dir())
        return (
            f"Skill '{skill_name}' not found. Available: {', '.join(sorted(available))}"
        )
    return path.read_text(encoding="utf-8")


@mcp.tool()
def scholar_auto_notes(paper_id: str | None = None, force: bool = False) -> str:
    """Generate structured reading notes (JSON status). Single paper or batch.

    Args:
        paper_id: Optional Paper ID; omit for batch over all papers
        force: Overwrite existing notes
    """
    try:
        from scholar import auto_notes as an

        if paper_id:
            ulid = _resolve(paper_id)
            result = an.generate_single_note(ulid, force=force)
            state = get_state()
            if state:
                state.invalidate_parsed(ulid)
            return json.dumps(result, ensure_ascii=False)
        result = an.generate_all_notes(force=force)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


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
    from scholar import research_loop as rl

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
    except Exception as e:
        return f"Interests {action} failed: {e}"
    return (
        f"Unknown action: {action}. Available: list, add, remove, logs, mark-analyzed"
    )


def _bearer_token_middleware(token: str):
    """Bearer token 鉴权中间件（公网部署用）。SSH 隧道模式不设
    SCHOLAR_MCP_TOKEN，行为不变。"""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    expected = f"Bearer {token}"

    class _Auth(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.headers.get("authorization", "") != expected:
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    return _Auth


def main():
    """stdio 为默认（dsh 本地挂载）；streamable-http 供服务器集中部署
    （队友 MCP over HTTP，数据与索引全部留在服务器，本地零论文数据）。
    host/port 由 SCHOLAR_MCP_HOST / SCHOLAR_MCP_PORT 控制；
    SCHOLAR_MCP_TOKEN 设置后强制 Bearer 鉴权（公网模式）。"""
    transport = os.getenv("SCHOLAR_MCP_TRANSPORT", "stdio")
    if transport != "streamable-http":
        mcp.run()
        return

    token = os.getenv("SCHOLAR_MCP_TOKEN", "")
    if not token:
        mcp.run(transport="streamable-http")
        return

    app = mcp.streamable_http_app()
    app.add_middleware(_bearer_token_middleware(token))
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SCHOLAR_MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("SCHOLAR_MCP_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
