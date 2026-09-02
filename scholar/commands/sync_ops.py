"""sync: one-command refresh of all derived indexes from parsed JSON (v0.2.0).

Single maintenance entry point replacing the manual
ingest → rag-index → graph-build → cite-resolve orchestration:

  1. relational mirror  (papers/sections/formulas/citations) — changed files only
  2. paper_vectors      (PG pgvector, L1 semantic retrieval) — md5-diff incremental
  3. passage chunks     (PG pgvector, location layer) — changed papers re-embedded
  4. graph cache        (in-memory graph, Neo4j replacement) — force rebuild

State: output/index/sync-state.json (per-file mtimes for step 1/3).
"""

import json
import time
from pathlib import Path
from typing import Optional

import typer

from .._shared import app, console, _get_db
from .. import config, graph_mem, rag, vecstore

STATE_FILE = config.OUTPUT_DIR / "index" / "sync-state.json"


def _load_state() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _changed_files(state: dict) -> tuple[list[Path], list[str]]:
    """Files new/modified since last sync, and parsed ids missing from PG."""
    changed: list[Path] = []
    seen: dict[str, float] = state.get("mtimes", {})
    all_json = sorted(config.PARSED_DIR.glob("*.json"))
    for f in all_json:
        if seen.get(str(f)) != f.stat().st_mtime:
            changed.append(f)
    return changed, [f.stem for f in all_json]


@app.command()
def sync(
    full: bool = typer.Option(False, "--full", help="全量重建（向量/图全部重算）"),
    skip_passages: bool = typer.Option(
        False, "--skip-passages", help="跳过 passage chunks 重嵌（更快）"
    ),
):
    """Rebuild all derived indexes from output/parsed JSON (single command)."""
    if not config.PARSED_DIR.exists():
        console.print(f"[red]parsed 目录不存在: {config.PARSED_DIR}[/]")
        raise typer.Exit(2)

    t0 = time.time()
    state = _load_state()
    changed, all_ids = _changed_files(state)
    if full:
        changed = sorted(config.PARSED_DIR.glob("*.json"))

    # ── 1. relational mirror (changed files only) ──────────────────────────
    ingested = 0
    db = _get_db()
    if db:
        for f in changed:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("paper_id"):
                    db.ingest_paper(data)
                    ingested += 1
            except Exception as e:
                console.print(f"[yellow]! ingest {f.stem}: {e}[/]")
        console.print(f"[green][OK][/] relational mirror: {ingested} changed")
    else:
        console.print("[yellow]! PG 不可用，跳过关系镜像（读路径不依赖它）[/]")

    # ── 2. paper_vectors (semantic L1) ─────────────────────────────────────
    vec_stats = vecstore.ensure_paper_vectors(force=full)
    console.print(
        f"[green][OK][/] paper_vectors: {vec_stats['embedded']} embedded, "
        f"{vec_stats['skipped']} skipped, {vec_stats['deleted']} deleted, "
        f"{vec_stats['errors']} errors"
    )

    # ── 3. passage chunks (changed papers) ─────────────────────────────────
    passage_done = 0
    if not skip_passages:
        if full:
            targets = all_ids
        else:
            targets = [f.stem for f in changed]
        for pid in targets:
            r = rag.index_single_paper(pid)
            if r.get("error"):
                console.print(f"[yellow]! passage {pid}: {r['error']}[/]")
            else:
                passage_done += 1
        console.print(f"[green][OK][/] passage chunks: {passage_done} re-embedded")

    # ── 4. graph cache ─────────────────────────────────────────────────────
    graph_mem.reset_cache()
    gm = graph_mem.ensure_graph(force=True)
    console.print(
        f"[green][OK][/] graph cache: {len(gm.papers)} papers, "
        f"{gm.g.number_of_edges()} cites, {len(gm.ref_resolved)} refs resolved"
    )

    # ── state ───────────────────────────────────────────────────────────────
    mtimes = state.get("mtimes", {})
    for f in sorted(config.PARSED_DIR.glob("*.json")):
        mtimes[str(f)] = f.stat().st_mtime
    _save_state(
        {
            "completedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "full": full,
            "mtimes": mtimes,
        }
    )
    console.print(
        f"\n[bold green]sync complete[/] in {time.time() - t0:.1f}s "
        f"({len(all_ids)} papers)"
    )
