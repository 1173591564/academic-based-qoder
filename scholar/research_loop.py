"""
Scholar Studio — Adaptive Research Loop

研究方向自动追踪：从对话日志提取兴趣 → 搜索 arXiv → 全流程入库。
支持：interests（兴趣管理）、research-sync（方向级同步）。
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from . import config
from . import kb_update


# ===================================================================
# 兴趣管理
# ===================================================================

def _empty_interests() -> dict:
    """返回空兴趣画像模板。"""
    return {
        "version": 1,
        "updated_at": "",
        "interests": [],
        "history": [],
    }


def load_interests() -> dict:
    """读取 output/research-interests.json，不存在则返回空模板。"""
    path = config.INTERESTS_FILE
    if not path.exists():
        return _empty_interests()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_interests()


def save_interests(data: dict) -> None:
    """原子写入兴趣文件（先写 .tmp 再 os.replace）。"""
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    path = config.INTERESTS_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def add_interest(keywords: str, category: str = "general", max_results: int = 10) -> dict:
    """添加兴趣条目。keywords 为逗号分隔字符串。自动按 category 去重。"""
    data = load_interests()
    # 去重：如果同 category 已存在，合并 keywords
    for item in data["interests"]:
        if item["category"].lower() == category.lower():
            # 规范化 keywords 为 list，去重，保持原始大小写
            existing_kw_lower = {k.strip().lower() for k in item["keywords"].split(",") if k.strip()}
            new_kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
            added = [k for k in new_kw_list if k.lower() not in existing_kw_lower]
            if added:
                # 重建完整 keyword 列表，保持干净的分隔
                all_kw = [k.strip() for k in item["keywords"].split(",") if k.strip()] + added
                item["keywords"] = ", ".join(all_kw)
            item["max_results"] = max(item.get("max_results", 10), max_results)
            save_interests(data)
            return data
    # 新条目
    data["interests"].append({
        "category": category,
        "keywords": keywords,
        "max_results": max_results,
        "added_at": datetime.now().strftime("%Y-%m-%d"),
        "search_count": 0,
        "last_searched": None,
    })
    save_interests(data)
    return data


def remove_interest(category: str) -> tuple[dict, bool]:
    """按 category 删除兴趣条目。

    返回: (data, removed) — removed=True 表示真有匹配项被删除
    """
    data = load_interests()
    original_count = len(data["interests"])
    data["interests"] = [
        i for i in data["interests"] if i["category"].lower() != category.lower()
    ]
    removed = len(data["interests"]) < original_count
    if removed:
        save_interests(data)
    return data, removed


# ===================================================================
# 日志分析
# ===================================================================

def get_unanalyzed_logs() -> tuple[Path, list[dict]]:
    """找到最早一个未分析的周日志文件，返回其内容。

    逻辑：
    1. 扫描 output/logs/week-*.jsonl 获取所有周文件
    2. 读取 output/logs/analyzed.json 获取已完成列表
    3. 差集 = 未分析的周（取最早的一周）
    4. 读取该文件所有行，解析为 dict 列表

    返回: (week_file_path, [{"ts": "...", "week": "...", "text": "..."}, ...])
         如果没有未分析的日志，返回 (Path(""), [])
    """
    logs_dir = config.LOGS_DIR
    week_files = sorted(logs_dir.glob("week-*.jsonl"))
    if not week_files:
        return Path(""), []

    # 读取已完成列表
    analyzed_path = logs_dir / "analyzed.json"
    analyzed = {}
    if analyzed_path.exists():
        try:
            analyzed = json.loads(analyzed_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # 找最早的未分析周
    for wf in week_files:
        # 从文件名提取 week_id，如 week-2026-W24.jsonl → 2026-W24
        match = re.match(r"week-(.+)\.jsonl", wf.name)
        if not match:
            continue
        week_id = match.group(1)
        if week_id in analyzed:
            continue
        # 读取该周日志
        entries = []
        for line in wf.read_text(encoding="utf-8").strip().splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return wf, entries

    return Path(""), []


def mark_week_analyzed(week_id: str, interests_found: int, entries: int) -> None:
    """标记某周日志已完成分析，写入 analyzed.json。

    week_id: ISO 周编号，如 "2026-W24"
    """
    analyzed_path = config.LOGS_DIR / "analyzed.json"
    analyzed = {}
    if analyzed_path.exists():
        try:
            analyzed = json.loads(analyzed_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    analyzed[week_id] = {
        "analyzed_at": datetime.now().isoformat(timespec="seconds"),
        "interests_found": interests_found,
        "entries": entries,
    }
    # 原子写入：先写 .tmp 再 os.replace，防止中断损坏文件
    tmp = analyzed_path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(analyzed, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(tmp, analyzed_path)


# ===================================================================
# 方向级同步（核心：确认方向后一条龙执行）
# ===================================================================

def sync_direction(category: str, max_results: int = 10) -> dict:
    """对一个已确认的研究方向执行完整管线：搜索→下载→入库。

    流程:
    1. load_interests() 获取该 category 的关键词
    2. 对每个 keyword 调用 kb_update.arxiv_download()（内部完成搜索+去重+下载）
    3. 收集新下载的 ULID 列表
    4. 调用 kb_update.batch_ingest() 全流程入库
    5. 更新 interests 的 search_count 和 last_searched
    6. 生成本次同步报告 → output/digests/sync-YYYY-MM-DD.md

    arxiv_download 内部已包含 3s rate limit 和重试逻辑。

    返回: {"category": "...", "downloaded": N, "ingested": N, "papers": [...], "errors": [...]}
    """
    data = load_interests()
    target = None
    for item in data["interests"]:
        if item["category"].lower() == category.lower():
            target = item
            break

    if not target:
        return {
            "category": category,
            "downloaded": 0,
            "ingested": 0,
            "papers": [],
            "errors": [f"未找到方向 '{category}'，请先用 interests add 添加"],
        }

    keywords = [k.strip() for k in target["keywords"].split(",") if k.strip()]
    all_new_papers = []
    errors = []
    seen_arxiv_ids: set[str] = set()  # 跨关键词去重

    for kw in keywords:
        try:
            # arxiv_download 内部完成：搜索 arXiv + 去重 + 下载 TeX/PDF
            dl_results = kb_update.arxiv_download(
                query=kw,
                max_results=max_results,
                download_pdf=True,
            )

            for r in dl_results:
                aid = r.get("arxiv_id", "")
                # 跨关键词去重：同一方向内不同关键词可能返回相同论文
                if aid and aid in seen_arxiv_ids:
                    continue
                if aid:
                    seen_arxiv_ids.add(aid)

                if r.get("status") == "downloaded":
                    all_new_papers.append(r)
                elif r.get("status") == "already_exists":
                    pass  # 已去重，跳过
                else:
                    errors.append(f"{r.get('title', '?')}: {r.get('status', 'unknown')}")

        except Exception as e:
            errors.append(f"搜索 '{kw}' 失败: {e}")

        # Rate limit between keywords
        time.sleep(3)

    # 全流程入库
    new_ulids = [p["ulid"] for p in all_new_papers if p.get("ulid")]
    ingested = 0
    if new_ulids:
        try:
            ingest_stats = kb_update.batch_ingest(ulids=new_ulids)
            # batch_ingest 返回 stats dict: {"total", "parsed", "errors", ...}
            ingested = ingest_stats.get("parsed", 0)
            ingest_errors = ingest_stats.get("errors", [])
            for err in ingest_errors:
                errors.append(
                    f"{err.get('paper_id', '?')} [{err.get('step', '?')}]: {err.get('error', '?')}"
                )
        except Exception as e:
            errors.append(f"批量入库失败: {e}")

    # 更新 interests 统计（仅在有成功入库或无入库需求时更新）
    if ingested > 0 or not new_ulids:
        target["search_count"] = target.get("search_count", 0) + 1
        target["last_searched"] = datetime.now().strftime("%Y-%m-%d")
    data["history"].append({
        "action": "sync",
        "category": category,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "papers_found": len(all_new_papers),
        "ingested": ingested,
    })
    save_interests(data)

    # 生成同步报告
    _write_sync_report(category, all_new_papers, errors)

    return {
        "category": category,
        "downloaded": len(all_new_papers),
        "ingested": ingested,
        "papers": all_new_papers,
        "errors": errors,
    }


def sync_all_directions(max_results: int = 10) -> dict:
    """对所有活跃研究方向执行 sync_direction。

    返回: {"total_categories": N, "total_papers": N, "results": [...]}
    """
    data = load_interests()
    if not data["interests"]:
        return {
            "total_categories": 0,
            "total_papers": 0,
            "results": [],
            "message": "兴趣画像为空，请先添加研究方向",
        }

    results = []
    total_papers = 0
    for item in data["interests"]:
        r = sync_direction(item["category"], max_results=max_results)
        results.append(r)
        total_papers += r["downloaded"]

    return {
        "total_categories": len(data["interests"]),
        "total_papers": total_papers,
        "results": results,
    }


# ===================================================================
# 同步报告生成
# ===================================================================

def _write_sync_report(category: str, papers: list[dict], errors: list[str]) -> Path:
    """生成本次同步的 Markdown 报告。"""
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = config.DIGESTS_DIR / f"sync-{today}.md"

    lines = []
    if report_path.exists():
        # 追加到已有报告（同一天多次同步），添加时间戳区隔
        lines = report_path.read_text(encoding="utf-8").splitlines()
        lines.append("")
        now_time = datetime.now().strftime("%H:%M")
        lines.append(f"### {now_time} 追加")
        lines.append("")
    else:
        lines = [f"# Research Sync — {today}", ""]

    paper_count = len(papers)
    lines.append(f"## {category} ({paper_count} papers synced)")
    for p in papers:
        title = p.get("title", "Unknown")
        arxiv_id = p.get("arxiv_id", "")
        ulid = p.get("ulid", "")
        year = p.get("year", "")
        lines.append(f"- {title} ({year}) — arXiv:{arxiv_id} -> {ulid[:8]}...")

    if errors:
        lines.append("")
        lines.append(f"**Errors**: {len(errors)}")
        for e in errors:
            lines.append(f"  - {e}")

    lines.append("")
    lines.append("---")
    lines.append(
        f"Total: {paper_count} papers synced | Direction: {category}"
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
