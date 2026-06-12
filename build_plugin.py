"""Build the Scholar Studio Qoder Plugin.

Copies skills and commands from the project into plugin/ directory,
then packages plugin/ as a distributable .zip.

Usage: python build_plugin.py
"""
import shutil
import zipfile
import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PLUGIN_DIR = PROJECT_ROOT / "plugin"
SKILLS_SRC = PROJECT_ROOT / ".qoder" / "skills"
COMMANDS_SRC = PROJECT_ROOT / ".qoder" / "commands"
SKILLS_DST = PLUGIN_DIR / "skills"
COMMANDS_DST = PLUGIN_DIR / "commands"
RULES_SRC = PROJECT_ROOT / ".qoder" / "rules"
RULES_DST = PLUGIN_DIR / "rules"
HOOKS_SRC = PROJECT_ROOT / ".qoder" / "hooks"
HOOKS_DST = PLUGIN_DIR / "hooks"


def clean():
    """Remove old plugin build artifacts."""
    for d in [SKILLS_DST, COMMANDS_DST, RULES_DST, HOOKS_DST]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Cleaned {d}")


def copy_skills():
    """Copy all skill directories into plugin/skills/."""
    count = 0
    for skill_dir in sorted(SKILLS_SRC.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        dst = SKILLS_DST / skill_dir.name
        dst.mkdir(parents=True, exist_ok=True)

        for f in skill_dir.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)

        count += 1

    print(f"  Copied {count} skills")
    return count


def copy_commands():
    """Copy all command .md files into plugin/commands/."""
    COMMANDS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in sorted(COMMANDS_SRC.glob("*.md")):
        shutil.copy2(f, COMMANDS_DST / f.name)
        count += 1
    print(f"  Copied {count} commands")
    return count


def copy_rules():
    """Copy rule .md files into plugin/rules/ (strip frontmatter for plugin use)."""
    RULES_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in sorted(RULES_SRC.glob("*.md")):
        shutil.copy2(f, RULES_DST / f.name)
        count += 1
    print(f"  Copied {count} rules")
    return count


def copy_hooks():
    """Copy hook scripts and hooks.json into plugin/hooks/."""
    HOOKS_DST.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in sorted(HOOKS_SRC.iterdir()):
        if f.is_file():
            shutil.copy2(f, HOOKS_DST / f.name)
            count += 1
    # Also copy plugin/hooks/hooks.json if it exists (not in .qoder/hooks/)
    hooks_json = PLUGIN_DIR / "hooks" / "hooks.json"
    if hooks_json.exists() and hooks_json.parent == HOOKS_DST:
        pass  # already in place
    print(f"  Copied {count} hook files")
    return count


def create_zip():
    """Package plugin/ as a distributable .zip file.

    The zip root = plugin root (no extra nesting), as required by Qoder.
    Filename: scholar-studio-{version}.zip
    """
    # Read version from plugin.json
    plugin_json = PLUGIN_DIR / ".qoder-plugin" / "plugin.json"
    with open(plugin_json, "r", encoding="utf-8") as f:
        meta = json.load(f)

    name = meta["name"]
    version = meta["version"]
    zip_name = f"{name}-{version}.zip"
    zip_path = PROJECT_ROOT / zip_name

    # Remove old zip if exists
    if zip_path.exists():
        zip_path.unlink()

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PLUGIN_DIR):
            # Skip __pycache__ and .git
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]

            for filename in files:
                file_path = Path(root) / filename
                arcname = file_path.relative_to(PLUGIN_DIR)
                zf.write(file_path, arcname)
                file_count += 1

    size_kb = zip_path.stat().st_size / 1024
    print(f"  Created {zip_name} ({file_count} files, {size_kb:.1f} KB)")
    return zip_name, file_count


def main():
    print("=" * 55)
    print("  Scholar Studio — Plugin Builder")
    print("=" * 55)

    print("\n[1/6] Cleaning old build artifacts...")
    clean()

    print("\n[2/6] Copying skills from .qoder/skills/ ...")
    skills = copy_skills()

    print("\n[3/6] Copying commands from .qoder/commands/ ...")
    commands = copy_commands()

    print("\n[4/6] Copying rules from .qoder/rules/ ...")
    rules = copy_rules()

    print("\n[5/6] Copying hooks from .qoder/hooks/ ...")
    hooks = copy_hooks()

    print("\n[6/6] Packaging plugin as .zip ...")
    zip_name, file_count = create_zip()

    # Summary
    print("\n" + "=" * 55)
    print(f"  Build complete!")
    print(f"  Skills:    {skills}")
    print(f"  Commands:  {commands}")
    print(f"  Rules:     {rules}")
    print(f"  Hooks:     {hooks}")
    print(f"  MCP:       scholar (41 tools)")
    print(f"  Output:    {zip_name} ({file_count} files)")
    print("=" * 55)

    # List final plugin structure (top-level only)
    print("\nPlugin structure:")
    for item in sorted(PLUGIN_DIR.iterdir()):
        prefix = "  "
        if item.is_dir():
            children = list(item.rglob("*"))
            n_files = len([c for c in children if c.is_file()])
            print(f"{prefix}{item.name}/ ({n_files} files)")
        else:
            print(f"{prefix}{item.name}")


if __name__ == "__main__":
    main()
