"""Private readiness metadata for one Scholar corpus process."""

import os
from datetime import datetime, timezone

from scholar import config, graph_mem


def _timestamp(path):
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def readiness_payload():
    """Return bounded readiness metadata without exposing corpus content."""
    corpus_version = os.getenv("SCHOLAR_CORPUS_VERSION", "").strip()
    workspace_isolation = os.getenv(
        "SCHOLAR_WORKSPACE_ISOLATION",
        "shared",
    ).strip()
    if not corpus_version:
        return 503, {"status": "unavailable", "reason": "corpus_version_missing"}
    if workspace_isolation not in {"shared", "tenant"}:
        return 503, {
            "status": "unavailable",
            "reason": "workspace_isolation_invalid",
        }
    parsed_files = [path for path in config.PARSED_DIR.glob("*.json") if path.is_file()]
    observed_paths = list(parsed_files)
    if graph_mem.GRAPH_CACHE.is_file():
        observed_paths.append(graph_mem.GRAPH_CACHE)
    synchronized_at = None
    if observed_paths:
        latest = max(path.stat().st_mtime for path in observed_paths)
        synchronized_at = datetime.fromtimestamp(latest, timezone.utc).isoformat()
    return 200, {
        "status": "ready",
        "corpus_version": corpus_version,
        "parsed_papers": len(parsed_files),
        "vector_chunks": 0,
        "graph_built_at": _timestamp(graph_mem.GRAPH_CACHE),
        "synchronized_at": synchronized_at,
        "workspace_isolation": workspace_isolation,
    }
