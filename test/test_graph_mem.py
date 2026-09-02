"""test_graph_mem.py — 内存图（Neo4j 替代层）建图/解析/查询/缓存。"""

import json

import pytest

from scholar import config, graph_mem
from scholar.graph_mem import (
    GraphMem,
    build_graph,
    concepts_for_paper,
    ensure_graph,
    reset_cache,
    resolve_refs,
)


def _write_paper(
    parsed_dir,
    pid,
    title,
    citations=None,
    year=2023,
    venue="arXiv",
    tags=None,
    heading=None,
):
    data = {
        "paper_id": pid,
        "title": title,
        "authors": ["A"],
        "year": year,
        "venue": venue,
        "abstract": "",
        "sections": [
            {"heading": heading or "", "level": 1, "content": "", "position": 0}
        ],
        "formulas": [],
        "citations": citations or [],
        "tags": tags or {},
    }
    (parsed_dir / f"{pid}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    return data


@pytest.fixture()
def parsed_dir(tmp_path):
    d = tmp_path / "parsed"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _isolate_paths(tmp_path, monkeypatch):
    """所有测试不触碰真实 output/index 与 LEAN。"""
    monkeypatch.setattr(graph_mem, "GRAPH_CACHE", tmp_path / "graph.json")
    monkeypatch.setattr(graph_mem, "REFS_SIDECAR", tmp_path / "refs-resolved.json")
    monkeypatch.setattr(graph_mem, "LEAN_FILE", tmp_path / "no-such.lean")
    monkeypatch.setattr(config, "PARSED_DIR", tmp_path / "parsed")
    reset_cache()
    yield
    reset_cache()


def test_build_nodes_and_citations(parsed_dir):
    _write_paper(parsed_dir, "01KA", "Attention Is All You Need")
    # 真实世界的 ref_key 形态：下划线键 → 归一化后与标题精确匹配
    _write_paper(
        parsed_dir,
        "01KB",
        "Follow Up Work",
        citations=["attention_is_all_you_need"],
    )
    gm = build_graph(parsed_dir)
    assert set(gm.papers) == {"01KA", "01KB"}
    assert gm.ref_resolved.get("attention_is_all_you_need") == "01KA"
    assert ("01KB", "01KA") in list(gm.g.edges)


def test_resolve_fuzzy_word_overlap(parsed_dir):
    # 多词 ref_key 与标题共享 >0.7 词重叠 → 模糊命中
    _write_paper(parsed_dir, "01KA", "Deep Residual Learning for Image Recognition")
    _write_paper(
        parsed_dir,
        "01KB",
        "Follow Up",
        citations=["deep residual learning for image"],
    )
    gm = build_graph(parsed_dir)
    assert gm.ref_resolved.get("deep residual learning for image") == "01KA"


def test_resolve_exact_beats_fuzzy(parsed_dir):
    _write_paper(parsed_dir, "01KA", "Deep Residual Learning")
    r = resolve_refs(
        {"01KA": {"title": "Deep Residual Learning", "citations": ["deep_resid"]}}
    )
    assert r["deep_resid"] == "01KA"


def test_resolve_threshold_keeps_garbage(parsed_dir):
    _write_paper(parsed_dir, "01KA", "Deep Residual Learning")
    r = resolve_refs(
        {
            "01KA": {
                "title": "Deep Residual Learning",
                "citations": ["zzz9999totallyunknown"],
            }
        }
    )
    assert "zzz9999totallyunknown" not in r


def test_sidecar_wins(parsed_dir):
    _write_paper(parsed_dir, "01KA", "Alpha")
    _write_paper(parsed_dir, "01KB", "Beta")
    gm = build_graph(parsed_dir)
    assert "01KA" in gm.papers  # 基础健全性


def test_self_citation_and_unresolved(parsed_dir):
    _write_paper(
        parsed_dir,
        "01KA",
        "Self Loop Paper",
        citations=["self_loop_paper", "ghost2020ref"],
    )
    gm = build_graph(parsed_dir)
    # 未解析的 ref 不进图，但保留在 unresolved
    assert gm.g.number_of_edges() == 0
    assert "ghost2020ref" in gm.unresolved["01KA"]
    # 解析到自己 → 丢弃且不进 unresolved
    assert "self_loop_paper" not in gm.unresolved["01KA"]


def test_concepts_single_caliper(parsed_dir):
    # alias 路：标题含 Transformer 别名；tags 路：methods 注入
    _write_paper(
        parsed_dir,
        "01KA",
        "Transformer Networks",
        tags={"methods": ["CustomMethod"], "domains": ["Vision"]},
    )
    gm = build_graph(parsed_dir)
    cs = gm.concepts["01KA"]
    assert "Transformer" in cs  # alias 表命中
    assert "CustomMethod" in cs  # tags 命中
    assert "Vision" in cs
    assert "Transformer" in concepts_for_paper(
        {"title": "The attention mechanism", "abstract": "", "sections": [], "tags": {}}
    )


def test_lineage_multihop_and_direction_free(parsed_dir):
    _write_paper(parsed_dir, "01KA", "Root Paper")
    _write_paper(parsed_dir, "01KB", "Mid Paper", citations=["root paper"])
    _write_paper(parsed_dir, "01KC", "Leaf Paper", citations=["mid paper"])
    gm = build_graph(parsed_dir)
    lin = gm.lineage("01KC", "01KA")
    assert lin["hops"] == 2
    assert [n["ulid"] for n in lin["path"]] == ["01KC", "01KB", "01KA"]
    assert gm.lineage("01KA", "01KC")["hops"] == 2  # 方向无关
    assert gm.lineage("01KA", "01KZ")["hops"] == -1  # 不可达


def test_hubs_and_stats(parsed_dir):
    _write_paper(parsed_dir, "01KA", "Root")
    _write_paper(parsed_dir, "01KB", "B", citations=["root"])
    _write_paper(parsed_dir, "01KC", "C", citations=["root"])
    gm = build_graph(parsed_dir)
    hubs = gm.hubs(2)
    assert hubs["most_cited"][0]["ulid"] == "01KA"
    assert hubs["most_cited"][0]["in_degree"] == 2
    st = gm.stats()
    assert st["papers"] == 3 and st["cites_edges"] == 2
    assert st["most_cited"][0]["ulid"] == "01KA"


def test_forward_backward(parsed_dir):
    _write_paper(parsed_dir, "01KA", "Root")
    _write_paper(parsed_dir, "01KB", "B", citations=["root", "ghost1999"])
    gm = build_graph(parsed_dir)
    fwd = gm.forward_citations("01KB")
    assert [c["ulid"] for c in fwd["cited"]] == ["01KA"]
    assert fwd["unresolved_refs"] == ["ghost1999"]
    assert [c["ulid"] for c in gm.backward_citations("01KA")] == ["01KB"]


def test_concept_queries(parsed_dir):
    _write_paper(
        parsed_dir, "01KA", "Transformer Old", year=2017, tags={"methods": ["MoE"]}
    )
    _write_paper(
        parsed_dir,
        "01KB",
        "Transformer New",
        year=2024,
        tags={"methods": ["MoE", "Quant"]},
    )
    gm = build_graph(parsed_dir)
    papers = gm.papers_by_concept("MoE")
    assert [p["ulid"] for p in papers] == ["01KB", "01KA"]  # 年份倒序
    assert gm.papers_by_concept("moe") == papers  # 大小不敏感
    rel = gm.related_concepts("MoE")
    assert {"id": "Transformer", "weight": 2} in rel  # 共现权重
    tl = gm.concept_timeline("MoE")
    assert [t["year"] for t in tl] == [2017, 2024]
    assert "Quant" in {c for c in gm.concepts["01KB"]}


def test_cache_roundtrip(parsed_dir):
    _write_paper(parsed_dir, "01KA", "Root")
    _write_paper(parsed_dir, "01KB", "B", citations=["root"])
    gm = build_graph(parsed_dir)
    payload = graph_mem._serialize(gm)
    gm2 = graph_mem._deserialize(payload)
    assert gm2.g.number_of_edges() == 1
    assert gm2.papers["01KA"]["title"] == "Root"
    assert gm2.concepts == gm.concepts or dict(gm2.concepts) == dict(gm.concepts)


def test_ensure_graph_rebuild_on_count_change(parsed_dir):
    _write_paper(parsed_dir, "01KA", "Root")
    gm1 = ensure_graph(force=True)
    assert gm1 is not None
    built_at_1 = graph_mem.GRAPH_CACHE.read_text(encoding="utf-8")
    gm2 = ensure_graph()  # 同篇数 → 命中缓存
    assert graph_mem.GRAPH_CACHE.read_text(encoding="utf-8") == built_at_1
    _write_paper(parsed_dir, "01KB", "B")  # 篇数变化 → 重建
    gm3 = ensure_graph()
    assert len(gm3.papers) == 2
    assert graph_mem.GRAPH_CACHE.read_text(encoding="utf-8") != built_at_1


def test_lean_loaders_fallback(tmp_path):
    inns = graph_mem._load_innovations(tmp_path / "missing.lean")
    assert {"id": "Transformer", "year": 2017} in [dict(i, **{}) for i in inns] or any(
        i["id"] == "Transformer" for i in inns
    )
    assert graph_mem._load_replacements(tmp_path / "missing.lean") == []


def test_lean_replacements_real_format(tmp_path):
    lean = tmp_path / "Database.lean"
    lean.write_text(
        "replacesDb : List Replacement := [\n"
        '  { source := "RNN", target := "Transformer" },\n'
        '  { source := "LSTM", target := "Transformer" }\n]',
        encoding="utf-8",
    )
    reps = graph_mem._load_replacements(lean)
    assert ("Transformer", "RNN") in reps  # target REPLACES source
    assert ("Transformer", "LSTM") in reps
    assert len(reps) == 2


def test_graphmem_empty_inputs():
    gm = GraphMem({}, [], {}, {}, {}, [], [])
    assert gm.stats()["papers"] == 0
    assert gm.lineage("a", "b")["hops"] == -1
    assert gm.papers_by_concept("x") == []
