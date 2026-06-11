"""
Scholar Studio — Year Completion Script

Cross-references parsed papers with Lean4 Database.lean to fill in missing years.
Also attempts to extract year from arXiv IDs, venue patterns, and content heuristics.
"""
import re
import json
from pathlib import Path
from typing import Optional

from . import config


# ===================================================================
# Lean4 Database.lean parser
# ===================================================================

def parse_lean_papers(lean_file: Path = None) -> dict:
    """
    Parse paper definitions from LEAN/AiEvolution/Database.lean.

    Returns: {paper_id: year} mapping
    e.g., {"Attention_Is_All_You_Need": 2017, "BERT": 2018, ...}
    """
    if lean_file is None:
        lean_file = config.LEAN_DIR / "AiEvolution" / "Database.lean"

    if not lean_file.exists():
        return {}

    content = lean_file.read_text(encoding="utf-8")
    papers = {}

    # Match: def p_XXX : Paper := { id := "XXX", year := YYYY }
    pattern = re.compile(
        r'def\s+p_\w+\s*:\s*Paper\s*:=\s*\{\s*id\s*:=\s*"([^"]+)"\s*,\s*year\s*:=\s*(\d{4})\s*\}'
    )
    for m in pattern.finditer(content):
        paper_id = m.group(1)
        year = int(m.group(2))
        papers[paper_id] = year

    return papers


def parse_lean_innovations(lean_file: Path = None) -> dict:
    """
    Parse innovation definitions from Database.lean.

    Returns: {innovation_id: {year, line, scalability, simplicity, stability}}
    """
    if lean_file is None:
        lean_file = config.LEAN_DIR / "AiEvolution" / "Database.lean"

    if not lean_file.exists():
        return {}

    content = lean_file.read_text(encoding="utf-8")
    innovations = {}

    pattern = re.compile(
        r'def\s+(\w+)\s*:\s*Innovation\s*:=\s*\{'
        r'\s*id\s*:=\s*"([^"]+)"\s*,'
        r'\s*line\s*:=\s*ResearchLine\.(\w+)\s*,'
        r'\s*core\s*:=\s*(true|false)\s*,'
        r'\s*year\s*:=\s*(\d{4})\s*,'
        r'\s*properties\s*:=\s*\{'
        r'\s*scalability\s*:=\s*(\d+)\s*,'
        r'\s*simplicity\s*:=\s*(\d+)\s*,'
        r'\s*stability\s*:=\s*(\d+)\s*'
        r'\}\s*\}'
    )
    for m in pattern.finditer(content):
        innovations[m.group(2)] = {
            "year": int(m.group(5)),
            "line": m.group(3),
            "core": m.group(4) == "true",
            "scalability": int(m.group(6)),
            "simplicity": int(m.group(7)),
            "stability": int(m.group(8)),
        }

    return innovations


# ===================================================================
# Title-based matching: Lean4 paper_id ↔ ULID folder
# ===================================================================

def normalize_title(title: str) -> str:
    """Normalize a title for fuzzy matching."""
    if not title:
        return ""
    title = title.lower()
    # Remove special chars and extra whitespace
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def build_title_to_ulid_map(parsed_dir: Path = None) -> dict:
    """Build a mapping from normalized title → ULID."""
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    title_map = {}
    for json_file in parsed_dir.glob("*.json"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        title = data.get("title", "")
        if title:
            norm = normalize_title(title)
            title_map[norm] = data["paper_id"]

    return title_map


def match_lean_to_ulid(lean_papers: dict, title_map: dict) -> dict:
    """
    Match Lean4 paper IDs to ULIDs via title matching.

    Lean4 uses IDs like "Attention_Is_All_You_Need".
    We convert this to "attention is all you need" and match against parsed titles.
    """
    matches = {}

    for lean_id, year in lean_papers.items():
        # Convert Lean ID to approximate title
        approx_title = normalize_title(lean_id.replace("_", " "))

        # Exact match
        if approx_title in title_map:
            matches[lean_id] = title_map[approx_title]
            continue

        # Fuzzy match: check if approx_title is contained in any parsed title
        best_match = None
        best_score = 0
        for norm_title, ulid in title_map.items():
            # Check containment
            if approx_title in norm_title or norm_title in approx_title:
                score = min(len(approx_title), len(norm_title))
                if score > best_score:
                    best_score = score
                    best_match = ulid
            # Check word overlap
            words_a = set(approx_title.split())
            words_b = set(norm_title.split())
            if words_a and words_b:
                overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
                if overlap > 0.7 and overlap > best_score:
                    best_score = overlap
                    best_match = ulid

        if best_match and best_score > 0.5:
            matches[lean_id] = best_match

    return matches


# ===================================================================
# Year completion: update parsed JSON files
# ===================================================================

def complete_years(parsed_dir: Path = None, dry_run: bool = True) -> dict:
    """
    Fill in missing years for parsed papers.

    Strategy:
    1. Match Lean4 Database.lean paper IDs → ULIDs via title matching
    2. For unmatched papers, try to extract year from content heuristics

    Args:
        dry_run: If True, only report what would change without modifying files

    Returns:
        Statistics about the completion
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    lean_papers = parse_lean_papers()
    title_map = build_title_to_ulid_map(parsed_dir)
    lean_to_ulid = match_lean_to_ulid(lean_papers, title_map)

    stats = {
        "lean_papers": len(lean_papers),
        "parsed_papers": len(title_map),
        "matched": len(lean_to_ulid),
        "filled": 0,
        "already_had_year": 0,
        "still_missing": 0,
    }

    updates = {}  # ulid → new_year

    # Phase 1: Fill from Lean4 matches
    for lean_id, ulid in lean_to_ulid.items():
        json_file = parsed_dir / f"{ulid}.json"
        if not json_file.exists():
            continue
        data = json.loads(json_file.read_text(encoding="utf-8"))
        if data.get("year"):
            stats["already_had_year"] += 1
        else:
            new_year = lean_papers[lean_id]
            updates[ulid] = new_year
            stats["filled"] += 1

    # Phase 2: For remaining papers without year, try content heuristics
    for json_file in parsed_dir.glob("*.json"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        if data.get("year"):
            continue
        ulid = data["paper_id"]
        if ulid in updates:
            continue

        # Try to infer year from citations (most recent cited year + 1)
        # or from venue patterns in content
        year = _infer_year_from_content(data)
        if year:
            updates[ulid] = year
            stats["filled"] += 1
        else:
            stats["still_missing"] += 1

    # Apply updates
    if not dry_run:
        for ulid, year in updates.items():
            json_file = parsed_dir / f"{ulid}.json"
            data = json.loads(json_file.read_text(encoding="utf-8"))
            data["year"] = year
            json_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    return stats, updates


def fetch_arxiv_year(title: str) -> Optional[int]:
    """Try to fetch publication year from arXiv API by title search."""
    try:
        import xml.etree.ElementTree as ET
        from . import config as _cfg

        xml_data = _cfg.arxiv_request(f"ti:{title[:200]}", max_results=1)

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_data)
        entries = root.findall("atom:entry", ns)
        if entries:
            published = entries[0].find("atom:published", ns).text
            if published:
                return int(published[:4])
    except Exception:
        pass
    return None


def complete_years_arxiv(parsed_dir: Path = None, limit: int = 50, dry_run: bool = True) -> dict:
    """
    For papers still missing year, query arXiv API.

    Args:
        limit: max papers to query (to avoid rate limiting)
        dry_run: if True, only report without writing

    Returns:
        {filled: int, results: list}
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    filled = 0
    results = []
    queried = 0

    for json_file in sorted(parsed_dir.glob("*.json")):
        if queried >= limit:
            break
        data = json.loads(json_file.read_text(encoding="utf-8"))
        if data.get("year"):
            continue

        title = data.get("title", "")
        if not title:
            continue

        queried += 1
        year = fetch_arxiv_year(title)
        if year:
            results.append({"ulid": data["paper_id"], "title": title[:50], "year": year})
            filled += 1
            if not dry_run:
                data["year"] = year
                json_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

    return {"queried": queried, "filled": filled, "results": results}


def _infer_year_from_content(data: dict) -> Optional[int]:
    """Try to infer publication year from paper content."""
    # Collect all years mentioned in the paper
    parts = []
    abstract = data.get("abstract")
    if abstract:
        parts.append(abstract)
    for s in data.get("sections", [])[:3]:
        content = s.get("content", "")
        if content:
            parts.append(content)
    all_text = " ".join(parts)

    # Look for patterns like "In 2023, ..." or "proposed in 2022"
    year_mentions = re.findall(r"\b(20[12]\d)\b", all_text)
    if year_mentions:
        from collections import Counter
        year_counts = Counter(year_mentions)
        # The most mentioned recent year is likely the publication year
        # Filter to years >= 2017 (AI boom era)
        recent = {y: c for y, c in year_counts.items() if int(y) >= 2017}
        if recent:
            return int(max(recent, key=recent.get))

    return None


# ===================================================================
# Author completion: arXiv API fallback for missing authors
# ===================================================================

def fetch_arxiv_authors(title: str) -> Optional[list]:
    """Try to fetch author list from arXiv API by title search."""
    try:
        import xml.etree.ElementTree as ET
        from . import config as _cfg

        xml_data = _cfg.arxiv_request(f"ti:{title[:200]}", max_results=1)

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_data)
        entries = root.findall("atom:entry", ns)
        if entries:
            authors = []
            for a in entries[0].findall("atom:author", ns):
                name_el = a.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text.strip())
            return authors if authors else None
    except Exception:
        pass
    return None


def complete_authors_arxiv(parsed_dir: Path = None, limit: int = 50, dry_run: bool = True) -> dict:
    """
    Fill in missing authors via arXiv API.

    Args:
        parsed_dir: Directory containing parsed paper JSONs
        limit: Maximum number of papers to query
        dry_run: If True, report what would change without modifying files

    Returns:
        Dict with filled/skipped/queried counts
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    import time
    stats = {"queried": 0, "filled": 0, "skipped_no_result": 0, "skipped_have_authors": 0, "errors": 0}

    for json_file in sorted(parsed_dir.glob("*.json")):
        if stats["queried"] >= limit:
            break
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        authors = data.get("authors", [])
        # Normalize: if it's a string repr, leave it alone
        if isinstance(authors, str):
            try:
                import ast
                authors = ast.literal_eval(authors)
            except Exception:
                authors = []

        if authors and len(authors) > 0:
            stats["skipped_have_authors"] += 1
            continue

        title = data.get("title", "")
        if not title:
            continue

        stats["queried"] += 1
        new_authors = fetch_arxiv_authors(title)
        if new_authors:
            data["authors"] = new_authors
            if not dry_run:
                json_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            stats["filled"] += 1
        else:
            stats["skipped_no_result"] += 1

        # Be polite to arXiv API
        time.sleep(3.0)

    return stats
