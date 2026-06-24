# -*- mode: python ; coding: utf-8 -*-
"""
Scholar Studio — PyInstaller spec file

Build command:
    pyinstaller scholar.spec
    # or
    python build_exe.py

Output:
    dist/scholar/scholar.exe   (--onedir mode, recommended for debugging)
    # or
    dist/scholar.exe           (--onefile mode, single executable)
"""

import os
import sys

# Collect all scholar submodules automatically
scholar_hiddenimports = [
    # --- scholar package ---
    'scholar',
    'scholar.cli',
    'scholar._shared',
    'scholar._state',
    'scholar.config',
    'scholar.db',
    'scholar.graph_db',
    'scholar.rag',
    'scholar.tex_parser',
    'scholar.auto_notes',
    'scholar.classify',
    'scholar.quality',
    'scholar.metadata_enrich',
    'scholar.year_fix',
    'scholar.cite_resolve',
    'scholar.kb_update',
    'scholar.research_loop',
    'scholar.id_resolver',
    # --- scholar.commands (CLI submodules) ---
    'scholar.commands',
    'scholar.commands.core_ops',
    'scholar.commands.paper_ops',
    'scholar.commands.metadata_ops',
    'scholar.commands.graph_ops',
    'scholar.commands.rag_ops',
    'scholar.commands.batch_ops',
    'scholar.commands.research_ops',
    'scholar.commands.execution_ops',
    'scholar.commands.external_ops',
    # --- scholar_mcp (MCP server integration) ---
    'scholar_mcp',
    'scholar_mcp.server',
    # --- third-party (often missed by PyInstaller) ---
    'psycopg2',
    'psycopg2.extras',
    'psycopg2.extensions',
    'neo4j',
    'neo4j.exceptions',
    'dotenv',
    'typer',
    'typer.core',
    'typer.main',
    'rich',
    'rich.console',
    'rich.panel',
    'rich.table',
    'rich.progress',
    'rich.traceback',
    'rich.markdown',
    'rich.syntax',
    'rich.tree',
    'rich.live',
    'fitz',           # PyMuPDF
    'ulid',           # optional but used if available
]

a = Analysis(
    ['scholar/scholar_cli.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=scholar_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',    # not used, huge dependency
        'numpy',         # only if PyMuPDF pulls it in
        'scipy',
        'pandas',
        'PIL',
        'torch',
        'tensorflow',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# --- onedir mode (recommended: faster startup, easier to debug) ---
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # True = onedir mode
    name='scholar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,            # console app, no GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # add .ico here if available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='scholar',
)

# --- Uncomment below for single-file mode (slower startup, one .exe) ---
# exe_onefile = EXE(
#     pyz,
#     a.scripts,
#     a.binaries,
#     a.datas,
#     [],
#     name='scholar',
#     debug=False,
#     bootloader_ignore_signals=False,
#     strip=False,
#     upx=True,
#     console=True,
#     icon=None,
# )
