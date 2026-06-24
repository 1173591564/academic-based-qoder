"""
Scholar Studio — Lean4 Dynamic Sync

Syncs paper data from parsed JSON → Lean4 Database.lean.
Generates theorem templates for dominance relations.

CLI: python -m scholar lean-sync [--apply] [--generate-theorems]
"""
import json
import re
from pathlib import Path
from typing import Optional

import typer

from . import config
from ._shared import app, console


# ===================================================================
# Paper ID generation: title → Lean4-safe identifier
# ===================================================================

def _title_to_lean_id(title: str) -> str:
    """Convert a paper title to a Lean4-safe identifier.
    
    "Attention Is All You Need" → "Attention_Is_All_You_Need"
    """
    if not title:
        return "Untitled"
    # Remove special characters, keep alphanumeric and spaces
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", title)
    # Title case and join with underscores
    words = cleaned.split()
    return "_".join(w.capitalize() for w in words) if words else "Untitled"


# ===================================================================
# Read papers from parsed JSON
# ===================================================================

def _load_papers(parsed_dir: Path = None) -> list[dict]:
    """Load papers from parsed JSON files.
    
    Returns: [{id, title, year, ulid, citations: [ref_key, ...]}]
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    papers = []
    for json_file in parsed_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        title = data.get("title", "")
        if not title:
            continue
        papers.append({
            "lean_id": _title_to_lean_id(title),
            "title": title,
            "year": data.get("year", 0) or 0,
            "ulid": data.get("paper_id", ""),
            "citations": data.get("citations", []),
        })
    return papers


# ===================================================================
# Generate Lean4 code
# ===================================================================

def _generate_papers_db(papers: list[dict], limit: int = 100) -> str:
    """Generate Lean4 papersDb definition."""
    lines = ["def papersDb : List Paper := ["]
    for i, p in enumerate(papers[:limit]):
        comma = "," if i < min(len(papers), limit) - 1 else ""
        lines.append(f'  {{ id := "{p["lean_id"]}", year := {p["year"]} }}{comma}')
    lines.append("]")
    return "\n".join(lines)


def _generate_citations_db(papers: list[dict], limit: int = 200) -> str:
    """Generate Lean4 citationsDb definition.
    
    Maps ref_keys to lean_ids where possible.
    """
    # Build lookup: ulid → lean_id
    ulid_to_lean = {p["ulid"]: p["lean_id"] for p in papers}
    # Also try ref_key matching (by normalized title)
    title_to_lean = {}
    for p in papers:
        norm = re.sub(r"[^a-z0-9]", "", p["title"].lower())
        if norm:
            title_to_lean[norm] = p["lean_id"]

    citations = []
    seen = set()
    for p in papers:
        source_lean = p["lean_id"]
        for ref_key in p.get("citations", [])[:20]:  # Limit per paper
            # Try to resolve ref_key to a known paper
            target_lean = None
            # Direct ulid match
            if ref_key in ulid_to_lean:
                target_lean = ulid_to_lean[ref_key]
            else:
                # Try normalized title match
                norm = re.sub(r"[^a-z0-9]", "", ref_key.replace("_", " ").lower())
                if norm in title_to_lean:
                    target_lean = title_to_lean[norm]

            if target_lean and target_lean != source_lean:
                key = (source_lean, target_lean)
                if key not in seen:
                    seen.add(key)
                    citations.append(key)

    lines = ["def citationsDb : List Citation := ["]
    for i, (src, tgt) in enumerate(citations[:limit]):
        comma = "," if i < min(len(citations), limit) - 1 else ""
        lines.append(f'  {{ source := "{src}", target := "{tgt}" }}{comma}')
    lines.append("]")
    return "\n".join(lines)


# ===================================================================
# Insert into Database.lean
# ===================================================================

def sync_database(apply: bool = False, paper_limit: int = 100, citation_limit: int = 200) -> dict:
    """
    Sync parsed paper data to Database.lean.
    
    Args:
        apply: If True, write to file. If False, return diff.
        paper_limit: Max papers to include.
        citation_limit: Max citations to include.
    
    Returns: {papers_count, citations_count, applied, diff}
    """
    lean_db_path = config.LEAN_DIR / "AiEvolution" / "Database.lean"
    if not lean_db_path.exists():
        return {"error": f"Database.lean not found at {lean_db_path}"}

    papers = _load_papers()
    if not papers:
        return {"error": "No papers found in parsed JSON"}

    papers_code = _generate_papers_db(papers, paper_limit)
    citations_code = _generate_citations_db(papers, citation_limit)

    # Read current content
    current = lean_db_path.read_text(encoding="utf-8")

    # Find insertion point: before "end AiEvolution.Database"
    insertion_marker = "end AiEvolution.Database"
    if insertion_marker not in current:
        return {"error": "Cannot find 'end AiEvolution.Database' in Database.lean"}

    # Remove existing papersDb/citationsDb if present
    current = re.sub(
        r"-- === Auto-generated.*?(?=end AiEvolution\.Database)",
        "",
        current,
        flags=re.DOTALL,
    )

    # Generate new section
    auto_section = f"""
-- ===================================================================
-- Auto-generated by scholar lean-sync (DO NOT EDIT MANUALLY)
-- Last sync: {len(papers)} papers, generated from output/parsed/
-- ===================================================================

{papers_code}

{citations_code}

"""

    # Insert before end marker
    parts = current.split(insertion_marker, 1)
    new_content = parts[0] + auto_section + insertion_marker + (parts[1] if len(parts) > 1 else "")

    if apply:
        # Backup
        backup = lean_db_path.with_suffix(".lean.bak")
        backup.write_text(current, encoding="utf-8")
        # Write new
        lean_db_path.write_text(new_content, encoding="utf-8")

    return {
        "papers_count": min(len(papers), paper_limit),
        "citations_count": min(len(_generate_citations_db(papers, citation_limit).split("\n")) - 2, citation_limit),
        "applied": apply,
        "backup": str(lean_db_path.with_suffix(".lean.bak")) if apply else None,
    }


# ===================================================================
# E3: Theorem template generator
# ===================================================================

def generate_theorem_templates() -> str:
    """
    Generate Lean4 theorem templates for dominance relations.
    
    For each replacement (A → B), checks if B dominates A on all three axes
    and generates a theorem template.
    
    Output: Lean4 code string for GeneratedTheorems.lean
    """
    lean_db_path = config.LEAN_DIR / "AiEvolution" / "Database.lean"
    if not lean_db_path.exists():
        return "-- Database.lean not found"

    content = lean_db_path.read_text(encoding="utf-8")

    # Parse innovations with their properties
    innovations = {}
    pattern = re.compile(
        r'def\s+(\w+)\s*:\s*Innovation\s*:=\s*\{[^}]*?'
        r'scalability\s*:=\s*(\d+)[^}]*?'
        r'simplicity\s*:=\s*(\d+)[^}]*?'
        r'stability\s*:=\s*(\d+)',
        re.DOTALL,
    )
    for m in pattern.finditer(content):
        innovations[m.group(1)] = {
            "scalability": int(m.group(2)),
            "simplicity": int(m.group(3)),
            "stability": int(m.group(4)),
        }

    # Parse replacements
    replacements = []
    rep_pattern = re.compile(r'\{\s*source\s*:=\s*"([^"]+)"\s*,\s*target\s*:=\s*"([^"]+)"\s*\}')
    rep_section = re.search(r"replacesDb.*?\[(.*?)\]", content, re.DOTALL)
    if rep_section:
        for m in rep_pattern.finditer(rep_section.group(1)):
            replacements.append((m.group(1), m.group(2)))

    # Generate theorems for dominance
    lines = [
        "/-",
        "  GeneratedTheorems — Auto-generated theorem templates.",
        "  These are UNVERIFIED templates. Each must be proven or disproven.",
        "  Generated by: scholar lean-sync --generate-theorems",
        "-/",
        "import AiEvolution.Basic",
        "import AiEvolution.Database",
        "",
        "open AiEvolution",
        "namespace AiEvolution.GeneratedTheorems",
        "",
        "open Database",
        "",
    ]

    count = 0
    for source, target in replacements:
        if source not in innovations or target not in innovations:
            continue
        s = innovations[source]
        t = innovations[target]

        # Check dominance: target >= source on all axes, strictly better on at least one
        dominates = (
            t["scalability"] >= s["scalability"]
            and t["simplicity"] >= s["simplicity"]
            and t["stability"] >= s["stability"]
            and (
                t["scalability"] > s["scalability"]
                or t["simplicity"] > s["simplicity"]
                or t["stability"] > s["stability"]
            )
        )

        if dominates:
            theorem_name = f"{target}_dominates_{source}"
            lines.extend([
                f"/-- Auto-generated: {target} dominates {source}. -/",
                f"theorem {theorem_name} : dominates {source} {target} := by",
                f"  unfold dominates",
                f"  refine ⟨?_, ?_, ?_, ?_⟩ <;> decide",
                "",
            ])
            count += 1

    lines.append(f"-- {count} theorem templates generated")
    lines.append("end AiEvolution.GeneratedTheorems")

    return "\n".join(lines)


# ===================================================================
# CLI commands (registered with shared app)
# ===================================================================

@app.command(name="lean-sync")
def lean_sync_cmd(
    apply: bool = typer.Option(False, "--apply", help="Write changes to Database.lean"),
    paper_limit: int = typer.Option(100, "--max-papers", help="Max papers to include"),
    citation_limit: int = typer.Option(200, "--max-citations", help="Max citations to include"),
):
    """Sync parsed papers to Lean4 Database.lean."""
    result = sync_database(apply=apply, paper_limit=paper_limit, citation_limit=citation_limit)
    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Papers: {result['papers_count']}[/]")
    console.print(f"[green]Citations: {result['citations_count']}[/]")
    if apply:
        console.print("[green]Written to Database.lean (backup saved as .bak)[/]")
    else:
        console.print("[yellow]Dry run. Use --apply to write.[/]")


@app.command(name="lean-templates")
def lean_templates_cmd(
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate Lean4 theorem templates for dominance relations."""
    code = generate_theorem_templates()
    if output:
        Path(output).write_text(code, encoding="utf-8")
        console.print(f"[green]Written to {output}[/]")
    else:
        out_path = config.LEAN_DIR / "AiEvolution" / "GeneratedTheorems.lean"
        out_path.write_text(code, encoding="utf-8")
        console.print(f"[green]Written to {out_path}[/]")


def main():
    """Standalone entry point for python -m scholar.lean_sync"""
    app()


if __name__ == "__main__":
    main()
