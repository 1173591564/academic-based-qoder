"""Evidence-first Scholar v2 query services."""

from __future__ import annotations

from collections.abc import Callable

from .embeddings import EmbeddingProvider
from .models import EvidencePointer, ScholarError, ToolEnvelope
from .repositories import ScholarRepository
from .runtime import RequestContext


class ScholarService:
    def __init__(
        self,
        repository: ScholarRepository,
        embed_fn: Callable[[str], list[float] | None] | None = None,
    ):
        self.repository = repository
        self.embed_fn = embed_fn

    def search_papers(
        self, context: RequestContext, query: str, limit: int = 10
    ) -> ToolEnvelope:
        context.check()
        rows = self.repository.search_papers(
            context.snapshot["relational_build_id"], query, limit
        )
        return self._envelope(context, {"papers": rows}, self._paper_evidence(rows))

    def get_paper(self, context: RequestContext, paper_id: str) -> ToolEnvelope:
        context.check()
        paper = self.repository.get_paper(
            context.snapshot["relational_build_id"], paper_id
        )
        return self._envelope(
            context,
            {"paper": paper},
            [
                EvidencePointer(
                    paper_id=paper["id"],
                    node_id=None,
                    xml_artifact_id=paper["artifact_id"],
                    xml_pointer="/document[1]",
                    quote=paper["abstract"][:500],
                )
            ],
        )

    def get_paper_outline(self, context: RequestContext, paper_id: str) -> ToolEnvelope:
        context.check()
        work_id = self.repository.resolve_work_id(
            paper_id, context.snapshot["relational_build_id"]
        )
        rows = self.repository.outline(context.snapshot["relational_build_id"], work_id)
        paper = self.repository.get_paper(
            context.snapshot["relational_build_id"], work_id
        )
        evidence = [
            EvidencePointer(
                paper_id=work_id,
                node_id=row["id"],
                xml_artifact_id=paper["artifact_id"],
                xml_pointer=row["xml_pointer"],
                quote=row["title"],
            )
            for row in rows
        ]
        return self._envelope(
            context, {"paper_id": work_id, "sections": rows}, evidence
        )

    def get_section_text(
        self,
        context: RequestContext,
        paper_id: str,
        section: str,
        span: int = 1,
        max_chars: int = 20_000,
    ) -> ToolEnvelope:
        context.check()
        result = self.repository.section_text(
            context.snapshot["relational_build_id"],
            paper_id,
            section,
            span,
            max_chars,
        )
        paper = self.repository.get_paper(
            context.snapshot["relational_build_id"], result["work_id"]
        )
        evidence = [
            EvidencePointer(
                paper_id=result["work_id"],
                node_id=node["id"],
                xml_artifact_id=paper["artifact_id"],
                xml_pointer=node["xml_pointer"],
                quote=(node["text"] or "")[:500],
            )
            for node in result["content_nodes"][:50]
        ]
        return self._envelope(context, result, evidence)

    def search_passages(
        self,
        context: RequestContext,
        query: str,
        limit: int = 10,
        paper_id: str | None = None,
        section: str | None = None,
        mode: str = "hybrid",
    ) -> ToolEnvelope:
        if mode not in {"lexical", "vector", "hybrid"}:
            raise ScholarError(
                "INVALID_ARGUMENT", "mode must be lexical, vector, or hybrid"
            )
        context.check()
        lexical = []
        vector = []
        warnings = []
        degraded = False
        resolved_paper_id = (
            self.repository.resolve_work_id(
                paper_id, context.snapshot["relational_build_id"]
            )
            if paper_id
            else None
        )
        if mode in {"lexical", "hybrid"}:
            lexical = self.repository.lexical_passages(
                context.snapshot["lexical_build_id"],
                query,
                limit * 3 if mode == "hybrid" else limit,
                resolved_paper_id,
                section,
            )
        if mode in {"vector", "hybrid"}:
            vector_build_id = context.snapshot.get("vector_build_id")
            if not vector_build_id:
                if mode == "vector":
                    raise ScholarError(
                        "VECTOR_UNAVAILABLE", "snapshot has no vector build"
                    )
                warnings.append(
                    "vector projection unavailable; lexical results returned"
                )
                degraded = True
            else:
                if isinstance(self.embed_fn, EmbeddingProvider):
                    model = self.repository.vector_model(vector_build_id)
                    if model is None or (
                        model["provider"] != self.embed_fn.provider
                        or model["model"] != self.embed_fn.model
                        or model["dimensions"] != self.embed_fn.dimensions
                    ):
                        if mode == "vector":
                            raise ScholarError(
                                "VECTOR_UNAVAILABLE",
                                "configured embedding provider does not match "
                                "the active vector build",
                            )
                        warnings.append(
                            "active vector build does not match the embedding "
                            "provider; lexical results returned"
                        )
                        degraded = True
                        return self._envelope(
                            context,
                            {"passages": lexical[:limit], "mode": mode},
                            self._passage_evidence(lexical[:limit]),
                            warnings,
                            degraded,
                        )
                context.check()
                if isinstance(self.embed_fn, EmbeddingProvider):
                    try:
                        embedding = self.embed_fn.embed(
                            query, max(0.001, context.remaining_ms() / 1000)
                        )
                    except ScholarError:
                        context.check()
                        raise
                else:
                    embedding = self.embed_fn(query) if self.embed_fn else None
                if not embedding:
                    if mode == "vector":
                        raise ScholarError(
                            "VECTOR_UNAVAILABLE", "embedding provider unavailable"
                        )
                    warnings.append(
                        "embedding provider unavailable; lexical results returned"
                    )
                    degraded = True
                else:
                    vector = self.repository.vector_passages(
                        vector_build_id,
                        embedding,
                        limit * 3 if mode == "hybrid" else limit,
                        resolved_paper_id,
                        section,
                    )
        if mode == "hybrid" and vector:
            rows = self._rrf(lexical, vector, limit)
        elif mode == "vector":
            rows = vector[:limit]
        else:
            rows = lexical[:limit]
        return self._envelope(
            context,
            {"passages": rows, "mode": mode},
            self._passage_evidence(rows),
            warnings,
            degraded,
        )

    def get_citation_context(
        self, context: RequestContext, paper_id: str, limit: int = 20
    ) -> ToolEnvelope:
        graph_build_id = context.snapshot.get("graph_build_id")
        if not graph_build_id:
            raise ScholarError("GRAPH_UNAVAILABLE", "snapshot has no graph build")
        context.check()
        rows = self.repository.citation_contexts(
            context.snapshot["relational_build_id"],
            graph_build_id,
            paper_id,
            limit,
        )
        evidence = [
            EvidencePointer(
                paper_id=row["citing_work_id"],
                node_id=row["content_node_id"],
                xml_artifact_id=row["artifact_id"],
                xml_pointer=row["xml_pointer"],
                quote=row["context_text"][:500],
            )
            for row in rows
        ]
        return self._envelope(context, {"citations": rows}, evidence)

    def get_lineage(
        self, context: RequestContext, paper_a: str, paper_b: str
    ) -> ToolEnvelope:
        graph_build_id = context.snapshot.get("graph_build_id")
        if not graph_build_id:
            raise ScholarError("GRAPH_UNAVAILABLE", "snapshot has no graph build")
        context.check()
        relational_build_id = context.snapshot["relational_build_id"]
        source_id = self.repository.resolve_work_id(paper_a, relational_build_id)
        target_id = self.repository.resolve_work_id(paper_b, relational_build_id)
        path = self.repository.lineage(graph_build_id, source_id, target_id)
        return self._envelope(
            context,
            {"path": path},
            self._graph_edge_evidence(relational_build_id, path),
        )

    def graph_neighbors(
        self,
        context: RequestContext,
        paper_id: str,
        direction: str = "both",
        edge_types: list[str] | None = None,
        limit: int = 50,
    ) -> ToolEnvelope:
        graph_build_id = context.snapshot.get("graph_build_id")
        if not graph_build_id:
            raise ScholarError("GRAPH_UNAVAILABLE", "snapshot has no graph build")
        context.check()
        work_id = self.repository.resolve_work_id(
            paper_id, context.snapshot["relational_build_id"]
        )
        rows = self.repository.graph_neighbors(
            graph_build_id, work_id, direction, edge_types, limit
        )
        return self._envelope(
            context,
            {
                "paper_id": work_id,
                "edges": rows,
            },
            self._graph_edge_evidence(context.snapshot["relational_build_id"], rows),
        )

    def graph_stats(self, context: RequestContext) -> ToolEnvelope:
        graph_build_id = context.snapshot.get("graph_build_id")
        if not graph_build_id:
            raise ScholarError("GRAPH_UNAVAILABLE", "snapshot has no graph build")
        return self._envelope(context, self.repository.graph_stats(graph_build_id))

    def get_method_modules(
        self,
        context: RequestContext,
        paper_ids: list[str] | None = None,
        limit: int = 50,
    ) -> ToolEnvelope:
        work_ids = (
            [
                self.repository.resolve_work_id(
                    item, context.snapshot["relational_build_id"]
                )
                for item in paper_ids
            ]
            if paper_ids
            else None
        )
        rows = self.repository.sections_by_roles(
            context.snapshot["relational_build_id"],
            ["method"],
            work_ids,
            limit,
        )
        return self._envelope(
            context,
            {"method_sections": rows},
            self._section_evidence(rows),
        )

    def compare_methods(
        self, context: RequestContext, paper_ids: list[str]
    ) -> ToolEnvelope:
        if not 2 <= len(paper_ids) <= 10:
            raise ScholarError("INVALID_ARGUMENT", "compare 2 to 10 papers")
        return self.get_method_modules(context, paper_ids, limit=50)

    def get_experiment_table(
        self, context: RequestContext, paper_id: str, limit: int = 20
    ) -> ToolEnvelope:
        rows = self.repository.paper_tables(
            context.snapshot["relational_build_id"], paper_id, limit
        )
        evidence = [
            EvidencePointer(
                paper_id=self.repository.resolve_work_id(
                    paper_id, context.snapshot["relational_build_id"]
                ),
                node_id=row["id"],
                xml_artifact_id=row["artifact_id"],
                xml_pointer=row["xml_pointer"],
                quote=row["caption"][:500],
            )
            for row in rows
        ]
        return self._envelope(context, {"tables": rows}, evidence)

    def compare_results(
        self, context: RequestContext, paper_ids: list[str]
    ) -> ToolEnvelope:
        if not 2 <= len(paper_ids) <= 10:
            raise ScholarError("INVALID_ARGUMENT", "compare 2 to 10 papers")
        tables = []
        evidence = []
        for paper_id in paper_ids:
            response = self.get_experiment_table(context, paper_id)
            tables.append(
                {
                    "paper_id": self.repository.resolve_work_id(
                        paper_id, context.snapshot["relational_build_id"]
                    ),
                    "tables": response.data["tables"],
                }
            )
            evidence.extend(response.evidence)
        return self._envelope(
            context,
            {"papers": tables},
            evidence,
            [
                "table evidence is L1; metric normalization and result comparability "
                "require a sealed semantic build"
            ],
            True,
        )

    def verify_claims(
        self, context: RequestContext, claim: str, limit: int = 10
    ) -> ToolEnvelope:
        response = self.search_passages(context, claim, limit=limit, mode="hybrid")
        response.data = {
            "claim": claim,
            "evidence_candidates": response.data["passages"],
            "verdict": "not_determined",
        }
        response.warnings.append(
            "retrieved evidence candidates do not constitute formal claim verification"
        )
        response.degraded = True
        return response

    def recommend_papers(
        self, context: RequestContext, paper_id: str, limit: int = 8
    ) -> ToolEnvelope:
        source = self.repository.get_paper(
            context.snapshot["relational_build_id"], paper_id
        )
        query = f"{source['title']} {source['abstract']}"
        response = self.search_passages(context, query, limit=limit * 3, mode="hybrid")
        seen = {source["id"]}
        papers = []
        for row in response.data["passages"]:
            if row["work_id"] in seen:
                continue
            seen.add(row["work_id"])
            papers.append(
                {
                    "paper_id": row["work_id"],
                    "title": row["paper_title"],
                    "score": row["score"],
                }
            )
            if len(papers) == limit:
                break
        response.data = {"source_paper_id": source["id"], "papers": papers}
        return response

    def get_gap_evidence(
        self, context: RequestContext, limit: int = 50
    ) -> ToolEnvelope:
        rows = self.repository.sections_by_roles(
            context.snapshot["relational_build_id"],
            ["limitations", "conclusion"],
            limit=limit,
        )
        return self._envelope(
            context,
            {"sections": rows},
            self._section_evidence(rows),
            ["these are source sections, not model-inferred research gaps"],
        )

    def read_parsed_paper(
        self, context: RequestContext, paper_id: str, full: bool = False
    ) -> ToolEnvelope:
        data = self.repository.parsed_document(
            context.snapshot["relational_build_id"], paper_id, full
        )
        paper = data["paper"]
        return self._envelope(
            context,
            data,
            [
                EvidencePointer(
                    paper_id=paper["id"],
                    node_id=None,
                    xml_artifact_id=paper["artifact_id"],
                    xml_pointer="/document[1]",
                    quote=paper["abstract"][:500],
                )
            ],
        )

    def list_papers(
        self,
        context: RequestContext,
        year: int | None = None,
        offset: int = 0,
        limit: int = 30,
    ) -> ToolEnvelope:
        rows = self.repository.list_papers(
            context.snapshot["relational_build_id"], year, offset, limit
        )
        return self._envelope(context, {"papers": rows}, self._paper_evidence(rows))

    def _envelope(
        self,
        context: RequestContext,
        data: dict | list,
        evidence: list[EvidencePointer] | None = None,
        warnings: list[str] | None = None,
        degraded: bool = False,
    ) -> ToolEnvelope:
        context.check()
        return ToolEnvelope(
            request_id=context.request_id,
            snapshot_id=context.snapshot_id,
            data=data,
            evidence=evidence or [],
            warnings=warnings or [],
            degraded=degraded,
        )

    def _paper_evidence(self, rows: list[dict]) -> list[EvidencePointer]:
        return [
            EvidencePointer(
                paper_id=row["id"],
                node_id=None,
                xml_artifact_id=row["artifact_id"],
                xml_pointer="/document[1]",
                quote=(row["abstract"] or "")[:500],
            )
            for row in rows
        ]

    def _passage_evidence(self, rows: list[dict]) -> list[EvidencePointer]:
        return [
            EvidencePointer(
                paper_id=row["work_id"],
                node_id=row["id"],
                xml_artifact_id=row["artifact_id"],
                xml_pointer=row["xml_pointer_start"],
                quote=row["content"][:500],
            )
            for row in rows
        ]

    def _section_evidence(self, rows: list[dict]) -> list[EvidencePointer]:
        return [
            EvidencePointer(
                paper_id=row["work_id"],
                node_id=row["id"],
                xml_artifact_id=row["artifact_id"],
                xml_pointer=row["xml_pointer"],
                quote=(row["text"] or "")[:500],
                fact_level="L2",
                extractor="section-role-heuristic-v1",
                confidence=0.9,
            )
            for row in rows
        ]

    def _graph_edge_evidence(
        self, relational_build_id: str, edges: list[dict]
    ) -> list[EvidencePointer]:
        reference_ids = sorted(
            {
                reference_id
                for edge in edges
                for reference_id in edge.get("properties", {}).get("reference_ids", [])
            }
        )
        rows = self.repository.reference_evidence(relational_build_id, reference_ids)
        return [
            EvidencePointer(
                paper_id=row["work_id"],
                node_id=row["id"],
                xml_artifact_id=row["artifact_id"],
                xml_pointer=row["xml_pointer"],
                quote=row["raw_text"][:500],
            )
            for row in rows
        ]

    def _rrf(self, lexical: list[dict], vector: list[dict], limit: int) -> list[dict]:
        scores: dict[str, float] = {}
        rows = {}
        for ranking in (lexical, vector):
            for rank, row in enumerate(ranking, 1):
                rows[row["id"]] = row
                scores[row["id"]] = scores.get(row["id"], 0.0) + 1 / (60 + rank)
        merged = sorted(scores, key=scores.get, reverse=True)[:limit]
        result = []
        for row_id in merged:
            row = dict(rows[row_id])
            row["score"] = round(scores[row_id], 6)
            result.append(row)
        return result
