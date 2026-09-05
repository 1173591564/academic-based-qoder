"""
Scholar Studio — Auto Notes Generator

Generates structured Markdown reading notes from parsed paper JSON.
Output: output/notes/<ULID>.md

Each note includes:
  1. One-sentence summary
  2. Core contributions (extracted from introduction/conclusion)
  3. Method overview
  4. Key formulas (top 5)
  5. Section structure tree
  6. Citation summary
"""

import json
import re
import ast
from pathlib import Path
from typing import Optional

from . import config
from . import db as dbmod


# ===================================================================
# Single paper note generation
# ===================================================================


def generate_note(data: dict) -> str:
    """
    Generate a structured Markdown reading note from parsed paper data.

    Args:
        data: Parsed paper JSON dict with keys:
              paper_id, title, authors, year, venue, abstract,
              sections, formulas, citations

    Returns:
        Markdown string
    """
    pid = data.get("paper_id", "unknown")
    title = data.get("title", "Untitled")
    authors = data.get("authors", [])
    year = data.get("year", "")
    venue = data.get("venue", "")
    abstract = data.get("abstract", "")
    sections = data.get("sections", [])
    formulas = data.get("formulas", [])
    citations = data.get("citations", [])

    # Handle authors that might be stored as string repr of list
    if isinstance(authors, str):
        try:
            authors = ast.literal_eval(authors)
        except Exception:
            authors = [authors]

    lines = []

    # Header
    lines.append(f"# {title}")
    lines.append("")
    meta_parts = []
    if authors:
        author_str = ", ".join(authors[:5])
        if len(authors) > 5:
            author_str += f" et al. ({len(authors)})"
        meta_parts.append(f"**Authors:** {author_str}")
    if year:
        meta_parts.append(f"**Year:** {year}")
    if venue:
        meta_parts.append(f"**Venue:** {venue}")
    meta_parts.append(f"**ULID:** `{pid}`")
    lines.append("  \n".join(meta_parts))
    lines.append("")

    # One-sentence summary (first sentence of abstract)
    lines.append("## Summary")
    if abstract:
        summary = _extract_first_sentence(abstract)
        lines.append(f"> {summary}")
    else:
        lines.append("> *No abstract available.*")
    lines.append("")

    # Core contributions (from introduction or abstract)
    lines.append("## Core Contributions")
    contributions = _extract_contributions(data)
    if contributions:
        for i, c in enumerate(contributions, 1):
            lines.append(f"{i}. {c}")
    else:
        lines.append("*Could not extract contributions automatically.*")
    lines.append("")

    # Method overview
    lines.append("## Method Overview")
    method = _extract_method_overview(data)
    lines.append(method if method else "*No method section found.*")
    lines.append("")

    # Key formulas (top 5)
    if formulas:
        lines.append("## Key Formulas")
        # Handle formulas stored as string repr of list
        if isinstance(formulas, str):
            try:
                formulas = ast.literal_eval(formulas)
            except Exception:
                formulas = []
        top_formulas = _select_top_formulas(formulas, n=5)
        for i, f in enumerate(top_formulas, 1):
            label = f.get("label", "")
            latex = f.get("latex", "").replace("\n", " ")[:200]
            env = f.get("env_type", "equation")
            if label:
                lines.append(f"{i}. **{label}** ({env}):")
            else:
                lines.append(f"{i}. ({env}):")
            lines.append(f"   $$ {latex} $$")
            lines.append("")

    # Section structure
    lines.append("## Section Structure")
    if sections:
        if isinstance(sections, str):
            try:
                sections = ast.literal_eval(sections)
            except Exception:
                sections = []
        for i, s in enumerate(sections):
            level = s.get("level", 1)
            heading = s.get("heading", "(untitled)")
            content_len = len(s.get("content", ""))
            indent = "  " * (level - 1)
            lines.append(f"- {indent}{heading} ({content_len} chars)")
    else:
        lines.append("*No sections parsed.*")
    lines.append("")

    # Citation summary
    lines.append("## Citations")
    if isinstance(citations, str):
        try:
            citations = ast.literal_eval(citations)
        except Exception:
            citations = []
    lines.append(f"Total references: **{len(citations)}**")
    if citations:
        lines.append("")
        for c in citations[:10]:
            lines.append(f"- {c}")
        if len(citations) > 10:
            lines.append(f"- ... and {len(citations) - 10} more")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Auto-generated from Scholar source data for `{pid}`.*")

    return "\n".join(lines)


# ===================================================================
# Extraction helpers
# ===================================================================


def _extract_first_sentence(text: str) -> str:
    """Extract the first meaningful sentence from text."""
    if not text:
        return ""
    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    for s in sentences:
        s = s.strip()
        if len(s) > 30:  # Skip very short fragments
            return s
    return text[:200]


def _extract_contributions(data: dict) -> list[str]:
    """
    Extract contribution-like statements from introduction/conclusion.

    Looks for patterns like:
    - "we propose", "we introduce", "we present", "our contribution"
    - "the main contribution", "we show that", "we demonstrate"
    """
    sections = data.get("sections", [])
    if isinstance(sections, str):
        try:
            sections = ast.literal_eval(sections)
        except Exception:
            sections = []

    # Find introduction and conclusion sections
    target_sections = []
    for s in sections:
        heading = (s.get("heading") or "").lower()
        if any(
            kw in heading
            for kw in ["introduction", "conclusion", "summary", "contribution"]
        ):
            target_sections.append(s.get("content", ""))

    # Fallback to abstract
    if not target_sections and data.get("abstract"):
        target_sections.append(data["abstract"])

    # Extract contribution patterns
    contribution_patterns = [
        r"we\s+(?:propose|introduce|present|develop|design|show|demonstrate)\s+[^.]+",
        r"(?:our|the\s+main|a\s+key)\s+contribution[^.]*",
        r"this\s+(?:paper|work|study)\s+(?:proposes|introduces|presents|develops|shows)[^.]+",
    ]

    contributions = []
    for text in target_sections:
        for pattern in contribution_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for m in matches:
                sentence = m.group(0).strip()
                if len(sentence) > 20 and sentence not in contributions:
                    contributions.append(sentence[:200])

    return contributions[:5]


def _extract_method_overview(data: dict) -> Optional[str]:
    """
    Extract a method overview from the paper.

    Strategy: Find the 'Method' or 'Approach' section and return first ~500 chars.
    """
    sections = data.get("sections", [])
    if isinstance(sections, str):
        try:
            sections = ast.literal_eval(sections)
        except Exception:
            sections = []

    method_keywords = [
        "method",
        "approach",
        "model",
        "architecture",
        "framework",
        "proposed",
        "technique",
        "algorithm",
    ]

    for s in sections:
        heading = (s.get("heading") or "").lower()
        if any(kw in heading for kw in method_keywords):
            content = s.get("content", "")
            if len(content) > 50:
                # Return first 500 chars as overview
                return content[:500] + ("..." if len(content) > 500 else "")

    return None


def _select_top_formulas(formulas: list[dict], n: int = 5) -> list[dict]:
    """
    Select the most important formulas.

    Heuristics:
    1. Formulas with labels are more important
    2. Longer formulas (more complex) are prioritized
    3. Equation environment > inline math
    """
    if not formulas:
        return []

    def score(f):
        s = 0
        if f.get("label"):
            s += 10
        latex = f.get("latex", "")
        s += min(len(latex) / 20, 5)  # Complexity bonus
        if f.get("env_type") in ("equation", "align", "gather"):
            s += 3
        return s

    sorted_formulas = sorted(formulas, key=score, reverse=True)
    return sorted_formulas[:n]


# ===================================================================
# Batch processing
# ===================================================================


def generate_all_notes(
    parsed_dir: Path = None, notes_dir: Path = None, force: bool = False
) -> dict:
    """
    Generate auto-notes for all parsed papers.

    Args:
        parsed_dir: Directory with parsed JSON files
        notes_dir: Output directory for notes
        force: If True, overwrite existing notes

    Returns:
        Statistics dict
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR
    if notes_dir is None:
        notes_dir = config.NOTES_DIR

    notes_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0
    failed = 0

    for json_file in sorted(parsed_dir.glob("*.json")):
        ulid = json_file.stem
        note_path = notes_dir / f"{ulid}.md"

        if note_path.exists() and not force:
            skipped += 1
            continue

        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            note = generate_note(data)
            note_path.write_text(note, encoding="utf-8")
            created += 1
        except Exception:
            failed += 1

    return {
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "total": created + skipped + failed,
    }


def generate_single_note(ulid: str, force: bool = False) -> dict:
    """
    Generate auto-note for a single paper.

    Returns:
        {status: str, path: str, content: str}
    """
    data = dbmod.load_parsed(ulid)
    if data is None:
        return {"status": "not_found", "path": "", "content": ""}

    note_path = config.NOTES_DIR / f"{ulid}.md"
    if note_path.exists() and not force:
        return {
            "status": "exists",
            "path": str(note_path),
            "content": note_path.read_text(encoding="utf-8"),
        }

    config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    note = generate_note(data)
    note_path.write_text(note, encoding="utf-8")
    return {"status": "created", "path": str(note_path), "content": note}
