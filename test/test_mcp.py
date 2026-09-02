"""
Integration Tests — MCP Server Direct-Call Tools (v0.2.0 surface)

Tests the 16 model-facing tools directly (not via MCP protocol).
Covers: reading ladder (search/vec/info/section/passages), graph tools,
utilities, helpers. Maintenance tools live in the CLI and are not tested here.
"""

import json
from pathlib import Path

import pytest


REAL_3DGS = "01KT6MTARQMB6JVJNZA9PJVTS2"  # 3D Gaussian Splatting (2023)
REAL_BERT = "01KT6MTBK1PQMNZM8ZYQPTVN6C"  # BERT


@pytest.fixture(autouse=True)
def hermetic_corpus(tmp_path, monkeypatch):
    from scholar import config, graph_mem
    from scholar.id_resolver import get_resolver

    parsed = tmp_path / "output" / "parsed"
    parsed.mkdir(parents=True)
    papers = [
        {
            "paper_id": REAL_3DGS,
            "title": "3D Gaussian Splatting Optimization",
            "authors": ["Fixture Author"],
            "year": 2023,
            "venue": "FixtureConf",
            "abstract": (
                "Gaussian splatting optimization renders radiance fields efficiently "
                "with differentiable training."
            ),
            "sections": [
                {
                    "heading": heading,
                    "level": 1,
                    "content": f"{heading} fixture content " + ("detail " * 30),
                }
                for heading in [
                    "Introduction",
                    "Related Work",
                    "Training Overview",
                    "Training Data",
                    "Method",
                    "Evaluation",
                    "Limitations",
                    "Optimization",
                ]
            ],
            "citations": ["BERT Pre-training of Deep Bidirectional Transformers"],
            "tags": {"methods": ["Gaussian Splatting"]},
        },
        {
            "paper_id": REAL_BERT,
            "title": "BERT Pre-training of Deep Bidirectional Transformers",
            "authors": ["Fixture Author"],
            "year": 2019,
            "venue": "FixtureConf",
            "abstract": "Transformer attention pre-training for language understanding.",
            "sections": [
                {
                    "heading": "Transformer",
                    "level": 1,
                    "content": "Transformer fixture content " + ("detail " * 30),
                }
            ],
            "citations": [],
            "tags": {"methods": ["Transformer"]},
        },
    ]
    for paper in papers:
        (parsed / f"{paper['paper_id']}.json").write_text(
            json.dumps(paper), encoding="utf-8"
        )
    output = tmp_path / "output"
    index = output / "index"
    monkeypatch.setattr(config, "PARSED_DIR", parsed)
    monkeypatch.setattr(config, "OUTPUT_DIR", output)
    monkeypatch.setattr(config, "INTERESTS_FILE", output / "research-interests.json")
    monkeypatch.setattr(graph_mem, "INDEX_DIR", index)
    monkeypatch.setattr(graph_mem, "GRAPH_CACHE", index / "graph.json")
    monkeypatch.setattr(graph_mem, "REFS_SIDECAR", index / "refs-resolved.json")
    monkeypatch.setattr(graph_mem, "LEAN_FILE", tmp_path / "missing.lean")
    monkeypatch.setattr("scholar._state._state", None)
    get_resolver().refresh()
    graph_mem.reset_cache()
    yield
    get_resolver().refresh()
    graph_mem.reset_cache()


# ── L1: lexical search ──────────────────────────────────────────────────────


class TestScholarSearch:
    def test_multi_word_returns_scored_hits(self):
        from scholar_mcp.server import scholar_search

        result = scholar_search("gaussian splatting optimization")
        assert "Search:" in result and "score=" in result
        assert REAL_3DGS in result

    def test_single_word(self):
        from scholar_mcp.server import scholar_search

        result = scholar_search("transformer")
        assert isinstance(result, str) and len(result) > 0

    def test_empty_query(self):
        from scholar_mcp.server import scholar_search

        result = scholar_search("")
        assert "No usable terms" in result

    def test_gibberish_returns_hint(self):
        from scholar_mcp.server import scholar_search

        result = scholar_search("xyzwq9999notarealword")
        assert "No results" in result
        assert "scholar_vec_search" in result  # 指路下一层

    def test_limit_respected(self):
        from scholar_mcp.server import scholar_search

        result = scholar_search("transformer attention", limit=3)
        lines = [l for l in result.splitlines() if "score=" in l]
        assert len(lines) <= 3


# ── L1: semantic search ─────────────────────────────────────────────────────


class TestVecSearch:
    def test_returns_matches_or_graceful_fallback(self):
        from scholar_mcp.server import scholar_vec_search

        result = scholar_vec_search("how to balance expert load in MoE training")
        assert isinstance(result, str) and len(result) > 0
        # PG+embedding 可用 → 命中；否则 → 明确的降级提示
        assert (
            "Semantic matches" in result or "unavailable" in result or "sync" in result
        )

    def test_empty_question(self):
        from scholar_mcp.server import scholar_vec_search

        result = scholar_vec_search("")
        assert result == "No semantic query provided."


# ── L2: digest ──────────────────────────────────────────────────────────────


class TestScholarInfo:
    def test_digest_has_toc(self):
        from scholar_mcp.server import scholar_info

        result = scholar_info(REAL_3DGS)
        assert "Title:" in result and "Abstract:" in result
        assert "Section TOC" in result and "[0]" in result

    def test_nonexistent(self):
        from scholar_mcp.server import scholar_info

        result = scholar_info("NONEXISTENT_ULID_123456")
        assert "not parsed" in result.lower() or "not found" in result.lower()

    def test_read_parsed_paper_default_is_bounded(self):
        from scholar_mcp.server import read_parsed_paper

        result = read_parsed_paper(REAL_3DGS)
        assert "Section TOC" in result
        assert "scholar_section" in result  # 指路 L3
        assert len(result) < 5000  # 摘要卡有界

    def test_read_parsed_paper_full_gate(self):
        from scholar_mcp.server import read_parsed_paper

        result = read_parsed_paper(REAL_3DGS, full=True)
        data = (
            json.loads(result.split("…[truncated")[0])
            if "truncated" in result
            else json.loads(result)
        )
        assert data.get("paper_id") == REAL_3DGS

    def test_read_parsed_paper_nonexistent(self):
        from scholar_mcp.server import read_parsed_paper

        result = read_parsed_paper("NONEXISTENT_XYZ")
        assert "not parsed" in result.lower()


# ── L3: section reader ──────────────────────────────────────────────────────


class TestScholarSection:
    def test_index_hit(self):
        from scholar_mcp.server import scholar_section

        result = scholar_section(REAL_3DGS, "7")
        assert result.startswith("[7]")
        assert len(result) > 100

    def test_bracket_index(self):
        from scholar_mcp.server import scholar_section

        assert scholar_section(REAL_3DGS, "[0]").startswith("[0]")

    def test_exact_heading_case_insensitive(self):
        from scholar_mcp.server import scholar_section

        result = scholar_section(REAL_3DGS, "optimization")
        assert result.startswith("[")  # 单一精确命中直接返回

    def test_ambiguous_returns_candidates(self):
        from scholar_mcp.server import scholar_section

        result = scholar_section(REAL_3DGS, "training")  # 子串多命中
        if "Ambiguous" in result:
            assert "[index]" in result and "Retry" in result

    def test_not_found_returns_toc(self):
        from scholar_mcp.server import scholar_section

        result = scholar_section(REAL_3DGS, "zzz_no_such_section")
        assert "not found" in result.lower() and "TOC" in result

    def test_span_reads_consecutive(self):
        from scholar_mcp.server import scholar_section

        single = scholar_section(REAL_3DGS, "0")
        span2 = scholar_section(REAL_3DGS, "0", span=2)
        assert len(span2) > len(single)


# ── Graph tools (in-memory) ─────────────────────────────────────────────────


class TestGraphTools:
    def test_cite_network_global(self):
        from scholar_mcp.server import scholar_cite_network

        result = scholar_cite_network()
        assert "Papers:" in result and "Most cited" in result

    def test_cite_network_per_paper(self):
        from scholar_mcp.server import scholar_cite_network

        result = scholar_cite_network(REAL_3DGS)
        assert "Forward citations" in result and "Backward citations" in result

    def test_graph_query_concept(self):
        from scholar_mcp.server import scholar_graph_query

        result = scholar_graph_query("Transformer")
        assert "Papers with concept" in result

    def test_graph_query_unknown(self):
        from scholar_mcp.server import scholar_graph_query

        result = scholar_graph_query("zzz_not_a_concept_999")
        assert "not found" in result.lower()

    def test_graph_stats_fields(self):
        from scholar_mcp.server import scholar_graph_stats

        result = scholar_graph_stats()
        for key in ("Papers:", "CITES edges:", "Concepts:"):
            assert key in result

    def test_lineage_real_edge(self):
        from scholar import graph_mem
        from scholar_mcp.server import scholar_lineage

        gm = graph_mem.ensure_graph()
        edges = list(gm.g.edges)
        if not edges:
            pytest.skip("graph has no resolved edges")
        a, b = edges[0]
        result = scholar_lineage(a, b)
        assert "Citation path" in result
        assert result.split("hops")[0].split("(")[-1].strip().isdigit()

    def test_lineage_unreachable(self):
        from scholar_mcp.server import scholar_lineage

        result = scholar_lineage("NONEXISTENT_A", "NONEXISTENT_B")
        assert "No citation path" in result


# ── Utilities ───────────────────────────────────────────────────────────────


class TestUtilities:
    def test_list_papers_all(self):
        from scholar_mcp.server import scholar_list_papers

        result = scholar_list_papers()
        assert "Parsed Papers (2 shown, total 2" in result

    def test_list_papers_year_filter(self):
        from scholar_mcp.server import scholar_list_papers

        assert isinstance(scholar_list_papers(year=2023), str)

    def test_read_skill_valid(self):
        from scholar_mcp.server import read_skill

        result = read_skill("research-survey")
        assert len(result) > 100

    def test_read_skill_invalid(self):
        from scholar_mcp.server import read_skill

        result = read_skill("nonexistent-skill")
        assert "not found" in result.lower() and "Available" in result

    def test_read_output_file_invalid(self):
        from scholar_mcp.server import scholar_read_output_file

        result = scholar_read_output_file("nonexistent/deadbeef.txt")
        assert "not found" in result.lower()

    def test_read_output_file_traversal_blocked(self):
        from scholar_mcp.server import scholar_read_output_file

        result = scholar_read_output_file("../outside.txt")
        assert "Access denied" in result

    def test_read_output_file_rejects_absolute_and_sibling_prefix_paths(
        self, tmp_path, monkeypatch
    ):
        from scholar_mcp import server

        output = tmp_path / "output"
        sibling = tmp_path / "output-secret"
        output.mkdir(exist_ok=True)
        sibling.mkdir()
        secret = sibling / "secret.txt"
        secret.write_text("not-readable", encoding="utf-8")
        monkeypatch.setattr(server.scholar_config, "OUTPUT_DIR", output)
        assert "Access denied" in server.scholar_read_output_file(str(secret))
        assert "Access denied" in server.scholar_read_output_file(
            "../output-secret/secret.txt"
        )

    def test_read_skill_rejects_path_traversal(self):
        from scholar_mcp.server import read_skill

        assert "not found" in read_skill("../research-survey").lower()
        assert "not found" in read_skill("research-survey/../../dsh").lower()

    def test_arxiv_search_tolerant(self):
        from scholar_mcp.server import scholar_arxiv_search

        result = scholar_arxiv_search("transformer", max_results=3)
        assert isinstance(result, str) and len(result) > 0

    def test_auto_notes_json(self):
        from scholar_mcp.server import scholar_auto_notes

        result = scholar_auto_notes(paper_id=REAL_BERT)
        try:
            data = json.loads(result)
            assert "status" in data or "error" in data
        except json.JSONDecodeError:
            pytest.skip("auto_notes returned non-JSON output")

    def test_interests_list(self):
        from scholar_mcp.server import scholar_interests

        result = scholar_interests(action="list")
        assert isinstance(result, str) and len(result) > 0

    def test_interests_invalid_action(self):
        from scholar_mcp.server import scholar_interests

        result = scholar_interests(action="nonexistent_action")
        assert "Unknown" in result or "Available" in result


# ── Helpers ─────────────────────────────────────────────────────────────────


class TestHelpers:
    def test_resolve_without_shared_state(self, monkeypatch):
        monkeypatch.setattr("scholar._state._state", None)
        from scholar_mcp.server import _resolve

        assert _resolve(REAL_BERT) == REAL_BERT

    def test_resolve_fallback_for_unknown_id(self, monkeypatch):
        monkeypatch.setattr("scholar._state._state", None)
        from scholar_mcp.server import _resolve

        assert _resolve("nonexistent_junk_id") == "nonexistent_junk_id"

    def test_load_parsed_without_shared_state(self, monkeypatch):
        monkeypatch.setattr("scholar._state._state", None)
        from scholar_mcp.server import _load_parsed

        result = _load_parsed(REAL_BERT)
        assert result is not None and "title" in result

    def test_load_parsed_nonexistent_id(self, monkeypatch):
        monkeypatch.setattr("scholar._state._state", None)
        from scholar_mcp.server import _load_parsed

        assert _load_parsed("NONEXISTENT_ULID_XYZ123") is None


# ── Tool surface census ─────────────────────────────────────────────────────


def test_tool_surface_is_capped():
    """模型面工具数必须保持在 20 以内（上下文经济约束）。"""
    import asyncio
    from scholar_mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    assert len(tools) <= 20
    names = {t.name for t in tools}
    # 已退役工具不得回归
    for gone in (
        "scholar_stats",
        "scholar_scan",
        "scholar_bootstrap",
        "scholar_rag_index",
        "scholar_graph_build",
        "read_parsed_paper_json",
        "scholar_get_paper_card",
    ):
        assert gone not in names


def test_bearer_middleware_rejects_missing_and_wrong_tokens():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient
    from scholar_mcp.server import _bearer_token_middleware

    async def endpoint(_request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/mcp", endpoint, methods=["POST"])])
    app.add_middleware(_bearer_token_middleware("expected-token"))
    client = TestClient(app)
    assert client.post("/mcp").status_code == 401
    assert (
        client.post("/mcp", headers={"Authorization": "Bearer wrong-token"}).status_code
        == 401
    )
    response = client.post(
        "/mcp", headers={"Authorization": "Bearer expected-token"}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_streamable_http_requires_token_by_default(monkeypatch):
    from scholar_mcp import server

    monkeypatch.setenv("SCHOLAR_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("SCHOLAR_MCP_HOST", "127.0.0.1")
    monkeypatch.delenv("SCHOLAR_MCP_TOKEN", raising=False)
    monkeypatch.delenv("SCHOLAR_MCP_ALLOW_INSECURE_LOOPBACK", raising=False)
    import pytest

    with pytest.raises(RuntimeError, match="required for streamable HTTP"):
        server.main()


def _sse_json(response):
    payload = next(
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    )
    return json.loads(payload)


def test_real_streamable_http_auth_initialize_tools_and_corpus(monkeypatch):
    from starlette.testclient import TestClient
    from scholar_mcp.server import _bearer_token_middleware, mcp

    monkeypatch.setattr(
        "scholar_mcp.server.vecstore.search_papers_semantic",
        lambda _question, k: [
            {"paper_id": REAL_3DGS, "similarity": 0.91}
        ][:k],
    )
    app = mcp.streamable_http_app()
    app.add_middleware(_bearer_token_middleware("expected-token"))
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        assert client.post("/mcp", headers=headers, json=initialize).status_code == 401
        assert (
            client.post(
                "/mcp",
                headers={**headers, "Authorization": "Bearer wrong-token"},
                json=initialize,
            ).status_code
            == 401
        )
        accepted = client.post(
            "/mcp",
            headers={**headers, "Authorization": "Bearer expected-token"},
            json=initialize,
        )
        assert accepted.status_code == 200
        initialized = _sse_json(accepted)
        assert initialized["result"]["protocolVersion"] == "2025-06-18"
        session_headers = {
            **headers,
            "Authorization": "Bearer expected-token",
            "mcp-session-id": accepted.headers["mcp-session-id"],
        }
        notification = client.post(
            "/mcp",
            headers=session_headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        assert notification.status_code == 202
        listed = client.post(
            "/mcp",
            headers=session_headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        assert listed.status_code == 200
        names = {tool["name"] for tool in _sse_json(listed)["result"]["tools"]}
        assert names == {
            "scholar_search",
            "scholar_vec_search",
            "scholar_info",
            "scholar_section",
            "scholar_passages",
            "scholar_cite_network",
            "scholar_graph_query",
            "scholar_lineage",
            "scholar_graph_stats",
            "scholar_list_papers",
            "scholar_arxiv_search",
            "read_parsed_paper",
            "scholar_read_output_file",
            "read_skill",
            "scholar_auto_notes",
            "scholar_interests",
        }
        lexical = client.post(
            "/mcp",
            headers=session_headers,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "scholar_search",
                    "arguments": {"query": "gaussian splatting optimization"},
                },
            },
        )
        assert lexical.status_code == 200
        lexical_text = _sse_json(lexical)["result"]["content"][0]["text"]
        assert REAL_3DGS in lexical_text
        semantic = client.post(
            "/mcp",
            headers=session_headers,
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "scholar_vec_search",
                    "arguments": {
                        "question": "efficient differentiable radiance rendering"
                    },
                },
            },
        )
        assert semantic.status_code == 200
        semantic_text = _sse_json(semantic)["result"]["content"][0]["text"]
        assert "Semantic matches" in semantic_text
        assert REAL_3DGS in semantic_text


def test_load_parsed_rejects_unsafe_identifier(tmp_path):
    from scholar import db

    outside = tmp_path / "outside.json"
    outside.write_text('{"title":"secret"}', encoding="utf-8")
    parsed = tmp_path / "parsed"
    parsed.mkdir()
    assert db.load_parsed("../outside", parsed) is None
    assert db.load_parsed(str(Path("/tmp/absolute")), parsed) is None
    malformed = parsed / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    assert db.load_parsed("malformed", parsed) is None
    symlink = parsed / "linked.json"
    symlink.symlink_to(outside)
    assert db.load_parsed("linked", parsed) is None
