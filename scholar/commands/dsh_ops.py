"""dsh_ops.py — dsh (deepseek-harness) 接入命令。

`scholar init-dsh`：把 Scholar Studio 以三层原生插件（工具/技能/人格）挂进 dsh headless
profile——wheel 自带插件模板（scholar/templates/dsh/），团队新成员装包后一条命令即完成接入，
无需手动维护 cordis.patch.yml。

写入 ~/.dsh/profiles/headless/cordis.patch.yml 的 >>> scholar <<< 段（幂等、可回滚，
与其它实验段共存）：
  1. mcp-scholar      dsh-mcp-client：stdio 挂 `python -m scholar_mcp`（55 工具）
                      SCHOLAR_HOME=本 CLI 解析的知识库根；SCHOLAR_WORKSPACE=!!js process.cwd()
                      （任意目录启动 dsh，该目录即工作区——全局挂载的核心机制）
  2. scholar-skills   隔离 skill-filesystem 实例 → <SCHOLAR_HOME>/.scholar/skills（15 技能）
  3. scholar-native   人格 + 文献环境注入插件（file:// 指向包内模板或 --plugin 指定）

用法：
  scholar init-dsh                # 安装/刷新（自动探测 dev/global 形态）
  scholar init-dsh --check        # 前置校验 + 打印当前 patch 段
  scholar init-dsh --uninstall    # 卸载（只删自己的段）
"""

import re
import shutil
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from scholar import config
from scholar._shared import app

console = Console()

MARKER = "# >>> scholar"
END_MARKER = "# <<< scholar"


def _y(p) -> str:
    return str(p).replace("\\", "/")


def _patch_path(dsh_home: Path, profile: str) -> Path:
    return dsh_home / "profiles" / profile / "cordis.patch.yml"


def _plugin_url(plugin: Path) -> str:
    """file:// URL——保留非 ASCII 原文（dsh loader 已验证接受裸 Unicode 路径；
    Path.as_uri() 的 percent-encoding 未验证，不用）。"""
    p = _y(Path(plugin).resolve())
    return ("file://" + p) if p.startswith("/") else ("file:///" + p)


def _detect_dev_tree(scholar_home: Path) -> bool:
    """源码树（editable/源码运行）判定：scholar 包与 .scholar/ 同根。"""
    return (Path(scholar_home) / "scholar" / "__init__.py").exists() and (
        Path(scholar_home) / "scholar_mcp"
    ).exists()


def _plugin_template() -> Path:
    """包内插件模板（dev 源码树与 pip 安装均在 templates/dsh/ 下）。"""
    return (
        Path(__file__).resolve().parent.parent
        / "templates"
        / "dsh"
        / "scholar-native.mjs"
    )


def _build_patch_block(
    scholar_home: Path, python_cmd: str, plugin_url: str, dev_tree: bool
) -> str:
    env_lines = [
        "        env:",
        f'          SCHOLAR_HOME: "{_y(scholar_home)}"',
        "          SCHOLAR_WORKSPACE: !!js process.cwd()",
    ]
    if dev_tree:
        env_lines.append(f'          PYTHONPATH: "{_y(scholar_home)}"')
    skills_dir = Path(scholar_home) / ".scholar" / "skills"
    return f"""{MARKER}
- insert:
    - id: mcp-scholar
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: scholar
        transport: stdio
        command: "{_y(python_cmd)}"
        args: ['-m', 'scholar_mcp']
{chr(10).join(env_lines)}
        failOnStartupError: false
    - id: scholar-skills
      name: '@deepseek-ai/dsh-skill-filesystem'
      config:
        providerName: scholar
        includeDefaultRoots: false
        customSkillDirs:
          - "{_y(skills_dir)}"
    - id: scholar-native
      name: {plugin_url}
      config:
        scholarHome: "{_y(scholar_home)}"
{END_MARKER}"""


def _preflight(scholar_home: Path, python_cmd: str, plugin: Path):
    problems = []
    skills_dir = Path(scholar_home) / ".scholar" / "skills"
    console.print(f"[preflight] python={python_cmd}")
    console.print(f"[preflight] SCHOLAR_HOME={scholar_home}")
    try:
        import importlib

        importlib.import_module("scholar_mcp")
        console.print("[preflight] [OK] scholar_mcp 可导入（MCP server 将随 dsh 启动）")
    except Exception as e:  # pragma: no cover
        problems.append(f"scholar_mcp 不可导入: {e}")
    if skills_dir.exists():
        n = len([d for d in skills_dir.iterdir() if not d.name.startswith(".")])
        console.print(f"[preflight] [OK] 技能目录: {n} 个技能 @ {skills_dir}")
        if n == 0:
            problems.append(f"技能目录为空（先 scholar init）: {skills_dir}")
    else:
        problems.append(
            f"技能目录不存在（先 scholar init 或 --scholar-home）: {skills_dir}"
        )
    if plugin.exists():
        console.print(f"[preflight] [OK] 插件模板: {plugin}")
    else:
        problems.append(f"插件模板缺失: {plugin}")
    parsed = Path(scholar_home) / "output" / "parsed"
    if parsed.exists():
        console.print(
            f"[preflight] [OK] parsed 目录: {len(list(parsed.glob('*.json')))} 篇（动态层索引源）"
        )
    else:
        console.print(
            "[preflight] [WARN] parsed 目录缺失——动态层注入将为空，工具层不受影响"
        )
    return problems


def _write_segment(patch: Path, block: str) -> str:
    """幂等写入 >>> scholar <<< 段，返回动作描述。"""
    patch.parent.mkdir(parents=True, exist_ok=True)
    prev = patch.read_text(encoding="utf-8") if patch.exists() else ""
    if MARKER in prev:
        seg = re.compile(re.escape(MARKER) + r"[\s\S]*?" + re.escape(END_MARKER), re.M)
        patch.write_text(seg.sub(block.strip(), prev), encoding="utf-8")
        return "refreshed"
    stripped = re.sub(r"^\s*\[\]\s*\n?", "", prev).rstrip()
    patch.write_text(
        (stripped + "\n\n" + block + "\n") if stripped else (block + "\n"),
        encoding="utf-8",
    )
    return "appended"


def _remove_segment(patch: Path):
    if not patch.exists() or MARKER not in patch.read_text(encoding="utf-8"):
        console.print("[uninstall] 无 scholar 段，skip")
        return
    prev = patch.read_text(encoding="utf-8")
    seg = re.compile(
        r"\n?" + re.escape(MARKER) + r"[\s\S]*?" + re.escape(END_MARKER) + r"\n?", re.M
    )
    patch.write_text(
        seg.sub("\n", prev).replace("\n\n\n", "\n\n").lstrip("\n"),
        encoding="utf-8",
    )
    console.print(f"[uninstall] removed scholar block @ {patch}")


@app.command()
def init_dsh(
    uninstall: bool = typer.Option(
        False, "--uninstall", help="移除 >>> scholar <<< 段"
    ),
    check: bool = typer.Option(False, "--check", help="仅校验并打印当前段，不写入"),
    profile: str = typer.Option("headless", help="dsh profile（本期仅支持 headless）"),
    dsh_home: Path = typer.Option(None, "--dsh-home", help="dsh 配置根（默认 ~/.dsh）"),
    scholar_home: Path = typer.Option(
        None, "--scholar-home", help="知识库根（默认本 CLI 解析值）"
    ),
    python_cmd: Path = typer.Option(
        None, "--python", help="MCP server 解释器（默认本 CLI 的 sys.executable）"
    ),
    plugin: Path = typer.Option(
        None,
        "--plugin",
        help="scholar-native.mjs 路径（默认包内模板；开发时指向 examples）",
    ),
):
    """把 Scholar Studio 挂进 dsh（三层原生插件：55 工具 + 15 技能 + 学术人格）。"""
    if profile != "headless":
        console.print("[!] 本期仅支持 headless profile")
        raise typer.Exit(2)

    dsh_home = Path(dsh_home) if dsh_home else Path.home() / ".dsh"
    scholar_home = Path(scholar_home) if scholar_home else Path(config.SCHOLAR_HOME)
    py = str(python_cmd) if python_cmd else sys.executable
    plugin = Path(plugin) if plugin else _plugin_template()
    patch = _patch_path(dsh_home, profile)
    dev_tree = _detect_dev_tree(scholar_home)

    if uninstall:
        _remove_segment(patch)
        return

    problems = _preflight(scholar_home, py, plugin)
    if problems:
        console.print("\n[red]前置校验未通过:[/]")
        for p in problems:
            console.print(f"  - {p}")
        raise typer.Exit(1)

    block = _build_patch_block(scholar_home, py, _plugin_url(plugin), dev_tree)
    if check:
        console.print(Panel(block, title=f"{patch} (preview)", border_style="cyan"))
        if patch.exists() and MARKER in patch.read_text(encoding="utf-8"):
            console.print("[green]已安装（如需刷新请去掉 --check）[/]")
        else:
            console.print("[yellow]未安装（去掉 --check 执行写入）[/]")
        return

    action = _write_segment(patch, block)
    console.print(f"[green][OK][/] {action} scholar block @ {patch}")
    console.print("\n验证：")
    console.print('  dsh --profile headless "用 scholar 工具查一下知识库规模"')
    console.print("\n卸载：")
    console.print("  scholar init-dsh --uninstall")
