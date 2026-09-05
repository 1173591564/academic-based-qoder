"""Snapshot-scoped graph traversal and statistics queries."""

from collections import defaultdict, deque


class GraphRepository:
    def graph_neighbors(
        self,
        graph_build_id: str,
        identifier: str,
        direction: str,
        edge_types: list[str] | None,
        limit: int,
    ) -> list[dict]:
        work_id = self.resolve_work_id(identifier)
        start_key = f"paper:{work_id}"
        clauses = ["e.build_id = %s"]
        params: list = [graph_build_id]
        if direction == "out":
            clauses.append("source.natural_key = %s")
        elif direction == "in":
            clauses.append("target.natural_key = %s")
        else:
            clauses.append("(source.natural_key = %s OR target.natural_key = %s)")
            params.append(start_key)
        params.append(start_key)
        if edge_types:
            clauses.append("e.edge_type = ANY(%s)")
            params.append(edge_types)
        params.append(limit)
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    f"""
                    SELECT e.id, e.edge_type, e.direct, e.weight, e.confidence,
                           e.evidence_node_ids, e.properties,
                           source.natural_key AS source_key,
                           source.label AS source_label,
                           target.natural_key AS target_key,
                           target.label AS target_label
                    FROM scholar_v2_graph_edges e
                    JOIN scholar_v2_graph_nodes source ON source.id = e.source_node_id
                    JOIN scholar_v2_graph_nodes target ON target.id = e.target_node_id
                    WHERE {" AND ".join(clauses)}
                    ORDER BY e.confidence DESC, e.edge_type, e.id
                    LIMIT %s
                    """,
                    params,
                )
                return [dict(row) for row in cur.fetchall()]

    def lineage(
        self, graph_build_id: str, source_identifier: str, target_identifier: str
    ) -> list[dict]:
        source_id = self.resolve_work_id(source_identifier)
        target_id = self.resolve_work_id(target_identifier)
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT source.natural_key AS source_key,
                           target.natural_key AS target_key, e.edge_type,
                           e.confidence, e.evidence_node_ids, e.properties
                    FROM scholar_v2_graph_edges e
                    JOIN scholar_v2_graph_nodes source ON source.id = e.source_node_id
                    JOIN scholar_v2_graph_nodes target ON target.id = e.target_node_id
                    WHERE e.build_id = %s
                      AND e.edge_type IN ('CITES', 'EXTENDS', 'COMPARES')
                    """,
                    (graph_build_id,),
                )
                edges = [dict(row) for row in cur.fetchall()]
        adjacency: dict[str, list[dict]] = defaultdict(list)
        for edge in edges:
            forward = dict(edge)
            forward["traversal"] = "forward"
            adjacency[edge["source_key"]].append(forward)
            reverse = dict(edge)
            reverse["traversal"] = "reverse"
            adjacency[edge["target_key"]].append(reverse)
        start = f"paper:{source_id}"
        goal = f"paper:{target_id}"
        queue = deque([(start, [])])
        visited = {start}
        while queue:
            node, path = queue.popleft()
            if len(path) >= 6:
                continue
            for edge in adjacency[node]:
                next_node = (
                    edge["target_key"]
                    if edge["traversal"] == "forward"
                    else edge["source_key"]
                )
                next_path = [*path, edge]
                if next_node == goal:
                    return next_path
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append((next_node, next_path))
        return []

    def graph_stats(self, graph_build_id: str) -> dict:
        with self.database.connection() as conn:
            with self._dict_cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT node_type, count(*) AS count
                    FROM scholar_v2_graph_nodes
                    WHERE build_id = %s GROUP BY node_type ORDER BY node_type
                    """,
                    (graph_build_id,),
                )
                nodes = {row["node_type"]: row["count"] for row in cur.fetchall()}
                cur.execute(
                    """
                    SELECT edge_type, count(*) AS count
                    FROM scholar_v2_graph_edges
                    WHERE build_id = %s GROUP BY edge_type ORDER BY edge_type
                    """,
                    (graph_build_id,),
                )
                edges = {row["edge_type"]: row["count"] for row in cur.fetchall()}
        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": sum(nodes.values()),
            "edge_count": sum(edges.values()),
        }
