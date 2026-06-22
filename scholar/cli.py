"""
Scholar Studio — CLI Entry Point

Shared objects (app, console, parser, _get_db) live in _shared.py.
Command implementations live in commands/*.py.

Usage: python -m scholar <command> [options]
"""
from ._shared import app  # noqa: F401

# Import command modules — each registers @app.command() decorators
from .commands import core_ops       # noqa: F401  init, scan, info, search, list-papers, stats
from .commands import paper_ops      # noqa: F401  parse, parse-all, ingest, export-bib
from .commands import metadata_ops   # noqa: F401  year-fix, author-fix, venue-fix, metadata-enrich
from .commands import graph_ops      # noqa: F401  graph-build, graph-stats, graph-query, cite-network, cite-resolve
from .commands import rag_ops        # noqa: F401  rag-index, rag-search
from .commands import batch_ops      # noqa: F401  auto-notes, quality-score, classify, bootstrap, batch-ingest, kb-update
from .commands import research_ops   # noqa: F401  interests, research-sync, survey, landscape
from .commands import execution_ops  # noqa: F401  compile-paper, exp-*, dataset-download
from .commands import external_ops   # noqa: F401  arxiv-search, arxiv-download


def main():
    app()
