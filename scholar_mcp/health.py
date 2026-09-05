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
                SELECT id, projection_type, status
                FROM scholar_v2_projection_builds
                WHERE id = ANY(%s)
                ORDER BY projection_type
                """,
                (build_ids,),
            )
            builds = [
                {"id": row[0], "kind": row[1], "state": row[2]}
                for row in cursor.fetchall()
            ]
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
