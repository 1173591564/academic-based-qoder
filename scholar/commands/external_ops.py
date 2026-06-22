"""External operations: arxiv-search, arxiv-download."""
import typer
from rich.table import Table
from rich.panel import Panel

from .._shared import app, console
from .. import config


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
        import xml.etree.ElementTree as ET
    except ImportError:
        console.print("[red]xml required (should be in stdlib)[/]")
        raise typer.Exit(1)

    console.print(f"Searching arXiv for [cyan]'{query}'[/]...")

    try:
        xml_data = config.arxiv_request(f"all:{query}", max_results=max_results)
    except Exception as e:
        console.print(f"[red]arXiv request failed:[/] {e}")
        console.print("[dim]Tip: set HTTP_PROXY env var if behind a proxy[/]")
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
# arxiv-download: Download papers from arXiv
# ===================================================================
@app.command(name="arxiv-download")
def arxiv_download(
    query: str = typer.Argument(help="arXiv search query"),
    max_results: int = typer.Option(10, "--max", help="Max papers to download"),
    pdf: bool = typer.Option(True, "--pdf/--no-pdf", help="Also download PDF (default: yes)"),
):
    """Download TeX source from arXiv into the knowledge base."""
    from .. import kb_update as kb

    console.print(f"[cyan]Downloading from arXiv:[/] {query} (max={max_results})")
    results = kb.arxiv_download(query, max_results=max_results, download_pdf=pdf)

    downloaded = [r for r in results if r.get("status") == "downloaded"]
    skipped = [r for r in results if r.get("status") == "already_exists"]
    failed = [r for r in results if "failed" in r.get("status", "")]

    console.print(Panel(
        f"Downloaded: [green]{len(downloaded)}[/]\n"
        f"Skipped:    {len(skipped)} (already exist)\n"
        f"Failed:     [red]{len(failed)}[/]",
        title="arXiv Download",
    ))
    for r in downloaded:
        console.print(f"  [green]+[/] {r['ulid'][:16]}... {r['title']}")
