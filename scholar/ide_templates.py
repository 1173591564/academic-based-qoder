"""Shared template projection for IDE and package layouts."""

import shutil
from dataclasses import dataclass
from pathlib import Path


DIRECT_COPY_DIRS = ("skills", "commands", "hooks")
TEMPLATE_DIRS = ("rules",)
SHARED_DIRS = DIRECT_COPY_DIRS + TEMPLATE_DIRS


@dataclass
class SyncStats:
    copied: int = 0
    templated: int = 0


def substitute_template(content: str, ide_name: str, ide_dir: str) -> str:
    return content.replace("{IDE_NAME}", ide_name).replace("{IDE_DIR}", ide_dir)


def _copy_tree(source: Path, target: Path) -> int:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return sum(path.is_file() for path in source.rglob("*"))


def sync_package_templates(source: Path, package_templates: Path) -> int:
    """Refresh shared package assets while retaining package-only templates."""
    copied = 0
    package_templates.mkdir(parents=True, exist_ok=True)

    for directory in SHARED_DIRS:
        source_dir = source / directory
        if source_dir.exists():
            copied += _copy_tree(source_dir, package_templates / directory)

    shutil.copy2(source / "IDE_ENTRY.md", package_templates / "IDE_ENTRY.md")
    return copied + 1


def sync_ide_templates(
    source: Path,
    target_root: Path,
    *,
    ide_name: str,
    ide_dir: str,
    entry_file: str | None,
) -> SyncStats:
    target = target_root / ide_dir
    target.mkdir(parents=True, exist_ok=True)
    stats = SyncStats()

    for directory in DIRECT_COPY_DIRS:
        source_dir = source / directory
        if source_dir.exists():
            stats.copied += _copy_tree(source_dir, target / directory)

    for directory in TEMPLATE_DIRS:
        source_dir = source / directory
        target_dir = target / directory
        if not source_dir.exists():
            continue
        if target_dir.exists():
            shutil.rmtree(target_dir)
        for source_file in source_dir.rglob("*"):
            if not source_file.is_file():
                continue
            target_file = target_dir / source_file.relative_to(source_dir)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(
                substitute_template(
                    source_file.read_text(encoding="utf-8"),
                    ide_name,
                    ide_dir,
                ),
                encoding="utf-8",
            )
            stats.templated += 1

    if entry_file:
        (target / entry_file).write_text(
            substitute_template(
                (source / "IDE_ENTRY.md").read_text(encoding="utf-8"),
                ide_name,
                ide_dir,
            ),
            encoding="utf-8",
        )
        stats.templated += 1

    return stats
