"""
Scholar Studio — Configuration

Environment variables are loaded from .env (gitignored) via python-dotenv.
The .env.example file documents all supported variables; copy it to .env and
fill in real values for your local setup.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Search PROJECT_ROOT (resolved below) for .env
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path, override=False)
except ImportError:
    # python-dotenv not installed; fall back to plain os.environ
    pass

# Project root: parent of scholar/ directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data directories
PAPERS_DIR = PROJECT_ROOT / "data" / "papers"
LEAN_DIR = PROJECT_ROOT / "LEAN"

# Output directories (all generated artifacts)
OUTPUT_DIR = PROJECT_ROOT / "output"
PARSED_DIR = OUTPUT_DIR / "parsed"
NOTES_DIR = OUTPUT_DIR / "notes"
DRAFTS_DIR = OUTPUT_DIR / "drafts"
BIB_DIR = OUTPUT_DIR / "bib"
EXPERIMENTS_DIR = OUTPUT_DIR / "experiments"

# Ensure output directories exist (parents=True for fresh-clone safety)
for d in [PARSED_DIR, NOTES_DIR, DRAFTS_DIR, BIB_DIR, EXPERIMENTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# PostgreSQL + pgvector: 结构化存储 + RAG 向量检索
PG_HOST = os.getenv("SCHOLAR_PG_HOST", "localhost")
PG_PORT = int(os.getenv("SCHOLAR_PG_PORT", "5433"))
PG_NAME = os.getenv("SCHOLAR_PG_NAME", "scholar")
PG_USER = os.getenv("SCHOLAR_PG_USER", "scholar")
PG_PASS = os.getenv("SCHOLAR_PG_PASS", "scholar2024")

# Neo4j: 概念图谱 + 引用网络
NEO4J_URI = os.getenv("SCHOLAR_NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("SCHOLAR_NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("SCHOLAR_NEO4J_PASS", "scholar2024")

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
def arxiv_request(search_query: str, max_results: int = 10, sort_by: str = "relevance") -> str:
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
