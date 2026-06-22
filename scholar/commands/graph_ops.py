"""Graph operations: graph-build, graph-stats, graph-query, cite-network, cite-resolve."""
import typer
from typing import Optional
from rich.table import Table
from rich.panel import Panel

from .._shared import app, console
from .. import config


# ===================================================================
# graph-build: Build citation + concept graph in Neo4j
# ===================================================================
@app.command(name="graph-build")
def graph_build():
    """Build citation network + concept graph in Neo4j."""
    from .. import graph_db as gdb_mod

    gdb = gdb_mod.GraphDB()
    if not gdb.available:
        console.print("[red]Neo4j not available.[/] Run: docker compose up neo4j")
        console.print("[dim]Or install: pip install neo4j[/]")
        raise typer.Exit(1)

    console.print("[cyan]Building citation network...[/]")
    cite_result = gdb_mod.build_citation_network(gdb)
    console.print(f"  Papers: {cite_result['papers']}, Citation edges: {cite_result['edges']}")

    console.print("[cyan]Resolving citation ref_keys to ULIDs...[/]")
    resolve_result = gdb_mod.resolve_ref_keys(gdb)
    console.print(f"  Resolved: {resolve_result['resolved']}, Unresolved: {resolve_result['unresolved']}")

    console.print("[cyan]Computing centrality metrics...[/]")
    centrality = gdb_mod.compute_centrality(gdb)
    console.print(f"  Top cited: {len(centrality.get('top_cited', []))} papers")
    console.print(f"  Top bridge: {len(centrality.get('top_bridge', []))} papers")

    console.print("[cyan]Building concept graph...[/]")
    concept_result = gdb_mod.build_concept_graph(gdb)
    console.print(f"  Papers with concepts: {concept_result['papers_with_concepts']}")
    console.print(f"  Paper-concept links: {concept_result['total_links']}")
    console.print(f"  Concept co-occurrence edges: {concept_result['cooccurrence_edges']}")

    console.print("[cyan]Syncing Lean4 replacements...[/]")
    lean_result = gdb_mod.sync_lean4_replacements(gdb)
    console.print(f"  REPLACES edges: {lean_result['replacements']}")

    console.print(Panel(
        f"Citation edges:   {cite_result['edges']}\n"
        f"Ref keys resolved: {resolve_result['resolved']}\n"
        f"Concept links:    {concept_result['total_links']}\n"
        f"Co-occurrence:    {concept_result['cooccurrence_edges']}\n"
        f"Lean4 replaces:   {lean_result['replacements']}",
        title="[green]Graph Build Complete[/]",
    ))
    gdb.close()


# ===================================================================
# graph-stats: Show graph statistics
# ===================================================================
@app.command(name="graph-stats")
def graph_stats():
    """Show detailed graph statistics: nodes, edges, centrality, components."""
    from .. import graph_db as gdb_mod

    gdb = gdb_mod.GraphDB()
    if not gdb.available:
        console.print("[red]Neo4j not available.[/]")
        raise typer.Exit(1)

    paper_count = gdb.run("MATCH (p:Paper) RETURN count(p) AS c")[0]["c"]
    innov_count = gdb.run("MATCH (i:Innovation) RETURN count(i) AS c")[0]["c"]

    cites_count = gdb.run("MATCH ()-[c:CITES]->() RETURN count(c) AS c")[0]["c"]
    concept_count = gdb.run("MATCH ()-[h:HAS_CONCEPT]->() RETURN count(h) AS c")[0]["c"]
    related_count = gdb.run("MATCH ()-[r:RELATED_TO]-() RETURN count(r) AS c")[0]["c"]
    replaces_count = gdb.run("MATCH ()-[r:REPLACES]->() RETURN count(r) AS c")[0]["c"]

    resolved = gdb.run("""
        MATCH ()-[c:CITES]->() WHERE c.resolved = true RETURN count(c) AS c
    """)[0]["c"]
    unresolved = cites_count - resolved

    isolated = gdb.run("""
        MATCH (p:Paper)
        WHERE NOT (p)--()
        RETURN count(p) AS c
    """)[0]["c"]

    console.print(Panel(
        f"Paper nodes:       {paper_count}\n"
        f"Innovation nodes:  {innov_count}\n"
        f"CITES edges:       {cites_count} (resolved: {resolved}, unresolved: {unresolved})\n"
        f"HAS_CONCEPT edges: {concept_count}\n"
        f"RELATED_TO edges:  {related_count}\n"
        f"REPLACES edges:    {replaces_count}\n"
        f"Isolated papers:   {isolated}",
        title="[cyan]Graph Statistics[/]",
    ))

    top_cited = gdb.run("""
        MATCH (p:Paper) WHERE p.in_degree > 0
        RETURN p.title AS title, p.in_degree AS score
        ORDER BY score DESC LIMIT 10
    """)
    if top_cited:
        table = Table(title="Top 10 Most Cited Papers")
        table.add_column("Title", max_width=60)
        table.add_column("Cited By", width=8)
        for r in top_cited:
            table.add_row((r.get("title") or "N/A")[:60], str(r.get("score", 0)))
        console.print(table)

    top_bridge = gdb.run("""
        MATCH (p:Paper) WHERE p.bridge_score > 0
        RETURN p.title AS title, p.bridge_score AS score,
               p.in_degree AS in_deg, p.out_degree AS out_deg
        ORDER BY score DESC LIMIT 10
    """)
    if top_bridge:
        table = Table(title="Top 10 Bridge Papers")
        table.add_column("Title", max_width=60)
        table.add_column("Score", width=8)
        table.add_column("In", width=5)
        table.add_column("Out", width=5)
        for r in top_bridge:
            table.add_row(
                (r.get("title") or "N/A")[:60],
                f"{r.get('score', 0):.1f}",
                str(r.get("in_deg", 0)),
                str(r.get("out_deg", 0)),
            )
        console.print(table)

    gdb.close()


# ===================================================================
# graph-query: Query concept graph
# ===================================================================
@app.command(name="graph-query")
def graph_query(
    concept: str = typer.Argument(help="Concept ID (e.g. Transformer, DPO_Loss)"),
):
    """Query the concept graph for a specific concept."""
    from .. import graph_db as gdb_mod

    gdb = gdb_mod.GraphDB()
    if not gdb.available:
        console.print("[red]Neo4j not available.[/]")
        raise typer.Exit(1)

    papers = gdb_mod.find_papers_by_concept(gdb, concept)
    if papers:
        table = Table(title=f"Papers with concept: {concept} ({len(papers)})")
        table.add_column("Title", max_width=50)
        table.add_column("Year", width=6)
        table.add_column("Venue", width=10)
        for p in papers[:20]:
            table.add_row(
                (p.get("title") or "N/A")[:50],
                str(p.get("year", "")),
                p.get("venue", "") or "",
            )
        console.print(table)
    else:
        console.print(f"No papers found for concept [cyan]{concept}[/]")

    related = gdb_mod.find_related_concepts(gdb, concept)
    if related:
        console.print(f"\n[bold]Related concepts:[/]")
        for r in related:
            console.print(f"  {r['id']} (line: {r['line']}, weight: {r['weight']})")

    gdb.close()


# ===================================================================
# cite-network: Citation network analysis
# ===================================================================
@app.command(name="cite-network")
def cite_network(
    paper_id: Optional[str] = typer.Argument(None, help="Paper ID (ULID/arXiv/DOI/slug, optional)"),
):
    """Show citation network statistics or analyze a specific paper."""
    from .. import graph_db as gdb_mod

    gdb = gdb_mod.GraphDB()
    if not gdb.available:
        console.print("[red]Neo4j not available.[/]")
        raise typer.Exit(1)

    if paper_id:
        from ..id_resolver import resolve_id
        ulid = resolve_id(paper_id) or paper_id
        forward = gdb_mod.get_forward_citations(gdb, ulid)
        backward = gdb_mod.get_backward_citations(gdb, ulid)

        console.print(f"[bold]Forward citations[/] (this paper cites): {len(forward)}")
        for p in forward[:10]:
            console.print(f"  -> [{p.get('year', '?')}] {(p.get('title') or 'N/A')[:50]}")

        console.print(f"\n[bold]Backward citations[/] (cited by): {len(backward)}")
        for p in backward[:10]:
            console.print(f"  <- [{p.get('year', '?')}] {(p.get('title') or 'N/A')[:50]}")
    else:
        stats = gdb_mod.get_citation_stats(gdb)
        console.print(Panel(
            f"Total papers in graph:  {stats['total_papers']}\n"
            f"Total citation edges:   {stats['total_citations']}",
            title="Citation Network",
        ))

        if stats.get("most_cited"):
            table = Table(title="Most Cited Papers (in-degree)")
            table.add_column("Title", max_width=50)
            table.add_column("Cited By", width=8)
            for p in stats["most_cited"][:10]:
                table.add_row(
                    (p.get("title") or p.get("ulid", ""))[:50],
                    str(p.get("cited_by", 0)),
                )
            console.print(table)

    gdb.close()


# ===================================================================
# cite-resolve: Citation resolution
# ===================================================================
@app.command(name="cite-resolve")
def cite_resolve(
    limit: int = typer.Option(200, help="Max arXiv queries"),
    dry_run: bool = typer.Option(True, help="Dry run (use --apply to write)"),
    apply: bool = typer.Option(False, "--apply", help="Apply changes"),
):
    """Resolve citation references: internal matching + arXiv API + Neo4j nodes."""
    from .. import cite_resolve as cr

    console.print("[cyan]Resolving citations...[/]")
    result = cr.resolve_citations(limit=limit, dry_run=not apply)
    console.print(Panel(
        f"Total references:     {result['total_refs']}\n"
        f"Resolved (internal):  [green]{result['resolved_internal']}[/]\n"
        f"Resolved (arXiv):     [green]{result['resolved_arxiv']}[/]\n"
        f"External nodes:       {result['external_nodes_created']}\n"
        f"Still unresolved:     [yellow]{result['still_unresolved']}[/]\n"
        f"arXiv queries:        {result['queried_arxiv']}",
        title="Cite Resolve" + ("" if apply else " (DRY RUN)"),
    ))
