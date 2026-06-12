"""
Scholar Studio — Hybrid ID Resolver

Supports ULID / arXiv ID / DOI / slug 任意格式查询，解析为内部 ULID。
带内存缓存，首次调用时扫描所有 parsed JSON 构建索引。
"""
import json
import re
from pathlib import Path
from typing import Optional

from . import config


class IDResolver:
    """多格式论文 ID 解析器，带内存缓存。"""

    def __init__(self):
        self._cache: dict[str, str] = {}  # any_id → ulid
        self._loaded = False

    def _ensure_loaded(self):
        """首次调用时扫描所有 parsed JSON，构建索引。"""
        if self._loaded:
            return
        for json_path in config.PARSED_DIR.glob("*.json"):
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                ulid = data["paper_id"]
                # 注册所有已知 ID 格式
                self._cache[ulid] = ulid
                if data.get("arxiv_id"):
                    self._cache[data["arxiv_id"]] = ulid
                if data.get("doi"):
                    self._cache[data["doi"]] = ulid
                if data.get("slug"):
                    self._cache[data["slug"]] = ulid
            except Exception:
                continue
        self._loaded = True

    def refresh(self):
        """清除缓存，下次调用时重新加载。"""
        self._cache.clear()
        self._loaded = False

    def resolve(self, query: str) -> Optional[str]:
        """尝试解析任意 ID 格式为 ULID。

        匹配优先级：
        1. 精确匹配（ULID / arxiv_id / DOI / slug）
        2. arXiv ID 归一化（去版本号：2402.01680v1 → 2402.01680）
        3. slug 模糊匹配（标题关键词）
        """
        if not query:
            return None
        self._ensure_loaded()
        query = query.strip()

        # 精确匹配
        if query in self._cache:
            return self._cache[query]

        # arXiv ID 格式归一化（2402.01680v1 → 2402.01680）
        arxiv_match = re.match(r"(\d{4}\.\d{4,5})", query)
        if arxiv_match:
            normalized = arxiv_match.group(1)
            if normalized in self._cache:
                return self._cache[normalized]

        # DOI 归一化（https://doi.org/10.xxx → 10.xxx）
        doi_match = re.match(r"(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,}/.+)", query)
        if doi_match:
            normalized_doi = doi_match.group(1)
            if normalized_doi in self._cache:
                return self._cache[normalized_doi]

        # slug 模糊匹配（标题关键词）— 仅匹配 slug 格式的键
        query_lower = query.lower().replace(" ", "-")
        for key, ulid_val in self._cache.items():
            # 只匹配 slug 键：含 "-" 且不以 "10." 开头（DOI）也不像 arXiv ID（\d{4}\.）
            if "-" in key and not key.startswith("10.") and not re.match(r"\d{4}\.", key):
                if query_lower in key:
                    return ulid_val

        return None

    def list_all_ulids(self) -> list[str]:
        """返回所有已注册的 ULID 列表。"""
        self._ensure_loaded()
        # ULID 的特征：26 字符，全大写 + 数字
        return [v for k, v in self._cache.items() if k == v]


# 全局单例
_resolver = IDResolver()


def resolve_id(query: str) -> Optional[str]:
    """便捷函数：解析任意 ID 格式为 ULID。"""
    return _resolver.resolve(query)


def get_resolver() -> IDResolver:
    """获取全局 IDResolver 实例。"""
    return _resolver
