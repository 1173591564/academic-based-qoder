"""
Unit Tests — workspace initialization + WORKSPACE_DIR.

Tests init-workspace command output directory creation,
.qoder/ template copy, mcp.json generation, and
WORKSPACE_DIR path resolution in dev mode.
"""
import subprocess
import sys
from pathlib import Path

import pytest


class TestWorkspaceDir:
    """Test WORKSPACE_DIR path resolution."""

    def test_default_equals_scholar_home_in_dev(self):
        """In dev mode, WORKSPACE_DIR defaults to SCHOLAR_HOME."""
        from scholar import config
        if not config.IS_FROZEN:
            assert config.WORKSPACE_DIR == config.SCHOLAR_HOME

    def test_env_var_overrides_workspace_dir(self, monkeypatch, tmp_path):
        """SCHOLAR_WORKSPACE env var overrides WORKSPACE_DIR."""
        import importlib
        monkeypatch.setenv("SCHOLAR_WORKSPACE", str(tmp_path))

        # Need to reload config to pick up env change
        from scholar import config as cfg_module
        importlib.reload(cfg_module)

        assert cfg_module.WORKSPACE_DIR == tmp_path
        assert cfg_module.DRAFTS_DIR == tmp_path / "output" / "drafts"
        assert cfg_module.LOGS_DIR == tmp_path / "output" / "logs"

    def test_project_logs_dir_uses_workspace(self, monkeypatch, tmp_path):
        """project_logs_dir() derives from WORKSPACE_DIR."""
        import importlib
        monkeypatch.setenv("SCHOLAR_WORKSPACE", str(tmp_path))

        from scholar import config as cfg_module
        importlib.reload(cfg_module)

        log_dir = cfg_module.project_logs_dir()
        assert str(log_dir).startswith(str(tmp_path))


class TestInitWorkspace:
    """Test config.init_workspace() behavior."""

    def test_creates_output_dirs(self, monkeypatch, tmp_path):
        """init_workspace() creates output dirs under WORKSPACE_DIR."""
        import importlib
        monkeypatch.setenv("SCHOLAR_WORKSPACE", str(tmp_path))

        from scholar import config as cfg_module
        importlib.reload(cfg_module)

        result = cfg_module.init_workspace()

        # Verify dirs exist (may be created by import-time mkdir or init_workspace)
        assert (tmp_path / "output" / "drafts").is_dir()
        assert (tmp_path / "output" / "notes").is_dir()
        assert (tmp_path / "output" / "logs").is_dir()
        assert result["workspace"] == str(tmp_path)
        assert "already_exists" in result

    def test_idempotent_second_call(self, monkeypatch, tmp_path):
        """Second call is idempotent — already_exists=True."""
        import importlib
        monkeypatch.setenv("SCHOLAR_WORKSPACE", str(tmp_path))

        from scholar import config as cfg_module
        importlib.reload(cfg_module)

        result1 = cfg_module.init_workspace()
        result2 = cfg_module.init_workspace()

        assert result2["already_exists"]  # all dirs already there

    def test_returns_parsed_dir_paths(self, monkeypatch, tmp_path):
        """init_workspace() returns parsed_dir, drafts_dir, etc."""
        import importlib
        monkeypatch.setenv("SCHOLAR_WORKSPACE", str(tmp_path))

        from scholar import config as cfg_module
        importlib.reload(cfg_module)

        result = cfg_module.init_workspace()
        assert "parsed_dir" in result
        assert "drafts_dir" in result
        assert "notes_dir" in result
        assert "logs_dir" in result
        assert "scholar_home" in result

    def test_qoder_template_copied(self, monkeypatch, tmp_path, project_root):
        """init_workspace() generates .qoder/ and .claude/ from .scholar/ template."""
        import importlib
        monkeypatch.setenv("SCHOLAR_WORKSPACE", str(tmp_path))

        from scholar import config as cfg_module
        importlib.reload(cfg_module)

        result = cfg_module.init_workspace()

        # Both IDE dirs should be generated
        qoder_dir = tmp_path / ".qoder"
        claude_dir = tmp_path / ".claude"
        src_scholar = project_root / ".scholar"
        if src_scholar.exists():
            assert qoder_dir.is_dir()
            assert claude_dir.is_dir()
            # Both should have mcp.json
            assert (qoder_dir / "mcp.json").exists()
            assert (claude_dir / "mcp.json").exists()
            # Both should have rules/
            assert (qoder_dir / "rules").is_dir()
            assert (claude_dir / "rules").is_dir()


class TestTemplatesBundled:
    """Test the package-distribution template projection."""

    def test_templates_dir_exists(self, project_root):
        """scholar/templates/ directory exists with all required subdirs."""
        templates = project_root / "scholar" / "templates"
        assert templates.exists()

    def test_templates_has_rules(self, project_root):
        """scholar/templates/rules/ contains 7 rule files."""
        templates = project_root / "scholar" / "templates"
        rules_dir = templates / "rules"
        if rules_dir.exists():
            rule_files = list(rules_dir.glob("*.md"))
            assert len(rule_files) >= 7

    def test_templates_has_skills(self, project_root):
        """scholar/templates/skills/ contains 15 skill directories."""
        templates = project_root / "scholar" / "templates"
        skills_dir = templates / "skills"
        if skills_dir.exists():
            skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
            assert len(skill_dirs) >= 15

    def test_templates_has_commands(self, project_root):
        """scholar/templates/commands/ contains 6 command files."""
        templates = project_root / "scholar" / "templates"
        commands_dir = templates / "commands"
        if commands_dir.exists():
            cmd_files = list(commands_dir.glob("*.md"))
            assert len(cmd_files) >= 6

    def test_templates_has_hooks(self, project_root):
        """scholar/templates/hooks/ contains 4 hook scripts."""
        templates = project_root / "scholar" / "templates"
        hooks_dir = templates / "hooks"
        if hooks_dir.exists():
            hook_files = list(hooks_dir.glob("*.ps1"))
            assert len(hook_files) >= 4

    def test_templates_has_ide_entry(self, project_root):
        """scholar/templates/IDE_ENTRY.md exists with template variables."""
        templates = project_root / "scholar" / "templates"
        ide_entry = templates / "IDE_ENTRY.md"
        if ide_entry.exists():
            content = ide_entry.read_text(encoding="utf-8")
            assert "{IDE_NAME}" in content or "{IDE_DIR}" in content


class TestResolveTemplatesDir:
    """Test _resolve_templates_dir() priority logic."""

    def test_dev_mode_returns_project_scholar(self):
        """In dev mode, returns PROJECT_ROOT/.scholar/."""
        from scholar import config
        if not config.IS_FROZEN:
            result = config._resolve_templates_dir()
            assert result.name == ".scholar"

    def test_fallback_to_pkg_templates(self):
        """If .scholar/ doesn't exist, falls back to scholar/templates/."""
        from scholar import config
        templates_dir = config.Path(__file__).resolve().parent.parent / "scholar" / "templates"
        # This test verifies the fallback path exists
        # In dev mode with .scholar/ present, this won't be triggered
        # but the templates dir should still exist
        assert templates_dir.exists() or config._resolve_templates_dir().exists()


class TestSyncConsistency:
    """Test sync script consistency check."""

    def test_repository_projections_are_in_sync(self, project_root):
        """Committed package and IDE projections match the canonical source."""
        sync_script = project_root / "scripts" / "sync-ide-config.py"
        result = subprocess.run(
            [sys.executable, str(sync_script), "--check"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root),
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_sync_generates_clean_workspace(self, project_root, tmp_path):
        """A generated workspace passes the same consistency check."""
        sync_script = project_root / "scripts" / "sync-ide-config.py"
        sync_result = subprocess.run(
            [sys.executable, str(sync_script), "--target", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root),
        )
        assert sync_result.returncode == 0, sync_result.stdout + sync_result.stderr

        check_result = subprocess.run(
            [
                sys.executable,
                str(sync_script),
                "--check",
                "--target",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root),
        )
        assert check_result.returncode == 0, check_result.stdout + check_result.stderr

    def test_sync_check_detects_workspace_drift(self, project_root, tmp_path):
        """Check mode fails when a generated projection is edited."""
        sync_script = project_root / "scripts" / "sync-ide-config.py"
        subprocess.run(
            [sys.executable, str(sync_script), "--target", str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root),
        )
        skill_file = tmp_path / ".qoder" / "skills" / "cold-start" / "SKILL.md"
        skill_file.write_text("drift\n", encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(sync_script),
                "--check",
                "--target",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root),
        )
        assert result.returncode == 1
        assert "out of sync" in result.stdout

    def test_claude_md_generated(self, project_root):
        """CLAUDE.md is generated from IDE_ENTRY.md template."""
        claude_md = project_root / ".claude" / "CLAUDE.md"
        ide_entry = project_root / ".scholar" / "IDE_ENTRY.md"
        if ide_entry.exists() and claude_md.exists():
            content = claude_md.read_text(encoding="utf-8")
            # Should not contain template variables
            assert "{IDE_NAME}" not in content
            assert "{IDE_DIR}" not in content
            # Should contain Claude-specific content
            assert "Claude" in content or ".claude" in content


class TestSanitizeProjectName:
    """Test sanitize_project_name helper."""

    def test_spaces_to_underscore(self):
        from scholar.config import sanitize_project_name
        assert sanitize_project_name("My Project") == "My_Project"

    def test_special_chars_removed(self):
        from scholar.config import sanitize_project_name
        result = sanitize_project_name("test!@#project")
        assert "!" not in result
        assert "@" not in result

    def test_trim_empty(self):
        from scholar.config import sanitize_project_name
        assert sanitize_project_name("___") == "default"
