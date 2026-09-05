"""Import an immutable XML release and persist its relational projection."""

import csv
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import psycopg2.extras

from scholar import config

from .database import V2Database
from .models import ScholarError
from .projection_models import PaperProjection
from .xml_projector import LaTeXMLProjector
from .xml_utils import SAFE_ID, normalized_name, normalized_title, stable_id


class CorpusImporter:
    """Persist one immutable release and its relational projection."""

    SCHEMA_VERSION = "scholar-v2-001"
    EXTRACTOR_VERSION = "latexml-projector-v4"

    def __init__(self, database: V2Database, projector: LaTeXMLProjector | None = None):
        self.database = database
        self.projector = projector or LaTeXMLProjector()

    def import_release(
        self,
        source_dir: Path,
        release_id: str,
        release_name: str | None = None,
        artifact_root: Path | None = None,
    ) -> dict:
        source_dir = Path(source_dir).resolve()
        manifest_path = source_dir / "manifest.csv"
        if not manifest_path.is_file():
            raise ScholarError("INVALID_ARGUMENT", "manifest.csv is required")
        rows = self._manifest_rows(manifest_path)
        manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        config_hash = hashlib.sha256(
            (manifest_sha + self.SCHEMA_VERSION + self.EXTRACTOR_VERSION).encode(
                "ascii"
            )
        ).hexdigest()
        build_id = stable_id("build", release_id, "relational", config_hash)
        artifact_root = (
            Path(artifact_root)
            if artifact_root is not None
            else config.V2_CORPUS_DIR / "releases" / release_id
        ).resolve()
        with self.database.advisory_lock(f"{release_id}:relational:{config_hash}"):
            already_imported = self._prepare_release(
                release_id,
                release_name or release_id,
                manifest_sha,
                source_dir,
                len(rows),
                build_id,
                config_hash,
            )
            if already_imported:
                return self._existing_result(release_id, build_id, artifact_root)
            copied_manifest = artifact_root / "manifest.csv"
            self._immutable_copy(manifest_path, copied_manifest, manifest_sha)
            duplicates = source_dir / "duplicates.csv"
            if duplicates.is_file():
                self._immutable_copy(
                    duplicates,
                    artifact_root / "duplicates.csv",
                    hashlib.sha256(duplicates.read_bytes()).hexdigest(),
                )
            totals: dict[str, int] = defaultdict(int)
            try:
                for row in rows:
                    paper_id = row["paper_id"]
                    xml_source = source_dir / paper_id / "latexml" / "paper.xml"
                    raw = xml_source.read_bytes()
                    try:
                        expected_size = int(row["size_bytes"])
                    except ValueError as error:
                        raise ScholarError(
                            "INVALID_ARGUMENT",
                            f"invalid size_bytes for {paper_id}",
                        ) from error
                    if len(raw) != expected_size:
                        raise ScholarError(
                            "INVALID_ARGUMENT",
                            f"size mismatch for {paper_id}",
                        )
                    raw_sha = hashlib.sha256(raw).hexdigest()
                    if raw_sha != row["sha256"]:
                        raise ScholarError(
                            "INVALID_ARGUMENT",
                            f"raw SHA-256 mismatch for {paper_id}",
                        )
                    canonical = ET.canonicalize(xml_data=raw.decode("utf-8"))
                    canonical_sha = hashlib.sha256(
                        canonical.encode("utf-8")
                    ).hexdigest()
                    if canonical_sha != row["canonical_sha256"]:
                        raise ScholarError(
                            "INVALID_ARGUMENT",
                            f"canonical SHA-256 mismatch for {paper_id}",
                        )
                    target = artifact_root / paper_id / "latexml" / "paper.xml"
                    self._immutable_copy(xml_source, target, raw_sha)
                    projection = self.projector.parse(
                        paper_id, target, namespace=build_id
                    )
                    self._insert_paper(
                        release_id,
                        build_id,
                        target,
                        row,
                        projection,
                    )
                    totals["works"] += 1
                    totals["sections"] += len(projection.sections)
                    totals["content_nodes"] += len(projection.content_nodes)
                    totals["formulas"] += len(projection.formulas)
                    totals["tables"] += len(projection.tables)
                    totals["references"] += len(projection.references)
                    totals["citation_mentions"] += len(projection.citation_mentions)
                    totals["chunks"] += len(projection.chunks)
                self._seal_release(release_id, build_id, totals)
            except Exception as error:
                self._fail_release(release_id, build_id, error)
                raise
        return {
            "release_id": release_id,
            "build_id": build_id,
            "artifact_root": str(artifact_root),
            **totals,
        }

    def _manifest_rows(self, manifest_path: Path) -> list[dict]:
        with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ScholarError("INVALID_ARGUMENT", "manifest.csv is empty")
        required = {
            "paper_id",
            "title",
            "size_bytes",
            "sha256",
            "canonical_sha256",
            "quality_tier",
        }
        if not required.issubset(rows[0]):
            raise ScholarError("INVALID_ARGUMENT", "manifest.csv has missing columns")
        ids = [row["paper_id"] for row in rows]
        if len(ids) != len(set(ids)) or any(
            not SAFE_ID.fullmatch(item) for item in ids
        ):
            raise ScholarError(
                "INVALID_ARGUMENT", "manifest contains invalid paper IDs"
            )
        return rows

    def _immutable_copy(self, source: Path, target: Path, expected_sha: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            observed = hashlib.sha256(target.read_bytes()).hexdigest()
            if observed != expected_sha:
                raise ScholarError(
                    "INVALID_ARGUMENT", f"immutable artifact conflict at {target.name}"
                )
            return
        temporary = target.with_suffix(target.suffix + ".partial")
        shutil.copyfile(source, temporary)
        observed = hashlib.sha256(temporary.read_bytes()).hexdigest()
        if observed != expected_sha:
            temporary.unlink(missing_ok=True)
            raise ScholarError("INTERNAL", "artifact copy verification failed")
        temporary.replace(target)

    def _prepare_release(
        self,
        release_id: str,
        name: str,
        manifest_sha: str,
        source_dir: Path,
        expected_works: int,
        build_id: str,
        config_hash: str,
    ) -> bool:
        with self.database.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5min'")
                cur.execute(
                    """
                    SELECT status, manifest_sha256
                    FROM scholar_v2_corpus_releases WHERE id = %s
                    """,
                    (release_id,),
                )
                existing = cur.fetchone()
                if existing and existing[0] == "sealed":
                    if existing[1] != manifest_sha:
                        raise ScholarError(
                            "INVALID_ARGUMENT", "sealed release manifest cannot change"
                        )
                    cur.execute(
                        """
                        SELECT status FROM scholar_v2_projection_builds WHERE id = %s
                        """,
                        (build_id,),
                    )
                    build = cur.fetchone()
                    if build and build[0] == "sealed":
                        return True
                cur.execute(
                    """
                    INSERT INTO scholar_v2_corpus_releases(
                        id, name, manifest_sha256, source_uri, expected_works, status
                    ) VALUES (%s, %s, %s, %s, %s, 'importing')
                    ON CONFLICT (id) DO UPDATE SET
                        status = CASE
                            WHEN scholar_v2_corpus_releases.status = 'sealed'
                                THEN 'sealed'
                            ELSE 'importing'
                        END,
                        sealed_at = CASE
                            WHEN scholar_v2_corpus_releases.status = 'sealed'
                                THEN scholar_v2_corpus_releases.sealed_at
                            ELSE NULL
                        END
                    """,
                    (
                        release_id,
                        name,
                        manifest_sha,
                        source_dir.as_uri(),
                        expected_works,
                    ),
                )
                cur.execute(
                    "DELETE FROM scholar_v2_projection_builds WHERE id = %s",
                    (build_id,),
                )
                cur.execute(
                    """
                    INSERT INTO scholar_v2_projection_builds(
                        id, release_id, projection_type, config_hash,
                        schema_version, extractor_version, status, source_count,
                        started_at
                    ) VALUES (%s, %s, 'relational', %s, %s, %s, 'running', %s, now())
                    """,
                    (
                        build_id,
                        release_id,
                        config_hash,
                        self.SCHEMA_VERSION,
                        self.EXTRACTOR_VERSION,
                        expected_works,
                    ),
                )
        return False

    def _existing_result(
        self, release_id: str, build_id: str, artifact_root: Path
    ) -> dict:
        with self.database.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT metrics
                    FROM scholar_v2_projection_builds
                    WHERE id = %s AND status = 'sealed'
                    """,
                    (build_id,),
                )
                row = cur.fetchone()
        metrics = row[0] if row and isinstance(row[0], dict) else {}
        return {
            "release_id": release_id,
            "build_id": build_id,
            "artifact_root": str(artifact_root),
            **metrics,
        }

    def _insert_paper(
        self,
        release_id: str,
        build_id: str,
        xml_path: Path,
        manifest: dict,
        projection: PaperProjection,
    ) -> None:
        work_version_id = stable_id("version", release_id, projection.paper_id)
        artifact_id = stable_id("artifact", release_id, manifest["sha256"])
        with self.database.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scholar_v2_works(
                        id, title, normalized_title, abstract, year, venue, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        projection.paper_id,
                        projection.title or manifest["title"],
                        projection.normalized_title
                        or normalized_title(manifest["title"]),
                        projection.abstract,
                        projection.year,
                        projection.venue,
                        json.dumps({"manifest": manifest}),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO scholar_v2_work_aliases(alias, work_id, alias_type)
                    VALUES (%s, %s, 'internal')
                    ON CONFLICT (alias) DO UPDATE SET work_id = EXCLUDED.work_id
                    """,
                    (projection.paper_id, projection.paper_id),
                )
                cur.execute(
                    """
                    INSERT INTO scholar_v2_work_versions(
                        id, work_id, release_id, version_label, source_metadata
                    ) VALUES (%s, %s, %s, 'accepted-latexml', %s)
                    ON CONFLICT (release_id, work_id) DO NOTHING
                    """,
                    (
                        work_version_id,
                        projection.paper_id,
                        release_id,
                        json.dumps(
                            {
                                "quality_tier": manifest["quality_tier"],
                                "title": projection.title or manifest["title"],
                                "abstract": projection.abstract,
                                "year": projection.year,
                                "venue": projection.venue,
                                "authors": projection.authors,
                            }
                        ),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO scholar_v2_artifacts(
                        id, release_id, work_version_id, kind, media_type, storage_uri,
                        raw_sha256, canonical_sha256, size_bytes, metadata
                    ) VALUES (
                        %s, %s, %s, 'latexml_xml', 'application/xml', %s,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        artifact_id,
                        release_id,
                        work_version_id,
                        xml_path.as_uri(),
                        manifest["sha256"],
                        manifest["canonical_sha256"],
                        int(manifest["size_bytes"]),
                        json.dumps({"authority": "immutable_xml"}),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO scholar_v2_papers(
                        build_id, work_id, artifact_id, title, normalized_title,
                        abstract, year, venue, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        build_id,
                        projection.paper_id,
                        artifact_id,
                        projection.title or manifest["title"],
                        projection.normalized_title
                        or normalized_title(manifest["title"]),
                        projection.abstract,
                        projection.year,
                        projection.venue,
                        json.dumps({"manifest": manifest}),
                    ),
                )
                quality_id = stable_id("quality", artifact_id, "strict-clean-v1")
                cur.execute(
                    """
                    INSERT INTO scholar_v2_quality_assessments(
                        id, artifact_id, assessor, assessor_version,
                        text_status, math_status, citation_status, render_status,
                        metrics, reasons
                    ) VALUES (
                        %s, %s, 'strict-clean-gate', 'v1',
                        'ready', 'ready', 'ready', 'not_evaluated', %s, '[]'::jsonb
                    )
                    ON CONFLICT (artifact_id, assessor, assessor_version) DO NOTHING
                    """,
                    (quality_id, artifact_id, json.dumps(manifest)),
                )
                for ordinal, author_name in enumerate(projection.authors):
                    author_key = normalized_name(author_name)
                    author_id = stable_id("author", author_key)
                    cur.execute(
                        """
                        INSERT INTO scholar_v2_authors(id, display_name, normalized_name)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (author_id, author_name, author_key),
                    )
                    cur.execute(
                        """
                        INSERT INTO scholar_v2_paper_authors(
                            build_id, work_id, author_id, display_name,
                            ordinal, role
                        ) VALUES (%s, %s, %s, %s, %s, 'author')
                        """,
                        (
                            build_id,
                            projection.paper_id,
                            author_id,
                            author_name,
                            ordinal,
                        ),
                    )
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO scholar_v2_sections(
                        id, build_id, work_id, artifact_id, parent_id, xml_id,
                        node_kind, semantic_role, level, ordinal, title,
                        xml_pointer, metadata
                    ) VALUES %s
                    """,
                    [
                        (
                            item.id,
                            build_id,
                            projection.paper_id,
                            artifact_id,
                            item.parent_id,
                            item.xml_id,
                            item.node_kind,
                            item.semantic_role,
                            item.level,
                            item.ordinal,
                            item.title,
                            item.xml_pointer,
                            json.dumps(item.metadata),
                        )
                        for item in projection.sections
                    ],
                )
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO scholar_v2_content_nodes(
                        id, build_id, work_id, artifact_id, section_id, parent_id,
                        xml_id, node_kind, semantic_role, granularity, ordinal,
                        title, text, tex, xml_pointer, metadata
                    ) VALUES %s
                    """,
                    [
                        (
                            item.id,
                            build_id,
                            projection.paper_id,
                            artifact_id,
                            item.section_id,
                            item.parent_id,
                            item.xml_id,
                            item.node_kind,
                            item.semantic_role,
                            item.granularity,
                            item.ordinal,
                            item.title,
                            item.text,
                            item.tex,
                            item.xml_pointer,
                            json.dumps(item.metadata),
                        )
                        for item in projection.content_nodes
                    ],
                )
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO scholar_v2_formulas(
                        id, build_id, work_id, content_node_id, xml_id, mode, tex,
                        presentation_mathml, content_mathml, cmml_valid,
                        xml_pointer, metadata
                    ) VALUES %s
                    """,
                    [
                        (
                            item.id,
                            build_id,
                            projection.paper_id,
                            item.content_node_id,
                            item.xml_id,
                            item.mode,
                            item.tex,
                            item.presentation_mathml,
                            item.content_mathml,
                            item.cmml_valid,
                            item.xml_pointer,
                            json.dumps(item.metadata),
                        )
                        for item in projection.formulas
                    ],
                )
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO scholar_v2_tables(
                        id, build_id, work_id, content_node_id, xml_id, caption,
                        xml_pointer, metadata
                    ) VALUES %s
                    """,
                    [
                        (
                            item.id,
                            build_id,
                            projection.paper_id,
                            item.content_node_id,
                            item.xml_id,
                            item.caption,
                            item.xml_pointer,
                            json.dumps(item.metadata),
                        )
                        for item in projection.tables
                    ],
                )
                cells = [
                    (
                        cell["id"],
                        table.id,
                        cell["row_index"],
                        cell["column_index"],
                        cell["row_span"],
                        cell["column_span"],
                        cell["text"],
                        cell["is_header"],
                        json.dumps(cell["metadata"]),
                    )
                    for table in projection.tables
                    for cell in table.cells
                ]
                if cells:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                        INSERT INTO scholar_v2_table_cells(
                            id, table_id, row_index, column_index, row_span,
                            column_span, text, is_header, metadata
                        ) VALUES %s
                        """,
                        cells,
                    )
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO scholar_v2_references(
                        id, build_id, work_id, artifact_id, xml_id, citation_key,
                        raw_text, title, authors, year, identifiers, xml_pointer
                    ) VALUES %s
                    """,
                    [
                        (
                            item.id,
                            build_id,
                            projection.paper_id,
                            artifact_id,
                            item.xml_id,
                            item.citation_key,
                            item.raw_text,
                            item.title,
                            json.dumps(item.authors),
                            item.year,
                            json.dumps(item.identifiers),
                            item.xml_pointer,
                        )
                        for item in projection.references
                    ],
                )
                reference_ids = {
                    item.xml_id: item.id
                    for item in projection.references
                    if item.xml_id is not None
                }
                mention_values = [
                    (
                        item.id,
                        build_id,
                        projection.paper_id,
                        item.content_node_id,
                        reference_ids.get(item.reference_xml_id),
                        item.reference_xml_id,
                        item.context_text,
                        item.xml_pointer,
                    )
                    for item in projection.citation_mentions
                ]
                if mention_values:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                        INSERT INTO scholar_v2_citation_mentions(
                            id, build_id, work_id, content_node_id, reference_id,
                            target_xml_id, context_text, xml_pointer
                        ) VALUES %s
                        """,
                        mention_values,
                    )
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO scholar_v2_chunks(
                        id, build_id, work_id, artifact_id, section_id,
                        source_node_ids, chunk_kind, semantic_role, ordinal,
                        content, token_estimate, xml_pointer_start,
                        xml_pointer_end, content_sha256
                    ) VALUES %s
                    """,
                    [
                        (
                            item.id,
                            build_id,
                            projection.paper_id,
                            artifact_id,
                            item.section_id,
                            json.dumps(item.source_node_ids),
                            item.chunk_kind,
                            item.semantic_role,
                            item.ordinal,
                            item.content,
                            max(1, len(item.content) // 4),
                            item.xml_pointer_start,
                            item.xml_pointer_end,
                            item.content_sha256,
                        )
                        for item in projection.chunks
                    ],
                )

    def _seal_release(
        self, release_id: str, build_id: str, totals: dict[str, int]
    ) -> None:
        with self.database.cursor() as cur:
            cur.execute(
                """
                UPDATE scholar_v2_projection_builds
                SET status = 'sealed', output_count = %s, metrics = %s,
                    sealed_at = now()
                WHERE id = %s
                """,
                (
                    totals["content_nodes"],
                    json.dumps(dict(totals)),
                    build_id,
                ),
            )
            cur.execute(
                """
                UPDATE scholar_v2_corpus_releases
                SET status = 'sealed', sealed_at = now()
                WHERE id = %s
                """,
                (release_id,),
            )

    def _fail_release(self, release_id: str, build_id: str, error: Exception) -> None:
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
                cur.execute(
                    """
                    UPDATE scholar_v2_corpus_releases SET status = 'failed'
                    WHERE id = %s AND status <> 'sealed'
                    """,
                    (release_id,),
                )
        except Exception:
            pass
