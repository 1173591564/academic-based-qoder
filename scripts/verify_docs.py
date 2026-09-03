#!/usr/bin/env python3
"""
verify_docs.py — Verify documentation numbers match actual project state.

Usage:
    python scripts/verify_docs.py

Exit code 0 = all consistent, 1 = mismatches found.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Ground truth ──────────────────────────────────────────────

def count_mcp_tools():
    server = ROOT / "scholar_mcp" / "server.py"
    content = server.read_text(encoding="utf-8")
    return len(re.findall(r'@mcp\.tool\(\)', content))

def count_skills():
    skills_dir = ROOT / ".scholar" / "skills"
    if not skills_dir.exists():
        return 0
    return len([d for d in skills_dir.iterdir() if d.is_dir()])

def count_rules():
    rules_dir = ROOT / ".scholar" / "rules"
    if not rules_dir.exists():
        return 0
    return len([f for f in rules_dir.iterdir() if f.suffix == ".md"])

def count_commands():
    cmds_dir = ROOT / ".scholar" / "commands"
    if not cmds_dir.exists():
        return 0
    return len([f for f in cmds_dir.iterdir() if f.suffix == ".md"])

def count_hooks():
    hooks_dir = ROOT / ".scholar" / "hooks"
    if not hooks_dir.exists():
        return 0
    return len([f for f in hooks_dir.iterdir() if f.suffix == ".ps1"])

def count_parsed_papers():
    parsed_dir = ROOT / "output" / "parsed"
    if not parsed_dir.exists():
        return 0
    return len([f for f in parsed_dir.iterdir() if f.suffix == ".json"])

def count_paper_dirs():
    papers_dir = ROOT / "data" / "papers"
    if not papers_dir.exists():
        return 0
    return len([d for d in papers_dir.iterdir() if d.is_dir()])

# ── Check docs ────────────────────────────────────────────────

def check_file(filepath: Path, expected_tools: int, expected_papers: int, expected_skills: int):
    """Check a markdown file for stale numbers."""
    errors = []
    if not filepath.exists():
        return [f"  File not found: {filepath}"]

    content = filepath.read_text(encoding="utf-8")
    rel = filepath.relative_to(ROOT)

    # Check tool count claims (common patterns: "16 工具", "16 个工具", "16 tools")
    for m in re.finditer(r'(\d+)\s*(?:个)?(?:工具|tools)', content, re.IGNORECASE):
        claimed = int(m.group(1))
        if claimed != expected_tools and claimed >= 10:
            errors.append(f"  {rel}: claims {claimed} tools, actual is {expected_tools}")

    # Fixed large corpus counts must match the locally installed corpus.
    for m in re.finditer(r'(\d+)\+?\s*篇', content):
        claimed = int(m.group(1))
        if claimed != expected_papers and claimed >= 100:
            errors.append(f"  {rel}: claims {claimed} papers, actual is {expected_papers}")

    # Check skill count claims
    for m in re.finditer(r'(\d+)\s*(?:个)?\s*skills?', content, re.IGNORECASE):
        claimed = int(m.group(1))
        if claimed != expected_skills and claimed >= 10:  # heuristic: only check skill totals
            errors.append(f"  {rel}: claims {claimed} skills, actual is {expected_skills}")

    return errors

# ── Main ──────────────────────────────────────────────────────

def main():
    tools = count_mcp_tools()
    skills = count_skills()
    rules = count_rules()
    commands = count_commands()
    hooks = count_hooks()
    papers = count_parsed_papers()
    paper_dirs = count_paper_dirs()

    print("=== Scholar Studio — Documentation Consistency Check ===\n")
    print(f"Ground truth (from source):")
    print(f"  MCP tools:      {tools}")
    print(f"  Skills:         {skills}")
    print(f"  Rules:          {rules}")
    print(f"  Commands:       {commands}")
    print(f"  Hooks:          {hooks}")
    print(f"  Parsed papers:  {papers}")
    print(f"  Paper folders:  {paper_dirs}")
    print()

    # Files to check
    docs = [
        ROOT / "README.md",
        ROOT / "README.zh.md",
        ROOT / ".scholar" / "IDE_ENTRY.md",
        ROOT / ".scholar" / "rules" / "identity.md",
        ROOT / ".scholar" / "rules" / "tools.md",
        ROOT / ".claude" / "CLAUDE.md",
        ROOT / ".claude" / "rules" / "identity.md",
        ROOT / ".claude" / "rules" / "tools.md",
        ROOT / ".qoder" / "rules" / "identity.md",
        ROOT / ".qoder" / "rules" / "tools.md",
        ROOT / "scholar" / "templates" / "IDE_ENTRY.md",
        ROOT / "scholar" / "templates" / "rules" / "identity.md",
        ROOT / "scholar" / "templates" / "rules" / "tools.md",
        ROOT / "scholar" / "templates" / "dsh" / "rules" / "identity.md",
    ]

    all_errors = []
    for doc in docs:
        errors = check_file(doc, tools, papers, skills)
        all_errors.extend(errors)

    if all_errors:
        print(f"MISMATCHES FOUND ({len(all_errors)}):")
        for e in all_errors:
            print(e)
        sys.exit(1)
    else:
        print("All documentation numbers are consistent.")
        sys.exit(0)


if __name__ == "__main__":
    main()
