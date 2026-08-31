"""test_dsh_ops.py — init-dsh 的 patch 段管理与 rules 分发逻辑。"""

from pathlib import Path

from scholar.commands import dsh_ops

BLOCK = dsh_ops.MARKER + "\n- insert:\n    - id: x\n" + dsh_ops.END_MARKER


def test_write_segment_idempotent(tmp_path):
    patch = tmp_path / "cordis.patch.yml"
    a1 = dsh_ops._write_segment(patch, BLOCK)
    a2 = dsh_ops._write_segment(patch, BLOCK)
    assert (a1, a2) == ("appended", "refreshed")
    text = patch.read_text(encoding="utf-8")
    assert text.count(dsh_ops.MARKER) == 1
    assert text.count(dsh_ops.END_MARKER) == 1


def test_write_segment_preserves_other_blocks(tmp_path):
    patch = tmp_path / "cordis.patch.yml"
    patch.write_text(
        "# >>> other\n- insert:\n    - id: y\n# <<< other\n", encoding="utf-8"
    )
    dsh_ops._write_segment(patch, BLOCK)
    text = patch.read_text(encoding="utf-8")
    assert "# >>> other" in text and "# <<< other" in text
    assert text.count(dsh_ops.MARKER) == 1


def test_remove_segment(tmp_path):
    patch = tmp_path / "cordis.patch.yml"
    dsh_ops._write_segment(patch, BLOCK)
    dsh_ops._remove_segment(patch)
    assert dsh_ops.MARKER not in patch.read_text(encoding="utf-8")
    # 再删一次不报错
    dsh_ops._remove_segment(patch)


def test_write_segment_strips_empty_array_placeholder(tmp_path):
    patch = tmp_path / "cordis.patch.yml"
    patch.write_text("[]\n", encoding="utf-8")
    dsh_ops._write_segment(patch, BLOCK)
    text = patch.read_text(encoding="utf-8")
    assert "[]" not in text and dsh_ops.MARKER in text


def test_ensure_rules_copy_if_missing(tmp_path, monkeypatch):
    # 伪造包布局：tmp/commands/dsh_ops.py → tmp/templates/dsh/rules/
    fake_src = tmp_path / "templates" / "dsh" / "rules"
    fake_src.mkdir(parents=True)
    (fake_src / "identity.md").write_text("researcher-profile", encoding="utf-8")
    (fake_src / "academic.md").write_text("norms", encoding="utf-8")
    ops_file = tmp_path / "commands" / "dsh_ops.py"
    ops_file.parent.mkdir(parents=True)
    ops_file.write_text("# stub", encoding="utf-8")
    monkeypatch.setattr(dsh_ops, "__file__", str(ops_file))

    scholar_home = tmp_path / "home"
    actions = dsh_ops._ensure_rules(scholar_home)
    assert len(actions) == 2
    dst = scholar_home / ".scholar" / "rules" / "identity.md"
    assert dst.read_text(encoding="utf-8") == "researcher-profile"

    # 用户自定义不覆盖
    dst.write_text("user-customized", encoding="utf-8")
    (fake_src / "identity.md").write_text("template-updated", encoding="utf-8")
    actions2 = dsh_ops._ensure_rules(scholar_home)
    assert actions2 == []
    assert dst.read_text(encoding="utf-8") == "user-customized"


def test_detect_dev_tree(tmp_path):
    assert dsh_ops._detect_dev_tree(tmp_path) is False
    (tmp_path / "scholar").mkdir()
    (tmp_path / "scholar" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "scholar_mcp").mkdir()
    assert dsh_ops._detect_dev_tree(tmp_path) is True
