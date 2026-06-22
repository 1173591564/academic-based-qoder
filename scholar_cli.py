"""
Scholar Studio — Standalone CLI entry point for PyInstaller.

Usage (after building):
    scholar.exe <command>
    scholar.exe stats
    scholar.exe search "transformer"

When running as a PyInstaller bundle, SCHOLAR_HOME defaults to
~/.scholar-studio/. Override with SCHOLAR_HOME environment variable.
"""
from scholar.cli import main

main()
