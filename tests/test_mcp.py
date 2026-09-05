"""MCP compatibility tests over the Scholar v2 adapter boundary."""

import asyncio
import json
import runpy

import pytest

from scholar.v2.models import EvidencePointer, ScholarError, ToolEnvelope


PAPER_ID = "01KT6MTARQMB6JVJNZA9PJVTS2"
SNAPSHOT_ID = "snapshot-test"


def test_module_entrypoint_calls_server_main(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("scholar_mcp.server.main", lambda: calls.append(True))

    runpy.run_module("scholar_mcp", run_name="__main__")

    assert calls == [True]


def envelope(data: dict, degraded: bool = False) -> ToolEnvelope:
    return ToolEnvelope(
        request_id="request-test",
        snapshot_id=SNAPSHOT_ID,
        data=data,
        evidence=[
            EvidencePointer(
                paper_id=PAPER_ID,
                node_id=None,
                xml_artifact_id="artifact-test",
                xml_pointer="/document[1]",
                quote="Evidence.",
            )
        ],
        degraded=degraded,
    )


def test_corpus_tools_delegate_to_v2_adapter(monkeypatch) -> None:
    from scholar_mcp import server

    calls = []

    def record(name):
        def operation(*args):
            calls.append((name, args))
            return name

        return operation

    for name in (
        "search",
        "vector_search",
        "paper_info",
        "section",
        "passages",
        "cite_network",
        "graph_query",
        "lineage",
        "graph_stats",
        "list_papers",
        "parsed_paper",
        "auto_notes",
    ):
        monkeypatch.setattr(server.v2_adapter, name, record(name))

    assert server.scholar_search("query", 999) == "search"
    assert server.scholar_vec_search("question", 0) == "vector_search"
    assert server.scholar_info(PAPER_ID) == "paper_info"
    assert server.scholar_section(PAPER_ID, "[2]", 99) == "section"
    assert server.scholar_passages("query", 99, PAPER_ID, "method", True) == "passages"
    assert server.scholar_cite_network(PAPER_ID) == "cite_network"
    assert server.scholar_graph_query("transformer") == "graph_query"
    assert server.scholar_lineage(PAPER_ID, "paper-b") == "lineage"
    assert server.scholar_graph_stats() == "graph_stats"
    assert server.scholar_list_papers(2023, -1) == "list_papers"
    assert server.read_parsed_paper(PAPER_ID, True) == "parsed_paper"
    assert server.scholar_auto_notes(PAPER_ID, True) == "auto_notes"
    assert calls == [
        ("search", ("query", 20)),
        ("vector_search", ("question", 1)),
        ("paper_info", (PAPER_ID,)),
        ("section", (PAPER_ID, "[2]", 5)),
        ("passages", ("query", 20, PAPER_ID, "method", True)),
        ("cite_network", (PAPER_ID,)),
        ("graph_query", ("transformer",)),
        ("lineage", (PAPER_ID, "paper-b")),
        ("graph_stats", ()),
        ("list_papers", (2023, 0)),
        (
            "parsed_paper",
            (PAPER_ID, True, server.MAX_FULL_JSON_CHARS),
        ),
        ("auto_notes", (PAPER_ID, True)),
    ]


def test_corpus_tools_render_typed_errors(monkeypatch) -> None:
    from scholar_mcp import server

    def unavailable(*_args):
        raise ScholarError("SNAPSHOT_UNAVAILABLE", "no active snapshot")

    monkeypatch.setattr(server.v2_adapter, "search", unavailable)
    assert server.scholar_search("query") == "[SNAPSHOT_UNAVAILABLE] no active snapshot"


def test_adapter_renders_search_and_paper_info(monkeypatch) -> None:
    from scholar_mcp import v2_adapter

    paper = {
        "id": PAPER_ID,
        "title": "Evidence First Systems",
        "abstract": "Structured source evidence.",
        "year": 2026,
        "venue": "TestConf",
        "rank": 0.75,
        "artifact_id": "artifact-test",
        "authors": [{"display_name": "Test Author"}],
    }
    monkeypatch.setattr(
        v2_adapter,
        "call",
        lambda *_args, **_kwargs: envelope({"papers": [paper]}),
    )
    search = v2_adapter.search("evidence", 10)
    assert PAPER_ID in search
    assert "score=0.75" in search

    monkeypatch.setattr(
        v2_adapter,
        "call",
        lambda *_args, **_kwargs: envelope(
            {
                "paper": paper,
                "outline": [
                    {
                        "id": "section-1",
                        "title": "Method",
                        "level": 1,
                    }
                ],
            }
        ),
    )
    info = v2_adapter.paper_info(PAPER_ID)
    assert "Title:     Evidence First Systems" in info
    assert "[0] (L1) Method" in info


def test_adapter_renders_section_passages_and_graph(monkeypatch) -> None:
    from scholar_mcp import v2_adapter

    section_response = envelope(
        {
            "sections": [
                {
                    "id": "section-1",
                    "ordinal": 3,
                    "title": "Method",
                    "level": 1,
                }
            ],
            "content_nodes": [
                {
                    "id": "node-1",
                    "section_id": "section-1",
                    "text": "Method evidence.",
                }
            ],
        }
    )
    monkeypatch.setattr(v2_adapter, "call", lambda *_args, **_kwargs: section_response)
    assert "[3] Method" in v2_adapter.section(PAPER_ID, "[3]", 1)

    passage_response = envelope(
        {
            "passages": [
                {
                    "id": "chunk-1",
                    "work_id": PAPER_ID,
                    "paper_title": "Evidence First Systems",
                    "section_title": "Method",
                    "content": "Method evidence.",
                    "score": 0.8,
                }
            ]
        }
    )
    monkeypatch.setattr(v2_adapter, "call", lambda *_args, **_kwargs: passage_response)
    assert "score=0.8" in v2_adapter.passages("method", 5, PAPER_ID, None, True)

    graph_response = envelope(
        {
            "paper_id": PAPER_ID,
            "edges": [
                {
                    "source_key": f"paper:{PAPER_ID}",
                    "target_key": "paper:target",
                    "source_label": "Source",
                    "target_label": "Target",
                    "confidence": 0.92,
                }
            ],
        }
    )
    monkeypatch.setattr(v2_adapter, "call", lambda *_args, **_kwargs: graph_response)
    assert "-> Target" in v2_adapter.cite_network(PAPER_ID)


def test_read_output_file_is_confined(tmp_path, monkeypatch) -> None:
    from scholar_mcp import server

    output = tmp_path / "output"
    output.mkdir()
    (output / "note.md").write_text("content", encoding="utf-8")
    monkeypatch.setattr(server.scholar_config, "OUTPUT_DIR", output)

    assert server.scholar_read_output_file("note.md") == "content"
    assert "Access denied" in server.scholar_read_output_file("../secret.txt")
    assert "Access denied" in server.scholar_read_output_file(
        str(tmp_path / "secret.txt")
    )


def test_read_skill_rejects_unsafe_names() -> None:
    from scholar_mcp.server import read_skill

    assert "not found" in read_skill("../research-survey").lower()
    assert "not found" in read_skill("research-survey/../../dsh").lower()


def test_arxiv_search_uses_external_api(monkeypatch, sample_arxiv_xml) -> None:
    from scholar_mcp import server

    monkeypatch.setattr(
        server.scholar_config,
        "arxiv_request",
        lambda _query, max_results: sample_arxiv_xml,
    )
    result = server.scholar_arxiv_search("attention", max_results=2)
    assert "2403.12345" in result
    assert "2406.67890" in result


def test_tool_surface_is_exactly_the_legacy_sixteen() -> None:
    from scholar_mcp.server import mcp

    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
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


def test_bearer_middleware_rejects_missing_and_wrong_tokens() -> None:
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from scholar_mcp.transport import bearer_token_middleware

    async def endpoint(_request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/mcp", endpoint, methods=["POST"])])
    app.add_middleware(bearer_token_middleware("expected-token"))
    client = TestClient(app)
    assert client.post("/mcp").status_code == 401
    assert (
        client.post("/mcp", headers={"Authorization": "Bearer wrong-token"}).status_code
        == 401
    )
    response = client.post("/mcp", headers={"Authorization": "Bearer expected-token"})
    assert response.status_code == 200


def test_streamable_http_requires_token_by_default(monkeypatch) -> None:
    from scholar_mcp import server

    monkeypatch.setenv("SCHOLAR_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("SCHOLAR_MCP_HOST", "127.0.0.1")
    monkeypatch.delenv("SCHOLAR_MCP_TOKEN", raising=False)
    monkeypatch.delenv("SCHOLAR_MCP_ALLOW_INSECURE_LOOPBACK", raising=False)
    with pytest.raises(RuntimeError, match="required for streamable HTTP"):
        server.main()


def _sse_json(response):
    payload = next(
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    )
    return json.loads(payload)


def test_streamable_http_initialize_list_and_call(monkeypatch) -> None:
    from starlette.testclient import TestClient

    from scholar_mcp import server, transport

    monkeypatch.setattr(
        server.v2_adapter,
        "search",
        lambda query, limit: f"Search: {query} ({limit})",
    )
    app = server.mcp.streamable_http_app()
    app.add_middleware(transport.bearer_token_middleware("expected-token"))
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Authorization": "Bearer expected-token",
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
        accepted = client.post("/mcp", headers=headers, json=initialize)
        assert accepted.status_code == 200
        session_headers = {
            **headers,
            "mcp-session-id": accepted.headers["mcp-session-id"],
        }
        client.post(
            "/mcp",
            headers=session_headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        listed = client.post(
            "/mcp",
            headers=session_headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )
        assert len(_sse_json(listed)["result"]["tools"]) == 16
        called = client.post(
            "/mcp",
            headers=session_headers,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "scholar_search",
                    "arguments": {"query": "evidence", "limit": 2},
                },
            },
        )
        text = _sse_json(called)["result"]["content"][0]["text"]
        assert text == "Search: evidence (2)"
