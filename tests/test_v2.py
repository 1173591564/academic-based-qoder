import json
import threading
import time
from contextlib import contextmanager

import pytest

from scholar.v2.build_validation import _validate_relational_build
from scholar.v2.embeddings import EmbeddingProvider
from scholar.v2.snapshot_builder import SnapshotBuilder
from scholar.v2.importer import LaTeXMLProjector, normalized_name, stable_id
from scholar.v2.models import EvidencePointer, ScholarError, ToolEnvelope
from scholar.v2.runtime import RequestContext, RequestCoordinator
from scholar.v2.services import ScholarService


LATEXML_FIXTURE = """\
<document xmlns="http://dlmf.nist.gov/LaTeXML"
          xmlns:m="http://www.w3.org/1998/Math/MathML">
  <title>Evidence First Systems</title>
  <creator><personname>张 伟</personname></creator>
  <creator><personname>张 伟</personname></creator>
  <abstract xml:id="abs"><p xml:id="abs.p1">A structured abstract.</p></abstract>
  <section xml:id="s1">
    <title>Method</title>
    <p xml:id="s1.p1">We define
      <Math xml:id="m1" mode="inline" tex="x+y">
        <m:math><m:apply xml:id="m1.cmml"><m:plus/><m:ci>x</m:ci><m:ci>y</m:ci></m:apply></m:math>
      </Math>
      and cite <cite><ref idref="bib.b1"/></cite>.
    </p>
    <table xml:id="t1">
      <caption>Results</caption>
      <tabular><tr><th>Metric</th><td>1.0</td></tr></tabular>
    </table>
  </section>
  <bibliography>
    <biblist>
      <bibitem xml:id="bib.b1" key="ref1">
        <bib-name>Example Author</bib-name>
        <bib-title>Prior Work</bib-title>, 2020.
      </bibitem>
    </biblist>
  </bibliography>
</document>
"""


def test_projector_preserves_structure_and_evidence(tmp_path):
    xml_path = tmp_path / "paper.xml"
    xml_path.write_text(LATEXML_FIXTURE, encoding="utf-8")

    projection = LaTeXMLProjector().parse("paper-1", xml_path, "build-1")

    assert projection.title == "Evidence First Systems"
    assert projection.authors == ["张 伟"]
    assert [section.semantic_role for section in projection.sections] == [
        "abstract",
        "method",
    ]
    assert len(projection.formulas) == 1
    assert projection.formulas[0].tex == "x+y"
    assert projection.formulas[0].cmml_valid is True
    assert len(projection.tables) == 1
    assert projection.tables[0].cells[0]["text"] == "Metric"
    assert len(projection.references) == 1
    assert projection.references[0].title == "Prior Work"
    assert len(projection.citation_mentions) == 1
    assert projection.citation_mentions[0].reference_xml_id == "bib.b1"
    assert projection.chunks
    assert all(
        chunk.xml_pointer_start.startswith("/document[1]")
        for chunk in projection.chunks
    )


def test_projection_identifiers_are_build_scoped(tmp_path):
    xml_path = tmp_path / "paper.xml"
    xml_path.write_text(LATEXML_FIXTURE, encoding="utf-8")
    projector = LaTeXMLProjector()

    first = projector.parse("paper-1", xml_path, "build-1")
    repeated = projector.parse("paper-1", xml_path, "build-1")
    second = projector.parse("paper-1", xml_path, "build-2")

    assert first.sections[0].id == repeated.sections[0].id
    assert first.sections[0].id != second.sections[0].id
    assert first.chunks[0].id != second.chunks[0].id


def test_unicode_author_normalization_and_stable_ids():
    assert normalized_name("  张　伟  ") == "张 伟"
    assert normalized_name("Émilie-Du Châtelet") == "émilie du châtelet"
    assert stable_id("work", "same") == stable_id("work", "same")
    assert stable_id("work", "same") != stable_id("work", "other")


def test_tool_envelope_serializes_evidence():
    envelope = ToolEnvelope(
        request_id="request-1",
        snapshot_id="snapshot-1",
        data={"papers": []},
        evidence=[
            EvidencePointer(
                paper_id="paper-1",
                node_id="node-1",
                xml_artifact_id="artifact-1",
                xml_pointer="/document[1]/section[1]",
            )
        ],
    )

    payload = envelope.as_dict()

    assert json.loads(json.dumps(payload))["evidence"][0]["node_id"] == "node-1"
    assert payload["schema_version"] == "scholar.tool.v2"


class _SnapshotDatabase:
    def active_snapshot(self):
        return {"id": "snapshot-1", "relational_build_id": "rel-1"}


def test_request_context_deadline_and_cancellation():
    expired = RequestContext("request-1", time.monotonic() - 1, {"id": "snapshot-1"})
    with pytest.raises(ScholarError, match="deadline exceeded") as deadline:
        expired.check()
    assert deadline.value.code == "DEADLINE_EXCEEDED"

    cancelled = RequestContext(
        "request-2", time.monotonic() + 10, {"id": "snapshot-1"}, threading.Event()
    )
    cancelled.cancelled.set()
    with pytest.raises(ScholarError, match="cancelled") as cancellation:
        cancelled.check()
    assert cancellation.value.code == "CANCELLED"


def test_request_coordinator_pins_snapshot_and_releases_capacity():
    coordinator = RequestCoordinator(_SnapshotDatabase(), max_inflight=1)

    with coordinator.request("search", 1_000, "request-1") as context:
        assert context.snapshot_id == "snapshot-1"
        assert context.request_id == "request-1"

    with coordinator.request("search", 1_000, "request-2") as context:
        assert context.request_id == "request-2"


class _PassageRepository:
    def lexical_passages(self, *_args):
        return [
            {
                "id": "chunk-1",
                "work_id": "paper-1",
                "artifact_id": "artifact-1",
                "xml_pointer_start": "/document[1]/section[1]/p[1]",
                "content": "lexical evidence",
                "score": 1.0,
            }
        ]

    def vector_model(self, _build_id):
        return {
            "provider": "deterministic-test",
            "model": "sha256",
            "model_version": "v2",
            "dimensions": 1024,
        }


def test_hybrid_search_degrades_to_lexical_without_vector_build():
    context = RequestContext(
        "request-1",
        time.monotonic() + 10,
        {
            "id": "snapshot-1",
            "relational_build_id": "rel-1",
            "lexical_build_id": "rel-1",
            "vector_build_id": None,
        },
    )

    result = ScholarService(_PassageRepository()).search_passages(
        context, "evidence", mode="hybrid"
    )

    assert result.degraded is True
    assert result.data["passages"][0]["id"] == "chunk-1"
    assert result.warnings == [
        "vector projection unavailable; lexical results returned"
    ]


def test_pure_vector_search_requires_vector_projection():
    context = RequestContext(
        "request-1",
        time.monotonic() + 10,
        {
            "id": "snapshot-1",
            "relational_build_id": "rel-1",
            "lexical_build_id": "rel-1",
            "vector_build_id": None,
        },
    )

    with pytest.raises(ScholarError) as error:
        ScholarService(_PassageRepository()).search_passages(
            context, "evidence", mode="vector"
        )
    assert error.value.code == "VECTOR_UNAVAILABLE"


def test_vector_search_rejects_provider_that_does_not_match_snapshot():
    context = RequestContext(
        "request-1",
        time.monotonic() + 10,
        {
            "id": "snapshot-1",
            "relational_build_id": "rel-1",
            "lexical_build_id": "rel-1",
            "vector_build_id": "vec-1",
        },
    )
    provider = EmbeddingProvider("openai", "text-embedding-3-small", "unused", 1024)

    with pytest.raises(ScholarError) as error:
        ScholarService(_PassageRepository(), provider).search_passages(
            context, "evidence", mode="vector"
        )
    assert error.value.code == "VECTOR_UNAVAILABLE"
    assert "does not match" in error.value.message


def test_hybrid_search_degrades_when_provider_does_not_match_snapshot():
    context = RequestContext(
        "request-1",
        time.monotonic() + 10,
        {
            "id": "snapshot-1",
            "relational_build_id": "rel-1",
            "lexical_build_id": "rel-1",
            "vector_build_id": "vec-1",
        },
    )
    provider = EmbeddingProvider("openai", "text-embedding-3-small", "unused", 1024)

    result = ScholarService(_PassageRepository(), provider).search_passages(
        context, "evidence", mode="hybrid"
    )

    assert result.degraded is True
    assert result.data["passages"][0]["id"] == "chunk-1"
    assert "does not match" in result.warnings[0]


class _BuildValidationCursor:
    def __init__(self, row):
        self.row = row

    def execute(self, _query, _params):
        return None

    def fetchone(self):
        return self.row


class _BuildValidationDatabase:
    def __init__(self, row):
        self.row = row

    @contextmanager
    def cursor(self, read_only=False):
        assert read_only is True
        yield _BuildValidationCursor(self.row)


@pytest.mark.parametrize(
    "row",
    [
        ("other-release", "relational", "sealed"),
        ("release-1", "graph", "sealed"),
        ("release-1", "relational", "running"),
    ],
)
def test_derived_builds_require_matching_sealed_relational_source(row):
    with pytest.raises(ScholarError) as error:
        _validate_relational_build(
            _BuildValidationDatabase(row), "release-1", "build-rel"
        )
    assert error.value.code == "INVALID_ARGUMENT"


class _SnapshotCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query, _params):
        return None

    def fetchall(self):
        return self.rows


class _SnapshotBuildDatabase:
    def __init__(self, rows):
        self.rows = rows

    @contextmanager
    def connection(self):
        database = self

        class Connection:
            @contextmanager
            def cursor(self, cursor_factory=None):
                assert cursor_factory is not None
                yield _SnapshotCursor(database.rows)

        yield Connection()


def test_snapshot_rejects_derived_build_from_another_relational_build():
    rows = [
        {
            "id": "build-rel",
            "projection_type": "relational",
            "status": "sealed",
            "release_id": "release-1",
            "metrics": {},
        },
        {
            "id": "build-graph",
            "projection_type": "graph",
            "status": "sealed",
            "release_id": "release-1",
            "metrics": {"relational_build_id": "build-other"},
        },
    ]
    with pytest.raises(ScholarError) as error:
        SnapshotBuilder(_SnapshotBuildDatabase(rows)).create(
            "release-1", "build-rel", graph_build_id="build-graph"
        )
    assert error.value.code == "SNAPSHOT_UNAVAILABLE"
