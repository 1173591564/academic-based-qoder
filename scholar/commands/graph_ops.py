"""Graph operations: graph-build, graph-stats, graph-query, cite-network, cite-resolve.

v0.2.0: the graph is an in-memory structure rebuilt from parsed JSON
(scholar/graph_mem.py) — no Neo4j, no Docker. `graph-build` is a thin alias
for rebuilding that cache; cite-resolve persists to refs-resolved.json.
"""

import typer
from rich.panel import Panel
from rich.table import Table

from .._shared import app, console


def _graph():
    from .. import graph_mem

    return graph_mem.ensure_graph()


# ===================================================================
# graph-build: rebuild the in-memory graph cache
# ===================================================================
@app.command(name="graph-build")
def graph_build():
    """Rebuild the in-memory citation/concept graph cache from parsed JSON."""
    from .. import graph_mem

    console.print("[cyan]Rebuilding graph cache from parsed JSON...[/]")
    gm = graph_mem.refresh()
    st = gm.stats()
    console.print(
        Panel(
            f"Papers:          {st['papers']}\n"
            f"CITES edges:     {st['cites_edges']} (library-internal)\n"
            f"Refs resolved:   {st['resolved_refs']}\n"
            f"Concept links:   {st['concept_links']} ({st['concepts']} concepts)\n"
            f"Lean4 replaces:  {st['replacements']}",
            title="[green]Graph Cache Rebuilt[/]",
        )
    )


# ===================================================================
# graph-stats: show graph statistics
# ===================================================================
@app.command(name="graph-stats")
def graph_stats():
    """Show graph statistics: papers, edges, refs, concepts, hubs."""
    gm = _graph()
    st = gm.stats()
    console.print(
        Panel(
            f"Papers:            {st['papers']}\n"
            f"CITES edges:       {st['cites_edges']} (library-internal)\n"
            f"Refs resolved:     {st['resolved_refs']}\n"
            f"Refs unresolved:   {st['unresolved_refs']}\n"
            f"Concepts:          {st['concepts']} ({st['concept_links']} links)\n"
            f"Innovations:       {st['innovations']}  Replacements: {st['replacements']}",
            title="[cyan]Graph Statistics[/]",
        )
    )

    if st["most_cited"]:
        table = Table(title="Top 10 Most Cited Papers")
        table.add_column("Title", max_width=60)
        table.add_column("Cited By", width=8)
        for r in st["most_cited"]:
            table.add_row((r.get("title") or "N/A")[:60], str(r.get("in_degree", 0)))
        console.print(table)

    if st["top_bridge"]:
        table = Table(title="Top 10 Bridge Papers")
        table.add_column("Title", max_width=60)
        table.add_column("Score", width=8)
        table.add_column("In", width=5)
        table.add_column("Out", width=5)
        for r in st["top_bridge"]:
            table.add_row(
                (r.get("title") or "N/A")[:60],
                f"{r.get('bridge_score', 0):.1f}",
                str(r.get("in_degree", 0)),
                str(r.get("out_degree", 0)),
            )
        console.print(table)


# ===================================================================
# graph-query: query concept graph
# ===================================================================
@app.command(name="graph-query")
def graph_query(
    concept: str = typer.Argument(help="Concept name (e.g. Transformer, MoE)"),
):
    """Papers tagged with a concept + related concepts."""
    gm = _graph()
    papers = gm.papers_by_concept(concept)
    if not papers:
        console.print(f"[yellow]Concept '{concept}' not found.[/]")
        raise typer.Exit(1)
    console.print(f"[bold]Papers with concept '{concept}' ({len(papers)})[/]")
    for p in papers[:20]:
        console.print(
            f"  [{p['ulid']}] {(p.get('title') or '')[:60]}  "
            f"{p.get('year', '')}  {p.get('venue', '')}"
        )
    related = gm.related_concepts(concept, top_n=8)
    if related:
        console.print("\n[bold]Related concepts:[/]")
        for r in related:
            console.print(f"  {r['id']} (weight {r['weight']})")


# ===================================================================
# cite-network: citation network analysis
# ===================================================================
@app.command(name="cite-network")
def cite_network(
    paper_id: str = typer.Argument("", help="Optional paper ID; empty = global stats"),
):
    """Citation network: global hubs, or one paper's forward/backward edges."""
    gm = _graph()
    if not paper_id:
        st = gm.stats()
        console.print(
            Panel(
                f"Papers: {st['papers']}  CITES edges: {st['cites_edges']}  "
                f"Resolved refs: {st['resolved_refs']}",
                title="[cyan]Citation Network[/]",
            )
        )
        return
    from ..id_resolver import resolve_id

    ulid = resolve_id(paper_id) or paper_id
    if ulid not in gm.papers:
        console.print(f"[yellow]Paper not in graph: {paper_id}[/]")
        raise typer.Exit(1)
    fwd = gm.forward_citations(ulid)
    bwd = gm.backward_citations(ulid)
    console.print(f"[bold][{ulid}] {(gm.papers[ulid].get('title') or '')[:70]}[/]")
    console.print(f"\nForward citations ({len(fwd['cited'])} in-library):")
    for p in fwd["cited"][:10]:
        console.print(f"  -> [{p.get('year', '?')}] {(p.get('title') or '')[:60]}")
    if fwd["unresolved_refs"]:
        console.print(f"  (…+{len(fwd['unresolved_refs'])} refs outside the library)")
    console.print(f"\nBackward citations ({len(bwd)}):")
    for p in bwd[:10]:
        console.print(f"  <- [{p.get('year', '?')}] {(p.get('title') or '')[:60]}")


# ===================================================================
# cite-resolve: resolve ref_keys (DOI/title/arXiv) -> sidecar JSON
# ===================================================================
@app.command(name="cite-resolve")
def cite_resolve(
    apply: bool = typer.Option(
        False, "--apply", help="Write resolutions to refs-resolved.json"
    ),
    limit: int = typer.Option(0, "--limit", help="Max arXiv queries (0=all)"),
):
    """Resolve citation ref_keys; --apply persists to refs-resolved.json."""
    from .. import cite_resolve as cr

    console.print("[cyan]Resolving citation references...[/]")
    result = cr.resolve_citations(dry_run=not apply, limit=limit if limit > 0 else 200)
    console.print(
        Panel(
            f"Total refs:       {result['total_refs']}\n"
            f"Resolved (DOI):   {result['resolved_doi']}\n"
            f"Resolved (title): {result['resolved_title']}\n"
            f"Resolved (arXiv): {result['resolved_arxiv']}\n"
            f"Sidecar refs:     {result.get('sidecar_refs', 0)}\n"
            f"Sidecar external: {result.get('sidecar_external', 0)}\n"
            f"Rate:             {result['resolution_rate']}",
            title="[green]Cite Resolve (--apply)[/]"
            if apply
            else "[yellow]Cite Resolve (dry-run)[/]",
        )
    )
