"""Legacy text rendering over snapshot-pinned Scholar v2 services."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from scholar import auto_notes as note_generator
from scholar import config
from scholar.v2.models import ScholarError, ToolEnvelope
from scholar.v2.embeddings import configured_provider
from scholar.v2.repositories import ScholarRepository
from scholar.v2.runtime import RequestContext, get_coordinator, get_database
from scholar.v2.services import ScholarService

logger = logging.getLogger(__name__)


def call(
    tool_name: str,
    operation: Callable[[ScholarService, RequestContext], ToolEnvelope],
    timeout_ms: int = 15_000,
) -> ToolEnvelope:
    coordinator = get_coordinator()
    with coordinator.request(tool_name, timeout_ms) as context:
        service = ScholarService(
            ScholarRepository(get_database()), configured_provider()
        )
        return operation(service, context)


def error_text(error: Exception) -> str:
    if isinstance(error, ScholarError):
        return f"[{error.code}] {error.message}"
    logger.exception("Scholar v2 request failed")
    return "[INTERNAL] Scholar v2 request failed."


def search(query: str, limit: int) -> str:
    response = call(
        "scholar_search",
        lambda service, context: service.search_papers(context, query, limit),
    )
    papers = response.data["papers"]
    if not papers:
        return f"No results for '{query}'."
    lines = [
        f"Search: '{query}' ({len(papers)} results, snapshot={response.snapshot_id})"
    ]
    for paper in papers:
        abstract = (paper.get("abstract") or "").replace("\n", " ")[:200]
        lines.append(
            f"  [{paper['id']}] {paper['title'][:70]} "
            f"({paper.get('year') or ''} {paper.get('venue') or ''}) "
            f"score={round(float(paper['rank']), 4)}"
        )
        if abstract:
            lines.append(f"      {abstract}…")
    lines.append(
        "Next: scholar_info <paper_id>; scholar_section for specific sections."
    )
    return "\n".join(lines)


def vector_search(question: str, limit: int) -> str:
    response = call(
        "scholar_vec_search",
        lambda service, context: service.search_passages(
            context, question, limit=limit * 3, mode="vector"
        ),
    )
    seen = set()
    papers = []
    for row in response.data["passages"]:
        if row["work_id"] in seen:
            continue
        seen.add(row["work_id"])
        papers.append(row)
        if len(papers) == limit:
            break
    if not papers:
        return "No semantic matches found in the server corpus."
    lines = [f"Semantic matches for: '{question}' ({len(papers)} papers)"]
    for row in papers:
        lines.append(
            f"  [{row['work_id']}] {row['paper_title'][:70]} "
            f"sim={round(float(row['score']), 4)}"
        )
        lines.append(f"      {row['content'][:200]}…")
    lines.append("Next: scholar_info <paper_id> for TOC; scholar_section to read.")
    return "\n".join(lines)


def paper_info(paper_id: str) -> str:
    response = call(
        "scholar_info",
        lambda service, context: service.read_parsed_paper(
            context, paper_id, full=False
        ),
    )
    return _render_paper_info(response)


def _render_paper_info(response: ToolEnvelope) -> str:
    paper = response.data["paper"]
    outline = response.data["outline"]
    authors = ", ".join(item["display_name"] for item in paper["authors"])
    lines = [
        f"Title:     {paper['title']}",
        f"Authors:   {authors[:120]}",
        f"Year:      {paper.get('year') or 'N/A'}  Venue: {paper.get('venue') or 'N/A'}",
        f"Sections:  {len(outline)}",
    ]
    if paper.get("abstract"):
        abstract = paper["abstract"]
        lines.append(
            f"\nAbstract: {abstract[:400]}{'…' if len(abstract) > 400 else ''}"
        )
    lines.append("\nSection TOC (use scholar_section with the [index]):")
    for index, section in enumerate(outline):
        lines.append(
            f"  [{index}] (L{section['level']}) "
            f"{(section['title'] or '(untitled)')[:60]}"
        )
    return "\n".join(lines)


def section(paper_id: str, section_name: str, span: int) -> str:
    normalized_section = section_name.strip()
    if normalized_section.startswith("[") and normalized_section.endswith("]"):
        normalized_section = normalized_section[1:-1]
    response = call(
        "scholar_section",
        lambda service, context: service.get_section_text(
            context, paper_id, normalized_section, span=span
        ),
    )
    sections = response.data["sections"]
    nodes = response.data["content_nodes"]
    nodes_by_section: dict[str, list[dict]] = {}
    for node in nodes:
        nodes_by_section.setdefault(node["section_id"], []).append(node)
    parts = []
    for item in sections:
        text = "\n".join(
            node["text"]
            for node in nodes_by_section.get(item["id"], [])
            if node["text"]
        )
        parts.append(
            f"[{item['ordinal']}] {item['title'] or '(untitled)'} "
            f"(L{item['level']})\n{text}"
        )
    return "\n\n".join(parts)


def passages(
    query: str,
    limit: int,
    paper_id: str | None,
    section_name: str | None,
    hybrid: bool,
) -> str:
    mode = "hybrid" if hybrid else "vector"
    response = call(
        "scholar_passages",
        lambda service, context: service.search_passages(
            context,
            query,
            limit=limit,
            paper_id=paper_id,
            section=section_name,
            mode=mode,
        ),
    )
    rows = response.data["passages"]
    if not rows:
        return f"No passages for '{query}'."
    lines = [f"Passages matching '{query}' ({len(rows)})"]
    for row in rows:
        lines.append(
            f"  [{row['work_id']}] {(row.get('section_title') or '')[:20]}  "
            f"{row['content'][:120]}  score={round(float(row['score']), 4)}"
        )
    if response.warnings:
        lines.append("Warnings: " + "; ".join(response.warnings))
    lines.append("Next: scholar_section <paper_id> <heading> for the full section.")
    return "\n".join(lines)


def cite_network(paper_id: str | None) -> str:
    if paper_id is None:
        response = call(
            "scholar_cite_network",
            lambda service, context: service.graph_stats(context),
        )
        nodes = response.data["nodes"]
        edges = response.data["edges"]
        return (
            f"Papers: {nodes.get('paper', 0)}  "
            f"CITES edges (library-internal): {edges.get('CITES', 0)}\n"
            f"Authors: {nodes.get('author', 0)}  "
            f"AUTHORED_BY edges: {edges.get('AUTHORED_BY', 0)}"
        )
    response = call(
        "scholar_cite_network",
        lambda service, context: service.graph_neighbors(
            context, paper_id, direction="both", edge_types=["CITES"], limit=50
        ),
    )
    edges = response.data["edges"]
    resolved_id = response.data["paper_id"]
    if not edges:
        return f"No library-internal citations for: {paper_id}"
    lines = [f"Citation network for [{paper_id}]"]
    for edge in edges:
        arrow = "->" if edge["source_key"] == f"paper:{resolved_id}" else "<-"
        label = edge["target_label"] if arrow == "->" else edge["source_label"]
        lines.append(f"  {arrow} {label[:70]} confidence={edge['confidence']}")
    return "\n".join(lines)


def graph_query(concept: str) -> str:
    response = call(
        "scholar_graph_query",
        lambda service, context: service.search_papers(context, concept, 20),
    )
    papers = response.data["papers"]
    if not papers:
        return f"Concept '{concept}' not found."
    lines = [f"Papers matching concept '{concept}' ({len(papers)})"]
    for paper in papers:
        lines.append(
            f"  [{paper['id']}] {paper['title'][:60]}  "
            f"{paper.get('year') or ''}  {paper.get('venue') or ''}"
        )
    lines.append("Concept-node expansion requires a sealed semantic projection.")
    return "\n".join(lines)


def lineage(paper_a: str, paper_b: str) -> str:
    response = call(
        "scholar_lineage",
        lambda service, context: service.get_lineage(context, paper_a, paper_b),
    )
    path = response.data["path"]
    if not path:
        return f"No citation path between '{paper_a}' and '{paper_b}'."
    lines = [f"Citation path ({len(path)} hops):"]
    for edge in path:
        lines.append(
            f"  {edge['source_key']} -> {edge['target_key']} ({edge['edge_type']})"
        )
    return "\n".join(lines)


def graph_stats() -> str:
    response = call(
        "scholar_graph_stats",
        lambda service, context: service.graph_stats(context),
    )
    return (
        f"Papers:            {response.data['nodes'].get('paper', 0)}\n"
        f"CITES edges:       {response.data['edges'].get('CITES', 0)} "
        "(library-internal)\n"
        f"Authors:           {response.data['nodes'].get('author', 0)}\n"
        f"AUTHORED_BY edges: {response.data['edges'].get('AUTHORED_BY', 0)}"
    )


def list_papers(year: int | None, offset: int) -> str:
    response = call(
        "scholar_list_papers",
        lambda service, context: service.list_papers(
            context, year=year, offset=offset, limit=30
        ),
    )
    papers = response.data["papers"]
    lines = [
        f"Parsed Papers ({len(papers)} shown, offset {offset}, "
        f"snapshot={response.snapshot_id})"
    ]
    for paper in papers:
        lines.append(
            f"  {paper['id']}  {paper['title'][:50]}  "
            f"{paper.get('year') or ''}  {paper.get('venue') or ''}"
        )
    return "\n".join(lines)


def parsed_paper(paper_id: str, full: bool, max_chars: int) -> str:
    response = call(
        "read_parsed_paper",
        lambda service, context: service.read_parsed_paper(
            context, paper_id, full=full
        ),
        timeout_ms=30_000,
    )
    if not full:
        return _render_paper_info(response) + (
            "\n\n(reading ladder: use scholar_section for specific sections "
            "instead of full JSON)"
        )
    raw = json.dumps(response.as_dict(), ensure_ascii=False)
    if len(raw) > max_chars:
        return raw[:max_chars] + f"\n…[truncated at {max_chars} of {len(raw)} chars]"
    return raw


def auto_notes(paper_id: str | None, force: bool) -> str:
    coordinator = get_coordinator()
    with coordinator.request("scholar_auto_notes", 120_000) as context:
        service = ScholarService(
            ScholarRepository(get_database()), configured_provider()
        )
        if paper_id:
            paper_ids = [
                service.repository.resolve_work_id(
                    paper_id, context.snapshot["relational_build_id"]
                )
            ]
        else:
            paper_ids = []
            offset = 0
            while True:
                rows = service.repository.list_papers(
                    context.snapshot["relational_build_id"],
                    year=None,
                    offset=offset,
                    limit=200,
                )
                paper_ids.extend(row["id"] for row in rows)
                if len(rows) < 200:
                    break
                offset += len(rows)
        config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
        created = skipped = failed = 0
        for work_id in paper_ids:
            context.check()
            target = config.NOTES_DIR / f"{work_id}.md"
            if target.exists() and not force:
                skipped += 1
                continue
            try:
                response = service.read_parsed_paper(context, work_id, full=True)
                target.write_text(
                    note_generator.generate_note(_note_source(response.data)),
                    encoding="utf-8",
                )
                created += 1
            except Exception as error:
                logger.warning(
                    "auto note generation failed for %s (%s)",
                    work_id,
                    type(error).__name__,
                )
                failed += 1
        return json.dumps(
            {
                "status": "completed",
                "created": created,
                "skipped": skipped,
                "failed": failed,
                "snapshot_id": context.snapshot_id,
            },
            ensure_ascii=False,
        )


def _note_source(data: dict) -> dict:
    paper = data["paper"]
    nodes_by_section: dict[str, list[str]] = {}
    for node in data.get("content_nodes", []):
        if node["section_id"] and node["text"]:
            nodes_by_section.setdefault(node["section_id"], []).append(node["text"])
    sections = [
        {
            "heading": section["title"],
            "level": section["level"],
            "content": "\n\n".join(nodes_by_section.get(section["id"], [])),
        }
        for section in data["outline"]
    ]
    return {
        "paper_id": paper["id"],
        "title": paper["title"],
        "authors": [author["display_name"] for author in paper.get("authors", [])],
        "year": paper.get("year"),
        "venue": paper.get("venue"),
        "abstract": paper.get("abstract", ""),
        "sections": sections,
        "formulas": [
            {
                "latex": formula.get("tex") or "",
                "label": formula.get("xml_id") or "",
                "env_type": formula.get("mode") or "math",
            }
            for formula in data.get("formulas", [])
        ],
        "citations": [
            reference.get("title") or reference.get("raw_text") or ""
            for reference in data.get("references", [])
        ],
    }
