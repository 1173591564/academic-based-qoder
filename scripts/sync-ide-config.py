#!/usr/bin/env python
"""Sync .scholar/ shared config to .qoder/ and .claude/ IDE directories.

Usage:
    python scripts/sync-ide-config.py          # Sync and show summary
    python scripts/sync-ide-config.py --check  # Check only, no writes (CI mode)
    python scripts/sync-ide-config.py --target /path/to/workspace  # Sync to custom workspace

The .scholar/ directory is the single source of truth for:
  - rules/   (with {IDE_NAME} and {IDE_DIR} template variables)
  - skills/  (direct copy, content identical across IDEs)
  - commands/ (direct copy, content identical across IDEs)
  - hooks/   (direct copy, IDE-agnostic implementations)
  - IDE_ENTRY.md (template for IDE-specific entry point, e.g., CLAUDE.md)

settings.json and mcp.json are generated only if they don't exist (for new workspace init).
Existing settings.json/mcp.json are preserved to allow user customization.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

# IDE configurations
IDE_CONFIGS = {
    "qoder": {
        "key": "qoder",
        "name": "Qoder",
        "dir": ".qoder",
        "entry_file": None,  # Qoder uses rules directly, no entry file needed
    },
    "claude": {
        "key": "claude",
        "name": "Claude",
        "dir": ".claude",
        "entry_file": "CLAUDE.md",  # Claude Code uses CLAUDE.md as project entry point
    },
}

# Directories to copy directly (no templating)
DIRECT_COPY_DIRS = ["skills", "commands", "hooks"]

# Directories with template substitution
TEMPLATE_DIRS = ["rules"]


def substitute_template(content: str, ide_name: str, ide_dir: str) -> str:
    """Replace template variables in content."""
    return content.replace("{IDE_NAME}", ide_name).replace("{IDE_DIR}", ide_dir)


def sync_ide(scholar_source: Path, target_root: Path, ide_config: dict, dry_run: bool = False) -> dict:
    """Sync .scholar/ to a specific IDE directory.

    Returns dict with stats: {"copied": N, "templated": N, "generated": N}
    """
    ide_name = ide_config["name"]
    ide_dir_name = ide_config["dir"]
    ide_target = target_root / ide_dir_name

    stats = {"copied": 0, "templated": 0, "generated": 0}

    if not dry_run:
        ide_target.mkdir(parents=True, exist_ok=True)

    # 1. Copy direct-copy directories (skills, commands, hooks)
    for subdir in DIRECT_COPY_DIRS:
        src = scholar_source / subdir
        if not src.exists():
            continue
        dst = ide_target / subdir
        if dry_run:
            for f in src.rglob("*"):
                if f.is_file():
                    stats["copied"] += 1
        else:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            for f in src.rglob("*"):
                if f.is_file():
                    stats["copied"] += 1

    # 2. Copy templated directories (rules)
    for subdir in TEMPLATE_DIRS:
        src = scholar_source / subdir
        if not src.exists():
            continue
        dst = ide_target / subdir
        if dry_run:
            for f in src.rglob("*"):
                if f.is_file():
                    stats["templated"] += 1
        else:
            if dst.exists():
                shutil.rmtree(dst)
            dst.mkdir(parents=True)
            for f in src.rglob("*"):
                if f.is_file():
                    content = f.read_text(encoding="utf-8")
                    templated = substitute_template(content, ide_name, ide_dir_name)
                    rel_path = f.relative_to(src)
                    out_file = dst / rel_path
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    out_file.write_text(templated, encoding="utf-8")
                    stats["templated"] += 1

    # 3. Generate IDE entry point from IDE_ENTRY.md template
    ide_entry_src = scholar_source / "IDE_ENTRY.md"
    entry_file_name = ide_config.get("entry_file")
    if ide_entry_src.exists() and entry_file_name:
        target_file = ide_target / entry_file_name
        if dry_run:
            stats["generated"] += 1
        else:
            content = ide_entry_src.read_text(encoding="utf-8")
            templated = substitute_template(content, ide_name, ide_dir_name)
            target_file.write_text(templated, encoding="utf-8")
            stats["generated"] += 1

    # 4. Generate settings.json (only if not exists)
    settings_path = ide_target / "settings.json"
    if not settings_path.exists():
        settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/task-done.ps1"}]},
                    {"hooks": [{"type": "command", "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/log-conversation.ps1"}]},
                ],
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/block-dangerous.ps1"}]},
                ],
                "PostToolUse": [
                    {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/verify-citations.ps1"}]},
                ],
            }
        }
        if not dry_run:
            settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
            stats["generated"] += 1
    else:
        # Update hook paths in existing settings.json (in case hooks changed)
        if not dry_run:
            try:
                existing = json.loads(settings_path.read_text(encoding="utf-8"))
                # Only update if hooks structure exists
                if "hooks" in existing:
                    hooks = existing["hooks"]
                    if "Stop" in hooks:
                        for i, stop_hook in enumerate(hooks["Stop"]):
                            if i < 2 and "hooks" in stop_hook and len(stop_hook["hooks"]) > 0:
                                hook_name = ["task-done.ps1", "log-conversation.ps1"][i]
                                stop_hook["hooks"][0]["command"] = f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/{hook_name}"
                    if "PreToolUse" in hooks:
                        for pre_hook in hooks["PreToolUse"]:
                            if "hooks" in pre_hook and len(pre_hook["hooks"]) > 0:
                                pre_hook["hooks"][0]["command"] = f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/block-dangerous.ps1"
                    if "PostToolUse" in hooks:
                        for post_hook in hooks["PostToolUse"]:
                            if "hooks" in post_hook and len(post_hook["hooks"]) > 0:
                                post_hook["hooks"][0]["command"] = f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/verify-citations.ps1"
                    settings_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
            except (json.JSONDecodeError, KeyError, IndexError):
                pass  # Preserve existing if parsing fails

    # 5. Generate mcp.json (only if not exists)
    mcp_path = ide_target / "mcp.json"
    if not mcp_path.exists():
        workspace = str(target_root)
        mcp_config = {
            "mcpServers": {
                "scholar": {
                    "command": "python",
                    "args": ["-m", "scholar_mcp"],
                    "cwd": workspace,
                    "env": {
                        "SCHOLAR_HOME": workspace,
                        "SCHOLAR_WORKSPACE": workspace,
                        "PYTHONPATH": workspace,
                    }
                }
            }
        }
        if not dry_run:
            mcp_path.write_text(json.dumps(mcp_config, indent=2, ensure_ascii=False), encoding="utf-8")
            stats["generated"] += 1

    return stats


def verify_consistency(scholar_source: Path, target_root: Path, ide_config: dict) -> list:
    """Compare .scholar/ with generated IDE config, return diff summary."""
    diffs = []
    ide_dir = target_root / ide_config["dir"]

    # Check rules (with template substitution)
    rules_src = scholar_source / "rules"
    if rules_src.exists():
        for rule_file in rules_src.rglob("*.md"):
            expected = substitute_template(
                rule_file.read_text(encoding="utf-8"),
                ide_config["name"], ide_config["dir"]
            )
            rel = rule_file.relative_to(rules_src)
            actual_path = ide_dir / "rules" / rel
            if actual_path.exists():
                actual = actual_path.read_text(encoding="utf-8")
                if expected != actual:
                    diffs.append(f"rules/{rel}: content mismatch")
            else:
                diffs.append(f"rules/{rel}: missing")

    # Check skills/commands/hooks (direct copy)
    for subdir in ["skills", "commands", "hooks"]:
        src_dir = scholar_source / subdir
        dst_dir = ide_dir / subdir
        if src_dir.exists():
            for f in src_dir.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(src_dir)
                    dst = dst_dir / rel
                    if not dst.exists():
                        diffs.append(f"{subdir}/{rel}: missing")
                    elif f.read_bytes() != dst.read_bytes():
                        diffs.append(f"{subdir}/{rel}: content mismatch")

    # Check IDE entry file
    ide_entry_src = scholar_source / "IDE_ENTRY.md"
    entry_file_name = ide_config.get("entry_file")
    if ide_entry_src.exists() and entry_file_name:
        expected = substitute_template(
            ide_entry_src.read_text(encoding="utf-8"),
            ide_config["name"], ide_config["dir"]
        )
        actual_path = ide_dir / entry_file_name
        if actual_path.exists():
            actual = actual_path.read_text(encoding="utf-8")
            if expected != actual:
                diffs.append(f"{entry_file_name}: content mismatch")
        else:
            diffs.append(f"{entry_file_name}: missing")

    return diffs


def main():
    parser = argparse.ArgumentParser(
        description="Sync .scholar/ shared config to .qoder/ and .claude/ IDE directories"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check only, no writes (CI mode). Exits with code 1 if drift detected."
    )
    parser.add_argument(
        "--target", type=str, default=None,
        help="Target workspace directory (default: project root)"
    )
    args = parser.parse_args()

    # Find project root (parent of scripts/)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    # Or use --target
    target_root = Path(args.target) if args.target else project_root
    scholar_source = project_root / ".scholar"

    if not scholar_source.exists():
        print(f"ERROR: .scholar/ not found at {scholar_source}")
        sys.exit(1)

    print(f"Source:  {scholar_source}")
    print(f"Target:  {target_root}")
    print(f"Mode:    {'check (dry-run)' if args.check else 'sync'}")
    print()

    total_stats = {"copied": 0, "templated": 0, "generated": 0}
    all_diffs = {}

    for ide_key, ide_config in IDE_CONFIGS.items():
        print(f"--- {ide_config['name']} ({ide_config['dir']}/) ---")
        stats = sync_ide(scholar_source, target_root, ide_config, dry_run=args.check)
        print(f"  Copied:     {stats['copied']} files")
        print(f"  Templated:  {stats['templated']} files")
        print(f"  Generated:  {stats['generated']} files")
        print()
        for k in total_stats:
            total_stats[k] += stats[k]

        # Run consistency check
        diffs = verify_consistency(scholar_source, target_root, ide_config)
        if diffs:
            all_diffs[ide_key] = diffs
            print(f"  Drift detected ({len(diffs)} differences):")
            for d in diffs:
                print(f"    - {d}")
            print()
        else:
            print(f"  Consistency: OK (0 drift)")
            print()

    print(f"Total: {total_stats['copied']} copied, {total_stats['templated']} templated, {total_stats['generated']} generated")

    if args.check:
        if all_diffs:
            total_drift = sum(len(d) for d in all_diffs.values())
            print(f"\nCheck mode: {total_drift} drift(s) detected. Run without --check to sync.")
            sys.exit(1)
        else:
            print("\nCheck mode: no drift detected. All IDE configs are consistent with .scholar/.")
    else:
        print("\nSync complete.")


if __name__ == "__main__":
    main()
#!/usr/bin/env python
"""Sync .scholar/ shared config to .qoder/ and .claude/ IDE directories.

Usage:
    python scripts/sync-ide-config.py          # Sync and show summary
    python scripts/sync-ide-config.py --check  # Check only, no writes (CI mode)
    python scripts/sync-ide-config.py --target /path/to/workspace  # Sync to custom workspace

The .scholar/ directory is the single source of truth for:
  - rules/   (with {IDE_NAME} and {IDE_DIR} template variables)
  - skills/  (direct copy, content identical across IDEs)
  - commands/ (direct copy, content identical across IDEs)
  - hooks/   (direct copy, IDE-agnostic implementations)

settings.json and mcp.json are generated only if they don't exist (for new workspace init).
Existing settings.json/mcp.json are preserved to allow user customization.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

# IDE configurations
IDE_CONFIGS = {
    "qoder": {
        "name": "Qoder",
        "dir": ".qoder",
    },
    "claude": {
        "name": "Claude",
        "dir": ".claude",
    },
}

# Directories to copy directly (no templating)
DIRECT_COPY_DIRS = ["skills", "commands", "hooks"]

# Directories with template substitution
TEMPLATE_DIRS = ["rules"]


def substitute_template(content: str, ide_name: str, ide_dir: str) -> str:
    """Replace template variables in content."""
    return content.replace("{IDE_NAME}", ide_name).replace("{IDE_DIR}", ide_dir)


def sync_ide(scholar_source: Path, target_root: Path, ide_config: dict, dry_run: bool = False) -> dict:
    """Sync .scholar/ to a specific IDE directory.

    Returns dict with stats: {"copied": N, "templated": N, "generated": N}
    """
    ide_name = ide_config["name"]
    ide_dir_name = ide_config["dir"]
    ide_target = target_root / ide_dir_name

    stats = {"copied": 0, "templated": 0, "generated": 0}

    if not dry_run:
        ide_target.mkdir(parents=True, exist_ok=True)

    # 1. Copy direct-copy directories (skills, commands, hooks)
    for subdir in DIRECT_COPY_DIRS:
        src = scholar_source / subdir
        if not src.exists():
            continue
        dst = ide_target / subdir
        if dry_run:
            for f in src.rglob("*"):
                if f.is_file():
                    stats["copied"] += 1
        else:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            for f in src.rglob("*"):
                if f.is_file():
                    stats["copied"] += 1

    # 2. Copy templated directories (rules)
    for subdir in TEMPLATE_DIRS:
        src = scholar_source / subdir
        if not src.exists():
            continue
        dst = ide_target / subdir
        if dry_run:
            for f in src.rglob("*"):
                if f.is_file():
                    stats["templated"] += 1
        else:
            if dst.exists():
                shutil.rmtree(dst)
            dst.mkdir(parents=True)
            for f in src.rglob("*"):
                if f.is_file():
                    content = f.read_text(encoding="utf-8")
                    templated = substitute_template(content, ide_name, ide_dir_name)
                    rel_path = f.relative_to(src)
                    out_file = dst / rel_path
                    out_file.parent.mkdir(parents=True, exist_ok=True)
                    out_file.write_text(templated, encoding="utf-8")
                    stats["templated"] += 1

    # 3. Generate settings.json (only if not exists)
    settings_path = ide_target / "settings.json"
    if not settings_path.exists():
        settings = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/task-done.ps1"}]},
                    {"hooks": [{"type": "command", "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/log-conversation.ps1"}]},
                ],
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/block-dangerous.ps1"}]},
                ],
                "PostToolUse": [
                    {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/verify-citations.ps1"}]},
                ],
            }
        }
        if not dry_run:
            settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
            stats["generated"] += 1
    else:
        # Update hook paths in existing settings.json (in case hooks changed)
        if not dry_run:
            try:
                existing = json.loads(settings_path.read_text(encoding="utf-8"))
                # Only update if hooks structure exists
                if "hooks" in existing:
                    hooks = existing["hooks"]
                    if "Stop" in hooks:
                        for i, stop_hook in enumerate(hooks["Stop"]):
                            if i < 2 and "hooks" in stop_hook and len(stop_hook["hooks"]) > 0:
                                hook_name = ["task-done.ps1", "log-conversation.ps1"][i]
                                stop_hook["hooks"][0]["command"] = f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/{hook_name}"
                    if "PreToolUse" in hooks:
                        for pre_hook in hooks["PreToolUse"]:
                            if "hooks" in pre_hook and len(pre_hook["hooks"]) > 0:
                                pre_hook["hooks"][0]["command"] = f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/block-dangerous.ps1"
                    if "PostToolUse" in hooks:
                        for post_hook in hooks["PostToolUse"]:
                            if "hooks" in post_hook and len(post_hook["hooks"]) > 0:
                                post_hook["hooks"][0]["command"] = f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/verify-citations.ps1"
                    settings_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
            except (json.JSONDecodeError, KeyError, IndexError):
                pass  # Preserve existing if parsing fails

    # 4. Generate mcp.json (only if not exists)
    mcp_path = ide_target / "mcp.json"
    if not mcp_path.exists():
        workspace = str(target_root)
        mcp_config = {
            "mcpServers": {
                "scholar": {
                    "command": "python",
                    "args": ["-m", "scholar_mcp"],
                    "cwd": workspace,
                    "env": {
                        "SCHOLAR_HOME": workspace,
                        "SCHOLAR_WORKSPACE": workspace,
                        "PYTHONPATH": workspace,
                    }
                }
            }
        }
        if not dry_run:
            mcp_path.write_text(json.dumps(mcp_config, indent=2, ensure_ascii=False), encoding="utf-8")
            stats["generated"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Sync .scholar/ shared config to .qoder/ and .claude/ IDE directories"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check only, no writes (CI mode)"
    )
    parser.add_argument(
        "--target", type=str, default=None,
        help="Target workspace directory (default: project root)"
    )
    args = parser.parse_args()

    # Find project root (parent of scripts/)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    # Or use --target
    target_root = Path(args.target) if args.target else project_root
    scholar_source = project_root / ".scholar"

    if not scholar_source.exists():
        print(f"ERROR: .scholar/ not found at {scholar_source}")
        sys.exit(1)

    print(f"Source:  {scholar_source}")
    print(f"Target:  {target_root}")
    print(f"Mode:    {'check (dry-run)' if args.check else 'sync'}")
    print()

    total_stats = {"copied": 0, "templated": 0, "generated": 0}

    for ide_key, ide_config in IDE_CONFIGS.items():
        print(f"--- {ide_config['name']} ({ide_config['dir']}/) ---")
        stats = sync_ide(scholar_source, target_root, ide_config, dry_run=args.check)
        print(f"  Copied:     {stats['copied']} files")
        print(f"  Templated:  {stats['templated']} files")
        print(f"  Generated:  {stats['generated']} files")
        print()
        for k in total_stats:
            total_stats[k] += stats[k]

    print(f"Total: {total_stats['copied']} copied, {total_stats['templated']} templated, {total_stats['generated']} generated")

    if args.check:
        print("\nCheck mode: no files written. Run without --check to sync.")
    else:
        print("\nSync complete.")


if __name__ == "__main__":
    main()
