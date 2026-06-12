"""
Scholar Studio — Knowledge Base Update

批量从 arXiv 下载论文并执行全流程入库。
支持：arxiv-download（下载）、batch-ingest（批量入库）、kb-update（一键组合）。
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


def _generate_ulid() -> str:
    """生成一个新的 ULID。"""
    try:
        import ulid as ulid_mod
        return str(ulid_mod.ULID())
    except ImportError:
        # 备用：使用时间戳 + 随机字符
        import secrets
        import base64
        ts = int(time.time() * 1000).to_bytes(6, "big")
        rand = secrets.token_bytes(10)
        raw = ts + rand
        encoded = base64.b32encode(raw).decode("ascii").rstrip("=")
        return encoded[:26]


def _parse_arxiv_entries(xml_data: str) -> list[dict]:
    """解析 arXiv API XML 响应，提取论文信息列表。"""
    root = ET.fromstring(xml_data)
    entries = root.findall("atom:entry", ARXIV_NS)
    results = []

    for entry in entries:
        title_elem = entry.find("atom:title", ARXIV_NS)
        title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else ""

        authors = [
            a.find("atom:name", ARXIV_NS).text
            for a in entry.findall("atom:author", ARXIV_NS)
            if a.find("atom:name", ARXIV_NS) is not None
               and a.find("atom:name", ARXIV_NS).text
        ]

        published = entry.find("atom:published", ARXIV_NS)
        year = published.text[:4] if published is not None and published.text else ""

        id_elem = entry.find("atom:id", ARXIV_NS)
        arxiv_id = ""
        if id_elem is not None and id_elem.text:
            raw_id = id_elem.text.strip()
            arxiv_id = raw_id.split("/abs/")[-1]
            match = re.match(r"(\d{4}\.\d{4,5})", arxiv_id)
            if match:
                arxiv_id = match.group(1)

        summary_elem = entry.find("atom:summary", ARXIV_NS)
        abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ""

        # 提取 TeX source 下载链接
        source_url = ""
        for link in entry.findall("atom:link", ARXIV_NS):
            if link.get("title") == "pdf":
                source_url = link.get("href", "")

        results.append({
            "title": title,
            "authors": authors,
            "year": year,
            "arxiv_id": arxiv_id,
            "abstract": abstract,
            "pdf_url": source_url,
        })

    return results


def arxiv_download(
    query: str,
    max_results: int = 10,
    download_pdf: bool = False,
    output_dir: Optional[Path] = None,
) -> list[dict]:
    """批量下载 arXiv 论文 TeX 源码。

    流程:
    1. 搜索 arXiv API
    2. 去重（检查已有 arxiv_id）
    3. 下载 TeX source（tar.gz）
    4. 可选下载 PDF
    5. 生成 ULID 目录结构: data/papers/<ULID>/paper.pdf + source.tar.gz
    6. 返回下载结果列表
    """
    if output_dir is None:
        output_dir = config.PAPERS_DIR

    # 1. 搜索 arXiv
    xml_data = config.arxiv_request(f"all:{query}", max_results=max_results)
    entries = _parse_arxiv_entries(xml_data)

    # 2. 去重：扫描已有 JSON 的 arxiv_id
    existing_ids = set()
    for json_path in config.PARSED_DIR.glob("*.json"):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if data.get("arxiv_id"):
                existing_ids.add(data["arxiv_id"])
        except Exception:
            continue

    results = []
    import urllib.request

    for entry in entries:
        arxiv_id = entry["arxiv_id"]
        title = entry["title"]

        # 去重
        if arxiv_id in existing_ids:
            results.append({
                "arxiv_id": arxiv_id,
                "title": title[:80],
                "status": "already_exists",
            })
            continue

        # 生成 ULID 目录
        paper_ulid = _generate_ulid()
        paper_dir = output_dir / paper_ulid
        paper_dir.mkdir(parents=True, exist_ok=True)

        result = {
            "ulid": paper_ulid,
            "arxiv_id": arxiv_id,
            "title": title[:80],
            "authors": entry["authors"],
            "year": entry["year"],
            "abstract": entry["abstract"],
            "status": "downloaded",
        }

        # 3. 下载 TeX source
        source_url = f"https://arxiv.org/e-print/{arxiv_id}"
        try:
            source_path = paper_dir / "source.tar.gz"
            proxy_handler = urllib.request.ProxyHandler()
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request(source_url, headers={"User-Agent": "ScholarStudio/1.0"})
            with opener.open(req, timeout=60) as resp:
                source_path.write_bytes(resp.read())
            result["source_size"] = source_path.stat().st_size
        except Exception as e:
            result["status"] = f"source_failed: {e}"
            results.append(result)
            continue

        # 4. 可选下载 PDF
        if download_pdf and entry.get("pdf_url"):
            try:
                pdf_path = paper_dir / "paper.pdf"
                req = urllib.request.Request(entry["pdf_url"], headers={"User-Agent": "ScholarStudio/1.0"})
                with opener.open(req, timeout=60) as resp:
                    pdf_path.write_bytes(resp.read())
                result["pdf_downloaded"] = True
            except Exception:
                result["pdf_downloaded"] = False

        # 保存初始元数据 JSON
        meta = {
            "paper_id": paper_ulid,
            "title": title,
            "authors": entry["authors"],
            "year": entry.get("year"),
            "arxiv_id": arxiv_id,
            "abstract": entry["abstract"],
            "venue": "",
        }
        meta_path = paper_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        results.append(result)
        existing_ids.add(arxiv_id)

        # Rate limit
        time.sleep(3)

    return results


def batch_ingest(
    ulids: Optional[list[str]] = None,
    skip_notes: bool = False,
    skip_quality: bool = False,
) -> dict:
    """批量执行 ingest 全流程。

    流程（7步）:
    1. parse（解析 TeX → JSON）
    2. author-fix（arXiv API 补作者）
    3. year-fix（arXiv API 补年份）
    4. metadata-enrich（arxiv_id + DOI 回填）
    5. graph-update（Neo4j 引用 + 概念图）
    6. rag-index（向量索引更新）
    7. auto-notes + quality-score + classify
    """
    from .tex_parser import parse_paper
    from . import metadata_enrich as me
    from .id_resolver import get_resolver

    # 确定要处理的论文列表
    if ulids:
        paper_ids = ulids
    else:
        # 找出所有有 source 但未 parse 的论文
        parsed_ids = set(dbmod.list_parsed())
        paper_ids = []
        for d in sorted(config.PAPERS_DIR.iterdir()):
            if d.is_dir() and d.name not in parsed_ids:
                has_source = any(
                    (d / name).exists()
                    for name in ["source.tar.gz", "source.tgz", "source.tar", "source.zip"]
                )
                if has_source:
                    paper_ids.append(d.name)

    stats = {
        "total": len(paper_ids),
        "parsed": 0,
        "enriched": 0,
        "noted": 0,
        "scored": 0,
        "classified": 0,
        "errors": [],
    }

    database = dbmod.Database()
    if database.available:
        for paper_id in paper_ids:
            paper_dir = config.PAPERS_DIR / paper_id

            # Step 1: Parse
            try:
                data = parse_paper(paper_dir, paper_id)
                out_path = dbmod.save_parsed(data)
                data["parsed_path"] = str(out_path)
                data["section_count"] = len(data.get("sections", []))
                data["formula_count"] = len(data.get("formulas", []))
                data["citation_count"] = len(data.get("citations", []))
                database.ingest_paper(data)
                stats["parsed"] += 1
            except Exception as e:
                stats["errors"].append({"paper_id": paper_id, "step": "parse", "error": str(e)})
                continue

        # Step 2-3: Author/year fix (best-effort)
            json_path = config.PARSED_DIR / f"{paper_id}.json"
            try:
                paper_data = json.loads(json_path.read_text(encoding="utf-8"))
                if not paper_data.get("authors"):
                    from . import year_fix as yf
                    new_authors = yf.fetch_arxiv_authors(paper_data.get("title", ""))
                    if new_authors:
                        paper_data["authors"] = new_authors
                        json_path.write_text(
                            json.dumps(paper_data, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        time.sleep(3)
            except Exception:
                pass

            # Step 4: Metadata enrich
            try:
                result = me.enrich_single_paper(json_path, dry_run=False)
                if result and result.get("status") in ("enriched", "already_have"):
                    stats["enriched"] += 1
            except Exception:
                pass

            # Step 5: Graph update (best-effort)
            gdb = None
            try:
                from . import graph_db as gdb_mod
                gdb = gdb_mod.GraphDB()
                if gdb.available:
                    paper_data = json.loads(json_path.read_text(encoding="utf-8"))
                    gdb_mod.upsert_paper_node(gdb, paper_data)
                    gdb_mod.upsert_paper_citations(gdb, paper_id, paper_data)
                    gdb_mod.upsert_paper_concepts(gdb, paper_id, paper_data)
            except Exception:
                pass
            finally:
                if gdb is not None:
                    try:
                        gdb.close()
                    except Exception:
                        pass

            # Step 6: RAG reindex (best-effort)
            if config.EMBEDDING_API_KEY:
                try:
                    from . import rag
                    rag.index_single_paper(paper_id)
                except Exception:
                    pass

            # Step 7: Auto-notes + quality + classify
            if not skip_notes:
                try:
                    from . import auto_notes as an
                    an.generate_single_note(paper_id, force=True)
                    stats["noted"] += 1
                except Exception:
                    pass

            if not skip_quality:
                try:
                    from . import quality as q
                    q.score_single_paper(paper_id)
                    stats["scored"] += 1
                except Exception:
                    pass

            try:
                from . import classify as cl
                cl.classify_single_paper(paper_id)
                stats["classified"] += 1
            except Exception:
                pass
    else:
        # Database unavailable — fall back to file-only mode
        for paper_id in paper_ids:
            paper_dir = config.PAPERS_DIR / paper_id

            # Step 1: Parse (file-only)
            try:
                data = parse_paper(paper_dir, paper_id)
                dbmod.save_parsed(data)
                stats["parsed"] += 1
            except Exception as e:
                stats["errors"].append({"paper_id": paper_id, "step": "parse", "error": str(e)})
                continue

            json_path = config.PARSED_DIR / f"{paper_id}.json"

            # Steps 2-4: Metadata best-effort (same as above)
            try:
                paper_data = json.loads(json_path.read_text(encoding="utf-8"))
                if not paper_data.get("authors"):
                    from . import year_fix as yf
                    new_authors = yf.fetch_arxiv_authors(paper_data.get("title", ""))
                    if new_authors:
                        paper_data["authors"] = new_authors
                        json_path.write_text(
                            json.dumps(paper_data, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        time.sleep(3)
            except Exception:
                pass

            try:
                result = me.enrich_single_paper(json_path, dry_run=False)
                if result and result.get("status") in ("enriched", "already_have"):
                    stats["enriched"] += 1
            except Exception:
                pass

            # Steps 5-7: Graph/RAG/notes/quality/classify best-effort
            if config.EMBEDDING_API_KEY:
                try:
                    from . import rag
                    rag.index_single_paper(paper_id)
                except Exception:
                    pass

            if not skip_notes:
                try:
                    from . import auto_notes as an
                    an.generate_single_note(paper_id, force=True)
                    stats["noted"] += 1
                except Exception:
                    pass

            if not skip_quality:
                try:
                    from . import quality as q
                    q.score_single_paper(paper_id)
                    stats["scored"] += 1
                except Exception:
                    pass

            try:
                from . import classify as cl
                cl.classify_single_paper(paper_id)
                stats["classified"] += 1
            except Exception:
                pass

    # 刷新 IDResolver 缓存
    get_resolver().refresh()

    return stats


def kb_update(
    query: str = "",
    max_results: int = 10,
) -> dict:
    """一键更新知识库：搜索 → 下载 → 批量入库。

    Args:
        query: arXiv 搜索关键词（空则只处理本地未入库论文）
        max_results: 最大下载数量
    """
    results = {"downloaded": [], "ingest": None}

    # Step 1: 下载（如果有 query）
    if query:
        try:
            download_results = arxiv_download(query, max_results=max_results)
            results["downloaded"] = download_results
            # 提取新下载的 ULID 列表
            new_ulids = [r["ulid"] for r in download_results if r.get("status") == "downloaded"]
        except Exception as e:
            results["download_error"] = str(e)
            new_ulids = []
    else:
        new_ulids = None

    # Step 2: 批量入库
    ingest_stats = batch_ingest(ulids=new_ulids)
    results["ingest"] = ingest_stats

    return results
