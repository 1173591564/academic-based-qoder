"""
Scholar Studio — RAG Module (智谱 / OpenAI / Local Embedding)

Handles:
  1. Chunking parsed paper sections into searchable units
  2. Generating embeddings via API
  3. Storing in PostgreSQL pgvector
  4. Semantic search
"""

import json
import re
import os
import math
from pathlib import Path
from typing import Optional
from collections import Counter

from . import config


# ===================================================================
# Chunking
# ===================================================================


def chunk_paper(data: dict, max_chunk_size: int = 500) -> list[dict]:
    """
    Split a parsed paper into chunks suitable for embedding.

    Strategy:
    - Each section becomes one or more chunks
    - Abstract is always a separate chunk
    - Formulas with context become separate chunks
    """
    chunks = []
    paper_id = data["paper_id"]
    title = data.get("title", "")

    # Abstract chunk
    if data.get("abstract"):
        chunks.append(
            {
                "paper_id": paper_id,
                "section": "Abstract",
                "content": f"[{title}] {data['abstract']}",
                "type": "abstract",
            }
        )

    # Section chunks
    for section in data.get("sections", []):
        heading = section.get("heading", "")
        content = section.get("content", "")
        level = section.get("level", 1)

        if not content.strip():
            continue

        # Split long sections into paragraphs
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) > max_chunk_size:
                if current_chunk:
                    chunks.append(
                        {
                            "paper_id": paper_id,
                            "section": heading,
                            "content": f"[{title} > {heading}] {current_chunk}",
                            "type": "section",
                        }
                    )
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk:
            chunks.append(
                {
                    "paper_id": paper_id,
                    "section": heading,
                    "content": f"[{title} > {heading}] {current_chunk}",
                    "type": "section",
                }
            )

    # Formula chunks (formulas with surrounding context)
    for formula in data.get("formulas", []):
        latex = formula.get("latex", "")
        label = formula.get("label", "")
        if latex:
            chunks.append(
                {
                    "paper_id": paper_id,
                    "section": label or "Formula",
                    "content": f"[{title}] Formula: ${latex}$",
                    "type": "formula",
                }
            )

    return chunks


# ===================================================================
# Embedding (智谱 API)
# ===================================================================


def get_embedding(text: str) -> Optional[list[float]]:
    """
    Get embedding for a text string.

    Supports:
    - 智谱 (zhipu) via API
    - OpenAI via API
    - Local (sentence-transformers) — placeholder
    """
    provider = config.EMBEDDING_PROVIDER

    if provider == "zhipu":
        return _zhipu_embedding(text)
    elif provider == "openai":
        return _openai_embedding(text)
    else:
        # Fallback: return None (no embedding)
        return None


def _zhipu_embedding(text: str) -> Optional[list[float]]:
    """Get embedding from 智谱 API."""
    api_key = config.EMBEDDING_API_KEY
    if not api_key:
        return None

    try:
        import urllib.request

        payload = json.dumps(
            {
                "model": config.EMBEDDING_MODEL,
                "input": text[:2000],  # 智谱 limit
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://open.bigmodel.cn/api/paas/v4/embeddings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["data"][0]["embedding"]
    except Exception as e:
        import sys as _sys

        print(f"[rag] Zhipu embedding failed: {e}", file=_sys.stderr)
        return None


def _openai_embedding(text: str) -> Optional[list[float]]:
    """Get embedding from OpenAI API."""
    api_key = config.EMBEDDING_API_KEY
    if not api_key:
        return None

    try:
        import urllib.request

        payload = json.dumps(
            {
                "model": "text-embedding-3-small",
                "input": text[:8000],
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["data"][0]["embedding"]
    except Exception as e:
        import sys as _sys

        print(f"[rag] OpenAI embedding failed: {e}", file=_sys.stderr)
        return None


# ===================================================================
# PostgreSQL pgvector storage
# ===================================================================


def store_chunks_pg(chunks: list[dict], embeddings: list[list[float]]):
    """Store chunks and embeddings in PostgreSQL pgvector (includes section field)."""
    conn = None
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=config.PG_HOST,
            port=config.PG_PORT,
            dbname=config.PG_NAME,
            user=config.PG_USER,
            password=config.PG_PASS,
        )
        cur = conn.cursor()

        # Batch insert using executemany for performance
        batch_data = []
        for chunk, emb in zip(chunks, embeddings):
            if emb is None:
                continue
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            batch_data.append(
                (chunk["paper_id"], chunk.get("section", ""), chunk["content"], emb_str)
            )

        if batch_data:
            cur.executemany(
                """
                INSERT INTO chunks (paper_id, section, content, embedding)
                VALUES (%s, %s, %s, %s::vector)
                """,
                batch_data,
            )

        conn.commit()
        cur.close()
    except Exception as e:
        print(f"PG store error: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def create_hnsw_index():
    """Create HNSW index on chunks.embedding for fast approximate nearest neighbor search."""
    conn = None
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=config.PG_HOST,
            port=config.PG_PORT,
            dbname=config.PG_NAME,
            user=config.PG_USER,
            password=config.PG_PASS,
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
            ON chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
        cur.close()
        return True
    except Exception as e:
        print(f"HNSW index creation error: {e}")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _get_pg_connection():
    """Get a PostgreSQL connection."""
    import psycopg2

    return psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        dbname=config.PG_NAME,
        user=config.PG_USER,
        password=config.PG_PASS,
    )


def search_rag(query: str, limit: int = 10) -> list[dict]:
    """
    Semantic search in the RAG index.

    Returns chunks most similar to the query.
    """
    query_emb = get_embedding(query)
    if query_emb is None:
        return []

    conn = None
    try:
        conn = _get_pg_connection()
        cur = conn.cursor()
        emb_str = "[" + ",".join(str(x) for x in query_emb) + "]"
        cur.execute(
            """
            SELECT paper_id, content, section,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (emb_str, emb_str, limit),
        )
        results = []
        for row in cur.fetchall():
            results.append(
                {
                    "paper_id": row[0],
                    "content": row[1],
                    "section": row[2],
                    "similarity": float(row[3]),
                }
            )
        cur.close()
        return results
    except Exception:
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ===================================================================
# BM25 keyword search (lightweight, no external dependency)
# ===================================================================


def _tokenize(text: str) -> list[str]:
    """Unicode-aware tokenizer: matches letters and digits from any language."""
    return re.findall(r"[^\W_]+", text.lower(), re.UNICODE)


class BM25Index:
    """Lightweight BM25 index over chunk content (built from PG data)."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: list[dict] = []  # [{id, paper_id, content, section, tokens}]
        self.avg_dl: float = 0
        self.df: Counter = Counter()  # term -> doc frequency
        self.N: int = 0

    def build_from_pg(self, limit: Optional[int] = None):
        """Load chunks from PostgreSQL and build BM25 index.

        v0.2.0: default covers ALL chunks (was LIMIT 5000 = ~9% coverage);
        memory cost ~20MB at 54k docs (content trimmed to 300 chars)."""
        conn = None
        try:
            conn = _get_pg_connection()
            cur = conn.cursor()
            if limit is None:
                cur.execute("SELECT id, paper_id, content, section FROM chunks")
            else:
                cur.execute(
                    "SELECT id, paper_id, content, section FROM chunks LIMIT %s",
                    (limit,),
                )
            for row in cur.fetchall():
                tokens = _tokenize(row[2])
                self.docs.append(
                    {
                        "id": row[0],
                        "paper_id": row[1],
                        "content": row[2][:300],
                        "section": row[3],
                        "tokens": tokens,
                    }
                )
                unique_tokens = set(tokens)
                for t in unique_tokens:
                    self.df[t] += 1
            cur.close()
            self.N = len(self.docs)
            if self.N > 0:
                self.avg_dl = sum(len(d["tokens"]) for d in self.docs) / self.N
        except Exception:
            pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """BM25 search, returns scored documents."""
        if self.N == 0:
            return []
        query_tokens = _tokenize(query)
        scores = []
        for doc in self.docs:
            dl = len(doc["tokens"])
            score = 0.0
            tf_map = Counter(doc["tokens"])
            for qt in query_tokens:
                tf = tf_map.get(qt, 0)
                if tf == 0:
                    continue
                df = self.df.get(qt, 0)
                idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
                norm_tf = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
                )
                score += idf * norm_tf
            if score > 0:
                scores.append(
                    {
                        "paper_id": doc["paper_id"],
                        "content": doc["content"],
                        "section": doc["section"] or "",
                        "bm25_score": score,
                    }
                )
        scores.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scores[:limit]


# Global BM25 instance (lazy-loaded)
_bm25_index: Optional[BM25Index] = None


def _get_bm25() -> BM25Index:
    global _bm25_index
    if _bm25_index is None or _bm25_index.N == 0:
        _bm25_index = BM25Index()
        _bm25_index.build_from_pg()
    return _bm25_index


# ===================================================================
# Hybrid Search: Vector + BM25 + RRF fusion
# ===================================================================


def search_rag_hybrid(
    query: str, limit: int = 10, k_vector: int = 30, k_bm25: int = 30
) -> list[dict]:
    """
    Hybrid search combining vector similarity and BM25 keyword matching.

    Uses Reciprocal Rank Fusion (RRF) to merge results:
        RRF_score = sum(1 / (k + rank))  where k=60 (standard)

    Returns fused results sorted by RRF score.
    """
    k_rrf = 60  # standard RRF constant

    # Vector search
    vector_results = search_rag(query, limit=k_vector)
    # BM25 search
    bm25_results = _get_bm25().search(query, limit=k_bm25)

    # RRF fusion: accumulate scores per paper_id
    rrf_scores: dict[
        str, dict
    ] = {}  # paper_id -> {score, content, section, vector_rank, bm25_rank}

    for rank, r in enumerate(vector_results):
        pid = r["paper_id"]
        if pid not in rrf_scores:
            rrf_scores[pid] = {
                "paper_id": pid,
                "content": r["content"],
                "section": r["section"],
                "rrf": 0.0,
            }
        rrf_scores[pid]["rrf"] += 1.0 / (k_rrf + rank + 1)

    for rank, r in enumerate(bm25_results):
        pid = r["paper_id"]
        if pid not in rrf_scores:
            rrf_scores[pid] = {
                "paper_id": pid,
                "content": r["content"],
                "section": r["section"],
                "rrf": 0.0,
            }
        rrf_scores[pid]["rrf"] += 1.0 / (k_rrf + rank + 1)

    results = sorted(rrf_scores.values(), key=lambda x: x["rrf"], reverse=True)

    # Rename rrf -> similarity for API compatibility
    for r in results:
        r["similarity"] = r.pop("rrf")

    return results[:limit]


# ===================================================================
# Batch indexing
# ===================================================================


def _get_batch_embeddings(
    texts: list[str], provider: str = None
) -> list[Optional[list[float]]]:
    """
    Get embeddings for a batch of texts.

    Falls back to single-text calls if batch API is not supported.
    """
    if provider is None:
        provider = config.EMBEDDING_PROVIDER

    api_key = config.EMBEDDING_API_KEY
    if not api_key:
        return [None] * len(texts)

    # 智谱 supports batch input
    if provider == "zhipu":
        try:
            import urllib.request

            # 智谱 allows up to ~30 texts per batch
            truncated = [t[:2000] for t in texts]
            payload = json.dumps(
                {
                    "model": config.EMBEDDING_MODEL,
                    "input": truncated,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                "https://open.bigmodel.cn/api/paas/v4/embeddings",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                # Sort by index to maintain order
                data = sorted(result["data"], key=lambda x: x["index"])
                return [d["embedding"] for d in data]
        except Exception:
            pass

    # Fallback: one-by-one
    return [get_embedding(t) for t in texts]


def index_all_papers(parsed_dir: Path = None, batch_size: int = 30) -> dict:
    """
    Index all parsed papers into the RAG system.

    1. Chunk all papers
    2. Generate embeddings in batches (with Rich progress bar)
    3. Store in PostgreSQL
    4. Create HNSW index after completion
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR

    # Phase 1: Chunk all papers
    all_chunks = []
    paper_count = 0
    for json_file in parsed_dir.glob("*.json"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        chunks = chunk_paper(data)
        all_chunks.extend(chunks)
        paper_count += 1

    total = len(all_chunks)
    embedded = 0
    failed = 0

    # Phase 2: Embed + store with progress bar
    try:
        from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
        from rich.console import Console

        _console = Console()
        _has_rich = True
    except ImportError:
        _has_rich = False

    if _has_rich:
        with Progress(
            TextColumn("[cyan]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(),
            console=_console,
        ) as progress:
            task = progress.add_task("Embedding chunks...", total=total)
            for i in range(0, total, batch_size):
                batch = all_chunks[i : i + batch_size]
                texts = [c["content"] for c in batch]
                embeddings = _get_batch_embeddings(texts)
                for emb in embeddings:
                    if emb:
                        embedded += 1
                    else:
                        failed += 1
                store_chunks_pg(batch, embeddings)
                progress.update(task, advance=len(batch))
    else:
        for i in range(0, total, batch_size):
            batch = all_chunks[i : i + batch_size]
            texts = [c["content"] for c in batch]
            embeddings = _get_batch_embeddings(texts)
            for emb in embeddings:
                if emb:
                    embedded += 1
                else:
                    failed += 1
            store_chunks_pg(batch, embeddings)
            if (i // batch_size) % 10 == 0:
                print(f"  Indexed {min(i + batch_size, total)}/{total} chunks...")

    # Phase 3: Create HNSW index
    hnsw_ok = create_hnsw_index()

    return {
        "papers": paper_count,
        "total_chunks": total,
        "embedded": embedded,
        "failed": failed,
        "hnsw_index": hnsw_ok,
    }


def index_single_paper(ulid: str, parsed_dir: Path = None) -> dict:
    """
    Re-index a single paper into the RAG store. Used by `ingest` for incremental updates.
    Deletes existing chunks for the paper first to keep the index consistent.
    """
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR
    json_path = parsed_dir / f"{ulid}.json"
    if not json_path.exists():
        return {"ulid": ulid, "embedded": 0, "error": "parsed JSON not found"}
    data = json.loads(json_path.read_text(encoding="utf-8"))

    # Delete existing chunks
    conn = None
    try:
        conn = _get_pg_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM chunks WHERE paper_id = %s", (ulid,))
        conn.commit()
        cur.close()
    except Exception:
        pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    chunks = chunk_paper(data)
    if not chunks:
        return {"ulid": ulid, "embedded": 0, "chunks": 0}
    texts = [c["content"] for c in chunks]
    embeddings = _get_batch_embeddings(texts)
    store_chunks_pg(chunks, embeddings)
    embedded = sum(1 for e in embeddings if e is not None)
    return {"ulid": ulid, "chunks": len(chunks), "embedded": embedded}
