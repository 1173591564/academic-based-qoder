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


# ── academic 用户级预设 ────────────────────────────────────────────────────

ARGS = dict(
    scholar_home=Path("C:/papers/.scholar-studio"),
    workspace=Path("C:/papers/ws"),
    python_cmd="C:/py/python.exe",
    plugin_url="file:///C:/pkg/scholar-native.mjs",
    dev_tree=False,
)  # type: dict


def test_write_preset_creates_dir_and_files(tmp_path):
    out = dsh_ops._write_preset(tmp_path, **ARGS)
    pdir = tmp_path / ".agent-presets" / "academic"
    assert Path(out) == pdir
    comp = (pdir / "agent.cordis.yml").read_text(encoding="utf-8")
    meta = (pdir / "preset.yml").read_text(encoding="utf-8")
    # standard 基座在位
    assert "id: tool-bash" in comp and "id: persona" in comp
    # scholar 段在位，且静态烘焙
    assert "id: mcp-scholar" in comp and "id: scholar-native" in comp
    assert '"C:/py/python.exe"' in comp
    assert "C:/papers/ws" in comp
    assert "process.cwd()" not in comp.split("scholar（由")[1]
    # 元数据
    assert "学术模式" in meta and "order: 5" in meta


def test_write_preset_idempotent_wholesale_rewrite(tmp_path):
    dsh_ops._write_preset(tmp_path, **ARGS)
    pdir = tmp_path / ".agent-presets" / "academic"
    comp = pdir / "agent.cordis.yml"
    (comp).write_text("garbage", encoding="utf-8")
    dsh_ops._write_preset(tmp_path, **ARGS)
    assert "id: mcp-scholar" in comp.read_text(encoding="utf-8")
    # 幂等：无重复段
    text = comp.read_text(encoding="utf-8")
    assert text.count("id: mcp-scholar") == 1


def test_write_preset_dev_tree_adds_pythonpath(tmp_path):
    dsh_ops._write_preset(tmp_path, **{**ARGS, "dev_tree": True})
    comp = (tmp_path / ".agent-presets" / "academic" / "agent.cordis.yml").read_text(
        encoding="utf-8"
    )
    scholar_seg = comp.split("scholar（由")[1]
    assert "PYTHONPATH" in scholar_seg
    # 基座段不受污染
    assert comp.count("PYTHONPATH") == 1


def test_remove_preset(tmp_path):
    dsh_ops._write_preset(tmp_path, **ARGS)
    pdir = tmp_path / ".agent-presets" / "academic"
    assert pdir.exists()
    dsh_ops._remove_preset(tmp_path)
    assert not pdir.exists()
    dsh_ops._remove_preset(tmp_path)  # 再删不报错


# ── remote 模式（MCP over HTTP，数据零分发）────────────────────────────────


def test_remote_rows_use_streamable_http():
    row = dsh_ops._mcp_scholar_row(
        "C:/py/python.exe",
        ARGS["scholar_home"],
        ARGS["workspace"],
        False,
        "http://127.0.0.1:9845/mcp",
        "",
    )
    assert "streamable-http" in row and "url:" in row
    assert "command" not in row and "SCHOLAR_HOME" not in row


def test_remote_rows_with_token():
    row = dsh_ops._mcp_scholar_row(
        "C:/py/python.exe",
        ARGS["scholar_home"],
        ARGS["workspace"],
        False,
        "http://47.0.0.2:9845/mcp",
        "",
        token="abc123",
    )
    assert 'Authorization: "Bearer abc123"' in row
    # 无 token 时不该出现 headers
    row2 = dsh_ops._mcp_scholar_row(
        "C:/py/python.exe",
        ARGS["scholar_home"],
        ARGS["workspace"],
        False,
        "http://47.0.0.2:9845/mcp",
        "",
    )
    assert "headers" not in row2


def test_write_preset_remote(tmp_path):
    dsh_ops._write_preset(
        tmp_path, **{**ARGS, "remote_url": "http://127.0.0.1:9845/mcp"}
    )
    comp = (tmp_path / ".agent-presets" / "academic" / "agent.cordis.yml").read_text(
        encoding="utf-8"
    )
    scholar_seg = comp.split("scholar（由")[1]
    assert "streamable-http" in scholar_seg
    assert "stdio" not in scholar_seg
    # 技能与人格插件仍本地（wheel 自带，与数据无关）
    assert "scholar-skills" in scholar_seg and "scholar-native" in scholar_seg


def test_build_patch_block_remote():
    block = dsh_ops._build_patch_block(
        ARGS["scholar_home"],
        "C:/py/python.exe",
        "file:///C:/pkg/scholar-native.mjs",
        False,
        workspace=ARGS["workspace"],
        remote_url="http://127.0.0.1:9845/mcp",
    )
    assert "streamable-http" in block and "stdio" not in block
    assert block.count(dsh_ops.MARKER) == 1
