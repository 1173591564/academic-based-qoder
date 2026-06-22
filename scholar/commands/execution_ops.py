"""Execution operations: compile-paper, exp-run, exp-compare, exp-setup, exp-debug, dataset-download."""
import json
import re
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel

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
# exp-run: Run experiment
# ===================================================================
@app.command(name="exp-run")
def exp_run(
    paper_id: str = typer.Argument(help="Paper ID (ULID/arXiv/DOI/slug)"),
    mode: str = typer.Option("quick", help="quick (CPU+synthetic) or full"),
    gpu: bool = typer.Option(False, "--gpu", help="Use GPU"),
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
    console.print(f"  Mode: {mode}, GPU: {gpu}, Timeout: {timeout}s")

    env_args = []
    if mode == "quick":
        env_args = ["--mode", "quick"]
    if gpu:
        env_args.append("--gpu")

    try:
        result = subprocess.run(
            [sys.executable, str(main_script)] + env_args,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(exp_dir),
        )

        log_path = exp_dir / "run_log.txt"
        log_path.write_text(
            f"=== STDOUT ===\n{result.stdout}\n=== STDERR ===\n{result.stderr}\n=== Return code: {result.returncode} ===\n",
            encoding="utf-8",
        )

        if result.returncode == 0:
            console.print(Panel(
                f"Script: {main_script.name}\n"
                f"Return code: [green]0[/]\n"
                f"Log: {log_path}",
                title="[green]Experiment OK[/]",
            ))
        else:
            console.print(Panel(
                f"Return code: [red]{result.returncode}[/]\n"
                f"Last stderr:\n{result.stderr[-500:]}\n"
                f"Log: {log_path}",
                title="[red]Experiment Failed[/]",
            ))
    except subprocess.TimeoutExpired:
        console.print(f"[red]Experiment timed out after {timeout}s[/]")


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
        if env_path.exists():
            console.print(f"  Found environment.yml, creating conda env: {env_name}")
            console.print(f"  [dim]Run: conda env create -f {env_path} -n {env_name}[/]")
        elif req_path.exists():
            console.print(f"  Found requirements.txt, creating conda env: {env_name}")
            console.print(f"  [dim]Run: conda create -n {env_name} python=3.10 && conda activate {env_name} && pip install -r {req_path}[/]")
        else:
            console.print("  [yellow]No requirements.txt or environment.yml found[/]")
    elif use_docker:
        dockerfile = exp_dir / "Dockerfile"
        if dockerfile.exists():
            console.print(f"  Found Dockerfile")
            console.print(f"  [dim]Run: docker build -t scholar-{ulid[:8]} {exp_dir}[/]")
        else:
            console.print("  [yellow]No Dockerfile found[/]")
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

    console.print(f"[yellow]Could not download {dataset_name}. Try manual download.[/]")
