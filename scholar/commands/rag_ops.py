"""RAG operations: rag-index, rag-search."""
import typer
from rich.table import Table
from rich.panel import Panel

from .._shared import app, console
from .. import config


# ===================================================================
# rag-index: Build RAG vector index
# ===================================================================
@app.command(name="rag-index")
def rag_index():
    """Build RAG vector index (requires SCHOLAR_EMBEDDING_API_KEY)."""
    from .. import rag

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
    from .. import rag

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
