"""
Scholar Studio — Paper-level vector store (v0.2.0).

One embedding per paper over `[title] abstract` — the paper's self-declared
contribution — stored in the PG pgvector table `paper_vectors`. This is the
L1 semantic retrieval unit: question-intent → paper-contribution cosine.

Passage-level chunks (rag.py) remain the optional location layer; their query
path gains optional filters here. Incremental updates are keyed by an md5 of
the indexed content, so `scholar sync` only pays for changed papers.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config, rag

EMBED_DIM = 1024


class EmbedUnavailable(RuntimeError):
    """Raised when no embedding provider/key is configured or a call fails."""


def _connect():
    import psycopg2

    return psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        dbname=config.PG_NAME,
        user=config.PG_USER,
        password=config.PG_PASS,
    )


def _ensure_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_vectors (
            paper_id   TEXT PRIMARY KEY,
            content_md5 TEXT NOT NULL,
            embedding  vector(%s) NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        (EMBED_DIM,),
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_paper_vectors_hnsw
        ON paper_vectors USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def paper_vector_content(data: dict) -> str:
    """The semantic identity of a paper: `[title] abstract`."""
    title = (data.get("title") or "").strip()
    abstract = (data.get("abstract") or "").strip()
    return f"[{title}] {abstract}"[:2000]


def plan_vector_updates(items: dict, existing: dict) -> tuple[dict, list]:
    """Pure diff: items {pid: content_md5} vs existing {pid: content_md5}.

    Returns (to_embed {pid: md5}, deleted [pid])."""
    to_embed = {pid: h for pid, h in items.items() if existing.get(pid) != h}
    deleted = [pid for pid in existing if pid not in items]
    return to_embed, deleted


def ensure_paper_vectors(
    parsed_dir: Path | None = None, embed_fn=None, force: bool = False
) -> dict:
    """Create/refresh paper_vectors incrementally. Returns step stats."""
    parsed_dir = Path(parsed_dir) if parsed_dir else config.PARSED_DIR
    embed_fn = embed_fn or rag.get_embedding
    items: dict[str, str] = {}
    contents: dict[str, str] = {}
    for f in sorted(parsed_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        pid = data.get("paper_id")
        if not pid:
            continue
        content = paper_vector_content(data)
        if not content.strip("[] "):
            continue
        items[pid] = hashlib.md5(content.encode("utf-8")).hexdigest()
        contents[pid] = content

    conn = _connect()
    try:
        cur = conn.cursor()
        _ensure_table(cur)
        if force:
            cur.execute("DELETE FROM paper_vectors")
            existing: dict = {}
        else:
            cur.execute("SELECT paper_id, content_md5 FROM paper_vectors")
            existing = dict(cur.fetchall())
        conn.commit()

        to_embed, deleted = plan_vector_updates(items, existing)
        errors = 0
        for pid, md5 in to_embed.items():
            emb = embed_fn(contents[pid])
            if not emb:
                errors += 1
                continue
            cur.execute(
                """
                INSERT INTO paper_vectors (paper_id, content_md5, embedding)
                VALUES (%s, %s, %s::vector)
                ON CONFLICT (paper_id) DO UPDATE
                SET content_md5 = EXCLUDED.content_md5,
                    embedding = EXCLUDED.embedding,
                    updated_at = now()
                """,
                (pid, md5, "[" + ",".join(str(x) for x in emb) + "]"),
            )
            conn.commit()
        for pid in deleted:
            cur.execute("DELETE FROM paper_vectors WHERE paper_id = %s", (pid,))
        conn.commit()
        return {
            "total": len(items),
            "embedded": len(to_embed) - errors,
            "skipped": len(items) - len(to_embed),
            "deleted": len(deleted),
            "errors": errors,
        }
    finally:
        conn.close()


def search_papers_semantic(query: str, k: int = 8, embed_fn=None) -> list[dict]:
    """Question → paper-level cosine top-k. Rows: {paper_id, similarity}."""
    if not query or not query.strip():
        return []
    embed_fn = embed_fn or rag.get_embedding
    emb = embed_fn(query[:2000])
    if not emb:
        raise EmbedUnavailable(
            "embedding provider unavailable (check SCHOLAR_EMBEDDING_API_KEY)"
        )
    emb_str = "[" + ",".join(str(x) for x in emb) + "]"
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT paper_id, 1 - (embedding <=> %s::vector) AS similarity
            FROM paper_vectors
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (emb_str, emb_str, k),
        )
        return [
            {"paper_id": r[0], "similarity": round(float(r[1]), 4)}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def search_passages(
    query: str,
    k: int = 10,
    paper_id: str | None = None,
    section: str | None = None,
    embed_fn=None,
) -> list[dict]:
    """Passage-level cosine search with optional scoping filters."""
    if not query or not query.strip():
        return []
    embed_fn = embed_fn or rag.get_embedding
    emb = embed_fn(query[:2000])
    if not emb:
        raise EmbedUnavailable(
            "embedding provider unavailable (check SCHOLAR_EMBEDDING_API_KEY)"
        )
    emb_str = "[" + ",".join(str(x) for x in emb) + "]"
    where = []
    params: list = []
    if paper_id:
        where.append("paper_id = %s")
        params.append(paper_id)
    if section:
        where.append("section ILIKE %s")
        params.append(f"%{section}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    params = [emb_str, emb_str, *params, k]
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT paper_id, section, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM chunks
            {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            params,
        )
        return [
            {
                "paper_id": r[0],
                "section": r[1],
                "content": (r[2] or "")[:160],
                "similarity": round(float(r[3]), 4),
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
