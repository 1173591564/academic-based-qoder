"""dsh_ops.py — dsh (deepseek-harness) 接入命令。

`scholar init-dsh` 把 Scholar Studio 以原生插件挂进 dsh，双通道：

1. **用户级预设** ~/.dsh/.agent-presets/academic/（本命令的核心产物）
   standard 预设全量行 + scholar 三层插件，Web UI「自定义」组直接出现
   「学术模式」；preset.yml 仅 name/description/order 元数据，trust=user。
2. **headless patch** ~/.dsh/profiles/headless/cordis.patch.yml 的 >>> scholar <<<
   段——headless bundle 无 preset roster，CLI one-shot 只能走 profile patch
   （与其它实验段共存，幂等可回滚）。

三层插件（两通道同构）：
  1. mcp-scholar      dsh-mcp-client：stdio 挂 `python -m scholar_mcp`（16 工具阅读阶梯）
                      SCHOLAR_HOME=本 CLI 解析的知识库根；SCHOLAR_WORKSPACE=学术工作区
                      （patch 用 !!js process.cwd() 随启动目录；预设按会话挂载、
                      组装每进程只装载一次，cwd 语义失效——改为 init-dsh 时静态烘焙）
  2. scholar-skills   skill-filesystem 实例 → <SCHOLAR_HOME>/.scholar/skills（15 技能）
  3. scholar-native   人格 + 文献环境注入插件（file:// 指向包内模板或 --plugin 指定）

用法：
  scholar init-dsh                # 安装/刷新（自动探测 dev/global 形态）
  scholar init-dsh --check        # 前置校验 + 打印当前段
  scholar init-dsh --uninstall    # 卸载（删 patch 段 + 预设目录）
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


def _preset_dir(dsh_home: Path) -> Path:
    return dsh_home / ".agent-presets" / "academic"


def _preset_base_template() -> Path:
    """预设基座：dsh standard 预设的全量插件行（复制时点见文件头注释）。"""
    return (
        Path(__file__).resolve().parent.parent
        / "templates"
        / "dsh"
        / "preset"
        / "base.agent.cordis.yml"
    )


def _mcp_scholar_row(
    python_cmd: str,
    scholar_home: Path,
    workspace: Path,
    dev_tree: bool,
    remote_url: str | None,
    indent: str,
    token: str | None = None,
) -> str:
    """mcp-scholar 插件行。remote_url 非空时走 streamable-http（服务器集中部署，
    数据零分发；token 非空时附 Bearer 鉴权头），否则 stdio 本地子进程。
    indent 为行缩进前缀（patch 4 空格、预设 0 空格）。"""
    i = indent
    if remote_url:
        headers = ""
        if token:
            headers = f'{i}    headers:\n{i}      Authorization: "Bearer {token}"\n'
        return f"""{i}- id: mcp-scholar
{i}  name: '@deepseek-ai/dsh-mcp-client'
{i}  config:
{i}    serverName: scholar
{i}    transport: streamable-http
{i}    url: "{remote_url}"
{headers}{i}    failOnStartupError: false
"""
    env_lines = [
        f"{i}    env:",
        f'{i}      SCHOLAR_HOME: "{_y(scholar_home)}"',
        f'{i}      SCHOLAR_WORKSPACE: "{_y(workspace)}"',
    ]
    if dev_tree:
        env_lines.append(f'{i}      PYTHONPATH: "{_y(scholar_home)}"')
    return f"""{i}- id: mcp-scholar
{i}  name: '@deepseek-ai/dsh-mcp-client'
{i}  config:
{i}    serverName: scholar
{i}    transport: stdio
{i}    command: "{_y(python_cmd)}"
{i}    args: ['-m', 'scholar_mcp']
{chr(10).join(env_lines)}
{i}    failOnStartupError: false
"""


def _build_patch_block(
    scholar_home: Path,
    python_cmd: str,
    plugin_url: str,
    dev_tree: bool,
    workspace: Path | None = None,
    remote_url: str | None = None,
    token: str | None = None,
) -> str:
    if workspace is None:
        workspace = scholar_home
    if remote_url:
        mcp_row = _mcp_scholar_row(
            python_cmd,
            scholar_home,
            workspace,
            dev_tree,
            remote_url,
            "    ",
            token=token,
        )
        skills_dir = Path(scholar_home) / ".scholar" / "skills"
        return f"""{MARKER}
- insert:
{mcp_row.rstrip()}
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


def _preflight(scholar_home: Path, python_cmd: str, plugin: Path, remote: bool = False):
    problems = []
    skills_dir = Path(scholar_home) / ".scholar" / "skills"
    console.print(f"[preflight] python={python_cmd}")
    console.print(f"[preflight] SCHOLAR_HOME={scholar_home}")
    if remote:
        console.print("[preflight] 模式=remote（MCP over HTTP，本地无论文数据）")
    else:
        try:
            import importlib

            importlib.import_module("scholar_mcp")
            console.print(
                "[preflight] [OK] scholar_mcp 可导入（MCP server 将随 dsh 启动）"
            )
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


def _ensure_rules(scholar_home: Path) -> list[str]:
    """把包内 rules 模板（templates/dsh/rules/）落到 <scholar_home>/.scholar/rules/，
    copy-if-missing——绝不覆盖用户自定义。返回动作列表。"""
    actions = []
    src_dir = Path(__file__).resolve().parent.parent / "templates" / "dsh" / "rules"
    if not src_dir.exists():
        return actions
    dst_dir = Path(scholar_home) / ".scholar" / "rules"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for f in src_dir.iterdir():
        if not f.is_file():
            continue
        dst = dst_dir / f.name
        if not dst.exists():
            shutil.copyfile(f, dst)
            actions.append(f"rule installed: {dst.name}")
    return actions


def _build_preset_rows(
    scholar_home: Path,
    workspace: Path,
    python_cmd: str,
    plugin_url: str,
    dev_tree: bool,
    remote_url: str | None = None,
    token: str | None = None,
) -> str:
    """预设组装的 scholar 段——结构与 headless patch 同构，两处差异：
    SCHOLAR_WORKSPACE 静态烘焙（预设组装每进程装载一次，cwd 语义失效）；
    结构与 standard 预设的裸 skill-filesystem 行保持一致（登记进分层
    registry，不发布进程级服务，无需 isolate realm）。"""
    mcp_row = _mcp_scholar_row(
        python_cmd,
        scholar_home,
        workspace,
        dev_tree,
        remote_url,
        "",
        token=token,
    )
    skills_dir = Path(scholar_home) / ".scholar" / "skills"
    return f"""# ── scholar（由 `scholar init-dsh` 生成/刷新，勿手改）──────────────────────
{mcp_row.rstrip()}

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
"""


def _write_preset(
    dsh_home: Path,
    scholar_home: Path,
    workspace: Path,
    python_cmd: str,
    plugin_url: str,
    dev_tree: bool,
    remote_url: str | None = None,
    token: str | None = None,
) -> str:
    """写用户级 academic 预设（standard 基座 + scholar 段，整文件重写、幂等）。"""
    base = _preset_base_template().read_text(encoding="utf-8")
    rows = _build_preset_rows(
        scholar_home,
        workspace,
        python_cmd,
        plugin_url,
        dev_tree,
        remote_url=remote_url,
        token=token,
    )
    pdir = _preset_dir(dsh_home)
    pdir.mkdir(parents=True, exist_ok=True)
    header = (
        "# The `academic` agent preset — generated by `scholar init-dsh`.\n"
        "# Base: dsh `standard` preset rows (verbatim copy, refresh on init-dsh)\n"
        "# + scholar rows appended below. Regenerated wholesale on every\n"
        "# `scholar init-dsh`; hand edits will be lost.\n\n"
    )
    (pdir / "agent.cordis.yml").write_text(
        header + base.rstrip() + "\n\n" + rows, encoding="utf-8"
    )
    meta = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / "dsh"
        / "preset"
        / "preset.yml"
    )
    shutil.copyfile(meta, pdir / "preset.yml")
    return str(pdir)


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


def _remove_preset(dsh_home: Path):
    pdir = _preset_dir(dsh_home)
    if not pdir.exists():
        return
    shutil.rmtree(pdir)
    console.print(f"[uninstall] removed preset dir @ {pdir}")


@app.command()
def init_dsh(
    uninstall: bool = typer.Option(
        False, "--uninstall", help="移除 >>> scholar <<< 段与 academic 预设目录"
    ),
    check: bool = typer.Option(False, "--check", help="仅校验并打印当前段，不写入"),
    profile: str = typer.Option("headless", help="dsh profile（CLI one-shot 用）"),
    dsh_home: Path = typer.Option(None, "--dsh-home", help="dsh 配置根（默认 ~/.dsh）"),
    scholar_home: Path = typer.Option(
        None, "--scholar-home", help="知识库根（默认本 CLI 解析值）"
    ),
    workspace: Path = typer.Option(
        None,
        "--workspace",
        help="学术工作区（论文/笔记根；默认当前目录；预设静态烘焙）",
    ),
    python_cmd: Path = typer.Option(
        None, "--python", help="MCP server 解释器（默认本 CLI 的 sys.executable）"
    ),
    plugin: Path = typer.Option(
        None,
        "--plugin",
        help="scholar-native.mjs 路径（默认包内模板；开发时指向 examples）",
    ),
    remote: str = typer.Option(
        None,
        "--remote",
        help="服务器集中模式：scholar_mcp 的 streamable-http URL "
        "（如 http://<服务器IP>:9845/mcp 或隧道 http://127.0.0.1:9845/mcp）。"
        "本地无论文数据、无需 PG 凭据；服务器由管理员部署（scholar_mcp + 数据私有）",
    ),
    token: str = typer.Option(
        None,
        "--token",
        help="服务器 Bearer token（管理员私发；服务器设了 SCHOLAR_MCP_TOKEN 时必填）",
    ),
):
    """把 Scholar Studio 挂进 dsh（学术模式预设 + headless one-shot patch）。"""
    dsh_home = Path(dsh_home) if dsh_home else Path.home() / ".dsh"
    scholar_home = Path(scholar_home) if scholar_home else Path(config.SCHOLAR_HOME)
    workspace = Path(workspace) if workspace else Path.cwd()
    py = str(python_cmd) if python_cmd else sys.executable
    plugin = Path(plugin) if plugin else _plugin_template()
    patch = _patch_path(dsh_home, profile)
    dev_tree = _detect_dev_tree(scholar_home)

    if uninstall:
        _remove_segment(patch)
        _remove_preset(dsh_home)
        return

    problems = _preflight(scholar_home, py, plugin, remote=bool(remote))
    if problems:
        console.print("\n[red]前置校验未通过:[/]")
        for p in problems:
            console.print(f"  - {p}")
        raise typer.Exit(1)

    block = _build_patch_block(
        scholar_home,
        py,
        _plugin_url(plugin),
        dev_tree,
        workspace=workspace,
        remote_url=remote,
        token=token,
    )
    if check:
        console.print(Panel(block, title=f"{patch} (preview)", border_style="cyan"))
        if patch.exists() and MARKER in patch.read_text(encoding="utf-8"):
            console.print("[green]已安装（如需刷新请去掉 --check）[/]")
        else:
            console.print("[yellow]未安装（去掉 --check 执行写入）[/]")
        return

    action = _write_segment(patch, block)
    console.print(f"[green][OK][/] {action} scholar block @ {patch}")
    pdir = _write_preset(
        dsh_home,
        scholar_home,
        workspace,
        py,
        _plugin_url(plugin),
        dev_tree,
        remote_url=remote,
        token=token,
    )
    console.print(f"[green][OK][/] academic preset written @ {pdir}")
    for r in _ensure_rules(scholar_home):
        console.print(f"[green][OK][/] {r}")
    console.print("\n验证：")
    console.print('  dsh --profile headless "用 scholar 工具查一下知识库规模"')
    console.print("  Web UI → 设置 → Agent 预设 → 自定义 →「学术模式」开新会话")
    if remote:
        console.print(f"\n[bold]remote 模式[/]：MCP 端点 = {remote}")
        console.print("隧道模式示例：ssh -N -L 9845:127.0.0.1:9845 server-47")
        if token:
            console.print("Bearer 鉴权已配置（token 写入本地预设/patch，勿外传）")
    console.print("\n卸载：")
    console.print("  scholar init-dsh --uninstall")
