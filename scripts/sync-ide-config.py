#!/usr/bin/env python
"""Project shared IDE templates into package, Qoder, and Claude layouts.

The repository's ``.scholar/`` directory is the canonical source. The
``scholar/templates/`` tree is its package-distribution mirror, while
``.qoder/`` and ``.claude/`` are generated IDE-specific projections.
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scholar.ide_templates import (
    DIRECT_COPY_DIRS,
    SHARED_DIRS,
    TEMPLATE_DIRS,
    substitute_template,
    sync_ide_templates,
    sync_package_templates,
)

IDE_CONFIGS = {
    "qoder": {"name": "Qoder", "dir": ".qoder", "entry": ""},
    "claude": {"name": "Claude", "dir": ".claude", "entry": "CLAUDE.md"},
}


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sync_ide(
    source: Path,
    target_root: Path,
    ide_config: dict[str, str],
) -> dict[str, int]:
    ide_name = ide_config["name"]
    ide_dir_name = ide_config["dir"]
    ide_target = target_root / ide_dir_name
    template_stats = sync_ide_templates(
        source,
        target_root,
        ide_name=ide_name,
        ide_dir=ide_dir_name,
        entry_file=ide_config["entry"] or None,
    )
    stats = {
        "copied": template_stats.copied,
        "templated": template_stats.templated,
        "generated": 0,
    }

    settings_path = ide_target / "settings.json"
    if not settings_path.exists():
        _write_json(
            settings_path,
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "powershell.exe -ExecutionPolicy Bypass "
                                        f"-File {ide_dir_name}/hooks/task-done.ps1"
                                    ),
                                }
                            ]
                        },
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "powershell.exe -ExecutionPolicy Bypass "
                                        f"-File {ide_dir_name}/hooks/log-conversation.ps1"
                                    ),
                                }
                            ]
                        },
                    ],
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "powershell.exe -ExecutionPolicy Bypass "
                                        f"-File {ide_dir_name}/hooks/block-dangerous.ps1"
                                    ),
                                }
                            ],
                        }
                    ],
                    "PostToolUse": [
                        {
                            "matcher": "Write|Edit",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "powershell.exe -ExecutionPolicy Bypass "
                                        f"-File {ide_dir_name}/hooks/verify-citations.ps1"
                                    ),
                                }
                            ],
                        }
                    ],
                }
            },
        )
        stats["generated"] += 1

    mcp_path = ide_target / "mcp.json"
    if not mcp_path.exists():
        workspace = str(target_root.resolve())
        _write_json(
            mcp_path,
            {
                "mcpServers": {
                    "scholar": {
                        "command": "python",
                        "args": ["-m", "scholar_mcp"],
                        "cwd": workspace,
                        "env": {
                            "SCHOLAR_HOME": workspace,
                            "PYTHONPATH": workspace,
                        },
                    }
                }
            },
        )
        stats["generated"] += 1

    return stats


def _verify_file(
    source_file: Path,
    target_file: Path,
    *,
    ide_name: str | None = None,
    ide_dir: str | None = None,
) -> str | None:
    if not target_file.exists():
        return f"missing: {target_file}"

    expected = source_file.read_text(encoding="utf-8")
    if ide_name is not None and ide_dir is not None:
        expected = substitute_template(expected, ide_name, ide_dir)
    if target_file.read_text(encoding="utf-8") != expected:
        return f"out of sync: {target_file}"
    return None


def _relative_files(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {
        path.relative_to(directory)
        for path in directory.rglob("*")
        if path.is_file()
    }


def _verify_tree(
    source_dir: Path,
    target_dir: Path,
    *,
    ide_name: str | None = None,
    ide_dir: str | None = None,
) -> list[str]:
    issues: list[str] = []
    source_files = _relative_files(source_dir)
    target_files = _relative_files(target_dir)

    for relative_path in sorted(source_files | target_files):
        if relative_path not in source_files:
            issues.append(f"unexpected: {target_dir / relative_path}")
        elif relative_path not in target_files:
            issues.append(f"missing: {target_dir / relative_path}")
        else:
            issue = _verify_file(
                source_dir / relative_path,
                target_dir / relative_path,
                ide_name=ide_name,
                ide_dir=ide_dir,
            )
            if issue:
                issues.append(issue)
    return issues


def verify_package_templates(source: Path, package_templates: Path) -> list[str]:
    issues: list[str] = []
    for directory in SHARED_DIRS:
        issues.extend(
            _verify_tree(source / directory, package_templates / directory)
        )

    issue = _verify_file(
        source / "IDE_ENTRY.md",
        package_templates / "IDE_ENTRY.md",
    )
    if issue:
        issues.append(issue)
    return issues


def verify_ide(
    source: Path,
    target_root: Path,
    ide_config: dict[str, str],
) -> list[str]:
    issues: list[str] = []
    ide_target = target_root / ide_config["dir"]

    for directory in DIRECT_COPY_DIRS:
        issues.extend(_verify_tree(source / directory, ide_target / directory))

    for directory in TEMPLATE_DIRS:
        issues.extend(
            _verify_tree(
                source / directory,
                ide_target / directory,
                ide_name=ide_config["name"],
                ide_dir=ide_config["dir"],
            )
        )

    entry_file = ide_config["entry"]
    if entry_file:
        issue = _verify_file(
            source / "IDE_ENTRY.md",
            ide_target / entry_file,
            ide_name=ide_config["name"],
            ide_dir=ide_config["dir"],
        )
        if issue:
            issues.append(issue)
    return issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync canonical .scholar templates to generated projections"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify projections without writing files",
    )
    parser.add_argument(
        "--target",
        type=Path,
        help="target workspace (default: repository root)",
    )
    args = parser.parse_args()

    target_root = args.target.resolve() if args.target else PROJECT_ROOT
    source = PROJECT_ROOT / ".scholar"
    package_templates = PROJECT_ROOT / "scholar" / "templates"

    if not source.exists():
        print(f"ERROR: canonical template directory not found: {source}")
        raise SystemExit(1)

    if not args.check:
        if target_root == PROJECT_ROOT:
            count = sync_package_templates(source, package_templates)
            print(f"Package mirror: {count} files")
        for ide_config in IDE_CONFIGS.values():
            stats = sync_ide(source, target_root, ide_config)
            print(
                f"{ide_config['name']}: "
                f"{stats['copied']} copied, "
                f"{stats['templated']} templated, "
                f"{stats['generated']} generated"
            )

    issues: list[str] = []
    if target_root == PROJECT_ROOT:
        issues.extend(verify_package_templates(source, package_templates))
    for ide_config in IDE_CONFIGS.values():
        issues.extend(verify_ide(source, target_root, ide_config))

    if issues:
        print("Generated templates are out of sync:")
        for issue in issues:
            print(f"  - {issue}")
        print("Run: python scripts/sync-ide-config.py")
        raise SystemExit(1)

    print("Template projections are in sync.")


if __name__ == "__main__":
    main()
