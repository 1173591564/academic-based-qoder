"""Private readiness metadata for the active Scholar snapshot."""

from scholar import config
from scholar.v2 import runtime
from scholar.v2.models import ScholarError


def readiness_payload():
    """Return bounded readiness metadata without exposing corpus content."""
    try:
        database = runtime.get_database()
        snapshot = database.active_snapshot()
        build_ids = [
            build_id
            for build_id in (
                snapshot["relational_build_id"],
                snapshot["graph_build_id"],
                snapshot["vector_build_id"],
                snapshot["semantic_build_id"],
            )
            if build_id
        ]
        with database.cursor(read_only=True) as cursor:
            cursor.execute(
                """
                SELECT id, projection_type, status, source_count, output_count,
                       metrics, sealed_at
                FROM scholar_v2_projection_builds
                WHERE id = ANY(%s)
                ORDER BY projection_type
                """,
                (build_ids,),
            )
            build_rows = cursor.fetchall()
        builds = [{"id": row[0], "kind": row[1], "state": row[2]} for row in build_rows]
        build_metadata = {
            row[1]: {
                "source_count": row[3],
                "output_count": row[4],
                "metrics": row[5],
                "sealed_at": row[6],
            }
            for row in build_rows
        }
        relational = build_metadata["relational"]
        vector = build_metadata.get("vector")
        graph = build_metadata.get("graph")
        degraded = [
            kind
            for kind, build_id in (
                ("vector", snapshot["vector_build_id"]),
                ("graph", snapshot["graph_build_id"]),
                ("semantic", snapshot["semantic_build_id"]),
            )
            if build_id is None
        ]
        return 200, {
            "status": "ready",
            "mode": "v2",
            "schema_version": snapshot["schema_version"],
            "channel": config.V2_SERVING_CHANNEL,
            "snapshot_id": snapshot["id"],
            "corpus_release_id": snapshot["release_id"],
            "corpus_version": snapshot["release_id"],
            "parsed_papers": relational["metrics"].get(
                "works", relational["source_count"]
            ),
            "vector_chunks": (
                vector["metrics"].get("embedded", vector["output_count"])
                if vector
                else 0
            ),
            "graph_built_at": (
                graph["sealed_at"].isoformat()
                if graph and graph["sealed_at"] is not None
                else None
            ),
            "synchronized_at": (
                snapshot["ready_at"].isoformat()
                if snapshot["ready_at"] is not None
                else None
            ),
            "workspace_isolation": "shared",
            "builds": builds,
            "degraded_capabilities": degraded,
        }
    except ScholarError as error:
        return 503, {
            "status": "unavailable",
            "mode": "v2",
            "code": error.code,
            "reason": error.message,
        }
    except Exception:
        return 503, {
            "status": "unavailable",
            "mode": "v2",
            "code": "INTERNAL",
            "reason": "Scholar v2 readiness check failed",
        }
