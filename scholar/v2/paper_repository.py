"""Snapshot-scoped paper metadata and structural queries."""

import psycopg2.extras

from .database import V2Database
from .models import ScholarError


class PaperRepository:
    def __init__(self, database: V2Database):
        self.database = database

    def resolve_work_id(
        self, identifier: str, relational_build_id: str | None = None
    ) -> str:
        value = identifier.strip()
        if not value:
            raise ScholarError("INVALID_ARGUMENT", "paper identifier is required")
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                if relational_build_id:
                    cur.execute(
                        """
                        SELECT work_id FROM (
                            SELECT work_id
                            FROM scholar_v2_papers
                            WHERE build_id = %s AND work_id = %s
                            UNION
                            SELECT p.work_id
                            FROM scholar_v2_work_aliases a
                            JOIN scholar_v2_papers p ON p.work_id = a.work_id
                            WHERE p.build_id = %s AND a.alias = %s
                            UNION
                            SELECT p.work_id
                            FROM scholar_v2_work_identifiers i
                            JOIN scholar_v2_papers p ON p.work_id = i.work_id
                            WHERE p.build_id = %s AND i.value = %s
                        ) matches
                        """,
                        (
                            relational_build_id,
                            value,
                            relational_build_id,
                            value,
                            relational_build_id,
                            value,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        SELECT work_id FROM (
                            SELECT id AS work_id
                            FROM scholar_v2_works WHERE id = %s
                            UNION
                            SELECT work_id
                            FROM scholar_v2_work_aliases WHERE alias = %s
                            UNION
                            SELECT work_id
                            FROM scholar_v2_work_identifiers WHERE value = %s
                        ) matches
                        """,
                        (value, value, value),
                    )
                matches = [row["work_id"] for row in cur.fetchall()]
                if not matches:
                    if relational_build_id:
                        cur.execute(
                            """
                            SELECT work_id
                            FROM scholar_v2_papers
                            WHERE build_id = %s
                              AND normalized_title = regexp_replace(
                                  lower(%s), '[^a-z0-9]+', ' ', 'g'
                              )
                            LIMIT 2
                            """,
                            (relational_build_id, value),
                        )
                        matches = [row["work_id"] for row in cur.fetchall()]
                    else:
                        cur.execute(
                            """
                            SELECT id FROM scholar_v2_works
                            WHERE normalized_title = regexp_replace(
                                lower(%s), '[^a-z0-9]+', ' ', 'g'
                            )
                            LIMIT 2
                            """,
                            (value,),
                        )
                        matches = [row["id"] for row in cur.fetchall()]
        unique = list(dict.fromkeys(matches))
        if not unique:
            raise ScholarError("NOT_FOUND", f"paper not found: {identifier}")
        if len(unique) > 1:
            raise ScholarError(
                "AMBIGUOUS_ID", f"paper identifier is ambiguous: {identifier}"
            )
        return unique[0]

    def list_papers(
        self, relational_build_id: str, year: int | None, offset: int, limit: int
    ) -> list[dict]:
        if offset < 0 or not 1 <= limit <= 200:
            raise ScholarError("INVALID_ARGUMENT", "invalid pagination")
        params: list = [relational_build_id]
        year_clause = ""
        if year is not None:
            year_clause = "AND p.year = %s"
            params.append(year)
        params.extend([limit, offset])
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    f"""
                    SELECT p.work_id AS id, p.title, p.abstract, p.year, p.venue,
                           a.id AS artifact_id, a.storage_uri
                    FROM scholar_v2_papers p
                    JOIN scholar_v2_artifacts a ON a.id = p.artifact_id
                    WHERE p.build_id = %s {year_clause}
                    ORDER BY p.year DESC NULLS LAST, p.title, p.work_id
                    LIMIT %s OFFSET %s
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]

    def search_papers(
        self, relational_build_id: str, query: str, limit: int
    ) -> list[dict]:
        query = query.strip()
        if not query or not 1 <= limit <= 100:
            raise ScholarError("INVALID_ARGUMENT", "query and valid limit are required")
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    WITH ranked AS (
                        SELECT p.work_id AS id, p.title, p.abstract, p.year, p.venue,
                               ts_rank_cd(
                                   to_tsvector('simple', p.title || ' ' || p.abstract),
                                   websearch_to_tsquery('simple', %s)
                               ) AS rank
                        FROM scholar_v2_papers p
                        WHERE to_tsvector('simple', p.title || ' ' || p.abstract)
                              @@ websearch_to_tsquery('simple', %s)
                          AND p.build_id = %s
                    )
                    SELECT ranked.*, a.id AS artifact_id, a.storage_uri
                    FROM ranked
                    JOIN scholar_v2_papers p
                      ON p.build_id = %s AND p.work_id = ranked.id
                    JOIN scholar_v2_artifacts a ON a.id = p.artifact_id
                    ORDER BY rank DESC, year DESC NULLS LAST, title
                    LIMIT %s
                    """,
                    (query, query, relational_build_id, relational_build_id, limit),
                )
                return [dict(row) for row in cur.fetchall()]

    def get_paper(self, relational_build_id: str, identifier: str) -> dict:
        work_id = self.resolve_work_id(identifier, relational_build_id)
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT p.work_id AS id, p.title, p.abstract, p.year, p.venue,
                           p.metadata,
                           a.id AS artifact_id, a.storage_uri, a.raw_sha256,
                           a.canonical_sha256, qa.text_status, qa.math_status,
                           qa.citation_status, qa.render_status, qa.metrics
                    FROM scholar_v2_papers p
                    JOIN scholar_v2_artifacts a ON a.id = p.artifact_id
                    LEFT JOIN scholar_v2_quality_assessments qa
                      ON qa.artifact_id = a.id
                    WHERE p.build_id = %s AND p.work_id = %s
                    ORDER BY qa.created_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    (relational_build_id, work_id),
                )
                paper = cur.fetchone()
                if paper is None:
                    raise ScholarError(
                        "NOT_FOUND", f"paper unavailable in snapshot: {identifier}"
                    )
                result = dict(paper)
                cur.execute(
                    """
                    SELECT pa.author_id AS id, pa.display_name, pa.ordinal
                    FROM scholar_v2_paper_authors pa
                    WHERE pa.build_id = %s AND pa.work_id = %s
                    ORDER BY pa.ordinal
                    """,
                    (relational_build_id, work_id),
                )
                result["authors"] = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT scheme, value, is_primary, metadata
                    FROM scholar_v2_work_identifiers
                    WHERE work_id = %s ORDER BY scheme
                    """,
                    (work_id,),
                )
                result["identifiers"] = [dict(row) for row in cur.fetchall()]
                return result

    def outline(self, relational_build_id: str, identifier: str) -> list[dict]:
        work_id = self.resolve_work_id(identifier, relational_build_id)
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT id, parent_id, xml_id, node_kind, semantic_role,
                           level, ordinal, title, xml_pointer, metadata
                    FROM scholar_v2_sections
                    WHERE build_id = %s AND work_id = %s
                    ORDER BY ordinal
                    """,
                    (relational_build_id, work_id),
                )
                rows = [dict(row) for row in cur.fetchall()]
        if not rows:
            raise ScholarError(
                "NOT_FOUND", f"paper unavailable in snapshot: {identifier}"
            )
        return rows

    def section_text(
        self,
        relational_build_id: str,
        identifier: str,
        section: str,
        span: int,
        max_chars: int,
    ) -> dict:
        if span < 1 or span > 10 or max_chars < 1:
            raise ScholarError("INVALID_ARGUMENT", "invalid section bounds")
        work_id = self.resolve_work_id(identifier, relational_build_id)
        section_ordinal = int(section) if section.isdigit() else -1
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT id, ordinal, title, semantic_role, xml_pointer
                    FROM scholar_v2_sections
                    WHERE build_id = %s AND work_id = %s
                      AND (
                          id = %s OR xml_id = %s OR
                          ordinal = %s OR
                          lower(title) = lower(%s) OR semantic_role = lower(%s)
                      )
                    ORDER BY
                      CASE WHEN id = %s OR xml_id = %s THEN 0 ELSE 1 END,
                      ordinal
                    LIMIT 2
                    """,
                    (
                        relational_build_id,
                        work_id,
                        section,
                        section,
                        section_ordinal,
                        section,
                        section,
                        section,
                        section,
                    ),
                )
                matches = [dict(row) for row in cur.fetchall()]
                if not matches:
                    raise ScholarError("NOT_FOUND", f"section not found: {section}")
                selected = matches[0]
                cur.execute(
                    """
                    SELECT id, title, semantic_role, level, ordinal, xml_pointer
                    FROM scholar_v2_sections
                    WHERE build_id = %s AND work_id = %s AND ordinal >= %s
                    ORDER BY ordinal LIMIT %s
                    """,
                    (
                        relational_build_id,
                        work_id,
                        selected["ordinal"],
                        span,
                    ),
                )
                sections = [dict(row) for row in cur.fetchall()]
                section_ids = [item["id"] for item in sections]
                cur.execute(
                    """
                    SELECT id, section_id, node_kind, ordinal, text, tex, xml_pointer
                    FROM scholar_v2_content_nodes
                    WHERE build_id = %s AND work_id = %s
                      AND section_id = ANY(%s)
                      AND node_kind IN ('p', 'table', 'figure', 'equation',
                                        'equationgroup', 'formula')
                    ORDER BY ordinal
                    """,
                    (relational_build_id, work_id, section_ids),
                )
                nodes = [dict(row) for row in cur.fetchall()]
        bounded_nodes = []
        text_parts = []
        consumed = 0
        for node in nodes:
            if consumed >= max_chars:
                break
            text = node["text"] or ""
            remaining = max_chars - consumed
            bounded_text = text[:remaining]
            bounded_node = dict(node)
            bounded_node["text"] = bounded_text
            bounded_nodes.append(bounded_node)
            text_parts.append(bounded_text)
            consumed += len(bounded_text)
        return {
            "work_id": work_id,
            "sections": sections,
            "content_nodes": bounded_nodes,
            "text": "\n\n".join(text_parts),
            "truncated": sum(len(item["text"] or "") for item in nodes) > max_chars,
        }

    def _dict_cursor(self, connection):
        return connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
