"""Versioned citation and authorship graph projection."""

import hashlib
import json

import psycopg2.extras

from .build_validation import _validate_relational_build
from .database import V2Database
from .models import ScholarError
from .xml_utils import normalized_title, stable_id


class GraphBuilder:
    RESOLVER_VERSION = "citation-resolver-v4"

    def __init__(self, database: V2Database):
        self.database = database

    def build(self, release_id: str, relational_build_id: str) -> dict:
        _validate_relational_build(self.database, release_id, relational_build_id)
        config_hash = hashlib.sha256(
            f"{relational_build_id}:{self.RESOLVER_VERSION}".encode("utf-8")
        ).hexdigest()
        build_id = stable_id("build", release_id, "graph", config_hash)
        with self.database.advisory_lock(f"{release_id}:graph:{config_hash}"):
            existing = self._prepare(
                build_id, release_id, relational_build_id, config_hash
            )
            if existing:
                return existing
            try:
                result = self._populate(build_id, relational_build_id)
                self._seal(build_id, result)
                return {"build_id": build_id, **result}
            except Exception as error:
                self._fail(build_id, error)
                raise

    def _prepare(
        self,
        build_id: str,
        release_id: str,
        relational_build_id: str,
        config_hash: str,
    ) -> dict | None:
        with self.database.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, metrics FROM scholar_v2_projection_builds
                    WHERE id = %s
                    """,
                    (build_id,),
                )
                row = cur.fetchone()
                if row and row[0] == "sealed":
                    metrics = row[1] if isinstance(row[1], dict) else {}
                    return {"build_id": build_id, **metrics}
                cur.execute(
                    "DELETE FROM scholar_v2_projection_builds WHERE id = %s",
                    (build_id,),
                )
                cur.execute(
                    """
                    INSERT INTO scholar_v2_projection_builds(
                        id, release_id, projection_type, config_hash,
                        schema_version, extractor_version, status, metrics, started_at
                    ) VALUES (
                        %s, %s, 'graph', %s, 'scholar-v2-001', %s,
                        'running', %s, now()
                    )
                    """,
                    (
                        build_id,
                        release_id,
                        config_hash,
                        self.RESOLVER_VERSION,
                        json.dumps({"relational_build_id": relational_build_id}),
                    ),
                )
        return None

    def _populate(self, build_id: str, relational_build_id: str) -> dict:
        with self.database.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT p.work_id, p.title, p.normalized_title, p.artifact_id
                    FROM scholar_v2_papers p
                    WHERE p.build_id = %s
                    """,
                    (relational_build_id,),
                )
                papers = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT work_id, author_id, display_name
                    FROM scholar_v2_paper_authors
                    WHERE build_id = %s
                    """,
                    (relational_build_id,),
                )
                authorships = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT r.id AS reference_id, r.work_id, r.xml_id,
                           r.raw_text, r.title, r.identifiers, r.xml_pointer,
                           a.id AS artifact_id
                    FROM scholar_v2_references r
                    JOIN scholar_v2_artifacts a ON a.id = r.artifact_id
                    WHERE r.build_id = %s
                    """,
                    (relational_build_id,),
                )
                references = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT reference_id,
                           array_agg(DISTINCT content_node_id) AS evidence_node_ids
                    FROM scholar_v2_citation_mentions
                    WHERE build_id = %s AND reference_id IS NOT NULL
                      AND content_node_id IS NOT NULL
                    GROUP BY reference_id
                    """,
                    (relational_build_id,),
                )
                evidence_nodes = {
                    row["reference_id"]: row["evidence_node_ids"]
                    for row in cur.fetchall()
                }

        paper_nodes = {
            paper["work_id"]: stable_id("gnode", build_id, "paper", paper["work_id"])
            for paper in papers
        }
        author_nodes = {
            author["author_id"]: stable_id(
                "gnode", build_id, "author", author["author_id"]
            )
            for author in authorships
        }
        nodes = [
            (
                node_id,
                build_id,
                "paper",
                f"paper:{paper['work_id']}",
                paper["work_id"],
                paper["title"],
                json.dumps(
                    {
                        "normalized_title": paper["normalized_title"],
                        "artifact_id": paper["artifact_id"],
                    }
                ),
            )
            for paper in papers
            for node_id in [paper_nodes[paper["work_id"]]]
        ]
        nodes.extend(
            (
                node_id,
                build_id,
                "author",
                f"author:{author_id}",
                None,
                next(
                    item["display_name"]
                    for item in authorships
                    if item["author_id"] == author_id
                ),
                "{}",
            )
            for author_id, node_id in author_nodes.items()
        )
        edges = []
        for authorship in authorships:
            source = paper_nodes.get(authorship["work_id"])
            target = author_nodes.get(authorship["author_id"])
            if source and target:
                edges.append(
                    (
                        stable_id(
                            "gedge",
                            build_id,
                            "AUTHORED_BY",
                            authorship["work_id"],
                            authorship["author_id"],
                        ),
                        build_id,
                        source,
                        target,
                        "AUTHORED_BY",
                        True,
                        1.0,
                        1.0,
                        "[]",
                        "latexml",
                        self.RESOLVER_VERSION,
                        json.dumps(
                            {
                                "fact_level": "L1",
                                "work_id": authorship["work_id"],
                            }
                        ),
                    )
                )

        title_index = {
            paper["normalized_title"]: paper["work_id"]
            for paper in papers
            if paper["normalized_title"]
        }
        titles_by_length = sorted(title_index, key=len, reverse=True)
        resolved_references: dict[str, tuple[str, float, str]] = {}
        citation_edges: dict[tuple[str, str], dict] = {}
        for reference in references:
            candidate = None
            confidence = 0.0
            rule = ""
            reference_title = normalized_title(reference["title"] or "")
            if reference_title and reference_title in title_index:
                candidate = title_index[reference_title]
                confidence = 0.99
                rule = "normalized-title-exact"
            elif reference["raw_text"]:
                normalized_raw = normalized_title(reference["raw_text"])
                for title in titles_by_length:
                    if len(title) >= 24 and title in normalized_raw:
                        candidate = title_index[title]
                        confidence = 0.92
                        rule = "normalized-title-substring"
                        break
            if candidate and candidate != reference["work_id"]:
                resolved_references[reference["reference_id"]] = (
                    candidate,
                    confidence,
                    rule,
                )
                key = (reference["work_id"], candidate)
                edge = citation_edges.setdefault(
                    key,
                    {
                        "confidence": confidence,
                        "reference_ids": [],
                        "evidence_node_ids": [],
                        "evidence": [],
                    },
                )
                edge["confidence"] = max(edge["confidence"], confidence)
                edge["reference_ids"].append(reference["reference_id"])
                edge["evidence_node_ids"].extend(
                    evidence_nodes.get(reference["reference_id"], [])
                )
                edge["evidence"].append(
                    {
                        "artifact_id": reference["artifact_id"],
                        "xml_pointer": reference["xml_pointer"],
                        "reference_id": reference["reference_id"],
                        "resolver_rule": rule,
                    }
                )

        for (source_work_id, target_work_id), edge in citation_edges.items():
            edges.append(
                (
                    stable_id(
                        "gedge",
                        build_id,
                        "CITES",
                        source_work_id,
                        target_work_id,
                    ),
                    build_id,
                    paper_nodes[source_work_id],
                    paper_nodes[target_work_id],
                    "CITES",
                    True,
                    1.0,
                    edge["confidence"],
                    json.dumps(sorted(set(edge["evidence_node_ids"]))),
                    self.RESOLVER_VERSION,
                    self.RESOLVER_VERSION,
                    json.dumps(
                        {
                            "fact_level": "L2",
                            "reference_ids": edge["reference_ids"],
                            "evidence": edge["evidence"],
                        }
                    ),
                )
            )

        with self.database.connection() as conn:
            with conn.cursor() as cur:
                if nodes:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                        INSERT INTO scholar_v2_graph_nodes(
                            id, build_id, node_type, natural_key, work_id,
                            label, properties
                        ) VALUES %s
                        """,
                        nodes,
                    )
                if edges:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                        INSERT INTO scholar_v2_graph_edges(
                            id, build_id, source_node_id, target_node_id,
                            edge_type, direct, weight, confidence,
                            evidence_node_ids, extractor, extractor_version,
                            properties
                        ) VALUES %s
                        """,
                        edges,
                    )
        return {
            "nodes": len(nodes),
            "edges": len(edges),
            "citation_edges": len(citation_edges),
            "resolved_references": len(resolved_references),
            "authorship_edges": len(edges) - len(citation_edges),
        }

    def _seal(self, build_id: str, metrics: dict) -> None:
        with self.database.cursor() as cur:
            cur.execute(
                """
                UPDATE scholar_v2_projection_builds
                SET status = 'sealed', output_count = %s,
                    metrics = metrics || %s::jsonb,
                    sealed_at = now()
                WHERE id = %s
                """,
                (metrics["edges"], json.dumps(metrics), build_id),
            )

    def _fail(self, build_id: str, error: Exception) -> None:
        try:
            with self.database.cursor() as cur:
                cur.execute(
                    """
                    UPDATE scholar_v2_projection_builds
                    SET status = 'failed', error_code = %s, error_message = %s
                    WHERE id = %s
                    """,
                    (
                        error.code if isinstance(error, ScholarError) else "INTERNAL",
                        str(error)[:1000],
                        build_id,
                    ),
                )
        except Exception:
            pass
