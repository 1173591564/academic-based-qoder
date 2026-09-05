"""Scholar v2 private readiness metadata tests."""

from contextlib import contextmanager

from scholar.v2.models import ScholarError
from scholar_mcp.health import readiness_payload


class FakeCursor:
    def execute(self, _query, _params) -> None:
        return None

    def fetchall(self):
        return [
            ("build-rel", "relational", "sealed"),
            ("build-graph", "graph", "sealed"),
        ]


class FakeDatabase:
    def active_snapshot(self):
        return {
            "id": "snapshot-test",
            "release_id": "release-test",
            "relational_build_id": "build-rel",
            "graph_build_id": "build-graph",
            "vector_build_id": None,
            "semantic_build_id": None,
            "schema_version": "scholar-v2-001",
        }

    @contextmanager
    def cursor(self, read_only=False):
        assert read_only is True
        yield FakeCursor()


def test_readiness_reports_snapshot_unavailable(monkeypatch) -> None:
    from scholar.v2 import runtime

    class UnavailableDatabase:
        def active_snapshot(self):
            raise ScholarError("SNAPSHOT_UNAVAILABLE", "no active production snapshot")

    monkeypatch.setattr(runtime, "get_database", lambda: UnavailableDatabase())
    status, payload = readiness_payload()
    assert status == 503
    assert payload == {
        "status": "unavailable",
        "mode": "v2",
        "code": "SNAPSHOT_UNAVAILABLE",
        "reason": "no active production snapshot",
    }


def test_readiness_reports_bounded_snapshot_metadata(monkeypatch) -> None:
    from scholar.v2 import runtime

    monkeypatch.setattr(runtime, "get_database", lambda: FakeDatabase())
    status, payload = readiness_payload()
    assert status == 200
    assert payload == {
        "status": "ready",
        "mode": "v2",
        "schema_version": "scholar-v2-001",
        "channel": "production",
        "snapshot_id": "snapshot-test",
        "corpus_release_id": "release-test",
        "builds": [
            {"id": "build-rel", "kind": "relational", "state": "sealed"},
            {"id": "build-graph", "kind": "graph", "state": "sealed"},
        ],
        "degraded_capabilities": ["vector", "semantic"],
    }
