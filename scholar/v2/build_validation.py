"""Shared validation for derived projection builds."""

from .database import V2Database
from .models import ScholarError


def _validate_relational_build(
    database: V2Database, release_id: str, relational_build_id: str
) -> None:
    with database.cursor(read_only=True) as cur:
        cur.execute(
            """
            SELECT release_id, projection_type, status
            FROM scholar_v2_projection_builds
            WHERE id = %s
            """,
            (relational_build_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ScholarError("NOT_FOUND", "relational build not found")
    if row != (release_id, "relational", "sealed"):
        raise ScholarError(
            "INVALID_ARGUMENT",
            "source build must be a sealed relational build for this release",
        )
