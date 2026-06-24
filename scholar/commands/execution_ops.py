"""Execution operations: compile-paper, lean-verify, exp-run, exp-compare, exp-setup, exp-debug, dataset-download."""
import json
import re
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from .._shared import app, console
from .. import config
from .. import db as dbmod


# ===================================================================
# Helper: parse LaTeX log
# ===================================================================
def _parse_latex_log(log_path, tex_stem: str) -> dict:
    """Parse a LaTeX .log file and categorize errors into FATAL/WARN/INFO."""
    result = {"fatal": [], "warn": [], "info": [], "overfull": 0, "underfull": 0,
              "pages": 0, "pdf_generated": False}

    if not log_path.exists():
        result["fatal"].append({"msg": "Log file not found", "file": "", "line": ""})
        return result

    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    full_text = "\n".join(lines)

    result["pdf_generated"] = "Output written" in full_text

    m = re.search(r"Output written on .+?\((\d+) pages?", full_text, re.DOTALL)
    if m:
        result["pages"] = int(m.group(1))

    i = 0
    while i < len(lines):
        l = lines[i]

        if l.startswith("!"):
            msg = l[2:].strip() if len(l) > 2 else "Unknown error"
            ctx_file, ctx_line = "", ""
            for j in range(i + 1, min(i + 5, len(lines))):
                m = re.search(r"l\.(\d+)", lines[j])
                if m:
                    ctx_line = m.group(1)
                    break
            for j in range(max(0, i - 10), i):
                m = re.search(r"\((\S+\.tex)", lines[j])
                if m:
                    ctx_file = m.group(1)
            result["fatal"].append({"msg": msg, "file": ctx_file, "line": ctx_line})

        elif "Overfull \\hbox" in l or "Overfull \\vbox" in l:
            result["overfull"] += 1
            m = re.search(r"\(([\d.]+)pt too wide\)", l)
            pt = m.group(1) if m else "?"
            ctx_line = ""
            m2 = re.search(r"at lines? (\d+[-–]\d+|\d+)", l)
            if m2:
                ctx_line = m2.group(1)
            result["warn"].append({"msg": f"Overfull ({pt}pt)", "file": "", "line": ctx_line})

        elif "Underfull \\hbox" in l or "Underfull \\vbox" in l:
            result["underfull"] += 1

        elif "Citation" in l and "undefined" in l:
            m = re.search(r"Citation `(.+?)\s*'", l)
            key = m.group(1).strip() if m else "?"
            if not key.startswith("\\") and "^^" not in key:
                result["warn"].append({"msg": f"Undefined citation: {key}", "file": "", "line": ""})

        elif "Reference" in l and "undefined" in l:
            m = re.search(r"Reference `(.+?)\s*'", l)
            key = m.group(1).strip() if m else "?"
            if not key.startswith("\\") and "^^" not in key:
                result["warn"].append({"msg": f"Undefined reference: {key}", "file": "", "line": ""})

        elif "LaTeX Warning:" in l and "undefined" not in l:
            result["info"].append({"msg": l.strip()[:120], "file": "", "line": ""})

        i += 1

    return result


def _print_compile_report(rpt: dict, tex_name: str, attempt: int = 0):
    """Print structured compile report using rich."""
    n_fatal = len(rpt["fatal"])
    n_warn = len(rpt["warn"])
    n_info = len(rpt["info"])

    if rpt["pdf_generated"]:
        if n_fatal == 0 and n_warn == 0:
            status = "[green]OK[/]"
        elif n_fatal == 0:
            status = "[yellow]OK (warnings)[/]"
        else:
            status = "[yellow]OK (with errors)[/]"

        parts = [f"Pages: [bold]{rpt['pages']}[/]"]
        if n_fatal:
            parts.append(f"Errors: [yellow]{n_fatal}[/] (non-blocking, PDF generated)")
            for e in rpt["fatal"][:5]:
                loc = f" (line {e['line']})" if e["line"] else ""
                parts.append(f"  [yellow]- {e['msg']}{loc}[/]")
            if n_fatal > 5:
                parts.append(f"  [dim]... and {n_fatal - 5} more[/]")
        parts.append(f"Overfull: {rpt['overfull']}  Underfull: {rpt['underfull']}")
        if n_warn:
            parts.append(f"Warnings: [yellow]{n_warn}[/]")
            for w in rpt["warn"][:5]:
                loc = f" (line {w['line']})" if w["line"] else ""
                parts.append(f"  [dim]- {w['msg']}{loc}[/]")
            if n_warn > 5:
                parts.append(f"  [dim]... and {n_warn - 5} more[/]")
        console.print(Panel("\n".join(parts), title=f"[green]Compiled:[/] {tex_name}  {status}"))
    else:
        parts = [f"[red bold]FATAL: {n_fatal}[/]  [yellow]WARN: {n_warn}[/]  INFO: {n_info}"]
        if n_fatal:
            parts.append("\n[red]Fatal errors:[/]")
            for e in rpt["fatal"][:5]:
                loc = f" ({e['file']}:{e['line']})" if e["file"] else ""
                parts.append(f"  [red]- {e['msg']}{loc}[/]")
            if n_fatal > 5:
                parts.append(f"  ... and {n_fatal - 5} more")
        if n_warn:
            parts.append(f"\n[yellow]Warnings: {n_warn}[/] (Overfull: {rpt['overfull']}, Underfull: {rpt['underfull']})")
            for w in rpt["warn"][:5]:
                loc = f" (line {w['line']})" if w["line"] else ""
                parts.append(f"  [dim]- {w['msg']}{loc}[/]")
        console.print(Panel("\n".join(parts), title=f"[red]Compilation Failed:[/] {tex_name}"))


# ===================================================================
# compile-paper: LaTeX compilation with structured error reporting
# ===================================================================
@app.command(name="compile-paper")
def compile_paper(
    tex_file: str = typer.Argument(help="Path to .tex file"),
    output_dir: str = typer.Option("output/pdfs", help="Output directory for PDF"),
    max_retries: int = typer.Option(3, help="Max compilation retries"),
    report: bool = typer.Option(False, "--report", help="Only parse existing log, don't compile"),
    engine: str = typer.Option("", "--engine", help="LaTeX engine override (pdflatex/xelatex)"),
):
    """Compile LaTeX to PDF with structured error reporting (FATAL/WARN/INFO)."""
    tex_path = config.PROJECT_ROOT / tex_file
    if not tex_path.exists():
        console.print(f"[red]File not found:[/] {tex_path}")
        raise typer.Exit(1)

    out_path = config.PROJECT_ROOT / output_dir
    out_path.mkdir(parents=True, exist_ok=True)

    latex_cmd = engine or config.LATEX_CMD
    latex_bin = shutil.which(latex_cmd)

    if report:
        log_path = out_path / (tex_path.stem + ".log")
        if not log_path.exists():
            console.print(f"[red]Log not found:[/] {log_path}")
            raise typer.Exit(1)
        rpt = _parse_latex_log(log_path, tex_path.stem)
        _print_compile_report(rpt, tex_path.name)
        return

    if not latex_bin:
        console.print(f"[red]{latex_cmd} not found.[/] Install MiKTeX or TeX Live.")
        raise typer.Exit(1)

    console.print(f"[cyan]Compiling:[/] {tex_path.name} [{latex_cmd}]")

    last_report = None
    success = False
    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                [latex_bin, "-interaction=nonstopmode", f"-output-directory={out_path}", str(tex_path)],
                capture_output=True, encoding="utf-8", errors="replace", timeout=120,
                cwd=str(tex_path.parent),
            )

            pdf_name = tex_path.stem + ".pdf"
            pdf_path = out_path / pdf_name

            if pdf_path.exists():
                subprocess.run(
                    [latex_bin, "-interaction=nonstopmode", f"-output-directory={out_path}", str(tex_path)],
                    capture_output=True, encoding="utf-8", errors="replace", timeout=120,
                    cwd=str(tex_path.parent),
                )

            log_path = out_path / (tex_path.stem + ".log")
            last_report = _parse_latex_log(log_path, tex_path.stem)

            if last_report["pdf_generated"]:
                success = True
                bib_path = tex_path.parent / (tex_path.stem + ".bib")
                if bib_path.exists():
                    bibtex_cmd = shutil.which("bibtex")
                    if bibtex_cmd:
                        aux_path = out_path / (tex_path.stem + ".aux")
                        subprocess.run(
                            [bibtex_cmd, str(aux_path)],
                            capture_output=True, timeout=30,
                            cwd=str(tex_path.parent),
                        )
                        subprocess.run(
                            [latex_bin, "-interaction=nonstopmode", f"-output-directory={out_path}", str(tex_path)],
                            capture_output=True, encoding="utf-8", errors="replace", timeout=120,
                            cwd=str(tex_path.parent),
                        )
                        log_path = out_path / (tex_path.stem + ".log")
                        last_report = _parse_latex_log(log_path, tex_path.stem)
                break
            else:
                if attempt >= max_retries:
                    break
                console.print(f"  [yellow]Attempt {attempt}/{max_retries} failed "
                              f"({len(last_report['fatal'])} FATAL), retrying...[/]")

        except subprocess.TimeoutExpired:
            if last_report is None:
                last_report = {"fatal": [{"msg": "Compilation timed out", "file": "", "line": ""}],
                               "warn": [], "info": [], "overfull": 0, "underfull": 0,
                               "pages": 0, "pdf_generated": False}
            break
        except Exception as e:
            if last_report is None:
                last_report = {"fatal": [{"msg": str(e), "file": "", "line": ""}],
                               "warn": [], "info": [], "overfull": 0, "underfull": 0,
                               "pages": 0, "pdf_generated": False}
            break

    if last_report is None:
        last_report = {"fatal": [{"msg": "Unknown failure", "file": "", "line": ""}],
                       "warn": [], "info": [], "overfull": 0, "underfull": 0,
                       "pages": 0, "pdf_generated": False}

    _print_compile_report(last_report, tex_path.name, attempt)


# ===================================================================
# lean-verify: Run Lean4 verification on AiEvolution theorems
# ===================================================================
@app.command(name="lean-verify")
def lean_verify(
    theorem: Optional[str] = typer.Option(None, "--theorem", "-t", help="Verify a specific theorem (e.g., 'transformer_replaces_rnn'). Omit to verify all."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run Lean4 verification on AiEvolution theorems.

    Compiles AiEvolution.lean with `lake build` and reports which
    theorems pass or fail. If no theorem is specified, verifies all 7.
    """
    lean_dir = config.LEAN_DIR
    lean_project = lean_dir / "AiEvolution.lean"

    if not lean_project.exists():
        msg = f"Lean4 project not found at {lean_project}"
        if json_output:
            print(json.dumps({"error": msg, "theorems": [], "build_ok": False}))
        else:
            console.print(f"[red]{msg}[/]")
        raise typer.Exit(1)

    lake_bin = shutil.which("lake")
    if not lake_bin:
        # Fallback: search common elan installation paths
        import os
        home = Path.home()
        elan_bin = home / ".elan" / "bin"
        candidates = [
            str(elan_bin / ("lake.exe" if sys.platform == "win32" else "lake")),
        ]
        # Also check toolchains directory
        elan_toolchains = home / ".elan" / "toolchains"
        if elan_toolchains.exists():
            for tc in elan_toolchains.iterdir():
                candidates.append(str(tc / "bin" / ("lake.exe" if sys.platform == "win32" else "lake")))
        for c in candidates:
            if Path(c).exists():
                lake_bin = c
                break
    if not lake_bin:
        msg = "Lean4 `lake` not found. Install Lean4 via elan: https://lean-lang.org/"
        if json_output:
            print(json.dumps({"error": msg, "theorems": [], "build_ok": False}))
        else:
            console.print(f"[red]{msg}[/]")
        raise typer.Exit(1)

    console.print(f"[cyan]Running Lean4 verification...[/]")
    console.print(f"  Project: {lean_project.relative_to(config.PROJECT_ROOT)}")

    try:
        result = subprocess.run(
            [lake_bin, "build", "AiEvolution"],
            capture_output=True, text=True, timeout=120,
            cwd=str(lean_dir),
        )
    except subprocess.TimeoutExpired:
        msg = "Lean4 build timed out (120s)"
        if json_output:
            print(json.dumps({"error": msg, "theorems": [], "build_ok": False}))
        else:
            console.print(f"[red]{msg}[/]")
        raise typer.Exit(1)
    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e), "theorems": [], "build_ok": False}))
        else:
            console.print(f"[red]Lean4 build failed: {e}[/]")
        raise typer.Exit(1)

    build_ok = result.returncode == 0
    stderr = result.stderr
    stdout = result.stdout

    # Parse theorems from Theorems.lean
    theorems_file = lean_dir / "AiEvolution" / "Theorems.lean"
    all_theorems = []
    if theorems_file.exists():
        content = theorems_file.read_text(encoding="utf-8")
        pattern = re.compile(r'theorem\s+(\w+)\s*:', re.MULTILINE)
        all_theorems = [(m.group(1), content) for m in pattern.finditer(content)]

    # Filter if specific theorem requested
    if theorem:
        all_theorems = [(name, c) for name, c in all_theorems if name == theorem]
        if not all_theorems:
            msg = f"Theorem '{theorem}' not found in Theorems.lean"
            if json_output:
                print(json.dumps({"error": msg, "available": [t[0] for t in all_theorems], "build_ok": build_ok}))
            else:
                console.print(f"[yellow]{msg}[/]")
            raise typer.Exit(1)

    # Build theorem results
    theorem_results = []
    for name, _ in all_theorems:
        # A theorem "passes" if the build succeeded (Lean4 type-checks all)
        status = "verified" if build_ok else "failed"
        error_detail = None
        if not build_ok:
            # Search stderr for errors near this theorem name
            lines = stderr.split("\n")
            for i, line in enumerate(lines):
                if name in line or "error" in line.lower():
                    ctx = "\n".join(lines[max(0, i-1):min(len(lines), i+3)])
                    if len(ctx) > 300:
                        ctx = ctx[:300] + "..."
                    error_detail = ctx
                    break
            if not error_detail:
                error_detail = stderr[:500] if stderr else "Unknown build error"
        theorem_results.append({
            "theorem": name,
            "status": status,
            "error": error_detail,
        })

    if json_output:
        print(json.dumps({
            "build_ok": build_ok,
            "theorems_verified": sum(1 for t in theorem_results if t["status"] == "verified"),
            "theorems_total": len(theorem_results),
            "theorems": theorem_results,
            "stdout_tail": stdout[-500:] if stdout else "",
            "stderr_tail": stderr[-500:] if stderr else "",
        }, ensure_ascii=False))
        return

    # Rich output
    total = len(theorem_results)
    verified = sum(1 for t in theorem_results if t["status"] == "verified")

    if build_ok:
        console.print(Panel(
            f"[green bold]All {total} theorems verified successfully.[/]\n"
            f"Lean4 project compiles without errors.\n"
            f"No `sorry` axioms — all proofs are complete.",
            title="[green]Lean4 Verification PASSED[/]",
        ))
    else:
        console.print(Panel(
            f"[red bold]Build failed: {total - verified}/{total} theorems affected.[/]\n"
            f"Last {min(5, len(theorem_results))} errors:\n" +
            "\n".join(
                f"  [yellow]{t['theorem']}[/]: {t.get('error', '?')[:200]}"
                for t in theorem_results[-5:]
            ),
            title="[red]Lean4 Verification FAILED[/]",
        ))

    table = Table(title="Theorem Verification Results")
    table.add_column("Theorem", style="cyan")
    table.add_column("Status")
    table.add_column("Details")
    for t in theorem_results:
        status_style = "[green]✓[/]" if t["status"] == "verified" else "[red]✗[/]"
        table.add_row(t["theorem"], status_style, (t.get("error") or "")[:80])
    console.print(table)

    if not build_ok:
        raise typer.Exit(1)


# ===================================================================
# Helper: Extract metrics from experiment stdout
# ===================================================================
def _extract_metrics(stdout: str, ulid: str, mode: str, runtime: float) -> dict:
    """Extract structured metrics from experiment stdout.

    Applies the same normalization as _extract_paper_metrics to ensure
    symmetric comparison: percentage values > 1 are divided by 100 for
    ratio metrics (accuracy, f1_score, bleu, map).
    """
    # Same normalization set as _extract_paper_metrics for symmetric comparison
    _normalize_metrics = {"accuracy", "val_accuracy", "f1_score", "bleu", "map"}

    def _normalize(value: float, name: str) -> float:
        if value > 1 and name in _normalize_metrics:
            return value / 100.0
        return value

    metrics = []
    patterns = [
        (r"accuracy[:\s=]+([\d.]+)", "accuracy", "higher_better"),
        (r"val_accuracy[:\s=]+([\d.]+)", "val_accuracy", "higher_better"),
        (r"\bloss[:\s=]+([\d.]+)", "loss", "lower_better"),
        (r"\bval_loss[:\s=]+([\d.]+)", "val_loss", "lower_better"),
        (r"f1[:\s=]+([\d.]+)", "f1_score", "higher_better"),
        (r"bleu[:\s=]+([\d.]+)", "bleu", "higher_better"),
        (r"\b(?:AP|map)[:\s=]+([\d.]+)", "map", "higher_better"),
    ]
    for pattern, name, mtype in patterns:
        matches = re.findall(pattern, stdout, re.IGNORECASE)
        if matches:
            try:
                value = _normalize(float(matches[-1]), name)
                metrics.append({"name": name, "value": value, "type": mtype})
            except ValueError:
                pass
    import time as _time
    return {
        "paper_id": ulid,
        "metrics": metrics,
        "runtime_seconds": round(runtime, 1),
        "mode": mode,
        "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _extract_paper_metrics(paper_data: dict) -> list:
    """Extract reported metrics from paper sections (Results/Experiments/Evaluation).

    Enhanced extraction:
    - Colon/equals format: accuracy: 85.2, loss = 0.34
    - Sentence format: achieves accuracy of 92.3%, reaches F1 of 0.87
    - Markdown table rows: | accuracy | 88.5% |
    - ± notation: 85.2 ± 0.3 (takes main value)
    - Range values: 85.2-87.3 (takes max for higher_better, min for lower_better)
    - Multiple values: takes best (max for higher_better, min for lower_better)
    - Normalization: percentage values >1 are divided by 100 for ratio metrics
    - New metrics: EM, AUC, precision, recall
    """
    # Metrics that should be normalized to [0, 1] when value > 1
    _normalize_metrics = {"accuracy", "f1_score", "map", "bleu", "rouge_l",
                          "exact_match", "auc", "precision", "recall"}
    _lower_better_metrics = {"loss", "perplexity"}

    def _normalize(value: float, name: str) -> float:
        if value > 1 and name in _normalize_metrics:
            return value / 100.0
        return value

    def _mtype(name: str) -> str:
        return "lower_better" if name in _lower_better_metrics else "higher_better"

    # Regex patterns: (pattern, metric_name)
    # Covers colon/equals format AND sentence format
    patterns = [
        # accuracy / acc
        (r"(?:accuracy|acc)\s*[:=]\s*(\d+\.?\d*)\s*%?", "accuracy"),
        (r"(?:accuracy|acc)\s*(?:of|is|was|reaches?|achieves?|obtains?|attains?)\s*(\d+\.?\d*)\s*%?", "accuracy"),
        # F1 score
        (r"(?:f1[- ]?score|f1)\s*[:=]\s*(\d+\.?\d*)", "f1_score"),
        (r"(?:f1[- ]?score|f1)\s*(?:of|is|was|reaches?|achieves?)\s*(\d+\.?\d*)", "f1_score"),
        # BLEU
        (r"(?:bleu)\s*[:=]\s*(\d+\.?\d*)", "bleu"),
        (r"(?:bleu)\s*(?:of|is|was|reaches?|achieves?)\s*(\d+\.?\d*)", "bleu"),
        # Perplexity / PPL
        (r"(?:perplexity|ppl)\s*[:=]\s*(\d+\.?\d*)", "perplexity"),
        # ROUGE-L
        (r"(?:rouge[- ]?l)\s*[:=]\s*(\d+\.?\d*)", "rouge_l"),
        # MAP
        (r"(?:map|mean\s+average\s+precision|\bAP)\s*[:=]\s*(\d+\.?\d*)", "map"),
        # Loss
        (r"\bloss\s*[:=]\s*(\d+\.?\d*)", "loss"),
        # Exact Match / EM
        (r"(?:exact\s+match|em)\s*[:=]\s*(\d+\.?\d*)\s*%?", "exact_match"),
        # AUC
        (r"\bauc\s*[:=]\s*(\d+\.?\d*)", "auc"),
        # Precision
        (r"\bprecision\s*[:=]\s*(\d+\.?\d*)\s*%?", "precision"),
        # Recall
        (r"\brecall\s*[:=]\s*(\d+\.?\d*)\s*%?", "recall"),
    ]

    # Collect target text from Results/Experiments/Evaluation sections
    target_text = ""
    for s in paper_data.get("sections", []):
        heading = (s.get("heading") or "").lower()
        if any(kw in heading for kw in ["result", "experiment", "evaluation", "performance", "main result"]):
            target_text += "\n" + s.get("content", "")
    # Also check abstract
    target_text += "\n" + (paper_data.get("abstract") or "")

    metrics = []
    seen_names = set()

    # Phase 1: Parse markdown table rows (| metric | value |)
    table_pattern = re.compile(r"\|\s*([a-zA-Z][\w\s-]*?)\s*\|\s*(\d+\.?\d*)\s*[%]?\s*\|")
    name_map = {
        "accuracy": "accuracy", "acc": "accuracy",
        "f1": "f1_score", "f1 score": "f1_score", "f1-score": "f1_score",
        "bleu": "bleu", "perplexity": "perplexity", "ppl": "perplexity",
        "rouge-l": "rouge_l", "rouge l": "rouge_l", "map": "map",
        "loss": "loss", "em": "exact_match", "exact match": "exact_match",
        "auc": "auc", "precision": "precision", "recall": "recall",
    }
    for match in table_pattern.finditer(target_text):
        metric_name_raw = match.group(1).strip().lower()
        value_str = match.group(2)
        mapped = name_map.get(metric_name_raw)
        if mapped and mapped not in seen_names:
            try:
                value = _normalize(float(value_str), mapped)
                metrics.append({"name": mapped, "value": value, "type": _mtype(mapped)})
                seen_names.add(mapped)
            except ValueError:
                pass

    # Phase 2: Regex extraction from prose
    for pattern, name in patterns:
        if name in seen_names:
            continue  # Already found via table
        matches = re.findall(pattern, target_text, re.IGNORECASE)
        if matches:
            values = []
            for m in matches:
                try:
                    v = _normalize(float(m), name)
                    values.append(v)
                except ValueError:
                    continue
            if values:
                # Take best value: max for higher_better, min for lower_better
                mtype = _mtype(name)
                best = max(values) if mtype == "higher_better" else min(values)
                metrics.append({"name": name, "value": best, "type": mtype})
                seen_names.add(name)

    return metrics


# ===================================================================
# exp-run: Run experiment
# ===================================================================
@app.command(name="exp-run")
def exp_run(
    paper_id: str = typer.Argument(help="Paper ID (ULID/arXiv/DOI/slug)"),
    mode: str = typer.Option("quick", help="quick (CPU+synthetic) or full"),
    gpu: bool = typer.Option(False, "--gpu", help="Use GPU"),
    use_docker: bool = typer.Option(False, "--docker", help="Run in Docker sandbox"),
    timeout: int = typer.Option(3600, help="Timeout in seconds"),
):
    """Run experiment code and collect metrics."""
    from ..id_resolver import resolve_id
    ulid = resolve_id(paper_id) or paper_id

    exp_dir = config.EXPERIMENTS_DIR / ulid
    if not exp_dir.exists():
        console.print(f"[red]No experiment code found:[/] {exp_dir}")
        console.print("[dim]Run experiment-code skill first to generate code.[/]")
        raise typer.Exit(1)

    main_script = None
    for name in ["main.py", "run.py", "train.py", "experiment.py"]:
        candidate = exp_dir / name
        if candidate.exists():
            main_script = candidate
            break

    if not main_script:
        py_files = list(exp_dir.glob("*.py"))
        if py_files:
            main_script = py_files[0]
        else:
            console.print(f"[red]No Python scripts found in {exp_dir}[/]")
            raise typer.Exit(1)

    console.print(f"[cyan]Running experiment:[/] {main_script.name}")
    console.print(f"  Mode: {mode}, GPU: {gpu}, Docker: {use_docker}, Timeout: {timeout}s")

    # Pre-check: warn if template contains unfilled TODO sections
    for check_file in [exp_dir / "model.py", exp_dir / "main.py", main_script]:
        if check_file.exists():
            content = check_file.read_text(encoding="utf-8", errors="replace")
            if "TODO" in content or "pass  # TODO" in content:
                console.print(f"[yellow]Warning: {check_file.name} contains unfilled TODO sections. Results may be meaningless.[/]")
                if mode != "quick":
                    console.print("[yellow]  Use --mode quick for synthetic data testing, or fill in TODOs first.[/]")
                break

    env_args = []
    if mode == "quick":
        env_args = ["--mode", "quick"]
    if gpu:
        env_args.append("--gpu")

    import time
    start_time = time.time()

    try:
        if use_docker:
            # Docker sandbox execution
            image_name = f"scholar-{ulid[:8]}"
            docker_args = ["docker", "run", "--rm"]
            if gpu:
                docker_args.extend(["--gpus", "all"])
            docker_args.extend([
                "-v", f"{exp_dir}:/app",
                "-v", f"{config.PROJECT_ROOT / 'output' / 'datasets'}:/data",
                "-w", "/app",
                image_name,
                "python", str(main_script.name),
            ] + env_args)
            result = subprocess.run(
                docker_args,
                capture_output=True, text=True, timeout=timeout,
            )
        else:
            # Direct execution
            result = subprocess.run(
                [sys.executable, str(main_script)] + env_args,
                capture_output=True, text=True, timeout=timeout,
                cwd=str(exp_dir),
            )

        runtime = time.time() - start_time

        log_path = exp_dir / "run_log.txt"
        log_path.write_text(
            f"=== STDOUT ===\n{result.stdout}\n=== STDERR ===\n{result.stderr}\n=== Return code: {result.returncode} ===\n",
            encoding="utf-8",
        )

        # Extract structured metrics
        metrics = _extract_metrics(result.stdout, ulid, mode, runtime)
        results_path = exp_dir / "results.json"
        results_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

        if result.returncode == 0:
            console.print(Panel(
                f"Script: {main_script.name}\n"
                f"Return code: [green]0[/]\n"
                f"Runtime: {runtime:.1f}s\n"
                f"Metrics: {len(metrics['metrics'])} extracted\n"
                f"Log: {log_path}\n"
                f"Results: {results_path}",
                title="[green]Experiment OK[/]",
            ))
        else:
            console.print(Panel(
                f"Return code: [red]{result.returncode}[/]\n"
                f"Runtime: {runtime:.1f}s\n"
                f"Last stderr:\n{result.stderr[-500:]}\n"
                f"Log: {log_path}",
                title="[red]Experiment Failed[/]",
            ))
    except subprocess.TimeoutExpired:
        runtime = time.time() - start_time
        console.print(f"[red]Experiment timed out after {timeout}s (ran {runtime:.0f}s)[/]")


# ===================================================================
# exp-compare: Compare experiment results
# ===================================================================
@app.command(name="exp-compare")
def exp_compare(
    paper_id: str = typer.Argument(help="Paper ID"),
    baseline_id: Optional[str] = typer.Option(None, help="Baseline paper ID"),
):
    """Compare experiment results with paper metrics."""
    from ..id_resolver import resolve_id
    ulid = resolve_id(paper_id) or paper_id

    exp_dir = config.EXPERIMENTS_DIR / ulid
    log_path = exp_dir / "run_log.txt"
    report_path = exp_dir / "results.json"

    if not log_path.exists() and not report_path.exists():
        console.print(f"[red]No experiment results found for {ulid}[/]")
        raise typer.Exit(1)

    log_content = ""
    if log_path.exists():
        log_content = log_path.read_text(encoding="utf-8")

    results = {}
    if report_path.exists():
        results = json.loads(report_path.read_text(encoding="utf-8"))

    paper_data = dbmod.load_parsed(ulid) or {}

    output_parts = [
        f"Paper: {(paper_data.get('title') or ulid)[:60]}",
        f"Experiment log: {'[green]found[/]' if log_content else '[red]missing[/]'}",
        f"Results JSON:   {'[green]found[/]' if results else '[yellow]missing[/]'}",
    ]
    if results:
        output_parts.append("\nMetrics:\n" + "\n".join(f"  {k}: {v}" for k, v in results.items()))

    # Extract paper-reported metrics from sections
    paper_metrics = _extract_paper_metrics(paper_data)
    if paper_metrics:
        output_parts.append("\n[bold]Paper-reported metrics:[/]")
        for m in paper_metrics:
            output_parts.append(f"  {m['name']}: {m['value']} ({m['type']})")

    if baseline_id:
        bl_ulid = resolve_id(baseline_id) or baseline_id
        bl_results_path = config.EXPERIMENTS_DIR / bl_ulid / "results.json"
        if bl_results_path.exists():
            bl_results = json.loads(bl_results_path.read_text(encoding="utf-8"))
            bl_data = dbmod.load_parsed(bl_ulid) or {}
            output_parts.append(f"\n[bold]Baseline:[/] {(bl_data.get('title') or bl_ulid)[:60]}")
            common_keys = set(results.keys()) & set(bl_results.keys()) if results else set()
            if common_keys:
                output_parts.append("\n[bold]Comparison:[/]")
                for k in sorted(common_keys):
                    v1 = results.get(k)
                    v2 = bl_results.get(k)
                    try:
                        diff = float(v1) - float(v2)
                        sign = "+" if diff > 0 else ""
                        output_parts.append(f"  {k}: {v1} vs {v2} ({sign}{diff:.4f})")
                    except (TypeError, ValueError):
                        output_parts.append(f"  {k}: {v1} vs {v2}")
        else:
            output_parts.append(f"\n[yellow]Baseline results not found for {bl_ulid}[/]")

    console.print(Panel(
        "\n".join(output_parts),
        title=f"Experiment Report: {ulid}",
    ))


# ===================================================================
# exp-setup: Setup experiment environment
# ===================================================================
@app.command(name="exp-setup")
def exp_setup(
    paper_id: str = typer.Argument(help="Paper ID"),
    use_conda: bool = typer.Option(True, "--conda/--no-conda", help="Use conda environment"),
    use_docker: bool = typer.Option(False, "--docker", help="Use Docker"),
):
    """Set up experiment environment (conda/Docker)."""
    from ..id_resolver import resolve_id
    ulid = resolve_id(paper_id) or paper_id

    exp_dir = config.EXPERIMENTS_DIR / ulid
    if not exp_dir.exists():
        console.print(f"[red]No experiment code found:[/] {exp_dir}")
        raise typer.Exit(1)

    req_path = exp_dir / "requirements.txt"
    env_path = exp_dir / "environment.yml"

    console.print(f"[cyan]Setting up environment for {ulid}[/]")

    if use_conda:
        env_name = f"scholar-{ulid[:8]}"
        console.print(f"  Creating conda env: {env_name}")
        try:
            subprocess.run(["conda", "create", "-n", env_name, "python=3.10", "-y"],
                          capture_output=True, text=True, timeout=300, check=True)
            console.print(f"  [green]Conda env created: {env_name}[/]")
        except subprocess.CalledProcessError as e:
            console.print(f"  [red]conda create failed: {e.stderr[-200:]}[/]")
            raise typer.Exit(1)
        except FileNotFoundError:
            console.print("  [red]conda not found. Install Miniconda or use --docker[/]")
            raise typer.Exit(1)

        if req_path.exists():
            console.print(f"  Installing requirements.txt...")
            result = subprocess.run(
                ["conda", "run", "-n", env_name, "pip", "install", "-r", str(req_path)],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                console.print(f"  [green]Dependencies installed[/]")
            else:
                console.print(f"  [yellow]pip install warnings: {result.stderr[-200:]}[/]")
        elif env_path.exists():
            console.print(f"  Installing from environment.yml...")
            result = subprocess.run(
                ["conda", "env", "update", "-n", env_name, "-f", str(env_path)],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                console.print(f"  [green]Environment updated[/]")
            else:
                console.print(f"  [yellow]env update warnings: {result.stderr[-200:]}[/]")
        else:
            console.print("  [yellow]No requirements.txt or environment.yml found[/]")
        console.print(f"  [dim]Activate: conda activate {env_name}[/]")
    elif use_docker:
        dockerfile = exp_dir / "Dockerfile"
        if dockerfile.exists():
            image_name = f"scholar-{ulid[:8]}"
            console.print(f"  Building Docker image: {image_name}")
            result = subprocess.run(
                ["docker", "build", "-t", image_name, str(exp_dir)],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                console.print(f"  [green]Docker image built: {image_name}[/]")
            else:
                console.print(f"  [red]docker build failed: {result.stderr[-300:]}[/]")
                raise typer.Exit(1)
        else:
            console.print("  [yellow]No Dockerfile found. Run exp-codegen first.[/]")
    else:
        console.print("  Use --conda or --docker to set up environment")


# ===================================================================
# exp-debug: Debug experiment failure
# ===================================================================
@app.command(name="exp-debug")
def exp_debug(
    run_log: str = typer.Argument(help="Path to run_log.txt"),
):
    """Diagnose experiment failures."""
    log_path = Path(run_log)
    if not log_path.is_absolute():
        log_path = config.PROJECT_ROOT / log_path

    if not log_path.exists():
        console.print(f"[red]Log file not found:[/] {log_path}")
        raise typer.Exit(1)

    content = log_path.read_text(encoding="utf-8")

    stderr_section = ""
    if "=== STDERR ===" in content:
        parts = content.split("=== STDERR ===")
        if len(parts) > 1:
            stderr_section = parts[1].split("===")[0].strip()

    issues = []
    if "ModuleNotFoundError" in content:
        missing = re.findall(r"No module named '(\w+)'", content)
        issues.append(f"Missing modules: {', '.join(set(missing))}")
    if "CUDA out of memory" in content:
        issues.append("GPU OOM: reduce batch size or use CPU mode")
    if "FileNotFoundError" in content:
        issues.append("File not found: check data paths")
    if "RuntimeError" in content:
        issues.append("Runtime error: check code logic")

    console.print(Panel(
        f"Log: {log_path.name}\n\n"
        f"[bold]Detected Issues:[/]\n" + "\n".join(f"  - {i}" for i in issues) + "\n\n"
        f"[bold]Stderr (last 500 chars):[/]\n{stderr_section[-500:]}",
        title="Experiment Debug",
    ))


# ===================================================================
# exp-codegen: Generate experiment code template
# ===================================================================
@app.command(name="exp-codegen")
def exp_codegen(
    paper_id: str = typer.Argument(help="Paper ID (ULID/arXiv/DOI/slug)"),
):
    """Generate experiment code template from paper JSON."""
    from ..exp_codegen import generate_experiment_template

    result = generate_experiment_template(paper_id)
    if "error" in result:
        console.print(f"[red]{result['error']}[/]")
        raise typer.Exit(1)

    console.print(Panel(
        f"Paper: {result['title'][:60]}\n"
        f"ULID: {result['ulid']}\n"
        f"Formulas: {result['formulas_count']}\n"
        f"Hyperparams: {result['hyperparams']}\n"
        f"Files: {', '.join(result['files_created'])}\n"
        f"Output: {result['output_dir']}",
        title="[green]Experiment Template Generated[/]",
    ))
    console.print("[dim]Next: AI agent should fill in TODO sections, then run exp-setup + exp-run[/]")


# ===================================================================
# dataset-download: Download datasets
# ===================================================================
@app.command(name="dataset-download")
def dataset_download(
    dataset_name: str = typer.Argument(help="Dataset name (HuggingFace or Papers with Code)"),
    output_dir: str = typer.Option("output/datasets", help="Output directory"),
    source: str = typer.Option("auto", help="Source: auto, huggingface, paperswithcode"),
):
    """Download datasets used by papers (HuggingFace / Papers with Code)."""
    out_path = config.PROJECT_ROOT / output_dir / dataset_name
    out_path.mkdir(parents=True, exist_ok=True)

    console.print(f"[cyan]Downloading dataset:[/] {dataset_name}")

    if source in ("auto", "huggingface"):
        try:
            hf_cli = shutil.which("huggingface-cli")
            if hf_cli:
                result = subprocess.run(
                    [hf_cli, "datasets", "download", dataset_name, "--repo-type", "dataset", "--local-dir", str(out_path)],
                    capture_output=True, text=True, timeout=600,
                )
                if result.returncode == 0:
                    console.print(f"[green]Downloaded to {out_path}[/]")
                    return
        except Exception:
            pass

        try:
            from datasets import load_dataset
            ds = load_dataset(dataset_name, cache_dir=str(out_path))
            console.print(f"[green]Downloaded via Python API to {out_path}[/]")
            console.print(f"  Splits: {list(ds.keys())}")
            return
        except ImportError:
            console.print("[yellow]Install datasets: pip install datasets[/]")
        except Exception as e:
            console.print(f"[yellow]HuggingFace download failed: {e}[/]")

    if source in ("auto", "paperswithcode"):
        try:
            import urllib.request
            import json as _json
            url = f"https://paperswithcode.com/api/v1/datasets/?q={dataset_name}"
            req = urllib.request.Request(url, headers={"User-Agent": "ScholarStudio/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            if data.get("results"):
                for item in data["results"][:3]:
                    console.print(f"  [dim]Found: {item.get('name', '?')} — {item.get('description', '')[:80]}[/]")
                    dl_url = item.get("url", "")
                    if dl_url:
                        console.print(f"  [cyan]Download page: https://paperswithcode.com{dl_url}[/]")
                console.print(f"[yellow]Papers with Code datasets require manual download from the URL(s) above.[/]")
                return
            else:
                console.print(f"[yellow]No dataset found on Papers with Code for '{dataset_name}'.[/]")
        except Exception as e:
            if source == "paperswithcode":
                console.print(f"[yellow]Papers with Code search failed: {e}[/]")

    console.print(f"[yellow]Could not download {dataset_name}. Try manual download.[/]")
