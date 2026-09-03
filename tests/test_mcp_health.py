"""Scholar private readiness metadata tests."""

from pathlib import Path

from scholar import config, graph_mem
from scholar_mcp.health import readiness_payload


def test_readiness_requires_explicit_corpus_version(monkeypatch) -> None:
    monkeypatch.delenv("SCHOLAR_CORPUS_VERSION", raising=False)

    status, payload = readiness_payload()

    assert status == 503
    assert payload == {
        "status": "unavailable",
        "reason": "corpus_version_missing",
    }


def test_readiness_reports_bounded_corpus_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    parsed_dir = tmp_path / "parsed"
    parsed_dir.mkdir()
    (parsed_dir / "paper-a.json").write_text("{}", encoding="utf-8")
    graph_path = tmp_path / "graph.json"
    graph_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "PARSED_DIR", parsed_dir)
    monkeypatch.setattr(graph_mem, "GRAPH_CACHE", graph_path)
    monkeypatch.setenv("SCHOLAR_CORPUS_VERSION", "corpus-v1")
    monkeypatch.setenv("SCHOLAR_WORKSPACE_ISOLATION", "tenant")

    status, payload = readiness_payload()

    assert status == 200
    assert payload["status"] == "ready"
    assert payload["corpus_version"] == "corpus-v1"
    assert payload["parsed_papers"] == 1
    assert payload["workspace_isolation"] == "tenant"
    assert payload["graph_built_at"] is not None
    assert payload["synchronized_at"] is not None
