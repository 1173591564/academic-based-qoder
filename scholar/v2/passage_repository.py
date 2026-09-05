"""Lexical, vector, and citation-evidence passage queries."""

from .models import ScholarError


class PassageRepository:
    def vector_model(self, vector_build_id: str) -> dict | None:
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT m.provider, m.model, m.model_version, m.dimensions
                    FROM scholar_v2_chunk_embeddings e
                    JOIN scholar_v2_embedding_models m ON m.id = e.model_id
                    WHERE e.build_id = %s
                    LIMIT 1
                    """,
                    (vector_build_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def lexical_passages(
        self,
        lexical_build_id: str,
        query: str,
        limit: int,
        paper_id: str | None = None,
        section: str | None = None,
    ) -> list[dict]:
        if not query.strip() or not 1 <= limit <= 100:
            raise ScholarError("INVALID_ARGUMENT", "query and valid limit are required")
        clauses = ["c.build_id = %s"]
        params: list = [query, lexical_build_id]
        if paper_id:
            clauses.append("c.work_id = %s")
            params.append(self.resolve_work_id(paper_id, lexical_build_id))
        if section:
            clauses.append("(c.semantic_role = %s OR s.title ILIKE %s)")
            params.extend([section.lower(), f"%{section}%"])
        params.extend([query, limit])
        where = " AND ".join(clauses)
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    f"""
                    SELECT c.id, c.work_id, p.title AS paper_title, c.section_id,
                           s.title AS section_title, c.semantic_role, c.content,
                           c.xml_pointer_start, c.xml_pointer_end, c.artifact_id,
                           ts_rank_cd(
                               to_tsvector('simple', c.content),
                               websearch_to_tsquery('simple', %s)
                           ) AS score
                    FROM scholar_v2_chunks c
                    JOIN scholar_v2_papers p
                      ON p.build_id = c.build_id AND p.work_id = c.work_id
                    LEFT JOIN scholar_v2_sections s ON s.id = c.section_id
                    WHERE {where}
                      AND to_tsvector('simple', c.content)
                          @@ websearch_to_tsquery('simple', %s)
                    ORDER BY score DESC, c.work_id, c.ordinal
                    LIMIT %s
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]

    def vector_passages(
        self,
        vector_build_id: str,
        query_embedding: list[float],
        limit: int,
        paper_id: str | None = None,
        section: str | None = None,
    ) -> list[dict]:
        clauses = ["e.build_id = %s"]
        vector = "[" + ",".join(str(value) for value in query_embedding) + "]"
        params: list = [vector, vector_build_id]
        if paper_id:
            clauses.append("c.work_id = %s")
            params.append(self.resolve_work_id(paper_id))
        if section:
            clauses.append("(c.semantic_role = %s OR s.title ILIKE %s)")
            params.extend([section.lower(), f"%{section}%"])
        params.extend([vector, limit])
        where = " AND ".join(clauses)
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    f"""
                    SELECT c.id, c.work_id, p.title AS paper_title, c.section_id,
                           s.title AS section_title, c.semantic_role, c.content,
                           c.xml_pointer_start, c.xml_pointer_end, c.artifact_id,
                           1 - (e.embedding <=> %s::vector) AS score
                    FROM scholar_v2_chunk_embeddings e
                    JOIN scholar_v2_chunks c ON c.id = e.chunk_id
                    JOIN scholar_v2_papers p
                      ON p.build_id = c.build_id AND p.work_id = c.work_id
                    LEFT JOIN scholar_v2_sections s ON s.id = c.section_id
                    WHERE {where}
                    ORDER BY e.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]

    def citation_contexts(
        self,
        relational_build_id: str,
        graph_build_id: str,
        identifier: str,
        limit: int,
    ) -> list[dict]:
        work_id = self.resolve_work_id(identifier, relational_build_id)
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT cm.id, cm.content_node_id, cm.context_text,
                           cm.xml_pointer,
                           coalesce(cn.artifact_id, r.artifact_id) AS artifact_id,
                           cm.work_id AS citing_work_id, p.title AS citing_title,
                           r.title AS reference_title, r.raw_text
                    FROM scholar_v2_citation_mentions cm
                    JOIN scholar_v2_papers p
                      ON p.build_id = cm.build_id AND p.work_id = cm.work_id
                    LEFT JOIN scholar_v2_content_nodes cn
                      ON cn.id = cm.content_node_id
                    JOIN scholar_v2_references r ON r.id = cm.reference_id
                    JOIN scholar_v2_graph_edges e
                      ON e.build_id = %s
                     AND EXISTS (
                         SELECT 1
                         FROM jsonb_array_elements_text(
                             e.properties -> 'reference_ids'
                         ) AS reference_id(value)
                         WHERE reference_id.value = r.id
                     )
                    JOIN scholar_v2_graph_nodes target
                      ON target.id = e.target_node_id AND target.work_id = %s
                    WHERE cm.build_id = %s
                    ORDER BY p.title, cm.id LIMIT %s
                    """,
                    (graph_build_id, work_id, relational_build_id, limit),
                )
                return [dict(row) for row in cur.fetchall()]
