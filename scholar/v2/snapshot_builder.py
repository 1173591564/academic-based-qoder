"""Validated serving-snapshot construction."""

import json

import psycopg2.extras

from .database import V2Database
from .models import ScholarError
from .xml_utils import stable_id


class SnapshotBuilder:
    def __init__(self, database: V2Database):
        self.database = database

    def create(
        self,
        release_id: str,
        relational_build_id: str,
        graph_build_id: str | None = None,
        vector_build_id: str | None = None,
        semantic_build_id: str | None = None,
    ) -> dict:
        build_ids = [
            relational_build_id,
            graph_build_id,
            vector_build_id,
            semantic_build_id,
        ]
        required = [item for item in build_ids if item]
        expected_types = {
            relational_build_id: "relational",
            **({graph_build_id: "graph"} if graph_build_id else {}),
            **({vector_build_id: "vector"} if vector_build_id else {}),
            **({semantic_build_id: "semantic"} if semantic_build_id else {}),
        }
        with self.database.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, projection_type, status, release_id, metrics
                    FROM scholar_v2_projection_builds
                    WHERE id = ANY(%s)
                    """,
                    (required,),
                )
                builds = {row["id"]: dict(row) for row in cur.fetchall()}
                missing = [item for item in required if item not in builds]
                if missing:
                    raise ScholarError(
                        "SNAPSHOT_UNAVAILABLE",
                        f"snapshot builds not found: {', '.join(missing)}",
                    )
                invalid = [
                    item
                    for item in required
                    if builds[item]["status"] != "sealed"
                    or builds[item]["release_id"] != release_id
                    or builds[item]["projection_type"] != expected_types[item]
                ]
                if invalid:
                    raise ScholarError(
                        "SNAPSHOT_UNAVAILABLE",
                        "all snapshot builds must be sealed for the same release",
                    )
                incompatible = [
                    item
                    for item in required
                    if item != relational_build_id
                    and builds[item]["metrics"].get("relational_build_id")
                    != relational_build_id
                ]
                if incompatible:
                    raise ScholarError(
                        "SNAPSHOT_UNAVAILABLE",
                        "derived builds do not depend on the selected relational build",
                    )
                snapshot_id = stable_id(
                    "snapshot",
                    release_id,
                    relational_build_id,
                    graph_build_id or "",
                    vector_build_id or "",
                    semantic_build_id or "",
                )
                cur.execute(
                    """
                    INSERT INTO scholar_v2_serving_snapshots(
                        id, release_id, relational_build_id, lexical_build_id,
                        vector_build_id, graph_build_id, semantic_build_id,
                        status, validation, ready_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, 'ready', %s, now()
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        snapshot_id,
                        release_id,
                        relational_build_id,
                        relational_build_id,
                        vector_build_id,
                        graph_build_id,
                        semantic_build_id,
                        json.dumps(
                            {
                                "vector_available": vector_build_id is not None,
                                "graph_available": graph_build_id is not None,
                                "semantic_available": semantic_build_id is not None,
                            }
                        ),
                    ),
                )
                cur.execute(
                    "SELECT * FROM scholar_v2_serving_snapshots WHERE id = %s",
                    (snapshot_id,),
                )
                return dict(cur.fetchone())
