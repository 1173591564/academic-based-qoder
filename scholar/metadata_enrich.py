"""
Scholar Studio — Metadata Enrichment

批量为已有论文添加 arxiv_id 和 DOI 字段。
通过标题在 arXiv API 搜索，提取 arXiv ID 和 DOI，写回 JSON + 更新 PG。
"""
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from . import config
from . import db as dbmod


ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _extract_arxiv_id(entry) -> Optional[str]:
    """从 arXiv API entry 提取 arXiv ID。"""
    id_elem = entry.find("atom:id", ARXIV_NS)
    if id_elem is None or not id_elem.text:
        return None
    # URL 格式：http://arxiv.org/abs/2402.01680v1 → 2402.01680
    raw = id_elem.text.strip()
    arxiv_id = raw.split("/abs/")[-1]
    # 去版本号
    match = re.match(r"(\d{4}\.\d{4,5})", arxiv_id)
    return match.group(1) if match else None


def _extract_doi(entry) -> Optional[str]:
    """从 arXiv API entry 提取 DOI。"""
    # arXiv DOI 通常在 <arxiv:doi> 或 <link rel="related" href="...doi...">
    # 标准 Atom 中没有 doi 字段，但部分 entry 有 <arxiv:doi>
    doi_elem = entry.find("{http://arxiv.org/schemas/atom}doi")
    if doi_elem is not None and doi_elem.text:
        return doi_elem.text.strip()
    # 备选：检查 link 标签
    for link in entry.findall("atom:link", ARXIV_NS):
        href = link.get("href", "")
        if "doi.org/" in href:
            return href.split("doi.org/")[-1]
    return None


def _title_similarity(title1: str, title2: str) -> float:
    """简单的标题相似度比较（小写化后词集合 Jaccard）。"""
    words1 = set(re.sub(r"[^\w\s]", "", title1.lower()).split())
    words2 = set(re.sub(r"[^\w\s]", "", title2.lower()).split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union)


def _extract_year(entry) -> Optional[int]:
    """从 arXiv API entry 提取发表年份。"""
    pub = entry.find("atom:published", ARXIV_NS)
    if pub is not None and pub.text:
        m = re.match(r"(\d{4})", pub.text.strip())
        if m:
            return int(m.group(1))
    return None


def search_arxiv_for_paper(title: str, max_results: int = 3) -> Optional[dict]:
    """用标题在 arXiv 搜索，返回最佳匹配的 arxiv_id、doi 和 year。

    Args:
        title: 论文标题
        max_results: arXiv API 返回的最大结果数

    Returns:
        dict with keys: arxiv_id, doi, year, matched_title
        or None if no good match
    """
    try:
        query_title = title[:200]
        # 避免在单词中间截断
        if len(title) > 200:
            query_title = query_title.rsplit(" ", 1)[0]
        xml_data = config.arxiv_request(f"ti:{query_title}", max_results=max_results)
    except Exception:
        return None

    root = ET.fromstring(xml_data)
    entries = root.findall("atom:entry", ARXIV_NS)

    best_match = None
    best_score = 0.0

    for entry in entries:
        entry_title_elem = entry.find("atom:title", ARXIV_NS)
        if entry_title_elem is None or not entry_title_elem.text:
            continue
        entry_title = entry_title_elem.text.strip().replace("\n", " ")
        score = _title_similarity(title, entry_title)

        if score > best_score:
            best_score = score
            arxiv_id = _extract_arxiv_id(entry)
            doi = _extract_doi(entry)
            if arxiv_id:
                year = _extract_year(entry)
                best_match = {
                    "arxiv_id": arxiv_id,
                    "doi": doi,
                    "year": year,
                    "matched_title": entry_title,
                    "score": score,
                }

    # 要求相似度 > 0.6 才算匹配成功（短标题放宽到 0.5）
    threshold = 0.5 if len(set(title.split())) <= 4 else 0.6
    if best_match and best_match["score"] > threshold:
        return best_match
    return None


def enrich_single_paper(json_path: Path, dry_run: bool = False) -> Optional[dict]:
    """为单篇论文回填 arxiv_id、doi、year、venue。

    Args:
        json_path: parsed JSON 文件路径
        dry_run: 若为 True 则不写入

    Returns:
        dict with keys: paper_id, arxiv_id, doi, year, venue, status
    """
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"paper_id": json_path.stem, "status": f"error: {e}"}

    paper_id = data.get("paper_id", json_path.stem)
    title = data.get("title", "")

    # 如果已有 arxiv_id，跳过
    if data.get("arxiv_id"):
        return {"paper_id": paper_id, "arxiv_id": data["arxiv_id"], "doi": data.get("doi"), "status": "already_have"}

    if not title:
        return {"paper_id": paper_id, "status": "no_title"}

    result = search_arxiv_for_paper(title)
    if not result:
        return {"paper_id": paper_id, "status": "no_match"}

    if not dry_run:
        data["arxiv_id"] = result["arxiv_id"]
        if result.get("doi"):
            data["doi"] = result["doi"]
        if result.get("year") and not data.get("year"):
            data["year"] = result["year"]
        if not data.get("venue"):
            data["venue"] = "arXiv"
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 更新 PG（如果可用）
        try:
            database = dbmod.Database()
            if database.available:
                database.upsert_paper(data)
        except Exception:
            pass

    return {
        "paper_id": paper_id,
        "arxiv_id": result["arxiv_id"],
        "doi": result.get("doi"),
        "year": result.get("year"),
        "status": "enriched" if not dry_run else "would_enrich",
    }


def enrich_all_papers(
    dry_run: bool = False,
    limit: int = 0,
    delay: float = 3.0,
) -> dict:
    """批量回填所有论文的 arxiv_id 和 doi。

    Args:
        dry_run: 若为 True 则不写入
        limit: 最大处理数量（0 = 全部）
        delay: arXiv API 请求间隔（秒）

    Returns:
        dict with keys: total, enriched, already_have, no_match, no_title, errors
    """
    json_files = sorted(config.PARSED_DIR.glob("*.json"))
    if limit > 0:
        json_files = json_files[:limit]

    stats = {
        "total": len(json_files),
        "enriched": 0,
        "already_have": 0,
        "no_match": 0,
        "no_title": 0,
        "venue_filled": 0,
        "year_filled": 0,
        "errors": 0,
        "results": [],
    }

    for i, json_path in enumerate(json_files):
        # Pre-check: fill venue for papers that already have arxiv_id but no venue
        try:
            pre_data = json.loads(json_path.read_text(encoding="utf-8"))
            if pre_data.get("arxiv_id") and not pre_data.get("venue"):
                if not dry_run:
                    pre_data["venue"] = "arXiv"
                    json_path.write_text(
                        json.dumps(pre_data, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                stats["venue_filled"] += 1
        except Exception:
            pass

        result = enrich_single_paper(json_path, dry_run=dry_run)
        status = "error"  # 默认值
        if result:
            status = result.get("status", "error")
            if status in ("enriched", "would_enrich"):
                stats["enriched"] += 1
                if result.get("year"):
                    stats["year_filled"] += 1
            elif status == "already_have":
                stats["already_have"] += 1
            elif status == "no_match":
                stats["no_match"] += 1
            elif status == "no_title":
                stats["no_title"] += 1
            else:
                stats["errors"] += 1
            stats["results"].append(result)

        # arXiv rate limit：每篇间隔 delay 秒（非 already_have 的才需要等）
        if status not in ("already_have",) and i < len(json_files) - 1:
            time.sleep(delay)

    return stats
