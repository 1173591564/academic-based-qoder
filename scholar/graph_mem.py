"""
Scholar Studio — In-memory citation/concept graph (v0.2.0, Neo4j replacement).

Source of truth is output/parsed/*.json. The graph is rebuilt from JSON in
seconds and cached at output/index/graph.json. It holds:

  1. Paper nodes (ulid, title, year, venue) + CITES edges (resolved to ULIDs)
  2. HAS_CONCEPT edges — single-caliper: alias-table text match ∪ JSON tags
  3. Concept co-occurrence (RELATED_TO semantics, computed on demand)
  4. Innovation nodes + REPLACES edges (from Lean4 Database.lean sidecar)

Unresolved citation ref_keys are kept OUT of the DiGraph (they pollute degree
metrics); they live in `unresolved` and are surfaced by the citation queries.
"""

import json
import re
import threading
from hashlib import sha256
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from . import config

# Concept vocabulary lives in scholar/concept_vocab.py (pure data).
from .concept_vocab import (  # noqa: F401
    CONCEPT_ALIASES,
    _FALLBACK_INNOVATIONS,
    _match_concept_in_text,
    _normalize_title,
)

INDEX_DIR = config.OUTPUT_DIR / "index"
GRAPH_CACHE = INDEX_DIR / "graph.json"
REFS_SIDECAR = INDEX_DIR / "refs-resolved.json"
LEAN_FILE = config.LEAN_DIR / "AiEvolution" / "Database.lean"

_RESOLVE_MIN_SCORE = 0.3
_RELATED_MIN_WEIGHT = 2

_lock = threading.Lock()
_cache: "GraphMem | None" = None


# ── Lean4 sidecar ──────────────────────────────────────────────────────────


def _load_innovations(lean_file: Path | None = None) -> list[dict]:
    """Parse Innovation records from Database.lean; fall back to 15 seeds."""
    lean_file = lean_file or LEAN_FILE
    if not lean_file.exists():
        return list(_FALLBACK_INNOVATIONS)
    content = lean_file.read_text(encoding="utf-8")
    pattern = re.compile(
        r"def\s+\w+\s*:\s*Innovation\s*:=\s*\{"
        r'\s*id\s*:=\s*"([^"]+)"\s*,'
        r"\s*line\s*:=\s*ResearchLine\.(\w+)\s*,"
        r"\s*core\s*:=\s*(true|false)\s*,"
        r"\s*year\s*:=\s*(\d{4})\s*,"
        r"\s*properties\s*:=\s*\{"
        r"\s*scalability\s*:=\s*(\d+)\s*,"
        r"\s*simplicity\s*:=\s*(\d+)\s*,"
        r"\s*stability\s*:=\s*(\d+)\s*"
        r"\}\s*\}"
    )
    out = [
        {
            "id": m.group(1),
            "line": m.group(2),
            "year": int(m.group(4)),
            "scalability": int(m.group(5)),
            "simplicity": int(m.group(6)),
            "stability": int(m.group(7)),
        }
        for m in pattern.finditer(content)
    ]
    return out or list(_FALLBACK_INNOVATIONS)


def _load_replacements(lean_file: Path | None = None) -> list[tuple[str, str]]:
    """Parse REPLACES pairs from Database.lean replacesDb.

    File semantics: `{ source := "RNN", target := "Transformer" }` means the
    target replaces the source, so the edge is (target) -REPLACES-> (source).
    """
    lean_file = lean_file or LEAN_FILE
    if not lean_file.exists():
        return []
    content = lean_file.read_text(encoding="utf-8")
    replaces: list[tuple[str, str]] = []
    in_replaces = False
    for line in content.splitlines():
        if "replacesDb" in line:
            in_replaces = True
            continue
        if in_replaces and "]" in line:
            break
        if in_replaces:
            m = re.search(
                r'source\s*:=\s*"([^"]+)"\s*,\s*target\s*:=\s*"([^"]+)"', line
            )
            if m:
                replaces.append((m.group(2), m.group(1)))
    return replaces


# ── Reference resolution ───────────────────────────────────────────────────


def _load_refs_sidecar() -> dict:
    """Manually/CLI-curated ref_key → ULID mappings (cite-resolve output)."""
    try:
        data = json.loads(REFS_SIDECAR.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if isinstance(data.get("refs"), dict):
                return data["refs"]
            return data
        return {}
    except Exception:
        return {}


def resolve_refs(papers: dict, sidecar: dict | None = None) -> dict:
    """Resolve citation ref_keys to library ULIDs by normalized-title matching.

    Same algorithm as the retired Neo4j resolve_ref_keys: exact normalized
    title hit (score 1.0), then substring containment and >0.7 word overlap
    over candidates from a word-level inverted index. Threshold 0.3.
    Sidecar entries (curated) always win.
    """
    sidecar = sidecar or {}
    title_to_ulid = {}
    word_index: dict[str, set[str]] = {}
    for ulid, meta in papers.items():
        norm = _normalize_title(meta.get("title") or "")
        if not norm:
            continue
        title_to_ulid[norm] = ulid
        for w in norm.split():
            if len(w) > 2:
                word_index.setdefault(w, set()).add(norm)

    resolved: dict[str, str] = {}
    for ref_key, ulid in sidecar.items():
        if ulid in papers:
            resolved[ref_key] = ulid

    def _match(ref_key: str):
        ref_lower = _normalize_title(ref_key.replace("_", " "))
        matched = title_to_ulid.get(ref_lower)
        best = 1.0 if matched else 0.0
        if matched:
            return matched, best
        ref_words = set(ref_lower.split())
        candidates: set[str] = set()
        for w in ref_words:
            candidates.update(word_index.get(w, ()))
        if len(candidates) > 100:
            scored = sorted(
                ((len(ref_words & set(c.split())), c) for c in candidates),
                reverse=True,
            )
            candidates = {c for _, c in scored[:50]}
        # 排序后迭代：字符串哈希随机化会让 set 顺序跨进程变化，
        # 平分时的 tie-break 必须确定，否则重建结果不可复现。
        for norm_title in sorted(candidates):
            ulid = title_to_ulid[norm_title]
            if ref_lower in norm_title or norm_title in ref_lower:
                score = min(len(ref_lower), len(norm_title))
                if score > best:
                    best, matched = score, ulid
            overlap = len(ref_words & set(norm_title.split())) / max(
                len(ref_words), len(set(norm_title.split()))
            )
            if ref_words and overlap > 0.7 and overlap > best:
                best, matched = overlap, ulid
        return (matched, best) if best > _RESOLVE_MIN_SCORE else (None, 0.0)

    for ref_key in {rk for p in papers.values() for rk in p.get("citations", [])}:
        if ref_key in resolved:
            continue
        ulid, _score = _match(ref_key)
        if ulid:
            resolved[ref_key] = ulid
    return resolved


# ── Concept extraction (single caliper) ────────────────────────────────────


def concepts_for_paper(data: dict) -> set[str]:
    """Alias-table text match over title/abstract/headings ∪ JSON tags."""
    text_parts = [data.get("title") or "", data.get("abstract") or ""]
    text_parts.extend(s.get("heading") or "" for s in data.get("sections", []))
    full_text = " ".join(text_parts).lower()

    found = {
        cid
        for cid, aliases in CONCEPT_ALIASES.items()
        if _match_concept_in_text(full_text, cid, aliases)
    }
    tags = data.get("tags") or {}
    for key in ("methods", "sub_directions", "domains"):
        for v in tags.get(key) or []:
            if isinstance(v, str) and v.strip():
                found.add(v.strip())
    return found


# ── Build / cache ──────────────────────────────────────────────────────────


def _read_paper(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


class GraphMem:
    """Query façade over the in-memory citation/concept graph."""

    def __init__(
        self,
        papers: dict,
        cites: list,
        unresolved: dict,
        ref_resolved: dict,
        concepts: dict,
        innovations: list,
        replaces: list,
        source_files: int = 0,
        source_fingerprint: str = "",
    ):
        self.source_files = source_files
        self.source_fingerprint = source_fingerprint
        self.papers = papers  # ulid -> {title, year, venue}
        self.g = nx.DiGraph()  # real papers + resolved CITES only
        for ulid, meta in papers.items():
            self.g.add_node(ulid, **meta)
        for a, b in cites:
            self.g.add_edge(a, b)
        self.unresolved = unresolved  # ulid -> [ref_key, ...]
        self.ref_resolved = ref_resolved  # ref_key -> ulid
        self.concepts = concepts  # ulid -> set[str]
        self.innovations = innovations  # [dict] from Lean4
        self.replaces = replaces  # [(from, to)]

    # -- citation queries ---------------------------------------------------

    def forward_citations(self, ulid: str) -> dict:
        cited = [{"ulid": t, **self.papers.get(t, {})} for t in self.g.successors(ulid)]
        unresolved = sorted(set(self.unresolved.get(ulid, [])) - set(self.ref_resolved))
        return {"cited": cited, "unresolved_refs": unresolved}

    def backward_citations(self, ulid: str) -> list[dict]:
        return [
            {"ulid": s, **self.papers.get(s, {})} for s in self.g.predecessors(ulid)
        ]

    def lineage(self, a: str, b: str) -> dict:
        """Shortest citation path between two papers (direction-agnostic)."""
        if a not in self.g or b not in self.g:
            return {"path": [], "hops": -1}
        try:
            path = nx.shortest_path(self.g.to_undirected(), a, b)
        except nx.NetworkXNoPath:
            return {"path": [], "hops": -1}
        return {
            "path": [{"ulid": u, **self.papers.get(u, {})} for u in path],
            "hops": len(path) - 1,
        }

    # -- hubs / stats ---------------------------------------------------------

    def hubs(self, top_n: int = 10) -> dict:
        deg = []
        for u in self.g.nodes:
            ind, outd = self.g.in_degree(u), self.g.out_degree(u)
            bridge = (ind * outd / (ind + outd)) if (ind + outd) else 0.0
            deg.append((u, ind, outd, bridge))
        top_cited = sorted(deg, key=lambda x: x[1], reverse=True)[:top_n]
        top_bridge = sorted(deg, key=lambda x: x[3], reverse=True)[:top_n]
        fmt = lambda row: {
            "ulid": row[0],
            **self.papers.get(row[0], {}),
            "in_degree": row[1],
            "out_degree": row[2],
            "bridge_score": round(row[3], 2),
        }
        return {
            "most_cited": [fmt(r) for r in top_cited],
            "top_bridge": [fmt(r) for r in top_bridge],
        }

    def stats(self) -> dict:
        n_concept_links = sum(len(v) for v in self.concepts.values())
        return {
            "papers": len(self.papers),
            "cites_edges": self.g.number_of_edges(),
            "resolved_refs": len(self.ref_resolved),
            "unresolved_refs": sum(len(v) for v in self.unresolved.values())
            - len(self.ref_resolved),
            "concepts": len({c for v in self.concepts.values() for c in v}),
            "concept_links": n_concept_links,
            "innovations": len(self.innovations),
            "replacements": len(self.replaces),
            **self.hubs(10),
        }

    # -- concept queries ------------------------------------------------------

    def _concept_papers(self, concept: str) -> set[str]:
        c = concept.strip()
        out = {u for u, cs in self.concepts.items() if c in cs}
        if not out:
            low = c.lower()
            out = {
                u
                for u, cs in self.concepts.items()
                if any(x.lower() == low for x in cs)
            }
        return out

    def papers_by_concept(self, concept: str) -> list[dict]:
        out = []
        for u in self._concept_papers(concept):
            meta = self.papers.get(u, {})
            out.append({"ulid": u, **meta, "year": meta.get("year") or 0})
        return sorted(out, key=lambda x: x["year"], reverse=True)

    def related_concepts(self, concept: str, top_n: int = 10) -> list[dict]:
        """Concepts co-occurring with `concept` within the same papers
        (RELATED_TO semantics of the retired Neo4j layer)."""
        base = self._concept_papers(concept)
        if not base:
            return []
        low = concept.strip().lower()
        co: Counter = Counter()
        for u in base:
            for c in self.concepts.get(u, ()):  # co-occurrence inside one paper
                if c.lower() != low:
                    co[c] += 1
        return [{"id": c, "weight": w} for c, w in co.most_common(top_n)]

    def concept_timeline(self, concept: str) -> list[dict]:
        out = []
        for u in self._concept_papers(concept):
            meta = self.papers.get(u, {})
            if meta.get("year"):
                out.append({"year": meta["year"], "ulid": u, **meta})
        return sorted(out, key=lambda x: x["year"])


def _source_fingerprint(parsed_dir: Path) -> str:
    digest = sha256()
    paths = sorted(parsed_dir.glob("*.json")) if parsed_dir.exists() else []
    paths.extend(path for path in (REFS_SIDECAR, LEAN_FILE) if path.exists())
    for path in paths:
        stat = path.stat()
        digest.update(str(path.resolve()).encode("utf-8"))
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return digest.hexdigest()


def build_graph(parsed_dir: Path | None = None) -> GraphMem:
    """Build the graph from parsed JSON (source of truth)."""
    parsed_dir = Path(parsed_dir) if parsed_dir else config.PARSED_DIR
    source_files = len(list(parsed_dir.glob("*.json"))) if parsed_dir.exists() else 0
    source_fingerprint = _source_fingerprint(parsed_dir)
    papers: dict = {}
    raw_citations: dict[str, list] = {}
    for f in sorted(parsed_dir.glob("*.json")):
        data = _read_paper(f)
        if not data or not data.get("paper_id"):
            continue
        pid = data["paper_id"]
        papers[pid] = {
            "title": data.get("title") or "",
            "year": data.get("year"),
            "venue": data.get("venue") or "",
        }
        raw_citations[pid] = [
            r for r in (data.get("citations") or []) if isinstance(r, str)
        ]

    sidecar = _load_refs_sidecar()
    ref_resolved = resolve_refs(
        {
            u: {"title": m["title"], "citations": raw_citations[u]}
            for u, m in papers.items()
        },
        sidecar,
    )

    cites: list[tuple[str, str]] = []
    unresolved: dict[str, list] = {}
    for src, refs in raw_citations.items():
        unres = []
        for rk in refs:
            dst = ref_resolved.get(rk)
            if dst and dst != src:
                cites.append((src, dst))
            elif not dst:
                unres.append(rk)
        if unres:
            unresolved[src] = unres

    concepts = {}
    for f in sorted(parsed_dir.glob("*.json")):
        data = _read_paper(f)
        if data and data.get("paper_id") in papers:
            cs = concepts_for_paper(data)
            if cs:
                concepts[data["paper_id"]] = cs

    return GraphMem(
        papers,
        cites,
        unresolved,
        ref_resolved,
        concepts,
        _load_innovations(),
        _load_replacements(),
        source_files=source_files,
        source_fingerprint=source_fingerprint,
    )


def _serialize(gm: GraphMem) -> dict:
    return {
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "sourceFiles": gm.source_files,
        "sourceFingerprint": gm.source_fingerprint,
        "papers": gm.papers,
        "cites": [[a, b] for a, b in gm.g.edges],
        "unresolved": gm.unresolved,
        "ref_resolved": gm.ref_resolved,
        "concepts": {u: sorted(cs) for u, cs in gm.concepts.items()},
        "innovations": gm.innovations,
        "replaces": gm.replaces,
    }


def _deserialize(payload: dict) -> GraphMem:
    concepts = {u: set(cs) for u, cs in (payload.get("concepts") or {}).items()}
    gm = GraphMem(
        payload.get("papers") or {},
        [tuple(e) for e in (payload.get("cites") or [])],
        payload.get("unresolved") or {},
        payload.get("ref_resolved") or {},
        concepts,
        payload.get("innovations") or [],
        [tuple(r) for r in (payload.get("replaces") or [])],
    )
    gm.source_files = int(payload.get("sourceFiles") or 0)
    gm.source_fingerprint = str(payload.get("sourceFingerprint") or "")
    return gm


def ensure_graph(force: bool = False) -> GraphMem:
    """Load cached graph; rebuild when source files change or force=True."""
    global _cache
    n = len(list(config.PARSED_DIR.glob("*.json"))) if config.PARSED_DIR.exists() else 0
    fingerprint = _source_fingerprint(config.PARSED_DIR)
    if (
        _cache is not None
        and not force
        and _cache.source_files == n
        and _cache.source_fingerprint == fingerprint
    ):
        return _cache
    with _lock:
        if (
            _cache is not None
            and not force
            and _cache.source_files == n
            and _cache.source_fingerprint == fingerprint
        ):
            return _cache
        if not force and GRAPH_CACHE.exists():
            try:
                payload = json.loads(GRAPH_CACHE.read_text(encoding="utf-8"))
                if (
                    payload.get("sourceFiles") == n
                    and payload.get("sourceFingerprint") == fingerprint
                    and payload.get("papers")
                ):
                    _cache = _deserialize(payload)
                    return _cache
            except Exception:
                pass
        gm = build_graph()
        try:
            INDEX_DIR.mkdir(parents=True, exist_ok=True)
            GRAPH_CACHE.write_text(
                json.dumps(_serialize(gm), ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass
        _cache = gm
        return gm


def refresh() -> GraphMem:
    """Force rebuild (maintenance entry: after ingest / cite-resolve)."""
    reset_cache()
    return ensure_graph(force=True)


def reset_cache() -> None:
    """Drop the process-local singleton (tests / after sync)."""
    global _cache
    with _lock:
        _cache = None
