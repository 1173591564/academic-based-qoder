#!/usr/bin/env python3
"""
sync_dotfiles.py — Sync .qoder/ → .claude/ and plugin/ directories.

Ensures all three locations have identical rules, skills, commands, and hooks.
Use this after editing any dotfile in .qoder/ to propagate changes.

Usage:
    python scripts/sync_dotfiles.py          # dry-run (show what would change)
    python scripts/sync_dotfiles.py --apply  # actually copy files
"""
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCE = ROOT / ".qoder"
TARGETS = [
    ROOT / ".claude",
    ROOT / "plugin",
]

SUBDIRS = ["rules", "skills", "commands", "hooks"]


def md5_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def sync_dir(src_dir: Path, dst_dir: Path, apply: bool) -> list[str]:
    """Sync src_dir → dst_dir. Return list of actions."""
    actions = []
    if not src_dir.exists():
        actions.append(f"  SKIP: {src_dir} does not exist")
        return actions

    dst_dir.mkdir(parents=True, exist_ok=True)

    # Remove files in dst that don't exist in src
    for dst_file in dst_dir.rglob("*"):
        if dst_file.is_file():
            rel = dst_file.relative_to(dst_dir)
            src_file = src_dir / rel
            if not src_file.exists():
                action = f"  DELETE: {dst_file.relative_to(ROOT)}"
                if apply:
                    dst_file.unlink()
                actions.append(action)

    # Copy/update files from src to dst
    for src_file in src_dir.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_dir)
        dst_file = dst_dir / rel

        if not dst_file.exists():
            action = f"  ADD:    {dst_file.relative_to(ROOT)}"
            if apply:
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
            actions.append(action)
        else:
            src_md5 = md5_file(src_file)
            dst_md5 = md5_file(dst_file)
            if src_md5 != dst_md5:
                action = f"  UPDATE: {dst_file.relative_to(ROOT)}"
                if apply:
                    shutil.copy2(src_file, dst_file)
                actions.append(action)

    return actions


def main():
    apply = "--apply" in sys.argv

    print(f"=== Dotfiles Sync ({'APPLY' if apply else 'DRY-RUN'}) ===\n")
    print(f"Source: {SOURCE.relative_to(ROOT)}")
    print()

    total_changes = 0

    for target in TARGETS:
        print(f"Target: {target.relative_to(ROOT)}")
        for subdir in SUBDIRS:
            src = SOURCE / subdir
            dst = target / subdir
            actions = sync_dir(src, dst, apply)
            for a in actions:
                print(a)
            total_changes += len(actions)
        print()

    if total_changes == 0:
        print("All dotfiles are in sync.")
    else:
        print(f"{total_changes} change(s) {'applied' if apply else 'detected'}.")
        if not apply:
            print("Run with --apply to execute changes.")

    sys.exit(0 if total_changes == 0 or apply else 1)


if __name__ == "__main__":
    main()
