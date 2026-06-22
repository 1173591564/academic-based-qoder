"""
Scholar Studio — Shared CLI Objects

Defines the Typer app, console, parser, and database helper used by both
cli.py (entry point) and commands/*.py (command implementations).

This module has NO circular imports — it only depends on scholar.tex_parser
and scholar.db, which are independent domain modules.
"""
from typing import Optional

import typer
from rich.console import Console

from .tex_parser import TeXParser
from . import db as dbmod

# ===================================================================
# Shared objects
# ===================================================================

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
