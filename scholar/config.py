"""
Scholar Studio — Configuration

支持两种运行模式：
- 开发模式：PROJECT_ROOT = 源码目录（python -m scholar）
- 打包模式：PROJECT_ROOT = ~/.scholar-studio/（scholar.exe）

环境变量可通过 .env 文件或 SCHOLAR_HOME 覆盖。
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional

from .ide_templates import sync_ide_templates


# ===================================================================
# 运行模式检测
# ===================================================================


def _is_source_tree() -> bool:
    """检测是否从源码树（含 pip editable）运行。

    源码树特征：scholar/ 的父目录下同时存在 .scholar/ 与 scholar_mcp/。
    pip 非 editable 安装（site-packages）不满足该特征。
    """
    root = Path(__file__).resolve().parent.parent
    return (root / ".scholar").exists() and (root / "scholar_mcp").exists()


def _resolve_scholar_home() -> Path:
    """确定知识库根目录。

    SCHOLAR_HOME 环境变量始终最高优先。
    打包模式（frozen）: ~/.scholar-studio/
    开发模式（源码树 / pip editable）: 源码目录（scholar/ 的父目录）
    pip 全局安装（非 editable）: ~/.scholar-studio/
    """
    env = os.getenv("SCHOLAR_HOME")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path.home() / ".scholar-studio"
    if _is_source_tree():
        return Path(__file__).resolve().parent.parent
    # pip 全局安装（site-packages）：全局模式
    return Path.home() / ".scholar-studio"


SCHOLAR_HOME = _resolve_scholar_home()
PROJECT_ROOT = SCHOLAR_HOME


def _resolve_templates_dir() -> Path:
    """确定 .scholar/ 模板源目录。

    优先级：
    1. 项目根目录 .scholar/（开发模式）
    2. SCHOLAR_HOME/.scholar/（全局安装后 init 过的）
    3. scholar/templates/（包内嵌副本，pip install 后）
    """
    # 开发模式：源码目录的 .scholar/
    dev_scholar = PROJECT_ROOT / ".scholar"
    if dev_scholar.exists():
        return dev_scholar

    # 全局模式：SCHOLAR_HOME/.scholar/
    global_scholar = SCHOLAR_HOME / ".scholar"
    if global_scholar.exists():
        return global_scholar

    # 包内嵌副本（pip install 后）
    pkg_templates = Path(__file__).resolve().parent / "templates"
    if pkg_templates.exists():
        return pkg_templates

    # fallback
    return dev_scholar


def _resolve_workspace_dir() -> Path:
    """Determine workspace directory (per-project output root).

    Priority: SCHOLAR_WORKSPACE env var > frozen/pip-global cwd > SCHOLAR_HOME
    In dev mode (source tree / pip editable), equals SCHOLAR_HOME (zero behavior change).
    """
    ws = os.getenv("SCHOLAR_WORKSPACE")
    if ws:
        return Path(ws)
    if getattr(sys, "frozen", False) or not _is_source_tree():
        return Path.cwd()
    return SCHOLAR_HOME


WORKSPACE_DIR = _resolve_workspace_dir()

# 加载 .env（从 SCHOLAR_HOME 目录）
try:
    from dotenv import load_dotenv

    _env_path = SCHOLAR_HOME / ".env"
    load_dotenv(_env_path, override=False)
    # 开发模式：若 SCHOLAR_HOME 与源码目录不同，也加载源码目录的 .env
    if not getattr(sys, "frozen", False):
        _dev_env = Path(__file__).resolve().parent.parent / ".env"
        if _dev_env != _env_path and _dev_env.exists():
            load_dotenv(_dev_env, override=False)
except ImportError:
    pass

# Current project name (for per-project output directories)
PROJECT_NAME = os.getenv("SCHOLAR_PROJECT_NAME", PROJECT_ROOT.name)


def sanitize_project_name(raw: str) -> str:
    """将原始项目名转为文件系统安全的短字符串。"""
    name = re.sub(r"[^\w\-]", "_", raw.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name[:50] if name else "default"


def project_logs_dir(project_name: str = PROJECT_NAME) -> Path:
    """返回指定项目的日志目录：output/logs/<project>/"""
    d = LOGS_DIR / sanitize_project_name(project_name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def project_drafts_dir(project_name: str = PROJECT_NAME) -> Path:
    """返回指定项目的草稿目录：output/drafts/<project>/"""
    d = DRAFTS_DIR / sanitize_project_name(project_name)
    d.mkdir(parents=True, exist_ok=True)
    return d


# Data directories
PAPERS_DIR = PROJECT_ROOT / "data" / "papers"
LEAN_DIR = PROJECT_ROOT / "LEAN"

# Output directories (all generated artifacts)
OUTPUT_DIR = PROJECT_ROOT / "output"
PARSED_DIR = OUTPUT_DIR / "parsed"
NOTES_DIR = WORKSPACE_DIR / "output" / "notes"
DRAFTS_DIR = WORKSPACE_DIR / "output" / "drafts"
BIB_DIR = OUTPUT_DIR / "bib"
EXPERIMENTS_DIR = OUTPUT_DIR / "experiments"
DATASETS_DIR = OUTPUT_DIR / "datasets"
PDFS_DIR = OUTPUT_DIR / "pdfs"
DIGESTS_DIR = OUTPUT_DIR / "digests"
LOGS_DIR = WORKSPACE_DIR / "output" / "logs"
INTERESTS_FILE = OUTPUT_DIR / "research-interests.json"

# Running mode flags
IS_FROZEN = getattr(sys, "frozen", False)
IS_SOURCE_TREE = (
    (Path(__file__).resolve().parent.parent / "pyproject.toml").is_file()
    and (Path(__file__).resolve().parent.parent / ".git").exists()
)


def init_scholar_home() -> dict:
    """初始化全局知识库目录结构。

    创建 ~/.scholar-studio/ 及所有子目录，生成 .env.example。
    复制 IDE 配置模板（.scholar/）到全局目录。
    返回 {"created": [...], "already_exists": bool, "env_example": Path}
    """
    import shutil as _shutil

    created: list[str] = []
    home = SCHOLAR_HOME

    # 创建目录结构
    dirs_to_create = [
        home,
        home / "data" / "papers",
        home / "output" / "parsed",
        home / "output" / "notes",
        home / "output" / "drafts",
        home / "output" / "bib",
        home / "output" / "experiments",
        home / "output" / "datasets",
        home / "output" / "pdfs",
        home / "output" / "digests",
        home / "output" / "logs",
        home / "LEAN",
    ]
    for d in dirs_to_create:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d))

    # 生成 .env.example
    env_example = home / ".env.example"
    if not env_example.exists():
        env_example.write_text(
            "# Scholar Studio — Environment Configuration\n"
            "# Copy to .env and fill in real values\n\n"
            "# PostgreSQL + pgvector\n"
            "SCHOLAR_PG_HOST=localhost\n"
            "SCHOLAR_PG_PORT=5433\n"
            "SCHOLAR_PG_NAME=scholar\n"
            "SCHOLAR_PG_USER=scholar\n"
            "SCHOLAR_PG_PASS=scholar2024\n\n"
            "# RAG Embedding (智谱 API)\n"
            "SCHOLAR_EMBEDDING_PROVIDER=zhipu\n"
            "SCHOLAR_EMBEDDING_MODEL=embedding-2\n"
            "SCHOLAR_EMBEDDING_DIM=1024\n"
            "SCHOLAR_EMBEDDING_API_KEY=your-api-key-here\n\n"
            "# LaTeX compiler\n"
            "SCHOLAR_LATEX_CMD=pdflatex\n",
            encoding="utf-8",
        )
        created.append(str(env_example))

    # 复制 IDE 配置模板到全局 .scholar/
    templates_src = _resolve_templates_dir()
    global_scholar = home / ".scholar"
    if templates_src.exists() and not global_scholar.exists():
        _shutil.copytree(
            templates_src,
            global_scholar,
            ignore=_shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        created.append(str(global_scholar))

    return {
        "home": str(home),
        "created": created,
        "already_exists": len(created) == 0,
        "env_example": str(env_example),
    }


def _sync_ide_config(ws: Path, scholar_source: Path) -> list[str]:
    """Sync .scholar/ templates to .qoder/ and .claude/ in the given workspace.

    Returns list of newly created directory paths.
    """
    import json as _json

    ide_configs = {
        "qoder": {"name": "Qoder", "dir": ".qoder", "entry_file": None},
        "claude": {"name": "Claude", "dir": ".claude", "entry_file": "CLAUDE.md"},
    }
    created = []

    for ide_cfg in ide_configs.values():
        ide_name = ide_cfg["name"]
        ide_dir_name = ide_cfg["dir"]
        ide_target = ws / ide_dir_name
        is_new = not ide_target.exists()

        sync_ide_templates(
            scholar_source,
            ws,
            ide_name=ide_name,
            ide_dir=ide_dir_name,
            entry_file=ide_cfg["entry_file"],
        )

        # Generate settings.json
        settings_path = ide_target / "settings.json"
        if not settings_path.exists():
            settings = {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/task-done.ps1",
                                }
                            ]
                        },
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/log-conversation.ps1",
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
                                    "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/block-dangerous.ps1",
                                }
                            ],
                        },
                    ],
                    "PostToolUse": [
                        {
                            "matcher": "Write|Edit",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f"powershell.exe -ExecutionPolicy Bypass -File {ide_dir_name}/hooks/verify-citations.ps1",
                                }
                            ],
                        },
                    ],
                }
            }
            settings_path.write_text(
                _json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        # Generate mcp.json (always overwrite to reflect correct paths)
        mcp_path = ide_target / "mcp.json"
        mcp_config = {
            "mcpServers": {
                "scholar": {
                    "command": "python",
                    "args": ["-m", "scholar_mcp"],
                    "cwd": str(SCHOLAR_HOME),
                    "env": {
                        "SCHOLAR_HOME": str(SCHOLAR_HOME),
                        "SCHOLAR_WORKSPACE": str(ws),
                        "PYTHONPATH": str(SCHOLAR_HOME),
                    },
                }
            }
        }
        mcp_path.write_text(
            _json.dumps(mcp_config, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        if is_new:
            created.append(str(ide_target))

    return created


def init_workspace(target_dir: Optional[str] = None) -> dict:
    """Initialize workspace directory structure (per-workspace outputs).

    Creates <target>/output/{drafts,notes,logs}.
    Syncs IDE config (.qoder/ and .claude/) from .scholar/ shared source.
    Shared knowledge base (parsed/) stays in SCHOLAR_HOME.

    Args:
        target_dir: Target project directory. Defaults to WORKSPACE_DIR.
                    When set, mcp.json will point SCHOLAR_WORKSPACE here
                    while SCHOLAR_HOME remains at the paper data root.
    """
    created: list[str] = []
    if target_dir:
        ws = Path(target_dir).resolve()
    else:
        ws = WORKSPACE_DIR
    dirs_to_create = [
        ws / "output" / "drafts",
        ws / "output" / "notes",
        ws / "output" / "logs",
    ]
    for d in dirs_to_create:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d))

    # Sync IDE config from the canonical source or packaged fallback.
    scholar_source = _resolve_templates_dir()
    if scholar_source.exists():
        ide_created = _sync_ide_config(ws, scholar_source)
        created.extend(ide_created)

    return {
        "workspace": str(ws),
        "scholar_home": str(SCHOLAR_HOME),
        "created": created,
        "already_exists": len(created) == 0,
        "parsed_dir": str(PARSED_DIR),
        "drafts_dir": str(ws / "output" / "drafts"),
        "notes_dir": str(ws / "output" / "notes"),
        "logs_dir": str(ws / "output" / "logs"),
    }


# PostgreSQL + pgvector: 结构化存储 + RAG 向量检索
# Note: defaults are for local Docker dev only; set .env for production
PG_HOST = os.getenv("SCHOLAR_PG_HOST", "localhost")
PG_PORT = int(os.getenv("SCHOLAR_PG_PORT", "5433"))
PG_NAME = os.getenv("SCHOLAR_PG_NAME", "scholar")
PG_USER = os.getenv("SCHOLAR_PG_USER", "scholar")
PG_PASS = os.getenv("SCHOLAR_PG_PASS", "scholar2024")

# RAG Embedding (智谱 API)
EMBEDDING_PROVIDER = os.getenv("SCHOLAR_EMBEDDING_PROVIDER", "zhipu")
EMBEDDING_MODEL = os.getenv("SCHOLAR_EMBEDDING_MODEL", "embedding-2")
EMBEDDING_DIM = int(os.getenv("SCHOLAR_EMBEDDING_DIM", "1024"))
EMBEDDING_API_KEY = os.getenv("SCHOLAR_EMBEDDING_API_KEY", "")

# MiKTeX (本地 LaTeX 编译)
LATEX_CMD = os.getenv("SCHOLAR_LATEX_CMD", "pdflatex")

# Lean4 (本地形式化验证)
LEAN_PROJECT_DIR = LEAN_DIR


# ===================================================================
# arXiv API 请求工具（带重试、超时、代理支持）
# ===================================================================
def arxiv_request(
    search_query: str, max_results: int = 10, sort_by: str = "relevance"
) -> str:
    """发起 arXiv API 请求，支持重试和代理。

    参数:
        search_query: arXiv 搜索语法，如 "all:transformer" 或 "ti:attention"
        max_results: 最大结果数
        sort_by: 排序方式 (relevance, lastUpdatedDate, submittedDate)

    返回:
        XML 响应字符串

    异常:
        Exception: 所有重试均失败时抛出
    """
    import urllib.request
    import urllib.parse
    import time as _time

    encoded = urllib.parse.quote(search_query)
    url = (
        f"http://export.arxiv.org/api/query?"
        f"search_query={encoded}&max_results={max_results}&sortBy={sort_by}"
    )

    # 代理支持：自动读取 HTTP_PROXY / HTTPS_PROXY 环境变量
    proxy_handler = urllib.request.ProxyHandler()
    opener = urllib.request.build_opener(proxy_handler)

    timeout = int(os.getenv("SCHOLAR_ARXIV_TIMEOUT", "30"))
    retries = int(os.getenv("SCHOLAR_ARXIV_RETRIES", "3"))

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ScholarStudio/1.0"},
            )
            with opener.open(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait = attempt * 2  # 2s, 4s backoff
                _time.sleep(wait)

    raise Exception(f"arXiv API 请求失败（已重试 {retries} 次）: {last_error}")
