"""Metadata operations: year-fix, author-fix, venue-fix, metadata-enrich."""
import json
from typing import Optional

import typer
from rich.panel import Panel

from .._shared import app, console
from .. import config


# ===================================================================
# author-fix: Complete missing authors via arXiv API
# ===================================================================
@app.command(name="author-fix")
def author_fix(
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default: dry run)"),
    limit: int = typer.Option(50, help="Max papers to query"),
):
    """Fill in missing authors using arXiv API title search."""

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
            import xml.etree.ElementTree as ET

            xml_data = config.arxiv_request(f"ti:{title[:200]}", max_results=1)

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
        title="Author Fix" + ("" if apply else " (DRY RUN -- use --apply to save)"),
    ))
    if results:
        for r in results[:10]:
            author_str = ", ".join(r['authors'][:3])
            if len(r['authors']) > 3:
                author_str += f" et al. ({len(r['authors'])})"
            console.print(f"  {r['ulid'][:16]}... -> {author_str}")


# ===================================================================
# year-fix: Complete missing years
# ===================================================================
@app.command(name="year-fix")
def year_fix(
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default: dry run)"),
):
    """Fill in missing years using Lean4 Database.lean cross-reference."""
    from .. import year_fix as yf

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
        title="Year Completion (Lean4)" + ("" if apply else " (DRY RUN -- use --apply to save)"),
    ))

    if stats['still_missing'] > 0:
        console.print(f"\n[cyan]Querying arXiv API for {stats['still_missing']} remaining papers...[/]")
        arxiv_result = yf.complete_years_arxiv(dry_run=not apply, limit=stats['still_missing'])
        console.print(
            f"  Queried: {arxiv_result['queried']}, "
            f"{'Would fill' if not apply else 'Filled'}: {arxiv_result['filled']}"
        )
        if arxiv_result['results']:
            for r in arxiv_result['results'][:10]:
                console.print(f"    {r['ulid'][:16]}... -> {r['year']}  ({r['title']})")


# ===================================================================
# metadata-enrich: Backfill arxiv_id/DOI
# ===================================================================
@app.command(name="metadata-enrich")
def metadata_enrich(
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default: dry run)"),
    limit: int = typer.Option(0, help="Max papers to process (0=all)"),
):
    """Backfill arxiv_id and DOI fields via arXiv API search."""
    from .. import metadata_enrich as me

    console.print("[cyan]Enriching metadata via arXiv API...[/]")
    stats = me.enrich_all_papers(dry_run=not apply, limit=limit)

    console.print(Panel(
        f"Total:        {stats['total']}\n"
        f"{'Would enrich' if not apply else 'Enriched'}: [green]{stats['enriched']}[/]\n"
        f"Already have: {stats['already_have']}\n"
        f"No match:     {stats['no_match']}\n"
        f"Venue filled: [green]{stats.get('venue_filled', 0)}[/]\n"
        f"Year filled:  [green]{stats.get('year_filled', 0)}[/]\n"
        f"Errors:       [red]{stats['errors']}[/]",
        title="Metadata Enrich" + ("" if apply else " (DRY RUN -- use --apply to save)"),
    ))


# ===================================================================
# venue-fix: Fill missing venue fields
# ===================================================================
@app.command(name="venue-fix")
def venue_fix(
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default: dry run)"),
):
    """Fill missing venue fields using heuristics (arxiv_id -> 'arXiv', title-only -> 'Preprint')."""
    parsed_dir = config.PARSED_DIR
    fixed_arxiv = 0
    fixed_preprint = 0
    skipped = 0

    for json_file in sorted(parsed_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
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

        if apply:
            data["venue"] = venue
            json_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    total_fixed = fixed_arxiv + fixed_preprint
    console.print(Panel(
        f"{'Would fix' if not apply else 'Fixed'}:   [green]{total_fixed}[/]\n"
        f"  arXiv:     {fixed_arxiv}\n"
        f"  Preprint:  {fixed_preprint}\n"
        f"Skipped:    {skipped} (no title, no arxiv_id)",
        title="Venue Fix" + ("" if apply else " (DRY RUN -- use --apply to save)"),
    ))
