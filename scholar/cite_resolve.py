"""
Scholar Studio — Citation Resolution Enhancement

Resolves citation references from raw ref_keys to:
  1. Internal papers (known ULIDs in output/parsed/)
  2. External papers (fetched from arXiv API, stored as lightweight nodes)

Creates Neo4j ExternalPaper nodes for unresolved references.

CLI: scholar cite-resolve [--limit N] [--dry-run]
"""
import json
import re
import ast
from pathlib import Path
from typing import Optional
from collections import Counter

from . import config


# ===================================================================
# Levenshtein distance for fuzzy title matching
# ===================================================================

def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def _similarity(s1: str, s2: str) -> float:
    """Normalized similarity (0-1) based on Levenshtein distance."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1.0 - _levenshtein(s1, s2) / max_len


def _normalize(text: str) -> str:
    """Normalize text for matching."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


# ===================================================================
# Internal matching: ref_key -> known ULID
# ===================================================================

def build_internal_index(parsed_dir: Path = None) -> dict:
    """
    Build index of all known papers: normalized_title -> {ulid, title, year}.

    Also includes ref_key patterns.
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    index = {}  # norm_title -> paper info
    ref_keys = {}  # normalized ref_key -> paper info

    for json_file in parsed_dir.glob("*.json"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        ulid = data["paper_id"]
        title = data.get("title", "")
        year = data.get("year", "")
        info = {"ulid": ulid, "title": title, "year": year}

        if title:
            index[_normalize(title)] = info

        # Also index citation ref_keys from other papers that cite this one
        # (This is useful when ref_keys match titles)
        norm = _normalize(title)
        if norm:
            ref_keys[norm] = info

    return {"titles": index, "count": len(index)}


def match_ref_to_internal(ref_key: str, internal_index: dict, threshold: float = 0.8) -> Optional[dict]:
    """
    Try to match a citation ref_key to a known internal paper.

    Strategy:
    1. Exact match (normalized)
    2. Levenshtein similarity > threshold
    3. Word overlap > 0.7
    """
    ref_norm = _normalize(ref_key.replace("_", " "))
    titles = internal_index["titles"]

    # Exact match
    if ref_norm in titles:
        return titles[ref_norm]

    # Levenshtein fuzzy match
    best_match = None
    best_sim = 0
    for norm_title, info in titles.items():
        sim = _similarity(ref_norm, norm_title)
        if sim > best_sim:
            best_sim = sim
            best_match = info

    if best_sim >= threshold:
        return best_match

    # Word overlap
    ref_words = set(ref_norm.split())
    for norm_title, info in titles.items():
        title_words = set(norm_title.split())
        if ref_words and title_words:
            overlap = len(ref_words & title_words) / max(len(ref_words), len(title_words))
            if overlap > 0.7:
                return info

    return None


# ===================================================================
# External resolution: arXiv API
# ===================================================================

def resolve_via_arxiv(ref_key: str) -> Optional[dict]:
    """
    Try to resolve a citation reference via arXiv API.

    Returns: {title, authors, year, arxiv_id} or None
    """
    try:
        import urllib.request
        import urllib.parse
        import xml.etree.ElementTree as ET

        # Clean up ref_key for search
        query = ref_key.replace("_", " ").replace("-", " ")
        encoded = urllib.parse.quote(query[:200])
        url = (
            f"http://export.arxiv.org/api/query?"
            f"search_query=ti:{encoded}&max_results=1&sortBy=relevance"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "ScholarStudio/0.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read().decode("utf-8")

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_data)
        entries = root.findall("atom:entry", ns)

        if entries:
            entry = entries[0]
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            authors = [
                a.find("atom:name", ns).text
                for a in entry.findall("atom:author", ns)
            ]
            published = entry.find("atom:published", ns).text
            arxiv_id = entry.find("atom:id", ns).text.split("/abs/")[-1]

            # Verify title similarity
            title_sim = _similarity(_normalize(ref_key), _normalize(title))
            if title_sim >= 0.7:
                return {
                    "title": title,
                    "authors": authors[:5],
                    "year": int(published[:4]) if published else None,
                    "arxiv_id": arxiv_id,
                    "similarity": title_sim,
                }
    except Exception:
        pass

    return None


# ===================================================================
# Neo4j ExternalPaper node creation
# ===================================================================

def create_external_nodes(gdb, external_papers: list[dict]) -> int:
    """
    Create ExternalPaper nodes in Neo4j for unresolved references.

    Also creates CITES edges from citing papers to external nodes.
    """
    created = 0
    for paper in external_papers:
        ref_key = paper["ref_key"]
        gdb.run("""
            MERGE (e:ExternalPaper {ref_key: $ref_key})
            SET e.title = $title,
                e.year = $year,
                e.arxiv_id = $arxiv_id,
                e.authors = $authors
        """, **{
            "ref_key": ref_key,
            "title": paper.get("title", ""),
            "year": paper.get("year"),
            "arxiv_id": paper.get("arxiv_id", ""),
            "authors": ", ".join(paper.get("authors", [])[:5]),
        })

        # Create CITES edge from citing paper
        from_ulid = paper.get("from_ulid")
        if from_ulid:
            gdb.run("""
                MATCH (from:Paper {ulid: $from_ulid})
                MATCH (to:ExternalPaper {ref_key: $ref_key})
                MERGE (from)-[:CITES {ref_key: $ref_key, resolved: false}]->(to)
            """, from_ulid=from_ulid, ref_key=ref_key)

        created += 1

    return created


# ===================================================================
# Main resolution pipeline
# ===================================================================

def resolve_citations(parsed_dir: Path = None, limit: int = 200,
                      dry_run: bool = True) -> dict:
    """
    Run the full citation resolution pipeline.

    1. Collect all unique ref_keys across all papers
    2. Try internal matching (Levenshtein)
    3. Try arXiv API for unresolved
    4. Create ExternalPaper nodes in Neo4j

    Returns statistics.
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    # Step 1: Collect all unique ref_keys with their source papers
    all_refs: dict[str, list[str]] = {}  # ref_key -> [from_ulid, ...]
    for json_file in parsed_dir.glob("*.json"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        ulid = data["paper_id"]
        citations = data.get("citations", [])
        if isinstance(citations, str):
            try:
                citations = ast.literal_eval(citations)
            except Exception:
                citations = []
        for ref in citations:
            if ref not in all_refs:
                all_refs[ref] = []
            all_refs[ref].append(ulid)

    total_refs = len(all_refs)

    # Step 2: Internal matching
    internal_index = build_internal_index(parsed_dir)
    resolved_internal = 0
    unresolved_refs = {}

    for ref_key, from_ulids in all_refs.items():
        match = match_ref_to_internal(ref_key, internal_index)
        if match:
            resolved_internal += 1
        else:
            unresolved_refs[ref_key] = from_ulids

    # Step 3: arXiv API resolution for unresolved (limited)
    resolved_arxiv = 0
    external_papers = []
    queried = 0

    for ref_key, from_ulids in unresolved_refs.items():
        if queried >= limit:
            break
        queried += 1

        result = resolve_via_arxiv(ref_key)
        if result:
            resolved_arxiv += 1
            result["ref_key"] = ref_key
            result["from_ulid"] = from_ulids[0] if from_ulids else None
            external_papers.append(result)

    # Step 4: Create external nodes in Neo4j (if not dry run)
    external_created = 0
    if not dry_run and external_papers:
        try:
            from . import graph_db as gdb_mod
            gdb = gdb_mod.GraphDB()
            if gdb.available:
                external_created = create_external_nodes(gdb, external_papers)
                gdb.close()
        except Exception:
            pass

    still_unresolved = len(unresolved_refs) - resolved_arxiv

    return {
        "total_refs": total_refs,
        "unique_refs": total_refs,
        "resolved_internal": resolved_internal,
        "resolved_arxiv": resolved_arxiv,
        "external_nodes_created": external_created,
        "still_unresolved": still_unresolved,
        "queried_arxiv": queried,
    }
