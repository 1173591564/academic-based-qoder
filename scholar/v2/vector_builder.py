"""Versioned pgvector chunk-embedding projection."""

import hashlib
import json
from collections.abc import Callable

import psycopg2.extras

from scholar import config

from .build_validation import _validate_relational_build
from .database import V2Database
from .embeddings import EmbeddingProvider, configured_provider
from .models import ScholarError
from .xml_utils import stable_id


class VectorBuilder:
    BUILDER_VERSION = "chunk-embedding-v2"

    def __init__(
        self,
        database: V2Database,
        embed_fn: Callable[[str], list[float] | None] | None = None,
    ):
        self.database = database
        self.embed_fn = embed_fn or configured_provider()

    def build(
        self,
        release_id: str,
        relational_build_id: str,
        provider: str | None = None,
        model_name: str | None = None,
        model_version: str = "configured",
        dimension: int | None = None,
    ) -> dict:
        provider = provider or config.EMBEDDING_PROVIDER
        model_name = model_name or config.EMBEDDING_MODEL
        dimension = dimension or config.V2_EMBEDDING_DIM
        _validate_relational_build(self.database, release_id, relational_build_id)
        if self.embed_fn is None:
            raise ScholarError(
                "VECTOR_UNAVAILABLE", "embedding provider is not configured"
            )
        if isinstance(self.embed_fn, EmbeddingProvider) and (
            provider != self.embed_fn.provider
            or model_name != self.embed_fn.model
            or dimension != self.embed_fn.dimensions
        ):
            raise ScholarError(
                "INVALID_ARGUMENT",
                "embedding build metadata does not match the configured provider",
            )
        if dimension != 1024:
            raise ScholarError(
                "INVALID_ARGUMENT",
                "the current pgvector projection requires 1024-dimensional embeddings",
            )
        model_id = stable_id(
            "embedding_model",
            provider,
            model_name,
            model_version,
            str(dimension),
        )
        config_hash = hashlib.sha256(
            (
                relational_build_id
                + provider
                + model_name
                + model_version
                + str(dimension)
                + self.BUILDER_VERSION
            ).encode("utf-8")
        ).hexdigest()
        build_id = stable_id("build", release_id, "vector", config_hash)
        with self.database.advisory_lock(f"{release_id}:vector:{config_hash}"):
            existing = self._prepare(
                build_id,
                release_id,
                relational_build_id,
                model_id,
                provider,
                model_name,
                model_version,
                dimension,
                config_hash,
            )
            if existing:
                return existing
            try:
                chunks = self._chunks(relational_build_id)
                vectors = []
                for chunk in chunks:
                    embedding = self.embed_fn(chunk["content"])
                    if not embedding:
                        raise ScholarError(
                            "VECTOR_UNAVAILABLE", "embedding provider is unavailable"
                        )
                    if len(embedding) != dimension:
                        raise ScholarError(
                            "VECTOR_UNAVAILABLE",
                            f"embedding dimension {len(embedding)} does not match {dimension}",
                        )
                    vectors.append(
                        {
                            "id": chunk["id"],
                            "embedding": embedding,
                            "content_sha256": chunk["content_sha256"],
                        }
                    )
                self._store(build_id, model_id, vectors)
                metrics = {"chunks": len(chunks), "embedded": len(vectors)}
                self._seal(build_id, metrics)
                return {"build_id": build_id, "model_id": model_id, **metrics}
            except Exception as error:
                self._fail(build_id, error)
                raise

    def _prepare(
        self,
        build_id: str,
        release_id: str,
        relational_build_id: str,
        model_id: str,
        provider: str,
        model_name: str,
        model_version: str,
        dimension: int,
        config_hash: str,
    ) -> dict | None:
        with self.database.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, metrics FROM scholar_v2_projection_builds
                    WHERE id = %s
                    """,
                    (build_id,),
                )
                row = cur.fetchone()
                if row and row[0] == "sealed":
                    metrics = row[1] if isinstance(row[1], dict) else {}
                    return {"build_id": build_id, "model_id": model_id, **metrics}
                cur.execute(
                    "DELETE FROM scholar_v2_projection_builds WHERE id = %s",
                    (build_id,),
                )
                cur.execute(
                    """
                    INSERT INTO scholar_v2_embedding_models(
                        id, provider, model, model_version, dimensions, config_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (config_hash) DO UPDATE SET
                        dimensions = EXCLUDED.dimensions
                    """,
                    (
                        model_id,
                        provider,
                        model_name,
                        model_version,
                        dimension,
                        hashlib.sha256(
                            (
                                provider + model_name + model_version + str(dimension)
                            ).encode("utf-8")
                        ).hexdigest(),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO scholar_v2_projection_builds(
                        id, release_id, projection_type, config_hash,
                        schema_version, extractor_version, status, metrics, started_at
                    ) VALUES (
                        %s, %s, 'vector', %s, 'scholar-v2-001', %s,
                        'running', %s, now()
                    )
                    """,
                    (
                        build_id,
                        release_id,
                        config_hash,
                        self.BUILDER_VERSION,
                        json.dumps(
                            {
                                "relational_build_id": relational_build_id,
                                "model_id": model_id,
                            }
                        ),
                    ),
                )
        return None

    def _chunks(self, relational_build_id: str) -> list[dict]:
        with self.database.connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, content, content_sha256 FROM scholar_v2_chunks
                    WHERE build_id = %s ORDER BY work_id, ordinal
                    """,
                    (relational_build_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def _store(self, build_id: str, model_id: str, vectors: list[dict]) -> None:
        values = [
            (
                vector["id"],
                model_id,
                build_id,
                "[" + ",".join(str(value) for value in vector["embedding"]) + "]",
                vector["content_sha256"],
            )
            for vector in vectors
        ]
        with self.database.connection() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO scholar_v2_chunk_embeddings(
                        chunk_id, model_id, build_id, embedding, content_sha256
                    ) VALUES %s
                    """,
                    values,
                    template="(%s, %s, %s, %s::vector, %s)",
                    page_size=100,
                )

    def _seal(self, build_id: str, metrics: dict) -> None:
        with self.database.cursor() as cur:
            cur.execute(
                """
                UPDATE scholar_v2_projection_builds
                SET status = 'sealed', output_count = %s,
                    metrics = metrics || %s::jsonb,
                    sealed_at = now()
                WHERE id = %s
                """,
                (metrics["embedded"], json.dumps(metrics), build_id),
            )

    def _fail(self, build_id: str, error: Exception) -> None:
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
        except Exception:
            pass
