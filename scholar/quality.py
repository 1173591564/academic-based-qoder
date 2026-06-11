"""
Scholar Studio — Quality Scoring Pipeline

Evaluates parsed papers across 7 dimensions:
  1. Metadata completeness (title, authors, year, venue, abstract)
  2. Structure quality (section count, depth, organization)
  3. Citation density (reference count, diversity)
  4. Reproducibility signals (code links, dataset mentions, hyperparameters)
  5. Problem definition clarity (problem statement extraction)
  6. Innovation signals (novelty claims, comparison to prior work)
  7. Experimental rigor (benchmark mentions, ablation, statistical analysis)

Output: paper JSON `quality` field + output/notes/<ULID>-quality.json
"""
import json
import re
import ast
from pathlib import Path
from typing import Optional

from . import config


# ===================================================================
# Dimension scorers (each returns 0-10)
# ===================================================================

def _score_metadata(data: dict) -> dict:
    """Score metadata completeness."""
    score = 0
    details = []
    if data.get("title"):
        score += 2
    else:
        details.append("missing title")
    authors = data.get("authors", [])
    if isinstance(authors, str):
        try:
            authors = ast.literal_eval(authors)
        except Exception:
            authors = [authors]
    if authors and len(authors) > 0:
        score += 2
    else:
        details.append("missing authors")
    if data.get("year"):
        score += 2
    else:
        details.append("missing year")
    if data.get("venue"):
        score += 2
    else:
        details.append("missing venue")
    if data.get("abstract") and len(data.get("abstract", "")) > 50:
        score += 2
    else:
        details.append("missing/short abstract")
    return {"score": score, "max": 10, "details": details}


def _score_structure(data: dict) -> dict:
    """Score paper structure quality."""
    sections = data.get("sections", [])
    if isinstance(sections, str):
        try:
            sections = ast.literal_eval(sections)
        except Exception:
            sections = []

    score = 0
    details = []

    n = len(sections)
    if n >= 5:
        score += 4
    elif n >= 3:
        score += 3
    elif n >= 1:
        score += 2
    else:
        details.append("no sections")

    # Check for key sections
    headings_lower = [s.get("heading", "").lower() for s in sections]
    key_sections = ["introduction", "method", "experiment", "conclusion"]
    found = sum(1 for k in key_sections if any(k in h for h in headings_lower))
    score += found  # up to 4 points

    # Depth diversity
    levels = set(s.get("level", 1) for s in sections)
    if len(levels) >= 2:
        score += 2
    elif len(levels) == 1 and n > 3:
        score += 1

    return {"score": min(score, 10), "max": 10, "details": details}


def _score_citations(data: dict) -> dict:
    """Score citation density and diversity."""
    citations = data.get("citations", [])
    if isinstance(citations, str):
        try:
            citations = ast.literal_eval(citations)
        except Exception:
            citations = []

    n = len(citations)
    score = 0
    details = []

    if n >= 30:
        score = 10
    elif n >= 20:
        score = 8
    elif n >= 10:
        score = 6
    elif n >= 5:
        score = 4
    elif n >= 1:
        score = 2
    else:
        details.append("no citations")

    return {"score": score, "max": 10, "details": details}


def _score_reproducibility(data: dict) -> dict:
    """Score reproducibility signals."""
    sections = data.get("sections", [])
    if isinstance(sections, str):
        try:
            sections = ast.literal_eval(sections)
        except Exception:
            sections = []

    all_text = " ".join(s.get("content", "") for s in sections).lower()
    score = 0
    signals = []

    # Code/GitHub mentions
    if re.search(r'github\.com|gitlab\.com|bitbucket\.org|code\s+available|open.?source', all_text):
        score += 3
        signals.append("code_link")

    # Dataset mentions
    if re.search(r'dataset|benchmark|corpus|test\s+set|validation\s+set', all_text):
        score += 2
        signals.append("dataset")

    # Hyperparameters
    if re.search(r'learning\s+rate|batch\s+size|epoch|hyperparameter|lambda|dropout', all_text):
        score += 2
        signals.append("hyperparameters")

    # Reproduction details
    if re.search(r'reproduc|implementation\s+detail|training\s+detail|experimental\s+setup', all_text):
        score += 2
        signals.append("repro_details")

    # Pre-trained model / checkpoint
    if re.search(r'checkpoint|pre.?trained|model\s+weight', all_text):
        score += 1
        signals.append("checkpoints")

    return {"score": min(score, 10), "max": 10, "details": signals}


def _score_problem_definition(data: dict) -> dict:
    """Score problem definition clarity."""
    sections = data.get("sections", [])
    if isinstance(sections, str):
        try:
            sections = ast.literal_eval(sections)
        except Exception:
            sections = []
    abstract = data.get("abstract", "")

    # Check introduction and abstract for problem statements
    intro_text = ""
    for s in sections:
        h = (s.get("heading") or "").lower()
        if "introduction" in h or "problem" in h or "motivation" in h:
            intro_text += s.get("content", "") + " "

    check_text = (abstract + " " + intro_text).lower()
    score = 0
    details = []

    # Problem framing keywords
    if re.search(r'we\s+(?:address|tackle|study|investigate|focus\s+on)', check_text):
        score += 3
        details.append("explicit_problem_statement")

    if re.search(r'challenge|problem|difficulty|limitation|gap|issue', check_text):
        score += 2
        details.append("challenges_mentioned")

    if re.search(r'motivat|why|important|significance|impact', check_text):
        score += 2
        details.append("motivation")

    if re.search(r'goal|objective|aim|target|purpose', check_text):
        score += 2
        details.append("goals")

    # Task definition
    if re.search(r'task|problem\s+(?:of|setting|formulation)', check_text):
        score += 1
        details.append("task_defined")

    return {"score": min(score, 10), "max": 10, "details": details}


def _score_innovation(data: dict) -> dict:
    """Score innovation signals."""
    sections = data.get("sections", [])
    if isinstance(sections, str):
        try:
            sections = ast.literal_eval(sections)
        except Exception:
            sections = []

    all_text = " ".join(s.get("content", "") for s in sections).lower()
    abstract = (data.get("abstract") or "").lower()
    full = abstract + " " + all_text

    score = 0
    details = []

    # Novelty claims
    if re.search(r'novel|new\s+approach|first\s+time|state.of.the.art|outperform|superior', full):
        score += 3
        details.append("novelty_claims")

    # Comparison to prior work
    if re.search(r'compared?\s+(?:to|with)|versus|baseline|prior\s+(?:work|art)|existing\s+method', full):
        score += 3
        details.append("prior_work_comparison")

    # Contribution statements
    if re.search(r'contribution|we\s+propose|we\s+introduce|our\s+method|our\s+approach', full):
        score += 2
        details.append("contribution_statements")

    # Ablation study
    if re.search(r'ablation|component\s+analysis|effect\s+of', full):
        score += 2
        details.append("ablation")

    return {"score": min(score, 10), "max": 10, "details": details}


def _score_experiments(data: dict) -> dict:
    """Score experimental rigor."""
    sections = data.get("sections", [])
    if isinstance(sections, str):
        try:
            sections = ast.literal_eval(sections)
        except Exception:
            sections = []

    # Find experiment sections
    exp_text = ""
    for s in sections:
        h = (s.get("heading") or "").lower()
        if any(kw in h for kw in ["experiment", "result", "evaluation", "analysis"]):
            exp_text += s.get("content", "") + " "

    full = exp_text.lower()
    score = 0
    details = []

    # Benchmarks
    if re.search(r'benchmark|standard\s+dataset|evaluation\s+protocol', full):
        score += 2
        details.append("benchmarks")

    # Metrics
    if re.search(r'accuracy|precision|recall|f1|bleu|rouge|perplexity|loss|metric|measure', full):
        score += 2
        details.append("metrics")

    # Statistical analysis
    if re.search(r'significant|p.?value|confidence|standard\s+deviation|variance|mean|average', full):
        score += 2
        details.append("statistical_analysis")

    # Multiple baselines
    if re.search(r'baseline|comparison|prior\s+work|existing\s+(?:method|approach)', full):
        score += 2
        details.append("baselines")

    # Tables/Figures (results presentation)
    if re.search(r'table\s+\d|figure\s+\d|fig\.\s*\d', full):
        score += 2
        details.append("results_tables")

    return {"score": min(score, 10), "max": 10, "details": details}


# ===================================================================
# Main scoring function
# ===================================================================

DIMENSIONS = {
    "metadata": _score_metadata,
    "structure": _score_structure,
    "citations": _score_citations,
    "reproducibility": _score_reproducibility,
    "problem_definition": _score_problem_definition,
    "innovation": _score_innovation,
    "experiments": _score_experiments,
}


def score_paper(data: dict) -> dict:
    """
    Score a paper across 7 quality dimensions.

    Returns:
        {
            "dimensions": {name: {score, max, details}},
            "total": int,
            "max_total": int,
            "grade": str,
        }
    """
    dimensions = {}
    total = 0
    for name, scorer in DIMENSIONS.items():
        result = scorer(data)
        dimensions[name] = result
        total += result["score"]

    max_total = sum(d["max"] for d in dimensions.values())

    # Grade mapping
    pct = total / max_total if max_total > 0 else 0
    if pct >= 0.85:
        grade = "A"
    elif pct >= 0.70:
        grade = "B"
    elif pct >= 0.55:
        grade = "C"
    elif pct >= 0.40:
        grade = "D"
    else:
        grade = "F"

    return {
        "dimensions": dimensions,
        "total": total,
        "max_total": max_total,
        "grade": grade,
    }


# ===================================================================
# Batch processing
# ===================================================================

def score_all_papers(parsed_dir: Path = None, notes_dir: Path = None) -> dict:
    """
    Score all parsed papers and save quality JSON.

    Also writes `quality` field into each paper's parsed JSON.
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR
    if notes_dir is None:
        notes_dir = config.NOTES_DIR
    notes_dir.mkdir(parents=True, exist_ok=True)

    results = {"scored": 0, "failed": 0, "grades": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}}

    for json_file in sorted(parsed_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            quality = score_paper(data)

            # Write quality JSON
            ulid = data["paper_id"]
            quality_path = notes_dir / f"{ulid}-quality.json"
            quality_path.write_text(
                json.dumps(quality, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Update paper JSON with quality field
            data["quality"] = {"total": quality["total"], "grade": quality["grade"]}
            json_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            results["scored"] += 1
            results["grades"][quality["grade"]] += 1
        except Exception:
            results["failed"] += 1

    return results


def score_single_paper(ulid: str) -> Optional[dict]:
    """Score a single paper and save quality JSON."""
    from . import db as dbmod

    data = dbmod.load_parsed(ulid)
    if data is None:
        return None

    quality = score_paper(data)

    # Write quality JSON
    config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    quality_path = config.NOTES_DIR / f"{ulid}-quality.json"
    quality_path.write_text(
        json.dumps(quality, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Update paper JSON
    data["quality"] = {"total": quality["total"], "grade": quality["grade"]}
    json_file = config.PARSED_DIR / f"{ulid}.json"
    json_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return quality
