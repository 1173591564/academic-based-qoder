"""
Scholar Studio — CLI Commands

Usage: python -m scholar <command> [options]
"""
import sys
import json
import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

from . import config
from .tex_parser import TeXParser, parse_paper
from . import db as dbmod

app = typer.Typer(
    name="scholar",
    help="Scholar Studio — Academic Research Toolkit",
    no_args_is_help=True,
)
console = Console()
parser = TeXParser()


def _get_db() -> Optional[dbmod.Database]:
    """Get database instance, or None if unavailable."""
    try:
        database = dbmod.Database()
        if database.available:
            return database
    except Exception:
        pass
    return None


# ===================================================================
# scan: Scan papers directory and show status
# ===================================================================
@app.command()
def scan():
    """Scan all papers and show parsing status."""
    paper_dirs = sorted(config.PAPERS_DIR.iterdir())
    paper_dirs = [d for d in paper_dirs if d.is_dir()]

    parsed_ids = set(dbmod.list_parsed())

    table = Table(title=f"Paper Library ({len(paper_dirs)} papers)")
    table.add_column("Status", width=6)
    table.add_column("ULID", width=28)
    table.add_column("Has Source", width=10)
    table.add_column("Has PDF", width=8)
    table.add_column("Parsed", width=8)

    parsed_count = 0
    has_source = 0
    has_pdf = 0

    # Render only first 15 + ellipsis + last 5 when total > 30 (avoid flooding the table)
    display_dirs = paper_dirs
    omitted = 0
    if len(paper_dirs) > 30:
        head = paper_dirs[:15]
        tail = paper_dirs[-5:]
        display_dirs = head + tail
        omitted = len(paper_dirs) - len(head) - len(tail)

    for d in display_dirs:
        ulid = d.name
        src = any(
            (d / name).exists()
            for name in ["source.tar.gz", "source.tgz", "source.tar", "source.zip"]
        )
        pdf = (d / "paper.pdf").exists()
        parsed = ulid in parsed_ids

        if src:
            has_source += 1
        if pdf:
            has_pdf += 1
        if parsed:
            parsed_count += 1

        status = "[green]OK[/]" if parsed else "[yellow]--[/]"
        table.add_row(
            status,
            ulid,
            "[green]Y[/]" if src else "[red]N[/]",
            "[green]Y[/]" if pdf else "[red]N[/]",
            "[green]Y[/]" if parsed else "[dim]N[/]",
        )

    # Insert ellipsis row when truncating
    if omitted > 0:
        table.add_row(
            "...",
            f"[dim]{omitted} more papers omitted[/]",
            "...",
            "...",
            "...",
        )

    # Always show full aggregate counts (computed from ALL papers, not the displayed subset)
    full_source = sum(
        1 for d in paper_dirs
        if any((d / n).exists() for n in ["source.tar.gz", "source.tgz", "source.tar", "source.zip"])
    )
    full_pdf = sum(1 for d in paper_dirs if (d / "paper.pdf").exists())
    full_parsed = sum(1 for d in paper_dirs if d.name in parsed_ids)

    console.print(table)
    console.print(
        Panel(
            f"Total: {len(paper_dirs)} | "
            f"Source: {full_source} | "
            f"PDF: {full_pdf} | "
            f"Parsed: {full_parsed}",
            title="Summary",
        )
    )


# ===================================================================
# parse: Parse a single paper
# ===================================================================
@app.command()
def parse(ulid: str = typer.Argument(help="Paper ULID")):
    """Parse a single paper's TeX source into structured JSON."""
    paper_dir = config.PAPERS_DIR / ulid
    if not paper_dir.exists():
        console.print(f"[red]Error:[/] Paper directory not found: {paper_dir}")
        raise typer.Exit(1)

    console.print(f"Parsing [cyan]{ulid}[/]...")
    try:
        data = parse_paper(paper_dir, ulid)
        out_path = dbmod.save_parsed(data)

        # Try DB ingest
        database = _get_db()
        if database:
            data["parsed_path"] = str(out_path)
            data["section_count"] = len(data.get("sections", []))
            data["formula_count"] = len(data.get("formulas", []))
            data["citation_count"] = len(data.get("citations", []))
            database.ingest_paper(data)
            console.print("[dim]Ingested into database[/]")

        console.print(Panel(
            f"Title:     {data.get('title', 'N/A')}\n"
            f"Authors:   {', '.join(data.get('authors', [])[:5])}{'...' if len(data.get('authors', [])) > 5 else ''}\n"
            f"Year:      {data.get('year', 'N/A')}\n"
            f"Venue:     {data.get('venue', 'N/A')}\n"
            f"Sections:  {len(data.get('sections', []))}\n"
            f"Formulas:  {len(data.get('formulas', []))}\n"
            f"Citations: {len(data.get('citations', []))}\n"
            f"Output:    {out_path}",
            title=f"[green]Parsed OK[/] {ulid}",
        ))
    except Exception as e:
        console.print(f"[red]Parse failed:[/] {e}")
        raise typer.Exit(1)


# ===================================================================
# parse-all: Batch parse all papers
# ===================================================================
@app.command(name="parse-all")
def parse_all(
    limit: int = typer.Option(0, help="Max papers to parse (0=all)"),
    force: bool = typer.Option(False, help="Re-parse already parsed"),
):
    """Batch parse all papers' TeX sources."""
    paper_dirs = sorted(config.PAPERS_DIR.iterdir())
    paper_dirs = [d for d in paper_dirs if d.is_dir()]
    parsed_ids = set(dbmod.list_parsed())

    if not force:
        paper_dirs = [d for d in paper_dirs if d.name not in parsed_ids]

    if limit > 0:
        paper_dirs = paper_dirs[:limit]

    console.print(f"Parsing {len(paper_dirs)} papers...")

    success = 0
    failed = 0
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing...", total=len(paper_dirs))
        for d in paper_dirs:
            ulid = d.name
            progress.update(task, description=f"Parsing {ulid[:16]}...")
            try:
                data = parse_paper(d, ulid)
                out_path = dbmod.save_parsed(data)

                database = _get_db()
                if database:
                    data["parsed_path"] = str(out_path)
                    data["section_count"] = len(data.get("sections", []))
                    data["formula_count"] = len(data.get("formulas", []))
                    data["citation_count"] = len(data.get("citations", []))
                    database.ingest_paper(data)

                success += 1
            except Exception as e:
                failed += 1
                errors.append((ulid, str(e)))
            progress.advance(task)

    console.print(
        Panel(
            f"Success: [green]{success}[/]  |  Failed: [red]{failed}[/]",
            title="Batch Parse Complete",
        )
    )
    if errors:
        console.print("[yellow]Failed papers:[/]")
        for ulid, err in errors[:20]:
            console.print(f"  {ulid}: {err}")
        if len(errors) > 20:
            console.print(f"  ... and {len(errors) - 20} more")


# ===================================================================
# info: Show detailed info about a paper
# ===================================================================
@app.command()
def info(ulid: str = typer.Argument(help="Paper ULID")):
    """Show detailed information about a parsed paper."""
    data = dbmod.load_parsed(ulid)
    if data is None:
        console.print(f"[yellow]Paper not parsed yet.[/] Run: python -m scholar parse {ulid}")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold]{data.get('title', 'N/A')}[/]\n\n"
        f"Authors:   {', '.join(data.get('authors', []))}\n"
        f"Year:      {data.get('year', 'N/A')}\n"
        f"Venue:     {data.get('venue', 'N/A')}\n"
        f"TeX files: {data.get('tex_file_count', 'N/A')}\n"
        f"Main file: {data.get('main_tex_file', 'N/A')}",
        title=f"Paper: {ulid}",
    ))

    # Abstract
    abstract = data.get("abstract")
    if abstract:
        console.print(Panel(
            abstract[:500] + ("..." if len(abstract) > 500 else ""),
            title="Abstract",
        ))

    # Sections
    sections = data.get("sections", [])
    if sections:
        table = Table(title=f"Sections ({len(sections)})")
        table.add_column("#", width=4)
        table.add_column("Level", width=6)
        table.add_column("Heading")
        table.add_column("Length", width=8)
        for i, s in enumerate(sections):
            indent = "  " * (s.get("level", 1) - 1)
            table.add_row(
                str(i),
                str(s.get("level", 1)),
                f"{indent}{s.get('heading', '(untitled)')}",
                str(len(s.get("content", ""))),
            )
        console.print(table)

    # Formulas (first 10)
    formulas = data.get("formulas", [])
    if formulas:
        console.print(f"\n[bold]Formulas ({len(formulas)}):[/]")
        for f in formulas[:10]:
            label = f"[{f['label']}]" if f.get("label") else ""
            latex_preview = f["latex"][:80].replace("\n", " ")
            console.print(f"  {f.get('env_type', 'math')}{label}: ${latex_preview}...")
        if len(formulas) > 10:
            console.print(f"  ... and {len(formulas) - 10} more")

    # Citations (first 15)
    citations = data.get("citations", [])
    if citations:
        console.print(f"\n[bold]Citations ({len(citations)}):[/]")
        console.print(f"  {', '.join(citations[:15])}")
        if len(citations) > 15:
            console.print(f"  ... and {len(citations) - 15} more")


# ===================================================================
# search: Full-text search across parsed papers
# ===================================================================
@app.command()
def search(
    keyword: str = typer.Argument(help="Search keyword"),
    limit: int = typer.Option(20, help="Max results"),
):
    """Search across all parsed papers (title, abstract, sections)."""
    keyword_lower = keyword.lower()
    results = []

    # Try DB first
    database = _get_db()
    if database:
        results = database.search_papers(keyword)
        results = results[:limit]
    else:
        # Fallback: search JSON files
        for paper_id in dbmod.list_parsed():
            data = dbmod.load_parsed(paper_id)
            if not data:
                continue
            score = 0
            # Check title
            if keyword_lower in (data.get("title") or "").lower():
                score += 10
            # Check abstract
            if keyword_lower in (data.get("abstract") or "").lower():
                score += 5
            # Check sections
            for s in data.get("sections", []):
                if keyword_lower in s.get("content", "").lower():
                    score += 1
                    if score >= 3:
                        break
            if score > 0:
                results.append({
                    "paper_id": paper_id,
                    "title": data.get("title", "N/A"),
                    "year": data.get("year"),
                    "score": score,
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:limit]

    if not results:
        console.print(f"No results for [cyan]'{keyword}'[/]")
        return

    table = Table(title=f"Search: '{keyword}' ({len(results)} results)")
    table.add_column("Paper ID", width=28)
    table.add_column("Title")
    table.add_column("Year", width=6)

    for r in results:
        table.add_row(
            r.get("paper_id", r.get("id", "")),
            (r.get("title") or "N/A")[:60],
            str(r.get("year", "")),
        )
    console.print(table)


# ===================================================================
# list-papers: List parsed papers
# ===================================================================
@app.command(name="list-papers")
def list_papers(
    year: Optional[int] = typer.Option(None, help="Filter by year"),
    limit: int = typer.Option(30, help="Max papers to show"),
):
    """List parsed papers with metadata."""
    database = _get_db()
    if database:
        papers = database.list_papers(year=year)
    else:
        papers = []
        for paper_id in dbmod.list_parsed():
            data = dbmod.load_parsed(paper_id)
            if data:
                if year and data.get("year") != year:
                    continue
                papers.append(data)
        papers.sort(key=lambda x: x.get("year") or 0, reverse=True)

    papers = papers[:limit]

    table = Table(title=f"Parsed Papers ({len(papers)} shown)")
    table.add_column("Paper ID", width=28)
    table.add_column("Title", max_width=50)
    table.add_column("Year", width=6)
    table.add_column("Venue", width=10)
    table.add_column("Sec", width=4)
    table.add_column("Fml", width=4)
    table.add_column("Cit", width=4)

    for p in papers:
        table.add_row(
            p.get("paper_id", ""),
            (p.get("title") or "N/A")[:50],
            str(p.get("year", "")),
            p.get("venue", "") or "",
            str(len(p.get("sections", []))),
            str(len(p.get("formulas", []))),
            str(len(p.get("citations", []))),
        )
    console.print(table)


# ===================================================================
# stats: Show knowledge base statistics
# ===================================================================
@app.command()
def stats():
    """Show knowledge base statistics."""
    paper_dirs = [d for d in config.PAPERS_DIR.iterdir() if d.is_dir()]
    parsed_ids = dbmod.list_parsed()

    database = _get_db()
    db_status = "connected" if database else "not available (file-only mode)"

    # Compute some stats from parsed JSON files
    years = {}
    venues = {}
    total_formulas = 0
    total_citations = 0
    total_sections = 0
    has_year = 0
    has_authors = 0
    has_abstract = 0
    has_venue = 0

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
    console.print(Panel(
        f"Paper folders:   {len(paper_dirs)}\n"
        f"Parsed:          {len(parsed_ids)}\n"
        f"Total sections:  {total_sections}\n"
        f"Total formulas:  {total_formulas}\n"
        f"Total citations: {total_citations}\n"
        f"Database:        {db_status}\n"
        f"\n"
        f"[bold]Metadata Coverage:[/]\n"
        f"  Year:      {has_year}/{total} ({has_year*100//total}%)\n"
        f"  Authors:   {has_authors}/{total} ({has_authors*100//total}%)\n"
        f"  Abstract:  {has_abstract}/{total} ({has_abstract*100//total}%)\n"
        f"  Venue:     {has_venue}/{total} ({has_venue*100//total}%)",
        title="Knowledge Base Stats",
    ))

    if years:
        sorted_years = sorted(years.items())
        year_str = ", ".join(f"{y}: {c}" for y, c in sorted_years)
        console.print(f"\n[bold]By Year:[/] {year_str}")

    if venues:
        sorted_venues = sorted(venues.items(), key=lambda x: x[1], reverse=True)
        venue_str = ", ".join(f"{v}: {c}" for v, c in sorted_venues[:10])
        console.print(f"[bold]By Venue:[/] {venue_str}")


# ===================================================================
# export-bib: Generate BibTeX from parsed papers
# ===================================================================
@app.command(name="export-bib")
def export_bib(
    output: str = typer.Option("output/bib/references.bib", help="Output .bib file path"),
):
    """Export BibTeX entries for all parsed papers."""
    entries = []
    for paper_id in dbmod.list_parsed():
        data = dbmod.load_parsed(paper_id)
        if not data:
            continue
        title = data.get("title", "Untitled")
        authors = " and ".join(data.get("authors", ["Unknown"]))
        year = data.get("year", "")
        venue = data.get("venue", "")

        # Generate a clean citation key
        cite_key = paper_id

        entry = f"@article{{{cite_key},\n"
        entry += f"  title = {{{title}}},\n"
        entry += f"  author = {{{authors}}},\n"
        if year:
            entry += f"  year = {{{year}}},\n"
        if venue:
            entry += f"  journal = {{{venue}}},\n"
        entry += "}\n"
        entries.append(entry)

    out_path = config.PROJECT_ROOT / output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(entries), encoding="utf-8")
    console.print(f"Exported [green]{len(entries)}[/] BibTeX entries to {out_path}")


# ===================================================================
# author-fix: Complete missing authors via arXiv API
# ===================================================================
@app.command(name="author-fix")
def author_fix(
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default: dry run)"),
    limit: int = typer.Option(50, help="Max papers to query"),
):
    """Fill in missing authors using arXiv API title search."""
    from . import year_fix as yf

    parsed_dir = config.PARSED_DIR
    filled = 0
    queried = 0
    results = []

    console.print("[cyan]Querying arXiv API for papers missing authors...[/]")

    for json_file in sorted(parsed_dir.glob("*.json")):
        if queried >= limit:
            break
        data = json.loads(json_file.read_text(encoding="utf-8"))
        authors = data.get("authors", [])
        if authors and any(a.strip() for a in authors):
            continue

        title = data.get("title", "")
        if not title:
            continue

        queried += 1
        try:
            import urllib.request
            import urllib.parse
            import xml.etree.ElementTree as ET

            encoded = urllib.parse.quote(title[:200])
            url = (
                f"http://export.arxiv.org/api/query?"
                f"search_query=ti:{encoded}&max_results=1&sortBy=relevance"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "ScholarStudio/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read().decode("utf-8")

            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(xml_data)
            entries = root.findall("atom:entry", ns)
            if entries:
                entry = entries[0]
                arxiv_authors = [
                    a.find("atom:name", ns).text
                    for a in entry.findall("atom:author", ns)
                    if a.find("atom:name", ns) is not None
                ]
                if arxiv_authors:
                    results.append({
                        "ulid": data["paper_id"],
                        "title": title[:50],
                        "authors": arxiv_authors,
                    })
                    filled += 1
                    if apply:
                        data["authors"] = arxiv_authors
                        json_file.write_text(
                            json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
        except Exception:
            pass

    console.print(Panel(
        f"Queried:    {queried}\n"
        f"{'Would fill' if not apply else 'Filled'}: {filled}",
        title="Author Fix" + ("" if apply else " (DRY RUN — use --apply to save)"),
    ))
    if results:
        for r in results[:10]:
            author_str = ", ".join(r['authors'][:3])
            if len(r['authors']) > 3:
                author_str += f" et al. ({len(r['authors'])})"
            console.print(f"  {r['ulid'][:16]}... -> {author_str}")


# ===================================================================
# arxiv-search: Search arXiv
# ===================================================================
@app.command(name="arxiv-search")
def arxiv_search(
    query: str = typer.Argument(help="Search query"),
    max_results: int = typer.Option(10, "--max", help="Max results"),
):
    """Search arXiv for papers."""
    try:
        import urllib.request
        import urllib.parse
        import xml.etree.ElementTree as ET
    except ImportError:
        console.print("[red]urllib/xml required (should be in stdlib)[/]")
        raise typer.Exit(1)

    encoded = urllib.parse.quote(query)
    url = (
        f"http://export.arxiv.org/api/query?"
        f"search_query=all:{encoded}&max_results={max_results}&sortBy=relevance"
    )

    console.print(f"Searching arXiv for [cyan]'{query}'[/]...")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ScholarStudio/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read().decode("utf-8")
    except Exception as e:
        console.print(f"[red]arXiv request failed:[/] {e}")
        raise typer.Exit(1)

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_data)
    entries = root.findall("atom:entry", ns)

    if not entries:
        console.print("No results found.")
        return

    table = Table(title=f"arXiv Results ({len(entries)})")
    table.add_column("#", width=3)
    table.add_column("Title", max_width=55)
    table.add_column("Authors", max_width=30)
    table.add_column("Year", width=6)
    table.add_column("arXiv ID", width=14)

    for i, entry in enumerate(entries):
        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        authors = [
            a.find("atom:name", ns).text
            for a in entry.findall("atom:author", ns)
        ]
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."
        published = entry.find("atom:published", ns).text[:4]
        arxiv_id = entry.find("atom:id", ns).text.split("/abs/")[-1]

        table.add_row(str(i + 1), title[:55], author_str[:30], published, arxiv_id)

    console.print(table)


# ===================================================================
# graph-build: Build citation + concept graph in Neo4j
# ===================================================================
@app.command(name="graph-build")
def graph_build():
    """Build citation network + concept graph in Neo4j."""
    from . import graph_db as gdb_mod

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
    from . import graph_db as gdb_mod

    gdb = gdb_mod.GraphDB()
    if not gdb.available:
        console.print("[red]Neo4j not available.[/]")
        raise typer.Exit(1)

    # Node counts
    paper_count = gdb.run("MATCH (p:Paper) RETURN count(p) AS c")[0]["c"]
    innov_count = gdb.run("MATCH (i:Innovation) RETURN count(i) AS c")[0]["c"]

    # Edge counts
    cites_count = gdb.run("MATCH ()-[c:CITES]->() RETURN count(c) AS c")[0]["c"]
    concept_count = gdb.run("MATCH ()-[h:HAS_CONCEPT]->() RETURN count(h) AS c")[0]["c"]
    related_count = gdb.run("MATCH ()-[r:RELATED_TO]-() RETURN count(r) AS c")[0]["c"]
    replaces_count = gdb.run("MATCH ()-[r:REPLACES]->() RETURN count(r) AS c")[0]["c"]

    # Resolved vs unresolved citations
    resolved = gdb.run("""
        MATCH ()-[c:CITES]->() WHERE c.resolved = true RETURN count(c) AS c
    """)[0]["c"]
    unresolved = cites_count - resolved

    # Isolated nodes (no edges at all)
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

    # Top cited papers
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

    # Top bridge papers
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
    from . import graph_db as gdb_mod

    gdb = gdb_mod.GraphDB()
    if not gdb.available:
        console.print("[red]Neo4j not available.[/]")
        raise typer.Exit(1)

    # Find papers with this concept
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

    # Find related concepts
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
    ulid: Optional[str] = typer.Argument(None, help="Paper ULID (optional)"),
):
    """Show citation network statistics or analyze a specific paper."""
    from . import graph_db as gdb_mod

    gdb = gdb_mod.GraphDB()
    if not gdb.available:
        console.print("[red]Neo4j not available.[/]")
        raise typer.Exit(1)

    if ulid:
        # Show forward/backward citations for a specific paper
        forward = gdb_mod.get_forward_citations(gdb, ulid)
        backward = gdb_mod.get_backward_citations(gdb, ulid)

        console.print(f"[bold]Forward citations[/] (this paper cites): {len(forward)}")
        for p in forward[:10]:
            console.print(f"  → [{p.get('year', '?')}] {(p.get('title') or 'N/A')[:50]}")

        console.print(f"\n[bold]Backward citations[/] (cited by): {len(backward)}")
        for p in backward[:10]:
            console.print(f"  ← [{p.get('year', '?')}] {(p.get('title') or 'N/A')[:50]}")
    else:
        # Global stats
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
# year-fix: Complete missing years
# ===================================================================
@app.command(name="year-fix")
def year_fix(
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default: dry run)"),
):
    """Fill in missing years using Lean4 Database.lean cross-reference."""
    from . import year_fix as yf

    console.print("[cyan]Parsing Lean4 Database.lean...[/]")
    lean_papers = yf.parse_lean_papers()
    console.print(f"  Found {len(lean_papers)} papers in Lean4")

    stats, updates = yf.complete_years(dry_run=not apply)
    console.print(Panel(
        f"Lean4 papers:      {stats['lean_papers']}\n"
        f"Parsed papers:     {stats['parsed_papers']}\n"
        f"Matched:           {stats['matched']}\n"
        f"Already had year:  {stats['already_had_year']}\n"
        f"{'Would fill' if not apply else 'Filled'}: {stats['filled']}\n"
        f"Still missing:     {stats['still_missing']}",
        title="Year Completion (Lean4)" + ("" if apply else " (DRY RUN — use --apply to save)"),
    ))

    # Phase 2: arXiv API fallback for remaining papers
    if stats['still_missing'] > 0:
        console.print(f"\n[cyan]Querying arXiv API for {min(stats['still_missing'], 50)} remaining papers...[/]")
        arxiv_result = yf.complete_years_arxiv(dry_run=not apply, limit=min(stats['still_missing'], 50))
        console.print(
            f"  Queried: {arxiv_result['queried']}, "
            f"{'Would fill' if not apply else 'Filled'}: {arxiv_result['filled']}"
        )
        if arxiv_result['results']:
            for r in arxiv_result['results'][:10]:
                console.print(f"    {r['ulid'][:16]}... -> {r['year']}  ({r['title']})")


# ===================================================================
# rag-index: Build RAG vector index
# ===================================================================
@app.command(name="rag-index")
def rag_index():
    """Build RAG vector index (requires SCHOLAR_EMBEDDING_API_KEY)."""
    from . import rag

    if not config.EMBEDDING_API_KEY:
        console.print("[yellow]No SCHOLAR_EMBEDDING_API_KEY set.[/]")
        console.print("Set it via: export SCHOLAR_EMBEDDING_API_KEY=your_key")
        console.print("Or for Windows: set SCHOLAR_EMBEDDING_API_KEY=your_key")
        raise typer.Exit(1)

    console.print(f"[cyan]Indexing papers with {config.EMBEDDING_PROVIDER} ({config.EMBEDDING_MODEL})...[/]")
    result = rag.index_all_papers()
    console.print(Panel(
        f"Papers:        {result['papers']}\n"
        f"Total chunks:  {result['total_chunks']}\n"
        f"Embedded:      {result['embedded']}\n"
        f"Failed:        {result['failed']}\n"
        f"HNSW index:    {'[green]OK[/]' if result['hnsw_index'] else '[red]Failed[/]'}",
        title="[green]RAG Index Complete[/]",
    ))


# ===================================================================
# rag-search: Semantic search
# ===================================================================
@app.command(name="rag-search")
def rag_search(
    query: str = typer.Argument(help="Search query"),
    limit: int = typer.Option(10, help="Max results"),
    hybrid: bool = typer.Option(False, "--hybrid", help="Use hybrid search (vector + BM25 + RRF)"),
):
    """Semantic search in the RAG index (supports hybrid mode)."""
    from . import rag

    if hybrid:
        results = rag.search_rag_hybrid(query, limit=limit)
        title = f"Hybrid Search: '{query}' ({len(results)} results)"
    else:
        results = rag.search_rag(query, limit=limit)
        title = f"RAG Search: '{query}' ({len(results)} results)"

    if not results:
        console.print(f"No RAG results for [cyan]'{query}'[/]")
        console.print("[dim]Make sure RAG index is built: python -m scholar rag-index[/]")
        return

    table = Table(title=title)
    table.add_column("Paper ID", width=28)
    table.add_column("Section", width=15)
    table.add_column("Content", max_width=60)
    table.add_column("Sim", width=5)

    for r in results:
        table.add_row(
            r.get("paper_id", ""),
            (r.get("section") or "")[:15],
            (r.get("content") or "")[:60],
            f"{r.get('similarity', 0):.3f}",
        )
    console.print(table)


# ===================================================================
# auto-notes: Generate reading notes
# ===================================================================
@app.command(name="auto-notes")
def auto_notes(
    ulid: Optional[str] = typer.Argument(None, help="Paper ULID (omit for batch mode)"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing notes"),
):
    """Generate structured reading notes from parsed paper data."""
    from . import auto_notes as an

    if ulid:
        result = an.generate_single_note(ulid, force=force)
        console.print(Panel(
            f"Status: {result['status']}\n"
            f"Path:   {result['path']}",
            title=f"Auto-Note: {ulid}",
        ))
    else:
        console.print("[cyan]Generating auto-notes for all papers...[/]")
        result = an.generate_all_notes(force=force)
        console.print(Panel(
            f"Created:  [green]{result['created']}[/]\n"
            f"Skipped:  {result['skipped']}\n"
            f"Failed:   [red]{result['failed']}[/]\n"
            f"Total:    {result['total']}",
            title="[green]Auto-Notes Complete[/]",
        ))


# ===================================================================
# quality-score: Quality scoring
# ===================================================================
@app.command(name="quality-score")
def quality_score(
    ulid: Optional[str] = typer.Argument(None, help="Paper ULID (omit for --all)"),
    all_papers: bool = typer.Option(False, "--all", help="Score all papers"),
):
    """Score paper quality across 7 dimensions."""
    from . import quality as q

    if ulid:
        result = q.score_single_paper(ulid)
        if result is None:
            console.print(f"[red]Paper not found:[/] {ulid}")
            raise typer.Exit(1)
        # Display dimensions
        table = Table(title=f"Quality Score: {ulid} (Grade: {result['grade']})")
        table.add_column("Dimension", width=20)
        table.add_column("Score", width=8)
        table.add_column("Details")
        for name, dim in result["dimensions"].items():
            table.add_row(
                name,
                f"{dim['score']}/{dim['max']}",
                ", ".join(str(d) for d in dim['details'][:3]),
            )
        table.add_row(
            "[bold]Total[/]",
            f"[bold]{result['total']}/{result['max_total']}[/]",
            f"Grade: [bold]{result['grade']}[/]",
        )
        console.print(table)
    elif all_papers:
        console.print("[cyan]Scoring all papers...[/]")
        result = q.score_all_papers()
        console.print(Panel(
            f"Scored:  [green]{result['scored']}[/]\n"
            f"Failed:  [red]{result['failed']}[/]\n"
            f"\n[bold]Grade Distribution:[/]\n"
            f"  A: {result['grades']['A']}  B: {result['grades']['B']}  "
            f"C: {result['grades']['C']}  D: {result['grades']['D']}  "
            f"F: {result['grades']['F']}",
            title="[green]Quality Scoring Complete[/]",
        ))
    else:
        console.print("Specify a ULID or use --all")


# ===================================================================
# classify: Paper classification
# ===================================================================
@app.command()
def classify(
    ulid: Optional[str] = typer.Argument(None, help="Paper ULID (omit for --all)"),
    all_papers: bool = typer.Option(False, "--all", help="Classify all papers"),
    list_tags: bool = typer.Option(False, "--list-tags", help="List all tags in corpus"),
):
    """Classify papers into domain/sub-direction/method tags."""
    from . import classify as cl

    if list_tags:
        tags = cl.list_all_tags()
        console.print("[bold]Domains:[/]")
        for d, c in tags["domains"].items():
            console.print(f"  {d}: {c}")
        console.print("\n[bold]Sub-directions (top 15):[/]")
        for s, c in list(tags["sub_directions"].items())[:15]:
            console.print(f"  {s}: {c}")
        console.print("\n[bold]Methods (top 20):[/]")
        for m, c in list(tags["methods"].items())[:20]:
            console.print(f"  {m}: {c}")
    elif ulid:
        result = cl.classify_single_paper(ulid)
        if result is None:
            console.print(f"[red]Paper not found:[/] {ulid}")
            raise typer.Exit(1)
        console.print(Panel(
            f"Domains:        {', '.join(result['domains'])}\n"
            f"Sub-directions: {', '.join(result['sub_directions'])}\n"
            f"Methods:        {', '.join(result['methods'][:8])}",
            title=f"Classification: {ulid}",
        ))
    elif all_papers:
        console.print("[cyan]Classifying all papers...[/]")
        result = cl.classify_all_papers()
        console.print(Panel(
            f"Classified: [green]{result['classified']}[/]\n"
            f"Failed:     [red]{result['failed']}[/]\n"
            f"\n[bold]Domain Distribution:[/]\n" +
            "\n".join(f"  {d}: {c}" for d, c in sorted(result['domain_counts'].items(), key=lambda x: -x[1])),
            title="[green]Classification Complete[/]",
        ))
    else:
        console.print("Specify a ULID, use --all, or --list-tags")


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
    from . import cite_resolve as cr

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


# ===================================================================
# bootstrap: Full initialization pipeline
# ===================================================================
@app.command()
def bootstrap():
    """Full initialization: parse -> year-fix -> author-fix -> graph-build -> rag-index -> auto-notes -> quality -> classify."""
    from . import auto_notes as an
    from . import quality as q
    from . import classify as cl
    from . import year_fix as yf

    console.print(Panel("[bold]Scholar Studio Bootstrap[/]\nFull initialization pipeline", title="Bootstrap"))

    # Step 1: Parse all
    console.print("\n[cyan][1/8] Parsing all papers...[/]")
    parsed_ids = dbmod.list_parsed()
    paper_dirs = [d for d in config.PAPERS_DIR.iterdir() if d.is_dir()]
    unparsed = len(paper_dirs) - len(parsed_ids)
    if unparsed > 0:
        console.print(f"  {unparsed} papers to parse...")
        # Inline parse-all
        parsed_count = 0
        for d in paper_dirs:
            if d.name not in set(parsed_ids):
                try:
                    data = parse_paper(d, d.name)
                    dbmod.save_parsed(data)
                    parsed_count += 1
                except Exception:
                    pass
        console.print(f"  Parsed [green]{parsed_count}[/] new papers")
    else:
        console.print("  All papers already parsed")

    # Step 2: Year fix
    console.print("\n[cyan][2/8] Completing years (Lean4 + heuristics)...[/]")
    stats, _ = yf.complete_years(dry_run=False)
    console.print(f"  Filled: [green]{stats['filled']}[/], Still missing: {stats['still_missing']}")

    # Step 3: Author fix (arXiv API)
    console.print("\n[cyan][3/8] Completing authors (arXiv API)...[/]")
    try:
        a_stats = yf.complete_authors_arxiv(limit=100, dry_run=False)
        console.print(
            f"  Queried: {a_stats['queried']}, Filled: [green]{a_stats['filled']}[/], "
            f"Skipped (have authors): {a_stats['skipped_have_authors']}"
        )
    except Exception as e:
        console.print(f"  [yellow]Author fix skipped: {e}[/]")

    # Step 4: Graph build (if Neo4j available)
    console.print("\n[cyan][4/8] Building graph (Neo4j)...[/]")
    try:
        from . import graph_db as gdb_mod
        gdb = gdb_mod.GraphDB()
        if gdb.available:
            cite_result = gdb_mod.build_citation_network(gdb)
            gdb_mod.resolve_ref_keys(gdb)
            gdb_mod.compute_centrality(gdb)
            concept_result = gdb_mod.build_concept_graph(gdb)
            gdb_mod.sync_lean4_replacements(gdb)
            gdb.close()
            console.print(f"  Papers: {cite_result['papers']}, Edges: {cite_result['edges']}, Concepts: {concept_result['total_links']}")
        else:
            console.print("  [yellow]Neo4j not available, skipping[/]")
    except Exception as e:
        console.print(f"  [yellow]Graph build skipped: {e}[/]")

    # Step 4b: Sync parsed papers to PostgreSQL (needed for RAG FK + other queries)
    console.print("\n[cyan][4b/8] Syncing papers to PostgreSQL...[/]")
    try:
        _db = dbmod.Database()
        if _db.available:
            sync_count = 0
            for json_file in config.PARSED_DIR.glob("*.json"):
                data = json.loads(json_file.read_text(encoding="utf-8"))
                _db.ingest_paper(data)
                sync_count += 1
            console.print(f"  Synced [green]{sync_count}[/] papers to PG (with sections/formulas/citations)")
        else:
            console.print("  [yellow]PostgreSQL not available, skipping[/]")
    except Exception as e:
        console.print(f"  [yellow]PG sync skipped: {e}[/]")

    # Step 5: RAG index (if API key available)
    console.print("\n[cyan][5/8] Building RAG index...[/]")
    if config.EMBEDDING_API_KEY:
        from . import rag
        rag_result = rag.index_all_papers()
        console.print(f"  Chunks: {rag_result['total_chunks']}, Embedded: {rag_result['embedded']}")
    else:
        console.print("  [yellow]No SCHOLAR_EMBEDDING_API_KEY, skipping[/]")

    # Step 6: Auto-notes
    console.print("\n[cyan][6/8] Generating auto-notes...[/]")
    notes_result = an.generate_all_notes(force=False)
    console.print(f"  Created: [green]{notes_result['created']}[/], Skipped: {notes_result['skipped']}")

    # Step 7: Quality scoring
    console.print("\n[cyan][7/8] Scoring quality...[/]")
    q_result = q.score_all_papers()
    console.print(f"  Scored: [green]{q_result['scored']}[/], Grades: A={q_result['grades']['A']} B={q_result['grades']['B']} C={q_result['grades']['C']}")

    # Step 8: Classification
    console.print("\n[cyan][8/8] Classifying papers...[/]")
    cl_result = cl.classify_all_papers()
    console.print(f"  Classified: [green]{cl_result['classified']}[/]")

    console.print(Panel(
        f"Papers:     {len(paper_dirs)}\n"
        f"Notes:      {notes_result['created'] + notes_result['skipped']}\n"
        f"Quality:    {q_result['scored']} scored\n"
        f"Classified: {cl_result['classified']}\n"
        f"\n[bold green]Bootstrap complete![/]",
        title="[green]Bootstrap Complete[/]",
    ))


# ===================================================================
# ingest: Incremental paper ingestion
# ===================================================================
@app.command()
def ingest(
    ulid: str = typer.Argument(help="Paper ULID to ingest"),
):
    """Ingest a single new paper: parse -> author-fix -> auto-notes -> quality -> classify -> graph-update -> rag-index."""
    from . import auto_notes as an
    from . import quality as q
    from . import classify as cl
    from . import year_fix as yf

    paper_dir = config.PAPERS_DIR / ulid
    if not paper_dir.exists():
        console.print(f"[red]Error:[/] Paper directory not found: {paper_dir}")
        raise typer.Exit(1)

    console.print(f"[cyan]Ingesting {ulid}...[/]")

    # 1. Parse
    console.print("  [1/6] Parsing...")
    try:
        data = parse_paper(paper_dir, ulid)
        dbmod.save_parsed(data)
        console.print(f"  Title: {(data.get('title') or 'N/A')[:60]}")
    except Exception as e:
        console.print(f"  [red]Parse failed: {e}[/]")
        raise typer.Exit(1)

    # 2. Author fix (only if authors missing)
    console.print("  [2/6] Checking authors...")
    json_path = config.PARSED_DIR / f"{ulid}.json"
    try:
        paper_data = json.loads(json_path.read_text(encoding="utf-8"))
        authors = paper_data.get("authors", [])
        if isinstance(authors, str):
            try:
                import ast as _ast
                authors = _ast.literal_eval(authors)
            except Exception:
                authors = []
        if not authors:
            new_authors = yf.fetch_arxiv_authors(paper_data.get("title", ""))
            if new_authors:
                paper_data["authors"] = new_authors
                json_path.write_text(
                    json.dumps(paper_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                console.print(f"  Filled {len(new_authors)} authors from arXiv")
            else:
                console.print("  [yellow]No arXiv result, authors left empty[/]")
    except Exception as e:
        console.print(f"  [yellow]Author check skipped: {e}[/]")

    # 3. Auto-notes
    console.print("  [3/6] Generating note...")
    an.generate_single_note(ulid, force=True)

    # 4. Quality
    console.print("  [4/6] Scoring quality...")
    q_result = q.score_single_paper(ulid)
    if q_result:
        console.print(f"  Grade: {q_result['grade']} ({q_result['total']}/{q_result['max_total']})")

    # 5. Classify
    console.print("  [5/6] Classifying...")
    cl_result = cl.classify_single_paper(ulid)
    if cl_result:
        console.print(f"  Domains: {', '.join(cl_result['domains'])}")

    # 6. Graph update + RAG reindex (best-effort)
    console.print("  [6/6] Updating graph + RAG...")
    try:
        from . import graph_db as gdb_mod
        gdb = gdb_mod.GraphDB()
        if gdb.available:
            # Re-build single paper's graph contributions
            json_path = config.PARSED_DIR / f"{ulid}.json"
            paper_data = json.loads(json_path.read_text(encoding="utf-8"))
            gdb_mod.upsert_paper_node(gdb, paper_data)
            gdb_mod.upsert_paper_citations(gdb, ulid, paper_data)
            gdb_mod.upsert_paper_concepts(gdb, ulid, paper_data)
            gdb.close()
            console.print("  Graph updated")
        else:
            console.print("  [yellow]Neo4j unavailable, graph not updated[/]")
    except Exception as e:
        console.print(f"  [yellow]Graph update skipped: {e}[/]")

    if config.EMBEDDING_API_KEY:
        try:
            from . import rag
            rag.index_single_paper(ulid)
            console.print("  RAG reindexed")
        except Exception as e:
            console.print(f"  [yellow]RAG reindex skipped: {e}[/]")
    else:
        console.print("  [yellow]No embedding key, RAG not updated[/]")

    console.print(f"\n[green]Ingested {ulid} successfully.[/]")


# ===================================================================
# survey: Full research survey pipeline
# ===================================================================
@app.command()
def survey(
    topic: str = typer.Argument(help="Research topic or question"),
    depth: str = typer.Option("standard", "--depth", "-d", help="standard or full"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max papers to include"),
):
    """Full research survey: RAG search -> graph query -> classify -> timeline -> structured output."""
    from . import rag
    from . import classify as cl
    import json, os

    console.print(f"[cyan]Surveying:[/] {topic}  (depth={depth})\n")

    # 1. Hybrid RAG search
    console.print("[bold]Step 1: Hybrid RAG Search[/]")
    seen_ids: list[str] = []
    rag_worked = False
    try:
        results = rag.search_rag_hybrid(topic, limit=limit)
        for r in results:
            pid = r.get("paper_id") or r.get("ulid") or ""
            if pid and pid not in seen_ids:
                seen_ids.append(pid)
        console.print(f"  Found {len(seen_ids)} unique papers via hybrid search")
        rag_worked = True
    except Exception as e:
        console.print(f"  [yellow]RAG unavailable ({e}), falling back to keyword search[/]")

    if not rag_worked:
        # File-based keyword fallback: scan parsed JSON for title/abstract matches
        try:
            kw_results: list[str] = []
            topic_lower = topic.lower()
            for ppath in config.PARSED_DIR.glob("*.json"):
                try:
                    pdata = json.loads(ppath.read_text(encoding="utf-8"))
                    title = (pdata.get("title") or "").lower()
                    abstract = (pdata.get("abstract") or "").lower()
                    if topic_lower in title or topic_lower in abstract:
                        kw_results.append(ppath.stem)
                        if len(kw_results) >= limit:
                            break
                except Exception:
                    continue
            for pid in kw_results:
                if pid and pid not in seen_ids:
                    seen_ids.append(pid)
        except Exception as e:
            console.print(f"  [yellow]Keyword fallback failed: {e}[/]")

    # 2. Graph query for related concepts
    console.print("\n[bold]Step 2: Graph Concept Query[/]")
    try:
        from . import graph_db
        gdb = graph_db.GraphDB()
        if gdb.available:
            # Direct Cypher: find concepts matching topic, then their papers
            concept_rows = gdb.run("""
                MATCH (c:Innovation)
                WHERE toLower(c.id) CONTAINS toLower($topic)
                   OR toLower(coalesce(c.line, '')) CONTAINS toLower($topic)
                WITH c LIMIT 10
                MATCH (p:Paper)-[:HAS_CONCEPT]->(c)
                RETURN DISTINCT p.ulid AS ulid
                LIMIT $max_papers
            """, topic=topic, max_papers=limit)
            concept_ids = [r.get("ulid", "") for r in concept_rows if r.get("ulid")]
            for cid in concept_ids:
                if cid and cid not in seen_ids:
                    seen_ids.append(cid)
            console.print(f"  {len(concept_ids)} papers from concept graph")
            gdb.close()
        else:
            console.print("  [yellow]Neo4j not available, skipping graph query[/]")
    except Exception as e:
        console.print(f"  [yellow]Graph unavailable ({e})[/]")

    # 3. Enrich with metadata
    console.print("\n[bold]Step 3: Enrich & Classify[/]")
    papers_data: list[dict] = []
    for pid in seen_ids[:limit]:
        ppath = config.PARSED_DIR / f"{pid}.json"
        if ppath.exists():
            try:
                pdata = json.loads(ppath.read_text(encoding="utf-8"))
                pdata["ulid"] = pid
                papers_data.append(pdata)
            except Exception:
                pass
    console.print(f"  Loaded {len(papers_data)} paper records")

    # Classify top papers
    tag_summary: dict[str, int] = {}
    for p in papers_data[:10]:
        tags = p.get("tags", {})
        for d in tags.get("domains", []):
            tag_summary[d] = tag_summary.get(d, 0) + 1

    # 4. Timeline
    console.print("\n[bold]Step 4: Timeline & Summary[/]")
    by_year: dict[int, list] = {}
    for p in papers_data:
        y = p.get("year", 0)
        if y:
            by_year.setdefault(y, []).append(p)

    # Output
    out_dir = config.OUTPUT_DIR / "drafts"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_topic = re.sub(r'[^\w\-]', '_', topic)[:50]
    out_path = out_dir / f"survey_{safe_topic}.md"

    lines = [f"# Research Survey: {topic}\n"]
    lines.append(f"**Papers found:** {len(papers_data)}  ")
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
    console.print(f"\n[green]Survey saved to {out_path}[/]")


# ===================================================================
# landscape: Field landscape analysis
# ===================================================================
@app.command()
def landscape(
    topic: str = typer.Argument(help="Research field or domain (e.g., NLP, RL, Safety)"),
):
    """Field landscape analysis: classify tags -> graph centrality -> year distribution -> key papers."""
    from . import classify as cl
    import json

    console.print(f"[cyan]Landscape Analysis:[/] {topic}\n")

    # 1. Tag matching
    console.print("[bold]Step 1: Domain Tag Matching[/]")
    all_tags = cl.list_all_tags()
    domain_papers: list[dict] = []
    matched_domain = None
    # list_all_tags() returns dict[str, int], not list[dict]
    for d_name, d_count in all_tags.get("domains", {}).items():
        if d_name.lower() == topic.lower() or topic.lower() in d_name.lower():
            matched_domain = d_name
            console.print(f"  Matched domain: {matched_domain} ({d_count} papers)")
            break

    if not matched_domain:
        # Try sub-directions
        for sd_name, sd_count in all_tags.get("sub_directions", {}).items():
            if topic.lower() in sd_name.lower():
                matched_domain = sd_name
                console.print(f"  Matched sub-direction: {matched_domain} ({sd_count} papers)")
                break

    # 2. Scan papers matching the topic
    console.print("\n[bold]Step 2: Paper Collection[/]")
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
    console.print(f"  {len(domain_papers)} papers in landscape")

    # 3. Year distribution
    console.print("\n[bold]Step 3: Year Distribution[/]")
    year_dist: dict[int, int] = {}
    for p in domain_papers:
        y = p.get("year", 0)
        if y:
            year_dist[y] = year_dist.get(y, 0) + 1
    for y in sorted(year_dist.keys()):
        bar = "█" * min(year_dist[y], 40)
        console.print(f"  {y}: {bar} {year_dist[y]}")

    # 4. Graph centrality
    console.print("\n[bold]Step 4: Key Papers (Centrality)[/]")
    try:
        from . import graph_db
        gdb = graph_db.GraphDB()
        if gdb.available:
            node_count = gdb.run("MATCH (p:Paper) RETURN count(p) AS c")[0]["c"]
            edge_count = gdb.run("MATCH ()-[c:CITES]->() RETURN count(c) AS c")[0]["c"]
            console.print(f"  Graph: {node_count} papers, {edge_count} citation edges")
            gdb.close()
        else:
            console.print("  [yellow]Neo4j not available[/]")
    except Exception as e:
        console.print(f"  [yellow]Graph unavailable ({e})[/]")

    # 5. Quality distribution
    console.print("\n[bold]Step 5: Quality Distribution[/]")
    grades: dict[str, int] = {}
    for p in domain_papers:
        g = p.get("quality", {}).get("grade", "N/A")
        grades[g] = grades.get(g, 0) + 1
    for g in ["A", "B", "C", "D", "F", "N/A"]:
        if g in grades:
            console.print(f"  {g}: {grades[g]} papers")

    # Save report
    out_dir = config.OUTPUT_DIR / "drafts"
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
        lines.append(f"{i}. **{title}** ({year}) — Grade {grade}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"\n[green]Landscape report saved to {out_path}[/]")


# ===================================================================
# Entry point
# ===================================================================
def main():
    app()
