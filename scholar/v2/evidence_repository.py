"""Structured evidence, table, and parsed-document queries."""


class EvidenceRepository:
    def reference_evidence(
        self, relational_build_id: str, reference_ids: list[str]
    ) -> list[dict]:
        if not reference_ids:
            return []
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT r.id, r.work_id, r.raw_text, r.xml_pointer,
                           p.artifact_id
                    FROM scholar_v2_references r
                    JOIN scholar_v2_papers p
                      ON p.build_id = r.build_id AND p.work_id = r.work_id
                    WHERE r.build_id = %s AND r.id = ANY(%s)
                    ORDER BY r.id
                    """,
                    (relational_build_id, reference_ids),
                )
                return [dict(row) for row in cur.fetchall()]

    def sections_by_roles(
        self,
        relational_build_id: str,
        roles: list[str],
        work_ids: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses = ["s.build_id = %s", "s.semantic_role = ANY(%s)"]
        params: list = [relational_build_id, roles]
        if work_ids:
            clauses.append("s.work_id = ANY(%s)")
            params.append(work_ids)
        params.append(limit)
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    f"""
                    SELECT s.id, s.work_id, p.title AS paper_title, s.title,
                           s.semantic_role, s.level, s.ordinal, s.xml_pointer,
                           a.id AS artifact_id,
                           left(
                               string_agg(n.text, E'\\n\\n' ORDER BY n.ordinal)
                                   FILTER (WHERE n.node_kind = 'p'),
                               20000
                           ) AS text
                    FROM scholar_v2_sections s
                    JOIN scholar_v2_papers p
                      ON p.build_id = s.build_id AND p.work_id = s.work_id
                    JOIN scholar_v2_content_nodes n
                      ON n.section_id = s.id AND n.build_id = s.build_id
                    JOIN scholar_v2_artifacts a ON a.id = n.artifact_id
                    WHERE {" AND ".join(clauses)}
                    GROUP BY s.id, s.work_id, p.title, s.title, s.semantic_role,
                             s.level, s.ordinal, s.xml_pointer, a.id
                    ORDER BY p.title, s.ordinal
                    LIMIT %s
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]

    def paper_tables(
        self, relational_build_id: str, identifier: str, limit: int = 50
    ) -> list[dict]:
        work_id = self.resolve_work_id(identifier, relational_build_id)
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT t.id, t.caption, t.xml_pointer, n.artifact_id,
                           n.section_id, s.title AS section_title,
                           s.semantic_role
                    FROM scholar_v2_tables t
                    JOIN scholar_v2_content_nodes n ON n.id = t.content_node_id
                    LEFT JOIN scholar_v2_sections s ON s.id = n.section_id
                    WHERE t.build_id = %s AND t.work_id = %s
                    ORDER BY n.ordinal LIMIT %s
                    """,
                    (relational_build_id, work_id, limit),
                )
                tables = [dict(row) for row in cur.fetchall()]
                for table in tables:
                    cur.execute(
                        """
                        SELECT row_index, column_index, row_span, column_span,
                               text, is_header
                        FROM scholar_v2_table_cells
                        WHERE table_id = %s
                        ORDER BY row_index, column_index
                        """,
                        (table["id"],),
                    )
                    table["cells"] = [dict(row) for row in cur.fetchall()]
        return tables

    def parsed_document(
        self, relational_build_id: str, identifier: str, full: bool
    ) -> dict:
        paper = self.get_paper(relational_build_id, identifier)
        outline = self.outline(relational_build_id, identifier)
        result = {"paper": paper, "outline": outline}
        if not full:
            return result
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT id, section_id, parent_id, xml_id, node_kind,
                           semantic_role, ordinal, title, text, tex, xml_pointer
                    FROM scholar_v2_content_nodes
                    WHERE build_id = %s AND work_id = %s
                    ORDER BY ordinal
                    """,
                    (relational_build_id, paper["id"]),
                )
                result["content_nodes"] = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT id, content_node_id, xml_id, mode, tex, cmml_valid,
                           xml_pointer
                    FROM scholar_v2_formulas
                    WHERE build_id = %s AND work_id = %s
                    ORDER BY id
                    """,
                    (relational_build_id, paper["id"]),
                )
                result["formulas"] = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """
                    SELECT id, xml_id, citation_key, raw_text, title, authors,
                           year, identifiers, xml_pointer
                    FROM scholar_v2_references
                    WHERE build_id = %s AND work_id = %s
                    ORDER BY id
                    """,
                    (relational_build_id, paper["id"]),
                )
                result["references"] = [dict(row) for row in cur.fetchall()]
        return result
